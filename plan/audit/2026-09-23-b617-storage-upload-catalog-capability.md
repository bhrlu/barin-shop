# Audit — B6.17 Storage upload refuses order_manager (2026-09-23)

## Task

`B6.17` (P2, Batch C), discovered during AB-FE-04 (`NEW-ABFE04-1`).

`POST /storage/upload-url` depended on `AdminUser`, and `AuthUser.is_admin` covers
`admin`/`super_admin` only. **order_manager** holds the `catalog` capability and has
created and edited products since B5.4b, yet it got 403 when adding an image. The
gallery then showed the backend's English «Admin role required». The `require_admin`
docstring ("any staff role passes") was also wrong. Part of the "continue the whole
backlog" run.

## Spec check (Rule 0)

`[BE-04]`: role checks are per route, from the DB-backed role set, which is what
`require_staff(capability)` does. The spec has no separate storage rule. The stack
header (Supabase Storage) is ignored; storage is MinIO.

## Recon / contract (Rules 6–9)

- **Consumers:** `AdminUser` had exactly one consumer, `routers/storage.py`
  (`create_upload_url`). `require_admin` has no other use.
- **Canonical guard (R7):** `StaffCatalog = require_staff("catalog")`, the same guard
  as product create/update/delete and variant CRUD. Anything that may edit a product
  may therefore add its images, and nothing else may.
- **Contract:** request and response unchanged. Status codes:
  - 401 when anonymous;
  - 403 for customer and support, now with the Persian `require_staff` message
    «دسترسی لازم برای این بخش را ندارید» instead of English;
  - 200 for order_manager (newly), admin and super_admin.

  `POST /storage/sign` stays `CurrentUser`: any signed-in user may read images.
- **Security (R9):**
  - no role gains more than it already had on products;
  - support stays refused;
  - roles come from `user_roles`, not the token claim. The tests mint every token
    with the claim `"customer"` and grant roles only in the DB.

## What was done

- `routers/storage.py`: `create_upload_url(..., user: StaffCatalog)`, with a comment
  giving the reason.
- `auth.py`: the `require_admin` docstring now states the truth (admin/super_admin
  only) and points staff routes at `require_staff(<capability>)`.
- `tests/test_storage_access.py` (new, 8 tests, fake MinIO client):
  - per-role `upload-url`: customer 403, support 403, order_manager 200, admin 200,
    super_admin 200, with the Persian message on refusal;
  - anonymous 401;
  - `/storage/sign` still open to a customer;
  - **the upload guard equals the product-edit guard** for four role sets
    (`PATCH /products/<missing>`: 404 means passed, 403 means refused).
- `tests/api_smoke.py`: `upload-url` as order_manager → 200 and as support → 403.

## Files changed

- `backend/app/routers/storage.py`, `backend/app/auth.py`
- `backend/tests/test_storage_access.py` (new), `backend/tests/api_smoke.py`
- docs: `backend/README.md` (storage row), this audit, `plan/MASTER-BACKLOG.md`,
  `plan/backend-tasks.md`, `plan/session-log.md`, `plan/README.md`

## How to verify

- `pytest tests/test_storage_access.py`: 8 passed. **Negative control** with `HEAD`'s
  `storage.py`: 4 fail.
  - order_manager 403;
  - customer and support refused with the English message;
  - upload guard ≠ product-edit guard.
- Full gates:
  - `pytest -q` 216 passed;
  - `ruff check app tests` clean;
  - `tests/api_smoke.py` 235/0, including the two new checks.
- **Browser** (real MinIO), signed in as **order_manager**: create a product, open
  the gallery and upload a PNG.
  - `upload-url` 200, and the tile joins with no error tile;
  - save → 200;
  - the stored ref is in MinIO with its 135 bytes;
  - no page errors.

  5/5 checks.

No DDL, infra or seed change, so a clean environment is not required (R14).

**Verification level:** integration tested + browser tested.

## What is NOT done / open

- **No server-side upload limits.** The presigned PUT still signs no size or content
  type. That is **B6.18** (next in that area).
- **`AdminUser` / `require_admin` unused.** Both are kept (R12) and documented.
  Removing them is a separate clean-up if wanted.
- `infra/README.md`, frontend docs: untouched. No frontend change was needed: the
  gallery already shows the server's message, and the upload now succeeds.
