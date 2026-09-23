# Audit — B6.18 Presigned image upload has no server-side size/type limit (2026-09-24)

## Task

`B6.18` (P3, Batch C), discovered during AB-FE-04 (`NEW-ABFE04-2`). The current
execution pointer of `plan/MASTER-BACKLOG.md` (§16).

The gallery's «≤ 5 MB, JPG/PNG/WEBP/GIF/AVIF» rule lived in the browser only.
`POST /storage/upload-url` returned a presigned **PUT** URL — and a V4 query-signed
PUT signs neither a length nor a content type. AB-FE-04 measured it: 200 kB of
random bytes sent as `text/plain` to a valid upload URL → 200. Anyone holding a
ticket could therefore store an object of any size and any type, for an hour.

## Spec check (Rule 0)

- **[FE-04] / §B3 image gallery** (`design/SANDE_FULL_DEV_SPEC.md` line 290):
  "storage bucket `product-images`", "Technical: … **direct bucket upload**". The
  spec has no upload-limit rule; the ≤ 5 MB / image-only rule comes from the
  gallery (`FEATURES.md` ۴.۳). Enforcement now lives in the ticket, so the upload
  stays **direct to the bucket** — the spec sentence is honoured, not contradicted.
- **Ignored (stale):** the spec's stack header (Supabase Storage) — storage is
  MinIO; no Supabase/RLS wording applies (`AGENTS.md`).
- No frozen status string, money rule or cart invariant is touched (Rule 4).

## Recon / contract (Rules 6–9)

- **Owning module:** `backend/app/routers/storage.py` (`create_upload_url`), the
  only producer of upload tickets.
- **Data flow:** `ProductImageManager.addFiles` → `api.uploadImage` (the sole
  consumer of `POST /storage/upload-url`) → MinIO bucket `product-images`; the
  returned path is appended to the product's `images` and later signed by
  `POST /storage/sign` (unchanged).
- **Auth dependency:** `StaffCatalog` (`require_staff("catalog")`) — unchanged from
  B6.17, so only admin/super_admin/order_manager can get a ticket.
- **Consumers grepped (R6/R7):** `upload_url` and `public_url_template` had exactly
  one consumer each — `src/lib/api.ts` (and nothing consumes
  `public_url_template`). The test fakes in `test_storage_access.py` and
  `test_catalog_errors.py` were the only other `presigned_put_object` callers.
- **Contract (R8)** — the shape changes because the mechanism does:

  | | before | after |
  |---|---|---|
  | request | `{filename, content_type}` | same |
  | 200 body | `{path, upload_url, public_url_template}` | `{path, upload_url, fields, max_bytes}` |
  | `upload_url` | presigned **PUT** URL for that key | the **bucket URL** the multipart POST goes to |
  | upload | `PUT` raw body to `upload_url` | `POST multipart/form-data` with every `fields` entry, then the `file` part last |

  Errors: anonymous 401, non-catalog 403 (unchanged); **new** 422 for a
  non-`image/*` request `content_type` (the extension check was already there).
  `public_url_template` was dropped — it was the same string as the new POST
  target and had no consumer; `max_bytes` replaces it as the useful field.
- **Security (R9):** the limits travel inside the base64 policy that MinIO
  verifies, so nothing in the browser can widen them. The policy pins the object
  key too, so a holder cannot write outside their own `uploads/<uuid>.<ext>` path.
  Roles still come from `user_roles`, not the token claim.
- **Sibling already solving this (R7):** none — `presigned_put_object` was the only
  presign in the repo; no second upload helper is introduced.

## What was done

**`backend/app/routers/storage.py`** — `create_upload_url` now signs a
`minio.datatypes.PostPolicy` instead of a PUT URL:

```python
policy.add_equals_condition("key", path)                        # pin the object key
policy.add_content_length_range_condition(1, MAX_IMAGE_BYTES)    # ≤ 5 MB
policy.add_starts_with_condition("Content-Type", "image/")       # image only
fields = client.presigned_post_policy(policy)
fields["key"] = path                 # minio-py signs the policy but omits `key`
fields["Content-Type"] = body.content_type
```

`MAX_IMAGE_BYTES = 5 * 1024 * 1024`, `ALLOWED_EXTENSIONS` (the former inline set),
and a 422 when `content_type` does not start with `image/`. The client is still
pointed at `MINIO_PUBLIC_ENDPOINT` with an explicit region, so signing stays local
(no `GetBucketLocation` round-trip) — the AB-FE-04/K8s-era fix is preserved.

**`vogue-vintage-vibes/src/lib/api.ts`** — `uploadImage` builds a `FormData` (all
signed `fields`, then `file` last), POSTs it with the same `XMLHttpRequest` so the
progress callback (0–1) is unchanged, and maps MinIO's XML refusal to a Persian
message: `EntityTooLarge` → «حجم فایل بیشتر از حد مجاز (۵ مگابایت) است»,
`AccessDenied` → «نوع فایل مجاز نیست؛ فقط تصویر قابل آپلود است». New exported
`UploadTicket` type documents the shape.

**MinIO behaviour verified first, not assumed:** with a real MinIO, a `starts-with
$Content-Type` condition is checked against the **`Content-Type` form field**, not
the file part's own header (a form without that field is refused even when the file
part is `image/png`). That is why the API puts `Content-Type` into `fields`.

## Files changed

- `backend/app/routers/storage.py`
- `vogue-vintage-vibes/src/lib/api.ts`
- `backend/tests/test_storage_access.py` (fake signs the policy for real)
- `backend/tests/test_catalog_errors.py` (fake updated to `presigned_post_policy`)
- `backend/tests/api_smoke.py` (+3 policy checks)
- docs: this audit, `plan/backend-tasks.md`, `plan/MASTER-BACKLOG.md`,
  `plan/session-log.md`, `plan/README.md`, `backend/README.md`,
  `vogue-vintage-vibes/FEATURES.md`, `vogue-vintage-vibes/DESIGN_SYSTEM.md`

## How to verify

```
cd backend
./.venv/bin/python -m pytest -q                  # 348 passed (4 new cases)
./.venv/bin/python -m ruff check app tests       # clean
./.venv/bin/python tests/api_smoke.py            # 257 checks, 0 failed
```

**Negative control** (Rule 13): with `HEAD`'s router restored and the fake extended
with both methods, 3 of the new tests fail — `KeyError: 'fields'` (no policy at
all) and `200 == 422` for a `text/plain` request, i.e. the old path accepted a
non-image declaration.

**New tests** (`tests/test_storage_access.py`): the decoded policy must contain
`["eq", "$key", <path>]`, `["content-length-range", 1, 5242880]` and
`["starts-with", "$Content-Type", "image/"]`; `fields` must carry `key` and
`Content-Type`; `max_bytes` = 5 MB; plus 3 parametrized 422 cases (`a.svg`,
`text/plain`, empty type). `test_catalog_errors.py` still proves a real bug (the
injected `AttributeError`) surfaces as a 500 rather than a masked 502.

**Live, against the running stack (real Postgres + real MinIO, no fakes)** — the
backend hot-reloads the bind-mounted `app/`, so the container served the new code:

```
1 upload via POST policy: 204 | ACAO: http://localhost:5173 | http://localhost:9000/product-images
  stored: 408 bytes, image/png | local file: 408 bytes | max_bytes: 5242880
  public GET: 200
2 oversized 5MB+1: 400 | <Code>EntityTooLarge</Code>
3 tampered form type: 403 | <Code>AccessDenied</Code>
4 tampered key: 403 | <Code>AccessDenied</Code>
5 API text/plain request: 422 {'detail': 'فرمت تصویر مجاز نیست'}
```

Check 1 reproduces the **browser's exact request** (multipart `POST`, fields then
the file part, `Origin` header) and confirms the response is CORS-readable by the
XHR (`Access-Control-Allow-Origin` echoed) and that the bytes stored equal the
bytes sent. Checks 2–4 are the tamper paths: the size ceiling, the type condition
and the key pinning are all enforced by MinIO itself.

**Frontend:** `tsc --noEmit` reports no error in `src/lib/api.ts` (the only errors
are pre-existing ones in `admin.users.tsx` / `admin.orders.tsx` /
`AdminDataTable.tsx`, files this task does not touch); `bun run lint` → 0 errors
(14 pre-existing warnings). `bun run build` **could not run in this session**: the
installed Vite/rolldown needs `node:util.styleText` and the local Node is v20.9.0 —
a pre-existing environment limitation, not a code error.

**Verification level:** integration tested (real MinIO + real Postgres + smoke,
error paths included) with the browser request reproduced at the HTTP level. **Not
click-tested in a browser** — no Playwright/Chromium is available in this session,
so a gallery pass (as order_manager) remains the one unrun check.

No DDL, infra, seed or config change (Rule 14 does not apply).

## What is NOT done / open

- **Not browser-click tested.** The XHR path (progress reporting, error tile text)
  is unchanged apart from the method and body, and the exact wire request was
  exercised against real MinIO, but the gallery was not driven in a browser.
- **The bytes themselves are still not sniffed.** MinIO enforces the *declared*
  `Content-Type` (`image/*`) and the size; a ticket holder could store arbitrary
  bytes labelled `image/png`. Recorded as **B6.18a** (P3) — only worth doing if the
  upload surface opens beyond catalog staff.
- `plan/frontend-tasks.md` was left untouched: it tracks the F1 cut-over, has no
  open item for this backend contract, and F1.1c (which mentions
  `/storage/upload-url`) is already `[x]`. Same for `plan/feature-roadmap.md`
  (its gallery line states a capability, not a contract) and `infra/README.md`
  (the presign-host note it documents is unchanged).
- `public_url_template` removal: no consumer existed (grep), but it is a shape
  removal — noted here deliberately rather than silently.
