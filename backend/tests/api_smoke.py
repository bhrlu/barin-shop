"""Local end-to-end smoke check: calls every backend route against a live server.

Run (server must be up, DB seeded):
    ./.venv/bin/python tests/_api_smoke.py

Reports each route's status; exits non-zero if any route returns 5xx.
Temporary helper — not a pytest file.
"""

import os
import sys
from uuid import uuid4

import httpx

BASE = os.environ.get("SANDE_API_URL", "http://127.0.0.1:8000")
results: list[tuple[str, str, int, str]] = []


def call(
    method: str,
    path: str,
    token: str | None = None,
    json=None,
    params=None,
    expect_5xx_ok=False,
):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        r = httpx.request(
            method, BASE + path, headers=headers, json=json, params=params, timeout=15
        )
        body = r.text[:200].replace("\n", " ")
    except Exception as exc:  # noqa: BLE001
        r = None
        body = f"EXC {exc!r}"
    status = r.status_code if r is not None else 0
    flag = "FAIL" if (status == 0 or status >= 500) and not expect_5xx_ok else "ok"
    results.append((flag, f"{method} {path}", status, body))
    return r


def login(email: str, password: str) -> str:
    r = httpx.post(BASE + "/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    customer = login("customer@sande.local", "customer1234")
    admin = login("admin@sande.local", "admin1234")
    print("tokens acquired\n")

    # --- public / catalog ---
    call("GET", "/health")
    call("GET", "/products")
    prods = call("GET", "/products").json()
    pid = prods[0]["id"] if prods else "missing"
    call("GET", f"/products/{pid}")
    call("GET", "/search?q=پیراهن")
    call("GET", "/search?q=tshirt&limit=5")

    # --- auth ---
    call("GET", "/auth/me", customer)
    call("PATCH", "/auth/me", customer, json={"full_name": "مشتری نمونه"})
    call("POST", "/auth/signup", json={
        "email": f"smoke_{uuid4().hex[:8]}@example.com",
        "password": "secret123", "full_name": "Smoke Test",
    })
    call("POST", "/auth/login", json={"email": "customer@sande.local", "password": "wrong"})

    # --- addresses (the reported bug) ---
    call("GET", "/addresses", customer)
    created = call("POST", "/addresses", customer, json={
        "title": "خانه", "receiver": "آزمون", "phone": "09120000000",
        "province": "تهران", "city": "تهران", "postal_code": "1998765432",
        "line": "خیابان تست، پلاک ۱", "is_default": False,
    })
    if created is not None and created.status_code == 201:
        call("DELETE", f"/addresses/{created.json()['id']}", customer)
    call("DELETE", f"/addresses/{uuid4()}", customer)  # expected 404

    # --- favorites ---
    call("GET", "/favorites", customer)
    call("POST", f"/favorites/{pid}", customer)
    call("POST", f"/favorites/{pid}", customer)

    # --- catalog: merchandising, related, reviews, variants ---
    call("GET", "/products?sort=price_asc&on_sale=true")
    call("GET", "/products?availability=in_stock&sort=rating")
    call("GET", "/products?category=tshirt&size=M")
    call("GET", f"/products/compare?ids={pid}")
    call("GET", f"/products/{pid}/related")
    call("GET", f"/products/{pid}/recommendations")
    call("GET", f"/products/{pid}/variants")
    call("GET", f"/products/{pid}/reviews")
    call(
        "POST",
        f"/products/{pid}/reviews",
        customer,
        json={"rating": 5, "title": "عالی", "body": "کیفیت خوب بود"},
    )
    call("POST", f"/products/{pid}/view", customer)
    call("GET", "/recently-viewed", customer)
    call("GET", "/search/suggest?q=ts")
    call("GET", "/search/history", customer)
    call("GET", "/admin/inventory", admin)
    call("GET", "/admin/inventory/low-stock", admin)
    call("GET", "/admin/reviews", admin)

    # variant admin CRUD (create → patch → delete)
    variant = call(
        "POST",
        f"/products/{pid}/variants",
        admin,
        json={"size": "M", "color": "رنگ آزمون", "stock": 3},
    )
    if variant is not None and variant.status_code == 201:
        vid = variant.json()["id"]
        call("PATCH", f"/variants/{vid}", admin, json={"stock": 5, "sku": "SMOKE-1"})
        call("DELETE", f"/variants/{vid}", admin)
    call("DELETE", "/search/history", customer)

    # --- stock + coupons ---
    call("POST", "/stock/check", json=[{"product_id": pid, "size": "", "color": "", "quantity": 1}])
    call("POST", "/coupons/validate", customer, json={"code": "SANDE10", "subtotal": 1_000_000})
    call("GET", "/coupons", admin)
    call(
        "POST",
        "/coupons",
        admin,
        json={"code": f"SMK{uuid4().hex[:6].upper()}", "percent_off": 5},
    )
    call("POST", "/coupons/generate", admin)

    # --- checkout (creates a real order for the customer) ---
    order_id = None
    color = prods[0]["colors"][0]["name"] if prods[0]["colors"] else "x"
    size = prods[0]["sizes"][0] if prods[0]["sizes"] else "M"
    chk = call(
        "POST",
        "/checkout",
        customer,
        json={
            "lines": [
                {"product_id": pid, "size": size, "color": color, "quantity": 1}
            ],
            "address": {
                "full_name": "آزمون",
                "phone": "09120000000",
                "city": "تهران",
                "line": "خیابان تست، پلاک ۱",
                "postal_code": "1998765432",
            },
        },
    )
    if chk is not None and chk.status_code == 201:
        order_id = chk.json()["order_id"]

    # --- orders / payments ---
    orders = call("GET", "/orders", customer)
    if not order_id and orders is not None and orders.status_code == 200 and orders.json():
        order_id = orders.json()[0]["id"]
    if order_id:
        call("GET", f"/orders/{order_id}", customer)
        call("GET", f"/orders/{order_id}/payment-session", customer)
        call("POST", "/payments/start", customer, json={"order_id": order_id})
        call("POST", f"/orders/{order_id}/payment-complete", customer, json={"outcome": "success"})
    call("POST", "/payments/verify", customer, params={"authority": "unknown-authority"})
    call("GET", "/payments/mine", customer)

    # --- admin ---
    call("GET", "/admin/stats", admin)
    call("GET", "/admin/users", admin)
    call("GET", "/admin/refunds", admin)
    call("GET", "/admin/orders", admin)
    call("GET", "/admin/payments", admin)

    # --- storage ---
    call("POST", "/storage/sign", customer, json={"paths": ["uploads/x.jpg", "cat-tshirt"]})
    call(
        "POST",
        "/storage/upload-url",
        admin,
        json={"filename": "x.jpg", "content_type": "image/jpeg"},
    )

    # --- unauthenticated guard ---
    call("GET", "/orders")
    call("GET", "/addresses")

    print(f"{'RESULT':6} {'ROUTE':55} STATUS  BODY")
    failures = 0
    for flag, route, status, body in results:
        if flag == "FAIL":
            failures += 1
        print(f"{flag:6} {route:55} {status:<7} {body}")
    print(f"\n{len(results)} routes, {failures} 5xx/failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
