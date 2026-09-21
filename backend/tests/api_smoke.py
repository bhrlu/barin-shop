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
results: list[tuple[str, str, int | str, str]] = []


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


def check(name: str, ok: bool, detail: str = "") -> None:
    """Record a logical assertion (empty result, missing kind…) in the same report."""
    results.append(("ok" if ok else "FAIL", name, "-", detail))


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

    # tag matching: a tag query must return hits and tags must be suggested
    hits = call("GET", "/search?q=کتان")
    total = hits.json().get("total") if hits is not None and hits.status_code == 200 else None
    check(
        "GET /search?q=کتان → tag hits",
        bool(total),
        f"total={total}" if total is not None else "no JSON body",
    )
    sug = call("GET", "/search/suggest?q=کتان")
    payload = sug.json() if sug is not None and sug.status_code == 200 else []
    kinds = [s.get("kind") for s in payload] if isinstance(payload, list) else []
    check("GET /search/suggest?q=کتان → tag kind", "tag" in kinds, f"kinds={kinds}")

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
    second = call("POST", "/addresses", customer, json={
        "title": "دفتر", "receiver": "آزمون دوم", "phone": "09120000001",
        "province": "تهران", "city": "تهران", "postal_code": "1998765433",
        "line": "خیابان تست، پلاک ۲", "is_default": True,
    })
    if created is not None and created.status_code == 201:
        first_id = created.json()["id"]
        second_ok = second is not None and second.status_code == 201
        second_id = second.json()["id"] if second_ok and second is not None else None

        # exactly one default, and it is the one just created as default
        listed = call("GET", "/addresses", customer)
        if listed is not None and listed.status_code == 200:
            defaults = [a["id"] for a in listed.json() if a["is_default"]]
            check(
                "only one default address",
                defaults == ([second_id] if second_id else defaults),
                f"defaults={defaults}",
            )

        # PATCH moves the default to the other address
        patched = call(
            "PATCH", f"/addresses/{first_id}", customer,
            json={"is_default": True, "title": "خانهٔ من"},
        )
        if patched is not None and patched.status_code == 200:
            body = patched.json()
            check(
                "PATCH address sets fields + default",
                body["is_default"] is True and body["title"] == "خانهٔ من",
                f"is_default={body['is_default']} title={body['title']}",
            )
            listed = call("GET", "/addresses", customer)
            if listed is not None and listed.status_code == 200:
                defaults = [a["id"] for a in listed.json() if a["is_default"]]
                check("PATCH keeps a single default", defaults == [first_id], str(defaults))

        # the account's edit form sends fields only (F2.7b), so it must not touch
        # the flag — otherwise saving an edit would demote the default address
        fields_only = call(
            "PATCH", f"/addresses/{first_id}", customer,
            json={
                "title": "خانهٔ ویرایش‌شده", "receiver": "آزمون ویرایش",
                "phone": "09120000009", "province": "البرز", "city": "کرج",
                "postal_code": "1998765439", "line": "خیابان تست، پلاک ۳",
            },
        )
        if fields_only is not None and fields_only.status_code == 200:
            body = fields_only.json()
            check(
                "PATCH fields only edits without touching is_default",
                body["is_default"] is True
                and body["city"] == "کرج"
                and body["receiver"] == "آزمون ویرایش",
                f"is_default={body['is_default']} city={body['city']} receiver={body['receiver']}",
            )

        # deleting the default promotes the remaining address
        call("DELETE", f"/addresses/{first_id}", customer)
        if second_id:
            listed = call("GET", "/addresses", customer)
            if listed is not None and listed.status_code == 200:
                rest = [a for a in listed.json() if a["id"] == second_id]
                check(
                    "deleting the default promotes the successor",
                    bool(rest) and rest[0]["is_default"] is True,
                    f"successor={rest}",
                )
            call("DELETE", f"/addresses/{second_id}", customer)
        call("PATCH", f"/addresses/{uuid4()}", customer, json={"is_default": True})  # 404
    call("DELETE", f"/addresses/{uuid4()}", customer)  # expected 404

    # --- contact form persistence ---
    sent = call(
        "POST",
        "/contact",
        json={
            "name": "آزمون تماس",
            "contact": "smoke@example.com",
            "message": "این پیام از اسکریپت اسموک است.",
        },
    )
    if sent is not None and sent.status_code == 201:
        message_id = sent.json()["id"]
        inbox = call("GET", "/admin/contact-messages", admin)
        listed = (inbox.json() if inbox is not None and inbox.status_code == 200 else []) or []
        check(
            "stored contact message is readable by an admin",
            any(m["id"] == message_id for m in listed),
            f"messages={len(listed)}",
        )
        call("DELETE", f"/admin/contact-messages/{message_id}", admin)
    call("POST", "/contact", json={"name": "x", "contact": "y", "message": "z"})  # 422

    # --- contact inbox mark-answered (F2.1b) ---
    sent2 = call(
        "POST",
        "/contact",
        json={
            "name": "آزمون پاسخ",
            "contact": "answerme@example.com",
            "message": "این پیام باید پاسخ‌داده‌شده علامت بخورد.",
        },
    )
    if sent2 is not None and sent2.status_code == 201:
        msg2 = sent2.json()["id"]
        marked = call(
            "PATCH", f"/admin/contact-messages/{msg2}", admin, json={"status": "answered"}
        )
        check(
            "PATCH /admin/contact-messages/{id} marks answered",
            marked is not None
            and marked.status_code == 200
            and marked.json().get("status") == "answered",
            f"{marked.status_code if marked else 0} {marked.text[:80] if marked else ''}",
        )
        inbox2 = call("GET", "/admin/contact-messages?status=answered", admin)
        listed2 = (inbox2.json() if inbox2 is not None and inbox2.status_code == 200 else []) or []
        check(
            "answered message appears under ?status=answered",
            any(m["id"] == msg2 for m in listed2),
            f"answered={len(listed2)}",
        )
        bad = call("PATCH", f"/admin/contact-messages/{msg2}", admin, json={"status": "bogus"})
        check(
            "PATCH /admin/contact-messages/{id} rejects unknown status",
            bad is not None and bad.status_code == 422,
            f"{bad.status_code if bad else 0}",
        )
        call("DELETE", f"/admin/contact-messages/{msg2}", admin)

    # --- favorites ---
    call("GET", "/favorites", customer)
    call("POST", f"/favorites/{pid}", customer)
    call("POST", f"/favorites/{pid}", customer)

    # --- catalog: merchandising, related, reviews, variants ---
    call("GET", "/products?sort=price_asc&on_sale=true")
    call("GET", "/products?availability=in_stock&sort=rating")
    call("GET", "/products?category=tshirt&size=M")

    # multi-value facets: repeated params and comma-separated values must agree
    flat = call("GET", "/products?size=M")
    repeat = call("GET", "/products?size=M&size=L")
    comma = call("GET", "/products?size=M,L")
    if all(r is not None and r.status_code == 200 for r in (flat, repeat, comma)):
        n_flat = len(flat.json())
        n_repeat = len(repeat.json())
        n_comma = len(comma.json())
        check(
            "multi-size: repeated == comma and OR widens",
            n_repeat == n_comma and n_repeat >= n_flat,
            f"M={n_flat} M+L={n_repeat}/{n_comma}",
        )
    call("GET", "/products?size=M,L&color=کرم")
    call("GET", "/products?size=")  # empty facet value must not 500
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

    # --- availability guard (B4.11) ---
    # Toggle the first product to coming_soon and back: both the stock pre-check
    # and checkout must reject it. The original value is restored either way.
    original = call("GET", f"/products/{pid}").json()["availability"]
    guard_size = prods[0]["sizes"][0] if prods[0]["sizes"] else "M"
    guard_color = prods[0]["colors"][0]["name"] if prods[0]["colors"] else "x"
    guard_line = {
        "product_id": pid,
        "size": guard_size,
        "color": guard_color,
        "quantity": 1,
    }
    call("PATCH", f"/products/{pid}", admin, json={"availability": "coming_soon"})
    guarded = call("POST", "/stock/check", json=[guard_line])
    if guarded is not None and guarded.status_code == 200:
        reasons = [i.get("reason") for i in guarded.json().get("issues", [])]
        check("coming_soon rejected by /stock/check", reasons == ["not_available"], str(reasons))
    guarded_order = call(
        "POST",
        "/checkout",
        customer,
        json={
            "lines": [guard_line],
            "address": {
                "full_name": "آزمون",
                "phone": "09120000000",
                "city": "تهران",
                "line": "خیابان تست، پلاک ۱",
            },
        },
    )
    if guarded_order is not None:
        detail = guarded_order.json().get("detail", {})
        check(
            "coming_soon rejected by /checkout (409 stock_conflict/not_available)",
            guarded_order.status_code == 409
            and isinstance(detail, dict)
            and detail.get("code") == "stock_conflict"
            and [i.get("reason") for i in detail.get("issues", [])] == ["not_available"],
            f"{guarded_order.status_code} {detail}",
        )
    call("PATCH", f"/products/{pid}", admin, json={"availability": original})

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
                "province": "تهران",
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
        order_detail = call("GET", f"/orders/{order_id}", customer)
        if order_detail is not None and order_detail.status_code == 200:
            addr = order_detail.json().get("shipping_address") or {}
            check(
                "checkout keeps province + postal code in shipping_address",
                addr.get("province") == "تهران" and addr.get("postal_code") == "1998765432",
                str(addr),
            )
        call("GET", f"/orders/{order_id}/payment-session", customer)
        started = call("POST", "/payments/start", customer, json={"order_id": order_id})
        authority = (
            started.json()["authority"]
            if started is not None and started.status_code == 200
            else None
        )

        # Gateway return, then the *same* authority again: B3.7 — the authority has
        # its own column now, so the repeat is an idempotent `already_paid`
        # (redirect / 200) instead of a 400 "session not found".
        def gateway_callback(auth: str):
            return httpx.get(
                BASE + "/payments/zarinpal/callback",
                params={"authority": auth},
                follow_redirects=False,
                timeout=15,
            )

        if authority:
            first_cb = gateway_callback(authority)
            check("gateway callback verifies (3xx)", 300 <= first_cb.status_code < 400,
                  f"{first_cb.status_code}")
            repeat_cb = gateway_callback(authority)
            check(
                "repeat gateway callback is idempotent (not 400)",
                repeat_cb.status_code < 400,
                f"{repeat_cb.status_code} {repeat_cb.text[:120]}",
            )
            verified = call("POST", "/payments/verify", customer, params={"authority": authority})
            if verified is not None:
                check(
                    "POST /payments/verify on a settled session → already_paid",
                    verified.status_code == 200
                    and verified.json().get("status") == "already_paid",
                    f"{verified.status_code} {verified.text[:120]}",
                )

        # the simulated in-app path still works on an order the gateway settled
        call("POST", f"/orders/{order_id}/payment-complete", customer, json={"outcome": "success"})
    call("POST", "/payments/verify", customer, params={"authority": "unknown-authority"})
    call("GET", "/payments/mine", customer)

    # --- admin ---
    call("GET", "/admin/stats", admin)
    call("GET", "/admin/users", admin)
    call("GET", "/admin/refunds", admin)
    call("GET", "/admin/orders", admin)
    check(
        "admin orders carry tracking_code",
        all("tracking_code" in o for o in (call("GET", "/admin/orders", admin).json() or [])),
        "",
    )
    if order_id:
        tracking24 = "249028345612345678901234"
        track = call("PATCH", f"/orders/{order_id}", admin, json={"tracking_code": tracking24})
        check(
            "PATCH /orders/{id} saves tracking_code",
            track is not None
            and track.status_code == 200
            and track.json().get("tracking_code") == tracking24,
            f"{track.status_code if track else 0} {track.text[:80] if track else ''}",
        )
        customer_view = call("GET", f"/orders/{order_id}", customer)
        check(
            "customer order shows tracking_code",
            customer_view is not None
            and customer_view.status_code == 200
            and customer_view.json().get("tracking_code") == tracking24,
            "",
        )
        cleared = call("PATCH", f"/orders/{order_id}", admin, json={"tracking_code": ""})
        cleared_value = (
            cleared.json().get("tracking_code")
            if cleared is not None and cleared.status_code == 200
            else "?"
        )
        check(
            "empty tracking_code clears the field",
            cleared is not None and cleared.status_code == 200 and cleared_value is None,
            f"{cleared_value}",
        )
        forbidden = call("PATCH", f"/orders/{order_id}", customer, json={"tracking_code": "hack"})
        check(
            "customer cannot set tracking_code",
            forbidden is not None and forbidden.status_code == 403,
            f"{forbidden.status_code if forbidden else 0}",
        )
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
    print(f"\n{len(results)} routes/checks, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
