# Audit — 2026-09-20 — Backend search matches product tags (F3.1b)

**Task:** close **F3.1b** from `plan/frontend-tasks.md` — the search matcher
ignored the `tags` column, so the tag rows the header dropdown shows
(`GET /search/suggest`, kind `tag`) led to «نتیجه‌ای پیدا نشد» once clicked.

## What was found

- `app/routers/search.py` **did** already suggest tags
  (`SELECT DISTINCT t FROM public.products p, unnest(p.tags) AS t …`) and the
  frontend routed tag suggestions to `/shop?q=<tag>`.
- `app/services/search.py` matched only `name`, `description`, `material` and
  `category` — never `tags`.
- Worse: **no seeded product had any tags** (`GET /products` → 0 of 20 products
  with tags). The column defaults to `'{}'` (`app/db.py`), and
  `app/seed_products.py` never set it, so tag suggestions could not appear at all
  and `GET /products?tag=` was a no-op on the starter catalog.

## Files changed

| File | Change |
|---|---|
| `backend/app/services/search.py` | `GET /search` now matches the `tags` array via `EXISTS (SELECT 1 FROM unnest(products.tags) AS tag WHERE tag ILIKE :pat)` in both the `WHERE` and a new `tag_hit` ranking flag; order is now `name_hit DESC, cat_hit DESC, tag_hit DESC, is_new DESC, created_at DESC`. Module docstring updated to describe the new matcher and ranking. |
| `backend/app/seed_products.py` | Browse tags added to all 20 starter products (2–4 each: `پنبه`, `کتان`, `دنیم`, `ریب`, `ویسکوز`, `مرینوس`, `پشمی`, `اورسایز`, `جادار`, `کلاسیک`, `بنددار`, `پفی`, `پیلی‌دار`, `نامرئی`, `خانگی`, `لانژ`, `تابستانی`, `زمستانی`, `مجلسی`, `روزمره`, `ساحلی`); the insert now writes `tags` and the conflict clause became `DO UPDATE SET tags = EXCLUDED.tags WHERE public.products.tags = '{}'::text[]` — an already-seeded row gets tags backfilled **only while it has none**, so an admin's own tags survive a re-run. Docstring updated. |
| `backend/tests/api_smoke.py` | New `check()` helper records logical assertions (not just 5xx) in the same report, plus two checks: `/search?q=کتان` must return hits and `/search/suggest?q=کتان` must include a `tag` kind. Summary line reworded to «routes/checks». |

No frontend change was needed: `HeaderSearch.tsx` already sends tag suggestions
to `?q=<tag>`, and `searchQuery()` already renders the hits.

## How to verify

```bash
cd backend
./.venv/bin/python -m pytest -q                 # 25 passed
./.venv/bin/python -m ruff check app tests      # All checks passed
# apply the tag backfill to the running dev DB (idempotent, tags only where empty)
docker compose -f ../infra/docker-compose.yml exec -T backend python -m app.seed_products
./.venv/bin/python tests/api_smoke.py           # 63 routes/checks, 0 failed
```

Live evidence gathered here (stack already up):

- `GET /products` → 20/20 products now carry tags.
- `GET /search?q=کتان` → `total=3` (شورت کتان پیلی‌دار هلیا، شورت کتان بغل‌چاک
  آرمیتا، ست کراپ و شورت شنی).
- `GET /search?q=زمستانی` → `total=1` (جوراب پشمی گرم زمستان) — a pure tag hit
  that returned **0** before this change.
- `GET /search/suggest?q=کتا` → first suggestion `{kind: "tag", label: "کتان"}`.
- Browser: `/shop?q=کتان` renders «۳ نتیجه برای «کتان»» with three product cards.

## What is NOT done / open

- **No DB-backed pytest test.** The repo still has no pytest DB fixture (open
  item under B3.5), and `search_products` is pure SQL, so tag matching is covered
  by the two new live checks in `tests/api_smoke.py` instead of a unit test. A
  string-assertion unit test on the SQL was deliberately avoided as brittle.
- Tag matching uses `ILIKE %q%` (contains, like the rest of the matcher); tags
  are **not** matched case-insensitively for Latin words beyond `ILIKE`, and there
  is no tag facet/count endpoint for the UI yet (the frontend still shows no tag
  filter chips — that is F3.3).
- `infra/initdb/02-public-schema.sql` was left as-is: a fresh database seeds
  products without tags and the `db-init` job's `seed_products` step backfills
  them in the same `compose up`, which is exactly what the new conflict clause is
  for.
- Tag vocabulary is hand-assigned in the seed, not derived from product text;
  admins can change tags per product through `PATCH /products/{id}`.
