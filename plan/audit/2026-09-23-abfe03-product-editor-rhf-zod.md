# Audit — AB-FE-03 Two-column product editor + RHF/Zod + swatches (2026-09-23)

## Task

`AB-FE-03` (P2, Batch E; unblocked by AB-BE-02 and F5.18). Required:

- a two-column layout;
- React Hook Form and a Zod schema;
- product details;
- a variant matrix with SKU, colour swatch, size, quantity and price override;
- storage through the existing MinIO flow.

Verification: create/edit, validation, and values persisted in the backend.

Acceptance, per the full-audit definition:

- per-field Persian errors;
- Zod mirrors `app/schemas.py` without inventing constraints (R8);
- no request/response shape change;
- RTL two columns at ≥ 768 px, stacked below.

Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

**Followed** from `[FE-04]`:

- the editor's two columns (wide: title, category, description; narrow: pricing,
  visibility, badges);
- the size × colour matrix with colour name + hex swatch picker, stock and custom
  SKU;
- RHF + Zod.

Also `B1` (Persian, RTL, tone tokens) and `[B0]`'s mono identifiers for SKUs.

**Deliberately not followed:**

- **A slug field and a rich-text description.** The backend has no slug, and adding
  one is not in this task.
- **A dedicated editor route.** The editor stays inline on `/admin/products`.
- **"Direct bucket upload."** Uploads go through the existing `/storage/upload-url` →
  MinIO flow (AB-FE-04 / B6.17).
- **The stack header** (Supabase), as always.

## Recon / contract (Rules 6–8)

**The old editor** (`admin.products.tsx`, 621 lines):

- hand-rolled `FormState` with only HTML `required`;
- no per-field errors: a bad number went to the server as `NaN`/float and came back
  as a 422 toast;
- `parsePayload()` built `ProductWrite`;
- `BADGES` / `AVAILABILITIES` were also used by the list;
- `VariantEditor` covered size, colour, stock and active only.

**Contract kept.** `POST /products` and `PATCH /products/{id}` get the same
`ProductWrite`; the browser test asserts the payload keys equal the old form's. The
variant API was extended in AB-BE-02 (`sku`, `price_override`, `color_hex`; `""`/`0`
clear), and F5.18 made the storefront show overrides, so exposing the price field is
now safe.

**Zod mirrors the backend:**

| Field | Rule |
| --- | --- |
| `name` | 1–200 |
| `category` | 1–40 |
| `price` | int > 0 |
| `old_price` | int > 0 or empty → `null` |
| `stock` | int ≥ 0 |
| `low_stock_threshold` | int ≥ 0; empty → 0, as before |
| `badge` / `availability` | enums |
| variant `size` | ≤ 40 |
| variant `color` | ≤ 60 |
| variant `sku` | ≤ 80 |
| variant `price_override` | > 0 or empty |
| variant `color_hex` | `#rrggbb` or empty |

Nothing stricter was invented. Numbers are typed as text, and Persian and Arabic
digits are read as Latin, which is input normalisation, not a new rule. Size and
colour are trimmed, as the old `VariantEditor` did.

## What was done

- **`src/lib/product-form.ts` (new, no components, so no `react-refresh` warning):**
  - `BADGES`, `AVAILABILITIES`, `toLatinDigits`, `wholeNumber`, `optionalPositive`;
  - `productSchema`, which transforms to the unchanged `ProductWrite`;
  - `emptyProductForm`, `productToForm`, `variantSchema`, `fieldErrors`.
- **`components/admin/ProductEditor.tsx` (new):**
  - `useForm<Input, unknown, ProductWrite>` with `zodResolver(productSchema)`;
  - shadcn `Form` / `FormField` / `FormMessage`: each message is linked to its field
    through `aria-describedby`;
  - two columns `md:grid-cols-[minmax(0,1fr)_300px]`;
  - the gallery (`ProductImageManager`) as the `images` field, and save blocked while
    it uploads (AB-FE-04);
  - `Switch` for «نمایش در فروشگاه» / «محصول جدید»;
  - `VariantEditor` shown when editing.
  - **Validation timing:** on submit, then on change. `onTouched` was tried first,
    and the browser test caught a lost click: blurring a field showed its message,
    which moved «ذخیره محصول» away before `mouseup`.
- **`components/admin/VariantEditor.tsx` (rewritten on the same structure):**
  - per row and in the add form: size, colour + round swatch (native colour picker;
    choosing one of the product's colours pre-fills its hex; «×» clears), SKU (mono,
    LTR), stock, price override (placeholder = the product price), active;
  - `variantSchema.safeParse` with inline Persian errors, and no request while
    invalid;
  - a row save sends every field, with `""`/`0` as the clear values;
  - a duplicate SKU shows the server's 409 message.
- **`routes/_authenticated/admin.products.tsx`:** the list keeps its filters, pager
  and row actions. «محصول جدید» and «ویرایش» open `ProductEditor`. The ~350-line
  inline form, its state and its helpers were removed (they moved, not copied — R7).
- **`components/ui/form.tsx`:** `FormField` gains React Hook Form's
  `TTransformedValues` generic, as current upstream shadcn has, so a transforming
  resolver type-checks. The only other change is to its types.

## Files changed

- `vogue-vintage-vibes/src/lib/product-form.ts` (new)
- `vogue-vintage-vibes/src/components/admin/ProductEditor.tsx` (new)
- `vogue-vintage-vibes/src/components/admin/VariantEditor.tsx`
- `vogue-vintage-vibes/src/routes/_authenticated/admin.products.tsx`
- `vogue-vintage-vibes/src/components/ui/form.tsx`
- docs:
  - `vogue-vintage-vibes/DESIGN_SYSTEM.md` (deps row, components, forms convention,
    FE-04 row);
  - `vogue-vintage-vibes/FEATURES.md` (۴.۲);
  - this audit;
  - `plan/MASTER-BACKLOG.md`, `plan/session-log.md`, `plan/README.md`.

## How to verify

Browser script (Playwright, Docker stack, admin): **29 checks, 0 failed**.

1. **Layout.** At 1366 px the narrow column sits left of the wide one on the same row
   (RTL). At 767 px it stacks under it.
2. **Validation.**
   - A submit with an empty name, price `abc`, stock `-1` and old price `0` shows the
     four Persian messages, each linked to its own field through
     `aria-describedby`.
   - Price `0` then updates live to «باید بیشتر از صفر باشد».
   - **No product request** is sent while the form is invalid.
3. **Create.** Every field is filled, including price «۱۲۰۰۰۰» in Persian digits, an
   empty threshold, `coming_soon` + date, badge, both switches off, and an image
   uploaded through the RHF field. Result: 201.
   - The **payload keys equal the old form's**.
   - GET shows price 120 000, old 150 000, stock 12, threshold 0, category, badge,
     availability + date, active/is_new false, sizes, colours, tags, material,
     description, and 2 images.
4. **Edit.** The form is pre-filled. Change the price, clear the old price and set
   `in_stock`: 200, old price `null`, and the date cleared.
5. **Variant matrix.**
   - Choosing a product colour pre-fills the swatch.
   - Picker `#aa3300`, SKU, stock 7, and price override `0` → inline error with
     **nothing sent**; «۹۰۰۰۰» → created.
   - GET shows the SKU, swatch, stock and 90 000.
   - A duplicate SKU → the server's «این SKU قبلاً…» message.
   - A row with the price emptied, the swatch cleared and an 81-character SKU →
     inline error.
   - With the SKU emptied, save sends `price_override: 0, color_hex: "", sku: ""`,
     and all three become `null`.
6. **Mobile.** No page overflow at 390 px. Screenshots reviewed.
7. No page errors.

**Mutation controls:**

| Mutation | Result |
| --- | --- |
| M1 — no `zodResolver` | 12 fail: every message is missing and an invalid POST reaches the server (422) |
| M2 — a row clear sends `null` instead of `0` | 2 fail: the override is not cleared |

**Regression.** The gallery lives inside the new form. AB-FE-04's suite passes 25/25
(including "name typed during an upload survives" and the blocked save) and B6.17's
order_manager upload passes 5/5. Their selectors were updated to the new form: the
name by label and save by the editor form.

Gates (frontend container):

- `prettier` clean;
- `tsc --noEmit` clean;
- `bun run lint` 0 errors / 14 warnings (unchanged; `form.tsx`'s one warning was
  already in the baseline);
- `bun run build` OK.

No backend change.

**Verification level:** browser tested.

## What is NOT done / open

- **Product colours are still a text field** («نام #hex, …»), as before. Its RTL/LTR
  mix displays in a jumbled bidi order. Swatches were built for the variant matrix,
  where `[FE-04]` puts them. A swatch list for product colours is a possible
  follow-up; no task was added.
- **Not built:** a slug, a rich-text description, a dedicated editor route, and the
  optimistic `is_active` list toggle (`[FE-04]` list items).
- `README.md`, `feature-roadmap.md`: untouched.
