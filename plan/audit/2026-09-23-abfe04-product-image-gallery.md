# Audit — AB-FE-04 Product image gallery manager (2026-09-23)

## Task

`AB-FE-04` (P2, Batch D). The product image gallery needs:

- drag/drop;
- preview;
- reorder;
- primary image;
- delete;
- progress;
- retry/error handling.

Canonical storage is `/storage/upload-url` + `/storage/sign` → MinIO. Verification:
a real upload/reorder/delete flow on the local Docker stack. Part of the "continue
the whole backlog" run.

## Spec check (Rule 0)

- **Followed:** the product-editor gallery in `[FE-02]`/`[FE-06]` (sortable gallery,
  primary image), and `B1` (Persian copy, RTL, tone tokens).
- **Not done here:** the spec's full two-column RHF/Zod editor is AB-FE-03, which
  depends on AB-BE-02.
- **Ignored:** the stack header (Supabase Storage); storage is MinIO through
  `/storage/*`.

## Recon / contract (Rules 6–9)

- **Owning module:** `components/admin/ProductImageManager.tsx`, used only by
  `admin.products.tsx`'s form (`value` = `form.images`, `onChange`).
- **Contract:** `images: string[]` on the product. `images[0]` is the primary (the
  storefront card's second image is `images[1]`). Refs are bundled asset keys,
  absolute URLs or `uploads/<uuid>.<ext>`. The component keeps `{value, onChange}`
  and adds only an optional `onBusyChange`, so the product payload is unchanged.
- **Upload path:** `api.uploadImage` → `POST /storage/upload-url` (presigned PUT,
  1 h) → `PUT` to MinIO. Previews use `resolveImageMap` → `POST /storage/sign`.
  Uploading does not touch the product row; the form's «ذخیره محصول» does.
- **Old behaviour found in recon:**
  - arrows, delete and URL entry worked;
  - there was no progress, retry, drop, drag-reorder or explicit primary action;
  - every reorder re-signed every image, so tiles flashed the wrong picture;
  - uploads were serial and appended with the `onChange`/`value` captured when the
    upload **started**, while the parent did `setForm({ ...form, images })`. **A
    field edited during an upload was reverted when the upload finished.** Mutation
    C below reproduces this.

## What was done

- **`src/lib/api.ts` — `uploadImage(file, onProgress?)`.** The MinIO `PUT` now goes
  through `XMLHttpRequest`, because `fetch` cannot report upload progress.
  `onProgress` gets 0–1. A network error surfaces as «ارتباط با فضای ذخیره‌سازی
  برقرار نشد». The presign call still goes through `request()`.
- **`ProductImageManager.tsx`:**
  - **Upload queue:** one file at a time, with a local object-URL preview, a
    progress bar (`role="progressbar"`, Persian percent) and a «در صف» state.
  - **Failed upload:** an error tile shows the server's message, with «تلاش دوباره»
    (retry) and «کنار گذاشتن» (dismiss).
  - **Validation before any request:** the backend's types (JPG/PNG/WEBP/GIF/AVIF)
    and ≤ 5 MB. The input's `accept` matches.
  - **Drop files** anywhere on the gallery (the drop zone is highlighted, «رها
    کنید»). **Drag tiles** to reorder. The arrows stay for keyboard and touch, and
    are disabled at the ends.
  - **★ button:** makes an image primary (moves it to index 0).
  - **Signed-URL cache:** only new refs are signed, so a reorder neither re-signs
    nor flashes. A just-uploaded file keeps its local preview. A failed preview
    shows «پیش‌نمایش در دسترس نیست».
  - **Latest value:** a finished upload appends to the latest `value`/`onChange`
    (a ref synced after each render).
  - **Busy state:** `onBusyChange(true)` while anything is queued or uploading.
  - Object URLs are revoked on unmount.
- **`admin.products.tsx`:**
  - `onChange` uses a functional `setForm(current => …)`;
  - «ذخیره محصول» is disabled and reads «در انتظار پایان آپلود تصاویر…» while images
    upload;
  - error tiles do not block saving.

## Files changed

- `vogue-vintage-vibes/src/components/admin/ProductImageManager.tsx`
- `vogue-vintage-vibes/src/lib/api.ts`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.products.tsx`
- docs:
  - `vogue-vintage-vibes/DESIGN_SYSTEM.md`, `vogue-vintage-vibes/FEATURES.md`;
  - this audit;
  - `plan/MASTER-BACKLOG.md` (+B6.17, +B6.18), `plan/backend-tasks.md`
    (+B6.17, +B6.18), `plan/session-log.md`, `plan/README.md`.

## How to verify

Browser script (Playwright on the Docker stack, real MinIO, admin): **25 checks,
0 failed**. A temporary product is created and then deleted.

1. The existing image is primary. Two picked PNGs upload in turn and join the
   gallery. An SVG is refused with a toast and never requested.
2. A 3 MB PNG over a throttled 4 Mbps uplink:
   - «ذخیره محصول» is disabled with the waiting text;
   - `aria-valuenow` moves through intermediate values;
   - the product **name typed during the upload survives**;
   - Save re-enables afterwards.
3. The first MinIO `PUT` is forced to 503: an error tile appears with «آپلود انجام
   نشد», it does not block saving, and «تلاش دوباره» uploads the file.
4. A file dropped via `DataTransfer` highlights the zone and uploads.
5. Save → `PATCH` 200. The stored `images` keep the old ref first, then the five
   uploads in order. **Each object exists in MinIO with its exact bytes**
   (135 / 136 / 3 001 298 / 136 / …), fetched through `/storage/sign`.
6. After reopening:
   - drag tile 4 onto tile 1 (it becomes primary);
   - ★ on tile 3;
   - delete tile 6;
   - «←» on tile 2;
   - the first tile's «→» is disabled.

   Save. The stored order equals the expected permutation exactly, and the name
   saved.
7. At 390 px the gallery fits with no page overflow (screenshot reviewed). No page
   errors.

Controls:

| Variant | Result |
| --- | --- |
| A — only the parent's old `setForm({ ...form, images })` | 25/25 pass (the latest-value ref protects on its own) |
| B — `onBusyChange` not wired | 1 fails: save is not blocked during the upload |
| C — the old behaviour: component uses the captured `onChange`/`value` **and** the parent is non-functional | 2 fail: the name typed during the upload is reverted, and the reverted name is what gets saved |
| D — captured closure in the component, functional parent | 25/25 pass (either fix alone prevents the loss) |

A plain `HEAD` swap is not a meaningful control: the old component has none of the
new structure, so the script stops at its first selector.

Gates (frontend container):

- `prettier --check` clean;
- `tsc --noEmit` clean;
- `bun run lint` 0 errors / **14** warnings, down from 16. Both removed warnings
  were `react-hooks/exhaustive-deps` in the old component's `[value.join("|")]`
  effect.
- `bun run build` OK.

No backend change.

**Verification level:** browser tested on the Docker stack (real MinIO).

## Found on the way (backend, not changed here — R12)

- **B6.17 (P2):** `POST /storage/upload-url` uses `AdminUser`, whose `is_admin`
  means admin/super_admin only. **order_manager**, who has the `catalog` capability
  and edits products since B5.4b, gets **403**, so the gallery cannot upload for
  that role. The tile would show the backend's English «Admin role required».
  Measured: order_manager `upload-url` 403, `PATCH /products/{id}` passes auth.
  Separately, the `require_admin` docstring says "any staff role passes", which is
  wrong.
- **B6.18 (P3):** the presigned `PUT` carries no size or content-type limit.
  Measured: 200 kB of random bytes sent as `text/plain` were accepted (200). The
  5 MB / image-type rule is client-side only. A presigned POST policy
  (`content-length-range`, `Content-Type` starts-with `image/`) would enforce it in
  MinIO.

## What is NOT done / open

- **Orphaned objects.** Removing an image, or abandoning an upload, does not delete
  the MinIO object. There is no delete endpoint, and a removed image may still be
  referenced by an unsaved form. A sweeper belongs with B2.5's background jobs; it is
  noted, not tracked separately.
- **No touch drag.** HTML5 drag-and-drop does not work on touch screens, so phones
  use the arrows and ★.
- **order_manager uploads.** They stay refused until B6.17.
- `README.md`, `feature-roadmap.md`: untouched.
