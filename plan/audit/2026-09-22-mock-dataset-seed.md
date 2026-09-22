# Audit — 2026-09-22 — Mock dataset seed (`app.seed_mock`) + smoke test ordering fix

## Task

User request, after the full-stack audit: build and run the project, then
"add some mock data to database" so the storefront and admin panel have
realistic content to demonstrate.

## Spec check (Rule 0)

`design/SANDE_FULL_DEV_SPEC.md` was read before the work started.

**Followed** — the dataset is shaped to exercise what the spec describes:

- `[BE-01]` — a size × colour variant matrix with independent stock per row
  (`tshirt-1`, `tshirt-2`, `crop-5`, `socks-13`), including a sold-out variant
  that stays visible but inactive.
- `[BE-02]` — extra coupons covering the states `[FE-07]` wants to render: an
  active campaign, an amount-off code, one exhausted (`VIP15`, 20/20 uses → the
  usage bar sits at 100%) and one expired/inactive (`NOWRUZ25`).
- `[BE-03]` / `[FE-06]` — refund claims in **all four** lifecycle states
  (`pending`, `approved`, `rejected`, `refunded`), with `admin_note`,
  `resolved_by` and `resolved_at` on the resolved ones and the Paya/Satna
  `bank_tracking_code` present only on the settled claim.
- `[BE-09]` / `[FE-03]` — orders backdated across 47 days so the KPI endpoint's
  daily revenue series, the MoM deltas and the status donut all have real shape,
  plus deliberate low-stock and out-of-stock products so "اقدامات فوری" fires.
- `[FE-05]` — every shipped/delivered order carries a 24-digit Iran Post
  tracking code, and none of the earlier-stage orders do.
- `[FE-08]` — staggered registration dates (one week apart) and varied order
  counts/spend so the customer list is not one flat timestamp.

**Deliberately not followed** — nothing in the spec was contradicted. The seed
writes only through the existing schema and does not touch any Rule 4 status
string or the cart money rules; in fact it asserts them (see the shipping-rule
check below).

## What was done

### New: `backend/app/seed_mock.py`

An optional, idempotent, deterministic seed (fixed RNG seed `20260922`, so every
fresh database produces identical figures — demos and screenshots stay
reproducible). It follows the conventions of the existing seeds: `startup_ddl()`
first, a single `engine.begin()` transaction, Persian content, progress lines.

Guarded by a marker account (`niloofar.ahmadi@example.com`): if it exists, the
module prints "mock data already present" and does nothing, so a second run can
never double-count revenue.

It is **not** wired into the compose `db-init` chain — the default stack stays
the small starter dataset, and the mock data is opt-in.

Internal rules the generator respects, so the data is not just "rows":

- Order money is computed, never faked: `subtotal = Σ(price × qty)`,
  `total = subtotal − discount + shipping`, with the repo's real shipping rule
  (۸۹٬۰۰۰ flat, free at/over ۲٬۰۰۰٬۰۰۰ after discount).
- Stock is decremented for every non-cancelled order and left alone for
  cancelled ones — mirroring checkout plus the `[BE-05]` restore-on-cancel rule
  fixed earlier today.
- Paid orders get a `succeeded` payment row; some pending orders get a `failed`
  one (abandoned gateway attempts); a settled refund flips the order to
  `refunded` **and** writes the matching `refund` ledger row.
- Reviews are only written by customers who actually received that product in a
  `delivered` order.

### Fixed: `backend/tests/api_smoke.py` (pre-existing bug, found by this work)

Running the smoke suite against a **freshly seeded** database failed one check:

```
FAIL   audit log records the admin order mutation   -   entries=2
```

The assertion looks for an `update_order_status` / `update_order_payment_status`
/ `update_order_tracking_code` entry in the audit log — but the script's first
`PATCH /orders/{id}` happens 41 lines **later** in the same function. The check
therefore only ever passed on a database that already held those rows from a
previous run; on a genuinely clean database it always failed. It is a test
ordering bug, not a product bug and not caused by the mock data — reproduced on
a clean database both with and without the mock seed.

Per Rule 10/11 the assertion was **not** weakened. The audit-log block was moved
so it runs after the order mutations it describes, with a comment recording why.
It now passes on a first run against a clean database.

## Files changed

- `backend/app/seed_mock.py` — **new**, the optional mock dataset.
- `backend/tests/api_smoke.py` — audit-log assertions moved after the order
  mutations they assert on.
- `backend/README.md`, `infra/README.md` — document the optional seed.
- `plan/audit/2026-09-22-mock-dataset-seed.md` (this file),
  `plan/backend-tasks.md`, `plan/session-log.md`.

## Seed counts (verified in Postgres, clean database)

| Entity | Total | From `seed_mock` |
|---|---|---|
| users / profiles | 12 | 8 |
| addresses | 10 | 8 |
| favorites | 21 | 18 |
| products | 20 | 0 (2 re-stocked for alerts) |
| product_variants | 14 | 14 |
| orders | 33 | 31 |
| order_items | 66 | 64 |
| payments | 29 | 27 |
| refund_requests | 5 | 5 |
| product_reviews | 18 | 18 |
| contact_messages | 5 | 5 |
| coupons | 6 | 4 |

Order mix: delivered/paid 10 · shipped/paid 5 · processing/paid 5 ·
pending/unpaid 5 · cancelled/unpaid 3 · cancelled/paid 4 · cancelled/refunded 1,
spread over 20 distinct days across a 47-day window.
Refunds: pending 2 · approved 1 · rejected 1 · refunded 1.

## How to verify

```bash
# clean stack, then the optional dataset
cd infra && docker compose down -v && docker compose up -d
docker compose exec backend python -m app.seed_mock      # counts printed above
docker compose exec backend python -m app.seed_mock      # → "already present", no-op

# consistency (all must return 0)
docker exec sandeh-postgres-1 psql -U sande -d postgres -c "
 select count(*) from orders o where o.subtotal <> (select coalesce(sum(i.price*i.quantity),0)
   from order_items i where i.order_id=o.id);
 select count(*) from orders where total <> subtotal - discount + shipping;
 select count(*) from orders where shipping <> (case when (subtotal-discount) >= 2000000
   then 0 else 89000 end);
 select count(*) from orders o where o.payment_status in ('paid','refunded') and not exists
   (select 1 from payments p where p.order_id=o.id and p.status='succeeded');
 select count(*) from orders where tracking_code is not null
   and status not in ('shipped','delivered');
 select count(*) from products where stock < 0;"

cd ../backend && ./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests                # clean
./.venv/bin/python tests/api_smoke.py                     # 173 checks, 0 failed
```

In the browser (sign in as `admin@sande.local` / `admin1234`): `/admin` shows
populated KPIs, a trend line and the status donut; `/admin/orders` lists 33
orders; `/admin/refunds` shows 3 pending / 2 settled / 5 total across its tabs;
`/admin/inventory`, `/admin/messages`, `/admin/reviews` and `/admin/users` are
all populated. Mock customers (e.g. `zahra.nouri@example.com` / `customer1234`)
have real order history.

## What is NOT done / open

- **`seed_mock` is not in the compose `db-init` chain** — deliberate, so the
  default stack stays minimal. Run it by hand when you want a populated demo.
- **No search history / recently-viewed rows** are seeded; those are per-session
  personalisation and look wrong when back-dated.
- **Reviews skew positive** (avg ★4.0 published) because the copy pool is mostly
  4–5 star. Fine for a demo, not a statistically shaped dataset.
- **Two reviews land in `hidden`** rather than the one the comment implies — a
  consequence of the `count % 9` rule over 18 reviews. Harmless: the moderation
  filter just has two subjects instead of one.
- `vogue-vintage-vibes/FEATURES.md`, `DESIGN_SYSTEM.md` and `plan/README.md`
  were **deliberately left untouched**: no feature, component, token or folder
  changed — this adds demo data and a developer script only.
