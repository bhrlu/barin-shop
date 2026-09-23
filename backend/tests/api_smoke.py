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
    support = login("support@sande.local", "staff1234")
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

    # --- pagination envelopes (F2.5) ---
    page1 = call("GET", "/products?page=1&page_size=5").json()
    check(
        "GET /products?page → envelope",
        isinstance(page1, dict)
        and {"items", "total", "page", "page_size", "pages"} <= set(page1)
        and len(page1["items"]) == 5
        and page1["pages"] >= 1,
        f"total={page1.get('total')} pages={page1.get('pages')}",
    )
    bare = call("GET", "/products").json()
    check("GET /products (no page) → bare list", isinstance(bare, list), f"len={len(bare)}")
    # /shop filter options without the whole catalogue (F5.8)
    facets = call("GET", "/products/facets").json()
    check(
        "GET /products/facets → sizes/colours/tags/price range of the active catalogue",
        isinstance(facets, dict)
        and set(facets.get("sizes", [])) == {s for p in bare for s in p["sizes"]}
        and facets.get("price_min") == min(p["price"] for p in bare)
        and facets.get("price_max") == max(p["price"] for p in bare),
        f"sizes={len(facets.get('sizes', []))} "
        f"range={facets.get('price_min')}–{facets.get('price_max')}",
    )
    for ep in (
        "/orders?page=1&page_size=5",
        "/admin/orders?page=1&page_size=5",
        "/admin/users?page=1&page_size=5",
        "/admin/payments?page=1&page_size=5",
        "/admin/contact-messages?page=1&page_size=5",
        "/admin/reviews?page=1&page_size=5",
    ):
        env = call("GET", ep, admin if ep.startswith("/admin") else customer).json()
        ok = isinstance(env, dict) and {"items", "total", "page", "page_size", "pages"} <= set(env)
        total = env.get("total") if isinstance(env, dict) else "?"
        check(f"GET {ep} → envelope", ok, f"total={total}")
    # --- admin data table filters (F4.3) ---
    filtered = call(
        "GET", "/admin/orders?page=1&page_size=5&status=pending,cancelled&sort=total_asc", admin
    ).json()
    totals = [o["total"] for o in filtered.get("items", [])] if isinstance(filtered, dict) else []
    check(
        "GET /admin/orders?status&sort → filtered envelope, ascending totals",
        isinstance(filtered, dict)
        and all(o["status"] in {"pending", "cancelled"} for o in filtered["items"])
        and totals == sorted(totals),
        f"total={filtered.get('total') if isinstance(filtered, dict) else '?'}",
    )
    staff = call("GET", "/admin/users?page=1&role=staff&q=sande.local", admin).json()
    check(
        "GET /admin/users?role=staff&q → the seeded staff accounts",
        isinstance(staff, dict) and staff["total"] >= 3
        and all(set(u["roles"]) & {"admin", "super_admin", "order_manager", "support"}
                for u in staff["items"]),
        f"total={staff.get('total') if isinstance(staff, dict) else '?'}",
    )
    both_kinds = call(
        "POST", "/coupons", admin, json={"code": "SMOKEBOTH", "percent_off": 10, "amount_off": 1000}
    )
    check(
        "POST /coupons with both discount kinds → 422 (B6.15)",
        both_kinds is not None and both_kinds.status_code == 422,
        f"{both_kinds.status_code if both_kinds is not None else 0}",
    )
    bad = call("GET", "/admin/orders?page=1&status=lost", admin)
    check("GET /admin/orders?status=lost → 422", bad is not None and bad.status_code == 422,
          f"{bad.status_code if bad is not None else 0}")
    offset_rows = call("GET", "/admin/audit-logs?limit=2&offset=2", admin).json()
    check(
        "GET /admin/audit-logs offset", isinstance(offset_rows, list), f"rows={len(offset_rows)}"
    )
    # B5.1c: a malformed admin_id is a 422 (was a Postgres CAST error → 500)
    bad_admin = call("GET", "/admin/audit-logs?admin_id=foo", admin)
    check(
        "GET /admin/audit-logs?admin_id=foo → 422",
        bad_admin is not None and bad_admin.status_code == 422,
        f"{bad_admin.status_code if bad_admin is not None else 0}",
    )
    good_admin = call(
        "GET", "/admin/audit-logs?admin_id=00000000-0000-0000-0000-000000000000", admin
    )
    check(
        "GET /admin/audit-logs?admin_id=<uuid> → 200 []",
        good_admin is not None and good_admin.status_code == 200 and good_admin.json() == [],
        f"{good_admin.status_code if good_admin is not None else 0}",
    )

    # --- auth ---
    call("GET", "/auth/me", customer)
    call("PATCH", "/auth/me", customer, json={"full_name": "مشتری نمونه"})
    call("POST", "/auth/signup", json={
        "email": f"smoke_{uuid4().hex[:8]}@example.com",
        "password": "secret123", "full_name": "Smoke Test",
    })
    call("POST", "/auth/login", json={"email": "customer@sande.local", "password": "wrong"})

    # --- password reset (F2.3): one answer for every address; bad links → 400 ---
    known = call("POST", "/auth/password/forgot", json={"email": "customer@sande.local"})
    unknown = call(
        "POST", "/auth/password/forgot", json={"email": f"nobody_{uuid4().hex[:6]}@example.com"}
    )
    check(
        "forgot password: known and unknown email answer identically (202)",
        known is not None and unknown is not None
        and known.status_code == unknown.status_code == 202
        and known.json() == unknown.json(),
        f"{known.status_code if known else 0}/{unknown.status_code if unknown else 0}",
    )
    bad_reset = call(
        "POST", "/auth/password/reset", json={"token": "x" * 43, "password": "secret123"}
    )
    check(
        "reset with an unknown token → 400",
        bad_reset is not None and bad_reset.status_code == 400,
        f"{bad_reset.status_code if bad_reset else 0}",
    )

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
        "line": "خیابان تست ۲", "is_default": False,
    })
    addr_id = created.json()["id"] if created is not None and created.status_code == 201 else None
    addr2 = second.json()["id"] if second is not None and second.status_code == 201 else None
    call("GET", f"/addresses/{addr_id}", customer)
    patched = call(
        "PATCH", f"/addresses/{addr_id}", customer,
        json={"is_default": True, "title": "خانهٔ من"},
    )
    if patched is not None and patched.status_code == 200:
        body = patched.json()
        check(
            "PATCH address sets fields + default",
            body["is_default"] is True and body["title"] == "خانهٔ من",
            f"is_default={body['is_default']} title={body['title']}",
        )
    call("PATCH", f"/addresses/{addr2}", customer, json={"title": "دفتر من"})
    call("DELETE", f"/addresses/{addr2}", customer)

    # --- contact form persistence ---
    contact = call("POST", "/contact", json={
        "name": "مشت آزمون", "contact": "smoke@example.com", "message": "پیام آزمون",
    })
    _ = contact
    call("GET", "/admin/contact-messages", admin)
    bad_contact = call("POST", "/contact", json={"name": "x", "contact": "y", "message": "z"})
    check(
        "POST /contact validates lengths (422)",
        bad_contact is not None and bad_contact.status_code == 422,
        f"{bad_contact.status_code if bad_contact else 0}",
    )

    # --- contact abuse guard (B3.11): a filled honeypot is rejected and never
    # stored. 429 is also a rejection — earlier runs from this host may have used
    # the IP's attempts for the window.
    bait = f"honeypot-{uuid4().hex[:8]}@example.com"
    trap = call("POST", "/contact", json={
        "name": "ربات آزمون", "contact": bait, "message": "پیام هرزنامه آزمون",
        "website": "http://spam.example",
    })
    inbox = call("GET", "/admin/contact-messages?limit=200", admin)
    inbox_rows = inbox.json() if inbox is not None and inbox.status_code == 200 else []
    check(
        "POST /contact honeypot rejected and not stored (B3.11)",
        trap is not None
        and trap.status_code in (400, 429)
        and not any(m.get("contact") == bait for m in inbox_rows),
        f"{trap.status_code if trap else 0}",
    )

    # --- contact inbox mark-answered (F2.1b) ---
    # B6.20: this run's POST /contact may have been refused by the per-IP limit
    # (5 / 10 min) on back-to-back runs, which used to skip this whole block silently.
    # Exercise this run's message when it exists, else any message, and restore its
    # status. One smoke message is kept as the fixture for later throttled runs (a
    # second one is deleted), so the block always runs. No message at all is a FAIL.
    own_id = (
        str(contact.json()["id"]) if contact is not None and contact.status_code == 201 else None
    )
    listed = call("GET", "/admin/contact-messages?limit=200", admin)
    msgs = listed.json() if listed is not None and listed.status_code == 200 else []
    target = next((m for m in msgs if str(m.get("id")) == own_id), None) or next(iter(msgs), None)
    check(
        "contact inbox has a message to exercise",
        target is not None,
        f"own={'yes' if own_id else 'rate-limited'} inbox={len(msgs)}",
    )
    if target:
        msg2, original = target["id"], target.get("status", "new")
        ans = call(
            "PATCH", f"/admin/contact-messages/{msg2}", admin, json={"status": "answered"}
        )
        check(
            "PATCH contact message marks answered",
            ans is not None and ans.status_code == 200 and ans.json().get("status") == "answered",
            f"{ans.status_code if ans else 0}",
        )
        bad = call("PATCH", f"/admin/contact-messages/{msg2}", admin, json={"status": "bogus"})
        check(
            "PATCH contact message rejects bogus status (422)",
            bad is not None and bad.status_code == 422,
            f"{bad.status_code if bad else 0}",
        )
        call("PATCH", f"/admin/contact-messages/{msg2}", admin, json={"status": original})
        older_smoke = any(
            m.get("contact") == "smoke@example.com" and str(m.get("id")) != own_id for m in msgs
        )
        if own_id and older_smoke:
            call("DELETE", f"/admin/contact-messages/{own_id}", admin)

    # --- favorites ---
    call("GET", "/favorites", customer)
    call("POST", "/favorites", customer, json={"product_id": pid})
    call("DELETE", f"/favorites/{pid}", customer)

    # --- catalog: merchandising, related, recommendations (B2.4), reviews ---
    call("GET", f"/products/{pid}/related")
    rec = call("GET", f"/products/{pid}/recommendations")
    rec_list = rec.json() if rec is not None and rec.status_code == 200 else []
    check(
        "GET /recommendations → excludes self, capped",
        all(p["id"] != pid for p in rec_list) and len(rec_list) <= 4,
        f"n={len(rec_list)}",
    )
    call("GET", f"/products/{pid}/compare")
    call("GET", f"/products/{pid}/variants")
    call("GET", f"/products/{pid}/reviews")
    rev = call("POST", f"/products/{pid}/reviews", customer, json={
        "rating": 5, "title": "عالی", "body": "خیلی خوب بود",
    })
    rev_id = rev.json()["id"] if rev is not None and rev.status_code in (200, 201) else None
    if rev_id:
        call("PATCH", f"/reviews/{rev_id}", admin, json={
            "status": "approved", "reply": "ممنون از خرید شما",
        })
        call("DELETE", f"/reviews/{rev_id}", customer)

    # --- stock + coupons ---
    color = prods[0]["colors"][0]["name"] if prods[0]["colors"] else "x"
    size = prods[0]["sizes"][0] if prods[0]["sizes"] else "M"
    call("POST", "/stock/check", json={
        "lines": [{"product_id": pid, "size": size, "color": color, "quantity": 1}],
    })
    call("POST", "/coupons/validate", json={"code": "SANDE10", "cart_total": 1000000})

    # --- availability guard (B4.11) ---
    # a coming-soon (or preorder) product can be checked for stock, but checkout
    # and checkout must reject it. The original value is restored either way.
    coming = call("GET", "/admin/products", admin)
    coming_list = coming.json() if coming is not None and coming.status_code == 200 else []
    target = next(
        (p for p in coming_list if p.get("availability") not in (None, "in_stock")), None
    )
    if target is None:
        target = next((p for p in coming_list if p.get("id") != pid), None)
    if target is not None:
        orig_avail = target.get("availability") or "in_stock"
        call("PATCH", f"/products/{target['id']}", admin, json={"availability": "coming_soon"})
        avail_check = call("POST", "/stock/check", json={
            "lines": [{
                "product_id": target["id"], "size": "M", "color": "x", "quantity": 1,
            }],
        })
        check(
            "stock check reports not_available for coming_soon",
            avail_check is not None and avail_check.status_code == 200
            and any(
                i.get("reason") == "not_available"
                for i in (avail_check.json() or {}).get("issues", [])
            ),
            str(avail_check.text[:120] if avail_check else ""),
        )
        bad_checkout = call(
            "POST",
            "/checkout",
            customer,
            json={
                "lines": [{
                    "product_id": target["id"], "size": "M", "color": "x", "quantity": 1,
                }],
                "address": {
                    "full_name": "آزمون", "phone": "09120000000", "province": "تهران",
                    "city": "تهران", "line": "خیابان تست، پلاک ۱", "postal_code": "1998765432",
                },
            },
        )
        check(
            "checkout rejects coming_soon (409 stock_conflict/not_available)",
            bad_checkout is not None and bad_checkout.status_code == 409
            and bad_checkout.json().get("code") == "stock_conflict",
            f"{bad_checkout.status_code if bad_checkout else 0}",
        )
        call("PATCH", f"/products/{target['id']}", admin, json={"availability": orig_avail})

    # --- checkout (creates a real order for the customer) ---
    # The first cart is deliberately TWO lines so the B2.4 co-purchase refresh
    # (multi-item orders only) runs inside the checkout transaction.
    order_id = None
    refund_id = None
    color = prods[0]["colors"][0]["name"] if prods[0]["colors"] else "x"
    size = prods[0]["sizes"][0] if prods[0]["sizes"] else "M"
    pid2 = prods[1]["id"] if len(prods) > 1 and prods[1]["id"] != pid else None
    first_lines = [
        {"product_id": pid, "size": size, "color": color, "quantity": 1}
    ]
    if pid2:
        c2 = prods[1]["colors"][0]["name"] if prods[1]["colors"] else color
        s2 = prods[1]["sizes"][0] if prods[1]["sizes"] else size
        first_lines.append({"product_id": pid2, "size": s2, "color": c2, "quantity": 1})
    chk = call(
        "POST",
        "/checkout",
        customer,
        json={
            "lines": first_lines,
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
    if chk is not None and chk.status_code in (200, 201):
        order_id = chk.json()["order_id"]
        if pid2:
            rec_after = call("GET", f"/products/{pid}/recommendations")
            check(
                "multi-item checkout keeps /recommendations healthy (B2.4)",
                rec_after is not None and rec_after.status_code == 200,
                f"{rec_after.status_code if rec_after else 0}",
            )

    # a SECOND order stays pending for the state-machine exercise (the first one
    # is walked through payment and ends up processing)
    chk2 = call(
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
    sm_order_id = (
        chk2.json()["order_id"] if chk2 is not None and chk2.status_code in (200, 201) else None
    )

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

    # --- order state machine (B6.1 / spec BE-05) ---
    # Uses the SECOND order, which is still `pending` here (the first order has
    # been paid via payment-complete, which moves it to `processing`).
    if sm_order_id:
        stock_before = call("GET", f"/products/{pid}").json().get("stock")
        # illegal: skip stages or jump to terminal states from pending
        for bad in ("shipped", "delivered"):
            resp = call("PATCH", f"/orders/{sm_order_id}", admin, json={"status": bad})
            check(
                f"illegal transition pending→{bad} rejected (409)",
                resp is not None and resp.status_code == 409,
                f"{resp.status_code if resp else 0}",
            )
        # legal: pending → processing (one stage forward)
        advance = call("PATCH", f"/orders/{sm_order_id}", admin, json={"status": "processing"})
        check(
            "legal transition pending→processing accepted",
            advance is not None and advance.status_code == 200
            and advance.json().get("status") == "processing",
            f"{advance.status_code if advance else 0}",
        )
        # illegal again: no going back
        back = call("PATCH", f"/orders/{sm_order_id}", admin, json={"status": "pending"})
        check(
            "illegal transition processing→pending rejected (409)",
            back is not None and back.status_code == 409,
            f"{back.status_code if back else 0}",
        )
        # admin cancels via the PATCH dropdown (legal from pending/processing);
        # the same transaction restores the taken stock
        admin_cancel = call(
            "PATCH", f"/orders/{sm_order_id}", admin, json={"status": "cancelled"}
        )
        check(
            "admin PATCH cancel from processing succeeds",
            admin_cancel is not None and admin_cancel.status_code == 200
            and admin_cancel.json().get("status") == "cancelled",
            f"{admin_cancel.status_code if admin_cancel else 0}",
        )
        stock_after = call("GET", f"/products/{pid}").json().get("stock")
        check(
            "cancellation restores order stock (+1)",
            stock_before is not None and stock_after is not None
            and stock_after == stock_before + 1,
            f"before={stock_before} after={stock_after}",
        )
        # AB-BE-01: the live checkout + cancel left a purchase and a return that net to 0
        ledger = call("GET", f"/admin/inventory/logs?order_id={sm_order_id}", admin).json()
        moves = [(e["reason"], e["change_amount"]) for e in ledger.get("items", [])]
        check(
            "inventory ledger: purchase + return for the cancelled order net to zero",
            sorted(r for r, _ in moves) == ["purchase", "return"]
            and sum(c for _, c in moves) == 0,
            f"{moves}",
        )
        hidden = call("GET", "/admin/inventory/logs", support)
        check(
            "inventory ledger is catalog staff only (support → 403)",
            hidden is not None and hidden.status_code == 403,
            f"{hidden.status_code if hidden else 0}",
        )
        revived = call("PATCH", f"/orders/{sm_order_id}", admin, json={"status": "processing"})
        check(
            "cancelled order cannot be revived (409)",
            revived is not None and revived.status_code == 409,
            f"{revived.status_code if revived else 0}",
        )

    # --- refund flow (B5.3): cancelled + paid order → request → settle ---
    if order_id:
        call("POST", f"/orders/{order_id}/cancel", customer)
        refund = call(
            "POST", f"/orders/{order_id}/refunds", customer, json={"reason": "smoke refund"}
        )
        if refund is not None and refund.status_code == 201:
            refund_id = refund.json()["id"]
            check(
                "refund request starts as pending",
                refund.json().get("status") == "pending",
                str(refund.json()),
            )
            listed = call("GET", "/admin/refunds", admin)
            entries = (
                listed.json() if listed is not None and listed.status_code == 200 else []
            ) or []
            mine = next((r for r in entries if r["id"] == refund_id), None)
            check(
                "admin refund list carries claimant contact",
                mine is not None and bool(mine.get("user_email")),
                f"user_email={mine.get('user_email') if mine else None}",
            )
            nobank = call(
                "PATCH",
                f"/refunds/{refund_id}",
                admin,
                json={"status": "refunded", "admin_note": "smoke"},
            )
            check(
                "settlement without bank tracking code is rejected",
                nobank is not None and nobank.status_code == 422,
                f"{nobank.status_code if nobank else 0}",
            )
            settled = call(
                "PATCH",
                f"/refunds/{refund_id}",
                admin,
                json={
                    "status": "refunded",
                    "admin_note": "smoke",
                    "bank_tracking_code": "SATNA123456",
                },
            )
            check(
                "settlement with bank code succeeds",
                settled is not None and settled.status_code == 200,
                f"{settled.status_code if settled else 0} {settled.text[:80] if settled else ''}",
            )
            listed2 = call("GET", "/admin/refunds", admin)
            entries2 = (
                listed2.json() if listed2 is not None and listed2.status_code == 200 else []
            ) or []
            mine2 = next((r for r in entries2 if r["id"] == refund_id), None)
            check(
                "settled refund records bank code + resolver",
                mine2 is not None
                and mine2.get("bank_tracking_code") == "SATNA123456"
                and bool(mine2.get("resolved_by"))
                and bool(mine2.get("resolved_at")),
                str(
                    {
                        k: mine2.get(k) if mine2 else None
                        for k in ("bank_tracking_code", "resolved_by", "resolved_at")
                    }
                ),
            )
            order_after = call("GET", f"/orders/{order_id}", customer)
            check(
                "settled refund flips order payment_status to refunded",
                order_after is not None
                and order_after.status_code == 200
                and order_after.json().get("payment_status") == "refunded",
                "",
            )

    # --- admin ---
    call("GET", "/admin/stats", admin)

    # --- KPI aggregation (B5.2 / spec BE-09) ---
    kpi = call("GET", "/admin/kpis?range=7d", admin)
    kpi_keys = (
        "grossRevenue",
        "netRevenue",
        "paidOrders",
        "aov",
        "pendingRefunds",
        "lowStock",
        "series",
        "statusBreakdown",
    )
    check(
        "KPI endpoint returns the aggregated block",
        kpi is not None
        and kpi.status_code == 200
        and all(key in (kpi.json() or {}) for key in kpi_keys),
        f"{kpi.status_code if kpi else 0}",
    )
    kpi_points = (
        len((kpi.json() or {}).get("series", []))
        if kpi is not None and kpi.status_code == 200
        else "?"
    )
    check(
        "KPI series carries one point per day",
        kpi is not None and kpi.status_code == 200 and kpi_points == 8,
        f"{kpi_points} points",
    )
    for r in ("today", "30d", "all"):
        call("GET", f"/admin/kpis?range={r}", admin)
    call("GET", "/admin/kpis?range=bogus", admin)  # expected 422
    call("GET", "/admin/kpis")  # unauthenticated → 401/403

    # --- audit log (B5.1 / spec BE-04) ---
    logs = call(
        "GET", "/admin/audit-logs?entity_type=order&limit=50", admin
    )
    log_entries = (
        logs.json() if logs is not None and logs.status_code == 200 else []
    ) or []
    order_audit_actions = (
        "update_order_status",
        "update_order_payment_status",
        "update_order_tracking_code",
    )
    check(
        "audit log records the admin order mutation",
        bool(log_entries)
        and any(e["action"] in order_audit_actions for e in log_entries),
        f"entries={len(log_entries)}",
    )
    # this run's own entries must carry who + when; rows of accounts deleted since
    # (e.g. by the pytest suite) keep admin_id NULL — audit_logs is append-only (B5.1b)
    own_entries = [
        e for e in log_entries
        if e.get("entity_id") in {str(order_id), str(sm_order_id)}
        and e.get("action") in order_audit_actions
    ]
    check(
        "audit entries carry admin identity + timestamps",
        bool(own_entries)
        and all(
            e.get("admin_id") and e.get("admin_email") == "admin@sande.local"
            and e.get("created_at")
            for e in own_entries
        ),
        f"own={len(own_entries)}",
    )
    # B5.1a: the middleware captures the caller IP (XFF-aware) on every request
    recent_ips = [e.get("ip_address") for e in log_entries]
    check(
        "audit entries capture the caller IP (B5.1a)",
        bool(log_entries) and any(recent_ips),
        f"ips={[i for i in recent_ips if i][:2]}",
    )
    if order_id and refund_id:
        by_entity = call(
            "GET", f"/admin/audit-logs?entity_type=order&entity_id={order_id}", admin
        )
        entity_entries = (
            by_entity.json() if by_entity is not None and by_entity.status_code == 200 else []
        ) or []
        check(
            "audit log filters by entity_id (refund resolution visible)",
            any(e["action"] == "resolve_refund" for e in entity_entries),
            f"actions={[e['action'] for e in entity_entries]}",
        )
    forbidden_logs = call("GET", "/admin/audit-logs", customer)
    check(
        "audit log is admin-only",
        forbidden_logs is not None and forbidden_logs.status_code == 403,
        f"{forbidden_logs.status_code if forbidden_logs else 0}",
    )

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

    # --- audit log (B5.1 / spec BE-04) ---
    # Runs *after* the order mutations above: the assertions below look for the
    # `update_order_*` entries those PATCHes write, so checking earlier only ever
    # passed on a database that already held rows from a previous run.
    logs = call(
        "GET", "/admin/audit-logs?entity_type=order&limit=50", admin
    )
    log_entries = (
        logs.json() if logs is not None and logs.status_code == 200 else []
    ) or []
    order_audit_actions = (
        "update_order_status",
        "update_order_payment_status",
        "update_order_tracking_code",
    )
    check(
        "audit log records the admin order mutation",
        bool(log_entries)
        and any(e["action"] in order_audit_actions for e in log_entries),
        f"entries={len(log_entries)}",
    )
    # the entries this run's own admin mutations wrote must carry who + when; rows of
    # accounts deleted since (e.g. by the pytest suite) legitimately keep admin_id NULL
    # — audit_logs is append-only and the FK nulls the attribution (B5.1b)
    own_entries = [
        e for e in log_entries
        if e.get("entity_id") in {str(order_id), str(sm_order_id)}
        and e.get("action") in order_audit_actions
    ]
    check(
        "audit entries carry admin identity + timestamps",
        bool(own_entries)
        and all(
            e.get("admin_id") and e.get("admin_email") == "admin@sande.local"
            and e.get("created_at")
            for e in own_entries
        ),
        f"own={len(own_entries)}",
    )
    if order_id and refund_id:
        by_entity = call(
            "GET", f"/admin/audit-logs?entity_type=order&entity_id={order_id}", admin
        )
        entity_entries = (
            by_entity.json() if by_entity is not None and by_entity.status_code == 200 else []
        ) or []
        check(
            "audit log filters by entity_id (refund resolution visible)",
            any(e["action"] == "resolve_refund" for e in entity_entries),
            f"actions={[e['action'] for e in entity_entries]}",
        )
    forbidden_logs = call("GET", "/admin/audit-logs", customer)
    check(
        "audit log is admin-only",
        forbidden_logs is not None and forbidden_logs.status_code == 403,
        f"{forbidden_logs.status_code if forbidden_logs else 0}",
    )


    # --- granular staff roles (B5.4 / spec BE-04) ---
    # create a throwaway user, grant order_manager, exercise the capability
    # matrix, then demote — leaves the DB as it started.
    staff_mail = f"staff_{uuid4().hex[:8]}@example.com"
    su = call(
        "POST", "/auth/signup",
        json={"email": staff_mail, "password": "secret123", "full_name": "کارمند آزمون"},
    )
    staff_uid = (
        su.json().get("id") if su is not None and su.status_code in (200, 201) else None
    )
    if staff_uid is None:
        # signup returns a token, not an id — find the user via the admin list
        ulist = call("GET", "/admin/users", admin)
        for u in (ulist.json() if ulist is not None and ulist.status_code == 200 else []):
            if u.get("email") == staff_mail:
                staff_uid = u["id"]
                break
    staff_tok = login(staff_mail, "secret123")

    if staff_uid:
        check("customer cannot self-grant staff roles", call(
            "PUT", f"/admin/users/{staff_uid}/roles",
            json={"roles": ["super_admin"]}, token=staff_tok,
        ).status_code == 403, "")

        granted = call(
            "PUT", f"/admin/users/{staff_uid}/roles", admin,
            json={"roles": ["order_manager"]},
        )
        check(
            "PUT /admin/users/{id}/roles grants order_manager",
            granted is not None and granted.status_code == 200
            and granted.json().get("roles") == ["order_manager"],
            f"{granted.status_code if granted else 0} {granted.text[:80] if granted else ''}",
        )
        staff_tok = login(staff_mail, "secret123")  # role set is DB-backed, re-login anyway

        check("order_manager reads orders (orders cap)", call(
            "GET", "/admin/orders", staff_tok).status_code == 200, "")
        check("order_manager reads KPIs (stats cap)", call(
            "GET", "/admin/kpis?range=7d", staff_tok).status_code == 200, "")
        check("order_manager blocked from audit log (audit cap)", call(
            "GET", "/admin/audit-logs", staff_tok).status_code == 403, "")
        check("order_manager blocked from users list (users cap)", call(
            "GET", "/admin/users", staff_tok).status_code == 403, "")
        check("order_manager blocked from review moderation", call(
            "PATCH", "/reviews/nonexistent", staff_tok, json={"status": "approved"},
        ).status_code == 403, "")

        # order_manager exercises a fulfillment mutation, then support can't
        if order_id:
            om_code = "249028345699999999999999"
            om_patch = call(
                "PATCH", f"/orders/{order_id}", staff_tok, json={"tracking_code": om_code}
            )
            check(
                "order_manager saves tracking_code",
                om_patch is not None and om_patch.status_code == 200,
                f"{om_patch.status_code if om_patch else 0}",
            )
        check("support blocked from fulfillment (orders cap)", call(
            "GET", "/admin/orders", support,
        ).status_code == 403, "")
        check("support reaches the contact inbox (contact_inbox cap)", call(
            "GET", "/admin/contact-messages", support,
        ).status_code == 200, "")

        roles_audit = call(
            "GET", f"/admin/audit-logs?entity_type=user&entity_id={staff_uid}", admin
        )
        role_entries = (
            roles_audit.json() if roles_audit is not None and roles_audit.status_code == 200 else []
        ) or []
        check(
            "role change is audited with old/new values",
            any(e["action"] == "update_user_roles" for e in role_entries)
            and any(e.get("old_values") is not None and e.get("new_values") for e in role_entries),
            f"entries={len(role_entries)}",
        )

        demoted = call("PUT", f"/admin/users/{staff_uid}/roles", admin, json={"roles": []})
        check(
            "demote back to plain customer",
            demoted is not None and demoted.status_code == 200
            and demoted.json().get("roles") == [],
            f"{demoted.status_code if demoted else 0}",
        )
        check("demoted user loses staff access", call(
            "GET", "/admin/orders", staff_tok).status_code == 403, "")
    else:
        check("B5.4 role flow (user created)", False, "could not resolve new user id")

    # --- notifications (B2.1): the flows above must have notified the customer
    # exactly once per event, however often they repeated a transition ---
    inbox = call("GET", "/notifications", customer, params={"page": 1, "page_size": 100})
    inbox_body = inbox.json() if inbox is not None and inbox.status_code == 200 else {}
    check(
        "GET /notifications → envelope",
        {"items", "total", "page", "page_size", "pages"} <= set(inbox_body),
        f"total={inbox_body.get('total')}",
    )
    items = inbox_body.get("items", [])

    def types_for(oid) -> list[str]:
        return sorted(n["type"] for n in items if (n.get("data") or {}).get("order_id") == oid)

    if order_id:
        # paid twice (gateway + simulator), cancelled, refunded — one row per event
        got = types_for(order_id)
        check(
            "paid+cancelled+refunded order → one notification per event",
            got == ["order_cancelled", "order_created", "order_paid", "refund_settled"],
            f"{got}",
        )
    if sm_order_id:
        got = types_for(sm_order_id)
        check(
            "staff-cancelled order → created + cancelled",
            got == ["order_cancelled", "order_created"],
            f"{got}",
        )
    check(
        "notifications are newest first",
        [n["created_at"] for n in items] == sorted((n["created_at"] for n in items), reverse=True),
        f"n={len(items)}",
    )
    if items:
        first_id = items[0]["id"]
        read = call("PATCH", f"/notifications/{first_id}/read", customer)
        check(
            "PATCH /notifications/{id}/read sets read_at",
            read is not None and read.status_code == 200 and bool(read.json().get("read_at")),
            f"{read.status_code if read else 0}",
        )
        foreign = call("PATCH", f"/notifications/{first_id}/read", admin)
        check(
            "another user's notification → 404",
            foreign is not None and foreign.status_code == 404,
            f"{foreign.status_code if foreign else 0}",
        )
    call("POST", "/notifications/read-all", customer)
    unread = call("GET", "/notifications/unread-count", customer)
    check(
        "read-all → unread-count 0",
        unread is not None and unread.status_code == 200 and unread.json() == {"unread": 0},
        f"{unread.text[:60] if unread is not None else ''}",
    )
    anon = call("GET", "/notifications")
    check("GET /notifications anonymous → 401", anon is not None and anon.status_code == 401, "")

    ns = call("GET", "/admin/settings/notifications", admin)
    ns_body = ns.json() if ns is not None and ns.status_code == 200 else {}
    check(
        "admin reads notification switches + provider state",
        ns_body.get("internal_enabled") is True
        and ns_body.get("sms_provider") == "kavenegar"
        and ns_body.get("email_provider") == "smtp",
        f"{ns_body}",
    )
    for who, tok in (("customer", customer), ("support", support)):
        denied = call("PATCH", "/admin/settings/notifications", tok, json={"sms_enabled": True})
        check(
            f"notification switches as {who} → 403",
            denied is not None and denied.status_code == 403,
            f"{denied.status_code if denied else 0}",
        )
    if ns_body:
        original = ns_body["sms_enabled"]
        flipped = call(
            "PATCH", "/admin/settings/notifications", admin, json={"sms_enabled": not original}
        )
        check(
            "admin flips the SMS switch",
            flipped is not None and flipped.status_code == 200
            and flipped.json().get("sms_enabled") is (not original)
            and flipped.json().get("internal_enabled") is True,
            f"{flipped.status_code if flipped else 0}",
        )
        call("PATCH", "/admin/settings/notifications", admin, json={"sms_enabled": original})
    empty = call("PATCH", "/admin/settings/notifications", admin, json={})
    check(
        "empty switch update → 400",
        empty is not None and empty.status_code == 400,
        f"{empty.status_code if empty else 0}",
    )

    # --- reports & exports (B2.2 / spec BE-08) ---
    csv_res = call("GET", "/admin/export/orders.csv?from=2026-01-01", admin)
    csv_ok = csv_res is not None and csv_res.status_code == 200
    csv_head = csv_res.text.splitlines()[0].lstrip("\ufeff") if csv_ok else ""
    cd = csv_res.headers.get("content-disposition", "")[:40] if csv_ok else ""
    check(
        "CSV export starts with a UTF-8 BOM (B2.2b)",
        csv_ok and csv_res.content.startswith(b"\xef\xbb\xbf"),
        f"{csv_res.content[:3] if csv_ok else b''}",
    )
    check(
        "GET /admin/export/orders.csv → header+rows",
        csv_ok
        and csv_head.startswith("order_number,created_at,status")
        and len(csv_res.text.splitlines()) > 1,
        f"lines={len(csv_res.text.splitlines()) if csv_ok else 0} cd={cd}",
    )
    xlsx_res = call("GET", "/admin/export/orders.xlsx", admin)
    xlsx_ok = xlsx_res is not None and xlsx_res.status_code == 200
    check(
        "GET /admin/export/orders.xlsx → PK zip magic",
        xlsx_ok and xlsx_res.content[:2] == b"PK",
        f"bytes={len(xlsx_res.content) if xlsx_ok else 0}",
    )
    pcsv = call("GET", "/admin/export/products.csv", admin)
    check(
        "GET /admin/export/products.csv",
        pcsv is not None and pcsv.status_code == 200
        and pcsv.text.lstrip("\ufeff").startswith("product_id,"),
        f"{pcsv.status_code if pcsv else 0}",
    )
    pxlsx = call("GET", "/admin/export/products.xlsx", admin)
    check(
        "GET /admin/export/products.xlsx",
        pxlsx is not None and pxlsx.status_code == 200 and pxlsx.content[:2] == b"PK",
        f"{pxlsx.status_code if pxlsx else 0}",
    )
    report = call("GET", "/admin/export/report", admin)
    rep = report.json() if report is not None and report.status_code == 200 else {}
    check(
        "GET /admin/export/report → daily/monthly/bestSellers",
        {"daily", "monthly", "bestSellers"} <= set(rep),
        f"days={len(rep.get('daily', []))} best={len(rep.get('bestSellers', []))}",
    )
    bad = call("GET", "/admin/export/orders.csv?from=2030-01-01&to=2026-01-01", admin)
    bad_code = bad.status_code if bad else 0
    check("export with from ≥ to → 422", bad is not None and bad_code == 422, f"{bad_code}")
    noauth = call("GET", "/admin/export/report")
    noauth_code = noauth.status_code if noauth else 0
    noauth_ok = noauth is not None and noauth_code == 401
    check("export unauthenticated → 401", noauth_ok, f"{noauth_code}")
    support_res = call("GET", "/admin/export/orders.csv", support)
    supp_code = support_res.status_code if support_res else 0
    check("export as support → 403", support_res is not None and supp_code == 403, f"{supp_code}")

    # --- storage ---
    call("POST", "/storage/sign", customer, json={"paths": ["uploads/x.jpg", "cat-tshirt"]})
    call(
        "POST",
        "/storage/upload-url",
        admin,
        json={"filename": "x.jpg", "content_type": "image/jpeg"},
    )
    # B6.17: presigning follows the catalog capability — order_manager yes, support no
    order_mgr = login("ordermgr@sande.local", "staff1234")
    for who, token, expected in (("order_manager", order_mgr, 200), ("support", support, 403)):
        res = call(
            "POST",
            "/storage/upload-url",
            token,
            json={"filename": "x.png", "content_type": "image/png"},
        )
        got = res.status_code if res is not None else 0
        check(f"upload-url as {who} → {expected}", got == expected, f"{got}")

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
