# B6.9 — Narrow refund exception handling

**Date:** 2026-09-22
**Task ID:** `B6.9` (P1 — Core product, `plan/MASTER-BACKLOG.md`; source
checkbox `plan/backend-tasks.md`)
**Title:** Narrow refund exception handling

## Original requirement

`POST /orders/{id}/refunds` wrapped its INSERT in a bare `except Exception`, so
*every* failure — including a real database or application error — was answered
with 409 «برای این سفارش قبلاً درخواست بازپرداخت ثبت شده است». The backlog asks
to:

* catch only the expected duplicate/idempotency condition;
* preserve the legitimate duplicate behaviour;
* let unexpected DB/application errors surface correctly;
* preserve the security and error-response conventions.

## Spec check (Rule 0)

* **`[BE-03]` Refund lifecycle / `[FE-06]`** — *followed, unchanged*. The refund
  request contract (cancelled + paid only, one request per order, `pending`
  start state, settlement requiring the Paya/Satna code) is untouched; this task
  only changes which exception maps to the 409.
* **Spec stack header (Supabase RPC / RLS)** — *deliberately ignored*: the
  handler is a FastAPI route with `CurrentUser` + an ownership filter, per the
  live architecture (Rule 0.2).
* **Rule 4 vocabulary** — no status string changed. Refund statuses stay
  `pending/approved/rejected/refunded`; the Persian duplicate message is
  byte-identical to before, so the UI copy does not move.

## Repository architecture check (Rule 6)

* **Owning module:** `backend/app/routers/orders.py` (`request_refund`). The
  refund *settlement* path lives in `services/payments.py` and was not touched.
* **Data flow:** `src/lib/api.ts::requestRefund` → `POST /orders/{id}/refunds` →
  `routers/orders.py` → `public.refund_requests` (UNIQUE `order_id`).
* **API contract (Rule 8):** unchanged on both success and duplicate — 201 with
  `{id, order_id, amount, status}`, 409 with the same `detail` string. The only
  observable change is that a genuine database fault now returns 500 instead of
  a false 409, which is the point of the task. `request()` in `src/lib/api.ts`
  surfaces either shape unchanged; no frontend edit was needed.
* **Auth (Rule 9):** unchanged. `CurrentUser` plus `_fetch_order(..., user_id=…)`
  means another user's order is a 404, an anonymous caller a 401, and the
  `amount` comes from the order row — never from the request body. All three are
  covered by the new tests.
* **Canonical implementation (Rule 7):** follows the existing
  `except IntegrityError` → 409 pattern in `routers/auth.py::signup`. The
  SQLSTATE predicate `_is_unique_violation()` is a four-line module-private
  helper next to its single caller rather than a new shared module (Rule 12); if
  a second caller appears it should move to a service.
* **State machine (Rule 10):** "what if this runs twice?" — the second request
  is exactly the duplicate case: the UNIQUE constraint rejects it, the
  transaction is rolled back, no second row is written and no money moves. The
  test asserts the row count stays at 1.

## Files changed

* `backend/app/routers/orders.py` — import `IntegrityError`; add
  `_is_unique_violation()`; `request_refund` now catches `IntegrityError`,
  answers 409 only for SQLSTATE `23505` (`unique_violation`), and logs +
  re-raises anything else after rolling the session back.
* `backend/tests/test_refund_requests.py` — **new** test module (4 predicate unit
  tests + 6 endpoint tests).

## Implementation summary

```python
except IntegrityError as exc:
    await session.rollback()
    if not _is_unique_violation(exc):
        log.exception("refund request failed with an unexpected integrity error")
        raise
    raise HTTPException(409, "برای این سفارش قبلاً …") from exc
```

Two narrowings, not one: `Exception` → `IntegrityError` (a connection drop, a
serialization failure or a bug in the handler is no longer a "duplicate"), and
`IntegrityError` → SQLSTATE `23505` (a foreign-key or check violation on
`refund_requests` is a real defect and must not be disguised either). The
rollback still runs first in both branches, so the session is always clean for
the dependency's own teardown.

## Tests executed

```
cd backend
DATABASE_URL=postgresql+asyncpg://sande:sande@localhost:5432/postgres \
  ./.venv/bin/python -m pytest -q tests/test_refund_requests.py   # 10 passed
DATABASE_URL=… ./.venv/bin/python -m pytest -q                    # 54 passed
./.venv/bin/python -m ruff check app tests                        # All checks passed
./.venv/bin/python tests/api_smoke.py                             # 196 checks, 0 failed
```

New tests (skipped when no database is reachable, matching B6.8's module):

* `_is_unique_violation` returns True for `23505` and False for `23503`
  (foreign key), `23514` (check) and a driver exposing no SQLSTATE;
* **success path** — the first request returns 201, `status = "pending"`, with
  the amount taken from the order;
* **true duplicate** — the second request returns 409 with the unchanged Persian
  message, and `refund_requests` still holds exactly one row;
* **unrelated DB failure** — a `get_session` override whose refund INSERT raises
  a `23503` IntegrityError produces a 500, and the body does not contain the
  duplicate message;
* **error paths** — an order that is not cancelled+paid → 409 with the
  eligibility message; another user's order → 404; anonymous → 401.

**Mutation check:** restoring the old bare `except Exception` body turns the
unrelated-failure test red (409 instead of 500) while the other nine stay green
— the new test isolates exactly the defect B6.9 describes.

### Live runtime flow (running stack, real HTTP)

Backend container rebuilt, then, as `customer@sande.local`: checkout →
`payment-complete success` → cancel → refund request.

| call | result |
| --- | --- |
| `POST /orders/{id}/refunds` (first) | 201 `{"status":"pending","amount":709000}` |
| `POST /orders/{id}/refunds` (repeat) | 409 «برای این سفارش قبلاً درخواست بازپرداخت ثبت شده است» |
| same call without a token | 401 «Missing bearer token» |
| unknown order id | 404 «سفارش پیدا نشد» |

`docker compose logs backend` shows no traceback for any of these — the 409 path
still does not log noise. The test order was deleted afterwards.

## Verification level

**Integration tested** (unit + DB-backed endpoint tests, full suite, ruff,
`api_smoke.py` against the running stack) **and exercised over real HTTP** on the
rebuilt container. Rule 14 clean-environment verification was **not** repeated:
this task changes no DDL, seed, Docker or configuration file — the
`docker compose down -v` proof from the B6.8 session earlier today still
describes the current schema.

## Remaining limitations

* **The 500 body is FastAPI's generic error**, not a Persian message. That is the
  intended outcome (an unexpected fault should not claim to be a business
  condition) and matches every other unhandled path in the service, but it means
  the UI shows its generic failure toast for it.
* **`api_smoke.py` has no duplicate-refund check.** It covers the 201 request and
  the settlement flow; the 409 duplicate and the 500 surface are covered by
  `tests/test_refund_requests.py` and by the manual live flow above. Adding a
  smoke check would have meant editing a file this task does not otherwise touch
  (Rule 12).
* **Other bare `except Exception` blocks remain** in `routers/products.py`
  (variant and product CRUD, four sites) and `routers/storage.py`. They have the
  same shape of problem but are outside B6.9's scope — recorded as a new backlog
  task rather than fixed here (Rule 12/17).

## Related follow-up findings

Recorded in the Master Backlog task index as discovered-during-B6.9:

* `NEW-B69-1` (P2) — narrow the four bare `except Exception` → 409 handlers in
  `routers/products.py` (and review `routers/storage.py`) the same way, so a real
  database fault is not reported as «این ترکیب سایز و رنگ قبلاً ثبت شده است».

No unrelated bug was fixed in this task.

## Docs deliberately left untouched

`backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`,
`FEATURES.md`, `DESIGN_SYSTEM.md`, `plan/feature-roadmap.md` and
`plan/README.md`: no endpoint, setup step, script, stack, feature status or UI
convention changed — only which internal exception maps to an already-documented
409.
