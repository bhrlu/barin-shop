# Audit — Address 500 fix + complete Catalog & Products backend

**Date:** 2026-09-20
**Task:** Ad-hoc user requests — (1) "test all backend api i get 500 from add
address check all api and fix it"; (2) "complete backend api for catalog &
products feature". Supersedes frontend F3 backend prerequisites and closes the
catalog half of `plan/feature-roadmap.md` §1.

---

## What was done

### 1. Fixed the 500 on add/list address (reported bug)

`AddressOut.created_at` is typed `str`, but Postgres returns a `datetime`.
Passing the raw datetime to the model raised a Pydantic v2 `ValidationError`
(`Input should be a valid string`), which FastAPI surfaced as **500** on both
`GET /addresses` and `POST /addresses`. Reproduced directly against the schema
before fixing.

`routers/addresses.py` now converts `created_at` with `.isoformat()` via a
`_row_to_out` helper, matching the existing pattern in `products.py`, `auth.py`
and `coupons.py` (which all already did this — addresses was the one missed).

### 2. Completed the Catalog & Products backend API

All eight §1 roadmap items now have backend support:

- **Merchandising fields** on `products`: `tags`, `badge`, `availability`
  (`in_stock`/`coming_soon`/`preorder`), `available_at`,
  `low_stock_threshold`; reads also expose `avg_rating` + `review_count`.
- **`GET /products` filters + sort**: `category, tag, badge, availability,
  on_sale, size, color, min_price, max_price, sort` (`new | price_asc |
  price_desc | popular | rating`).
- **Variants (size × color) with separate stock**: `product_variants` table,
  `GET/POST /products/{id}/variants`, `PATCH/DELETE /variants/{id}`. Variant
  stock is **authoritative** for its combination and is wired into both
  `POST /stock/check` and checkout (decrement + guarded).
- **Reviews & ratings + seller replies**: `product_reviews` table,
  `GET/POST /products/{id}/reviews`, `GET /admin/reviews`,
  `PATCH /reviews/{id}` (moderate + reply), `DELETE /reviews/{id}`.
- **Search autocomplete + history**: `GET /search/suggest`,
  `GET/DELETE /search/history`, `DELETE /search/history/{id}`; `GET /search`
  records history for signed-in users.
- **Related / recommended**: `GET /products/{id}/related`,
  `/products/{id}/recommendations`.
- **Recently viewed + comparison**: `recently_viewed` table,
  `POST /products/{id}/view`, `GET /recently-viewed`, `GET /products/compare`.
- **Low-stock alerts**: `GET /admin/inventory`, `GET /admin/inventory/low-stock`.

New tables/columns are created by **idempotent DDL** at startup
(`app/db.py` → `CATALOG_DDL`), the same mechanism already used for the coupon
tables, so a fresh DB and an already-seeded DB both converge with no manual step.

## Files changed

**New**
- `backend/app/routers/reviews.py`
- `backend/app/services/variants.py`
- `backend/tests/api_smoke.py` (end-to-end route exerciser; not pytest-collected)
- `backend/tests/test_addresses.py`
- `backend/tests/test_variants.py`
- `plan/audit/2026-09-20-catalog-backend-and-address-fix.md` (this file)
- `plan/feature-roadmap.md`, `vogue-vintage-vibes/DESIGN_SYSTEM.md` (earlier in
  the same session)

**Changed (backend)**
- `app/db.py` (catalog DDL), `app/models.py` (new tables + product columns),
  `app/schemas.py` (product/variant/review/search schemas)
- `app/routers/products.py` (filters, related/recommended/compare/recently
  viewed, variants), `app/routers/search.py` (suggest + history),
  `app/routers/stock.py`, `app/services/checkout.py` (variant stock),
  `app/routers/admin.py` (inventory), `app/routers/reviews.py` (new),
  `app/auth.py` (`get_optional_user`), `app/main.py` (register router)
- `tests/api_smoke.py` extended with the new routes

**Docs (Rule 5)**
- `plan/RULES.md` (new Rule 5 — update affected docs at end of each task)
- `plan/backend-tasks.md`, `plan/frontend-tasks.md`, `plan/session-log.md`,
  `plan/README.md`, `backend/README.md`, `infra/README.md`,
  `vogue-vintage-vibes/README.md`, `vogue-vintage-vibes/FEATURES.md`

## How to verify

```bash
# 1) unit tests + lint
cd backend
./.venv/bin/python -m pytest -q          # 25 passed
./.venv/bin/python -m ruff check app tests   # clean

# 2) bring the stack up (postgres + minio + backend + frontend)
docker compose -f infra/docker-compose.yml up -d

# 3) exercise every route against the live API
./.venv/bin/python tests/api_smoke.py    # 59 routes, 0 5xx
```

Manual check of the original bug:

```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"customer@sande.local","password":"customer1234"}' | jq -r .access_token)
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/addresses -H "Authorization: Bearer $TOKEN"   # 200
```

Variant-stock authority was verified end-to-end: a variant with `stock: 0`
makes `POST /stock/check` return `ok:false` and checkout `409`; raising it to 2
makes checkout succeed and decrements the variant to 1.

## What is NOT done / open

- **No frontend wiring** — none of the new catalog endpoints are called by the
  UI yet. Tracked as `plan/frontend-tasks.md` **Milestone F3**.
- **Variants are size × color only** — the "model" dimension from the roadmap is
  not modeled (would need a variant model/name column).
- **No stock reservation with TTL** — stock is decremented at order creation,
  as before; there is no hold during checkout.
- **Historical 500s in the container log** (`178.128.69.202`, several
  `/addresses`, one `/checkout`) are all **from before the fix/reload**; a rerun
  shows 0 new 5xx and the checkout coupon path now returns a clean 422.
- `backend/README.md` and `infra/README.md` were refreshed in this task (B3.2 /
  B3.3) — see those files.
