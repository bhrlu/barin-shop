# Audit — F5.14 Admin coupon create / edit / toggle fail with 422 (2026-09-22)

## Task

`F5.14` (P1, Batch D) from `plan/MASTER-BACKLOG.md`, discovered during B2.1's
browser regression sweep: every coupon create, edit and «فعال» toggle on
`/admin/coupons` was rejected with 422.

## Spec check (Rule 0)

- `[FE-07]` coupon manager / `[BE-02]` / `[BE-06]` — the feature this restores;
  no UI or contract change, so nothing else in the spec applies.
- Stack header (Supabase/`createServerFn`) — ignored, stale (Rule 0.2).

## Root cause

`api.adminCreateCoupon` and `api.adminUpdateCoupon` passed
`body: JSON.stringify(…)`. `request()` in `src/lib/api.ts` sets
`Content-Type: application/json` only on its `json:` path, so these two calls went
out as `text/plain;charset=UTF-8`. FastAPI 0.141 does not parse a non-JSON body
into the `CouponCreate` / `CouponUpdate` model and answered 422
(`model_attributes_type`, «Input should be a valid dictionary…»). Confirmed with
curl before the fix: the identical body is 200 as `application/json`, 422 as
`text/plain`. They were the only two raw-`body:` JSON calls in `src/`.

## Recon (Rule 6) / contract (Rule 8) / security (Rule 9)

- Owning module: `src/lib/api.ts` (the canonical HTTP layer, R7); consumers are
  `admin.coupons.tsx` (toggle mutation + create/edit dialog) only.
- Contract unchanged: same paths, same payload fields, same responses
  (`POST /coupons` 201 `CouponOut`, `PATCH /coupons/{id}` 200 `{ok}`, 409 on a
  duplicate code). `request()` itself untouched.
- Auth unchanged (`StaffCoupons`; the bearer header is added by `request()` as before).

## What was done

`src/lib/api.ts`: both methods now call `request(…, { method, json: payload })`.
Two lines.

## Files changed

- `vogue-vintage-vibes/src/lib/api.ts`
- docs: this audit, `plan/frontend-tasks.md`, `plan/MASTER-BACKLOG.md`,
  `plan/session-log.md`

## How to verify

```bash
cd infra && docker compose exec frontend sh -c 'bunx tsc --noEmit && bun run lint && bun run build'
# browser: /admin/coupons as admin@sande.local → «کد جدید» → save; toggle «فعال»;
# «ویرایش» → change the percent → save; «حذف»
```

## Verification results

| Check | Result |
|---|---|
| Before the fix (B2.1 sweep + curl) | toggle → `PATCH 422`; same body as JSON → 200 |
| Headless Chromium, `/admin/coupons` as admin | **14/14**: create (15 %, 5 uses, expiry) → toast + persisted; every write sent as `application/json` (POST 201, PATCH 200 ×4, duplicate POST 409); toggle off → toast + persisted + switch UI off; toggle back on; edit percent → 20 persisted; duplicate code → Persian error in the dialog (no raw 422 dump); neither percent nor amount → client error; delete removes it; no page errors; no 5xx |
| `prettier --check` / `tsc --noEmit` / `bun run lint` / `bun run build` | clean / clean / 0 errors (15 pre-existing warnings) / OK |

Backend untouched, so pytest/smoke were not re-run for this task.

**Verification level: browser tested.**

## Discovered (recorded, not fixed)

- **F5.16** (`NEW-F514-1`, P2) — the edit dialog cannot *clear* a field: it sends
  `null` for an emptied expiry / total cap / the other discount kind, and
  `PATCH /coupons/{id}` treats `null` as "unchanged". Observed in the browser:
  clearing the expiry and saving left `expires_at = 2030-01-31`. Clearing
  `max_uses` has no API encoding at all, so the fix spans the dialog and the
  PATCH semantics.

## What is NOT done / open

- F5.16 above (payload/PATCH semantics were explicitly out of F5.14's scope).
- F5.9 (the discount-cap field in the dialog) is still open.
- `FEATURES.md` §۴.۱۰ already describes the coupon manager as working; left as is.
