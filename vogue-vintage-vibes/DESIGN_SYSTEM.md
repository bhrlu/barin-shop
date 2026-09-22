# SÂNDÉ — Frontend Design System & Component Guide

Reference for building UI in `vogue-vintage-vibes/`. Describes the stack, design
tokens, component inventory, and the conventions to follow.

> **Two sources, one document.** This guide merges
> [`../design/SANDE_FULL_DEV_SPEC.md`](../design/SANDE_FULL_DEV_SPEC.md) (Sections
> B0–B5 — the design intent and the admin panel target) with what the repository
> actually does today. Where they disagree, **the repo wins** (working rule
> [`plan/RULES.md`](../plan/RULES.md) Rule 0.2) and §5 lists every conflict with the
> precedence, so a spec sentence is never followed into a stack this project left
> behind. Prose below marks the two kinds of statement explicitly:
>
> - **Now** — true of the current code; build new UI this way to match it.
> - **Target** — from the spec, applies to new work (mainly the admin panel); not
>   yet implemented, with the path to get there.

---

## 1. Stack

| Concern | Choice | Source |
|---|---|---|
| Framework | TanStack Start (Vite 8) + React 19, SSR via `src/server.ts` | repo |
| Routing | TanStack Router (file-based, `src/routes/`, generated `routeTree.gen.ts`) | repo |
| Data fetching | TanStack React Query (`QueryClientProvider` in `__root.tsx`) | repo |
| Backend | **FastAPI in `../backend` — the sole backend**, called through `src/lib/api.ts` with our own JWT | repo |
| Styling | Tailwind CSS **v4** (CSS-first `@theme`, no `tailwind.config.js`) | repo |
| Component kit | **shadcn/ui**, style `new-york`, base color `slate` (`components.json`) | repo |
| Primitives | Radix UI (`@radix-ui/react-*`) | repo |
| Variants | `class-variance-authority` (CVA) | repo |
| Icons | `lucide-react` | repo |
| Toasts | `sonner` (`<Toaster position="top-center" />`) | repo |
| Carousel | `embla-carousel-react` → `ui/carousel.tsx` | repo |
| Package manager | **Bun** (`bun.lock`, `bunfig.toml`) | repo |
| `@tanstack/react-table` v8 | **not installed** — target for the admin data grid ([FE-02]) | spec |
| `react-hook-form` + `zod` | installed; only the unused shadcn `ui/form.tsx` wrapper imports RHF, nothing imports `zod` — target | spec |
| `recharts` | used by the admin dashboard since F2.6 (area + donut, token-coloured) | repo |
| Supabase / Lovable Cloud / `createServerFn` | **not part of this project** | spec-only, see §5 |

- **Language / direction:** Persian, RTL. `<html lang="fa" dir="rtl">` in
  `routes/__root.tsx`. All copy is Persian; write new UI in Persian.
- **Path alias:** `@/` → `src/` (injected by `@lovable.dev/vite-tanstack-config`,
  do **not** add plugins to `vite.config.ts` manually).

---

## 2. Design tokens

Defined entirely in `src/styles.css`. **All colors must be `oklch`.**

### 2.1 Brand palette (terracotta & sage)

| Token | Utility | Light value | Use |
|---|---|---|---|
| `--sand` | `bg-sand` | `oklch(0.938 0.018 68)` | section backgrounds, inputs, editorial bento panels |
| `--clay` | `bg-clay` | `oklch(0.885 0.03 62)` | image placeholders, shimmer skeletons |
| `--terracotta` | `text/bg-terracotta` | `oklch(0.585 0.115 34)` | brand primary, links, accents |
| `--terracotta-soft` | `bg-terracotta-soft` | `oklch(0.79 0.085 52)` | soft accents |
| `--apricot` | `bg-apricot` | `oklch(0.845 0.07 62)` | gradients |
| `--sage` | `bg-sage` | `oklch(0.7 0.055 138)` | `accent` |
| `--sage-deep` | `text-sage-deep` | `oklch(0.45 0.055 140)` | eyebrow text, step-done, positive badges |
| `--gold` | `text-gold` | `oklch(0.76 0.105 88)` | highlights / chart |

### 2.2 Semantic tokens

Registered in `@theme inline` so they become utilities (`bg-primary`,
`text-muted-foreground`, …): `background, foreground, card, popover, primary,
secondary, muted, accent, destructive, border, input, ring`, `chart-1..5`,
`sidebar*`.

Key mappings: `--primary` = terracotta, `--secondary`/`--muted` = sand,
`--accent` = sage, `--border`/`--input` = `oklch(0.885 0.022 62)`.

### 2.3 Status semantics (**target**, spec B0.2 + B4.2)

The spec asks for a red/amber/green reading of state («Delivered = success»,
«Pending = warning», «Cancelled = danger»). **Now** every order/payment chip is the
same colour (`bg-terracotta/10 text-terracotta` for the order status, `bg-sand` for
payment — see `account.orders.tsx`), so state is only in the text. The mapping below
expresses the spec's *meaning* through the tokens this project already has, which is
also what the spec's own B1.1 invariant demands («never hardcode colors» — its B0.2
table writes `bg-emerald-50 …`, which its B4.2 snippet then hardcodes; that is the
one place the spec contradicts itself).

| Meaning | Class recipe | Statuses |
|---|---|---|
| Positive | `border-sage/40 bg-sage/20 text-sage-deep` | `delivered`, `paid`, refund `approved`, `refunded` |
| In progress | `border-gold/50 bg-gold/15 text-foreground` | `processing`, `shipped` |
| Waiting | `border-border bg-sand text-foreground` | `pending`, `unpaid` |
| Negative | `border-destructive/30 bg-destructive/10 text-destructive` | `cancelled`, refund `rejected`, out of stock |
| Commerce / meta | `border-terracotta/30 bg-terracotta/10 text-terracotta` | special-offer badge, «موجودی کم», refunds pending review |

Rule of thumb: `terracotta` stays the **brand/CTA** colour (buttons, links, discount
accents) and is *not* used for negative state — `destructive` is. Badges are pills:
`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium`.
If literal green/amber/rose is ever wanted, add `--status-success`,
`--status-warning`, `--status-danger` to `styles.css` first (§2.8) — never inline
Tailwind palette classes.

### 2.4 Radii

`--radius: 0.25rem` → `rounded-sm|md|lg|xl|2xl|3xl|4xl` derived.

- **Now:** editorial surfaces use large custom radii (`rounded-3xl`,
  `rounded-[1.25rem]`); buttons and inputs are deliberately square (`rounded-none`)
  on the storefront (checkout, cart, product page, contact).
- **Target (spec B0.4):** data widgets — tables, cards, sheets — use
  `rounded-xl`/`rounded-2xl`, and **never** `rounded-none` on an admin data widget.
  The square-corner storefront language is grandfathered; don't extend it to the
  admin panel.

### 2.5 Typography

| Token | Stack | Use |
|---|---|---|
| `--font-display` | Cormorant Garamond → Vazirmatn → serif | headings, logo (`font-display`) |
| `--font-sans` | Vazirmatn → Karla → system | body (default) |
| `--font-latin` | Karla → Vazirmatn | Latin-only runs |

Fonts loaded via Google Fonts `<link>` in `__root.tsx`.

- **Target (spec B0.3):** `font-serif` for brand/modal titles and big KPI figures
  (now: `font-display`), `font-sans` for data, and **`font-mono tracking-wider` for
  identifiers** — order numbers, SKUs, tracking codes, Sheba numbers. There is **no
  mono token yet** (`styles.css` defines only the three above), so add
  `--font-mono` in `:root` + `@theme inline` before using `font-mono`; today order
  numbers and references render in the body font.

### 2.6 Spacing, borders, elevation (**target**, spec B0.4)

| Concern | Rule |
|---|---|
| Padding | compact widgets `p-4` · standard cards `p-6` · modals/drawers `p-6`–`p-8` |
| Borders | `border-border/60` for separators in dense UI; full `border-border` on editorial cards |
| Elevation | cards `shadow-sm border border-border/60`; floating layers `shadow-lg border border-border/80`; the brand `shadow-soft` for editorial surfaces |
| Table rows | `h-14`/`h-16` with `hover:bg-muted/40` |

No harsh black shadows; elevation comes from the terracotta-tinted `shadow-soft`
(§2.9) on the storefront.

### 2.7 Micro-interactions & feedback (**target**, spec B0.5)

- Transitions: `transition-all duration-200 ease-out` (now: mostly
  `transition-colors`, which is fine for chips/links).
- Loading is **shimmering skeletons, never spinners** — `bg-clay animate-pulse` is
  this project's skeleton token (spec writes `bg-muted`; both are semantic, the repo
  one is warmer — use `bg-clay`).
- Toast position **conflicts**: the spec says bottom-left, the app mounts
  `<Toaster position="top-center" />`. The running app wins (§5); don't move it in a
  feature task.
- Mutations always report through `toast.success` / `toast.error` (sonner).

### 2.8 Adding a new semantic color

Per the comment at the top of `styles.css`:
1. Add the variable to `:root` (light) **and** `.dark` (dark).
2. Register it in `@theme inline` as `--color-<name>: var(--<name>)`.

### 2.9 Brand utilities (custom `@utility`)

| Utility | Effect |
|---|---|
| `surface-warm` | terracotta→apricot gradient background, primary-foreground text |
| `surface-courtyard` | sand→sage gradient background |
| `shadow-soft` | soft terracotta-tinted drop shadow |
| `rule-terracotta` | terracotta-tinted border color |

---

## 3. Component inventory

### 3.1 Application components (`src/components/`)

| Component | Notes |
|---|---|
| `SiteHeader.tsx` | Sticky header, `surface-warm` top rule, mobile drawer, cart badge, and the `<HeaderSearch />` trigger. |
| `HeaderSearch.tsx` | Popover search: debounced (`GET /search/suggest`) suggestions grouped by kind (product / category / tag / previous query), product thumbnails, signed-in recent searches with per-entry delete + clear-all, ArrowUp/Down + Enter navigation. Submits to `/shop?q=…`. |
| `SiteFooter.tsx` | Category links via `search={{ category }}`. |
| `ProductCard.tsx` | Two-image hover swap, `isNew` badge, price + struck `oldPrice`, rating (`avgRating`/`reviewCount`) and a compare toggle. Root is a wrapper `<div>` with the product `<Link>` inside it, so the toggle is never a button nested in an anchor. Typed against `@/data/products`. |
| `CompareBar.tsx` | Sticky bar above the footer showing the comparison basket (count, clear, link to `/compare`); hidden while empty. Rendered once from `__root.tsx`. |
| `CancelOrderButton.tsx` | Mutation calling `api.cancelOrder`. |
| `admin/ProductImageManager.tsx` | Upload (`api.uploadImage`) + URL entry + reorder + primary-image badge. |
| `admin/VariantEditor.tsx` | Per-product size × colour stock CRUD (`/products/{id}/variants`, `/variants/{id}`): datalist-backed size/colour inputs, per-row save (never on-blur) and delete; invalidates the admin list, the storefront variant query, the catalog and the inventory queries. |
| `product/VariantPicker.tsx` | Size × colour selection with per-combination availability (disabled sold-out/deactivated combos, disabled colours) and an `aria-live` stock line. Uses `@/lib/variants` — never re-implement the rule. |
| `product/ReviewsSection.tsx` | Rating summary + 1–5 distribution, review list (seller replies, Jalali dates), star-input write/edit form; one review per customer per product (backend upserts). |
| `product/ProductRail.tsx` | RTL embla carousel rail (`ui/carousel`, `direction: "rtl"`) with header arrow buttons tracking `canScrollPrev/Next`; used for related, recommended and recently-viewed products. |
| `product/RecentlyViewedRail.tsx` | `ProductRail` fed by `recentlyViewedQuery`; hidden for guests and while the list is empty (home + shop). |

Supporting `src/lib` modules that carry UI rules: `format.ts` (`toFa`,
`formatToman`, `formatFaDate`, `formatFaDateTime`), `variants.ts` (the backend's combo rule), `compare.tsx`
(localStorage basket), `cart.tsx` (localStorage cart), **`stock-issues.ts`** (the one
copy of the Persian copy per rejected-line reason — cart line note vs checkout toast).

### 3.2 shadcn/ui primitives (`src/components/ui/`)

48 files, "new-york" style. Notable ones:
`button, input, textarea, label, select, checkbox, radio-group, switch, slider,
form, dialog, alert-dialog, sheet, drawer, popover, tooltip, hover-card,
dropdown-menu, context-menu, menubar, navigation-menu, command, tabs, accordion,
collapsible, card, badge, avatar, table, pagination, breadcrumb, progress,
separator, skeleton, toggle, toggle-group, alert, calendar, input-otp,
aspect-ratio, scroll-area, resizable, carousel, chart, sidebar, sonner`.

`Button` variants: `default | destructive | outline | secondary | ghost | link`;
sizes: `default | sm | lg | icon`. `asChild` supported via Radix `Slot`.

### 3.3 Admin panel: spec target vs today (**target**, spec B2 + B3)

The spec describes a sidebar-shell back-office. The shell itself now matches it
(F4.2: `admin.tsx` renders the right `w-64` sidebar + topbar, with per-role tab
gating from B5.4); the remaining rows below track the individual screens.
Mapping:

| Spec module | Spec target | Today |
|---|---|---|
| [FE-01] `admin/AdminLayout.tsx` | `w-64` right sidebar, 18px lucide icons, terracotta active edge, topbar with `Cmd+K` search + avatar/role/logout | **exists** (`admin.tsx`, F4.2): sticky topbar (h-16, blur) with quick search → `/shop?q=`, role badge («مدیر ارشد» / «مدیر» / «مدیر سفارش‌ها» / «پشتیبانی») + logout; right sidebar in a rounded card (desktop) / right-side Sheet (mobile); 18px lucide icons, active `bg-terracotta/10`, per-tab badges fed by `/admin/kpis`; navigation is **role-gated** per `ROLE_TAB_KEYS` (mirrors backend `ROLE_CAPABILITIES`, B5.4). Spec's breadcrumb header and avatar are not built |
| [FE-02] `admin/AdminDataTable.tsx` | `@tanstack/react-table` v8, server-side pagination/sort/filter, bulk-action bar, CSV/Excel export | **missing** (no react-table installed, no pagination — F2.5) |
| [FE-03] `admin.index.tsx` | 4 KPI cards with MoM deltas, weekly sales area chart, order-status donut, urgent-actions callout | **exists** (F2.6 + B5.2): 4 KPI cards with period-over-period delta badges, terracotta revenue area chart, status donut with legend, amber urgent-actions callout, range selector (امروز/۷/۳۰/همه); latest orders kept via `adminStats` |
| [FE-04] `admin.products.tsx` | Stock colour alerts (>10 / 1–9 / 0), `is_active` toggle with optimistic update, size×colour matrix generator, image manager | product CRUD + merchandising fields + `VariantEditor` (F3.6); no optimistic toggle, no dedicated editor route |
| [FE-05] `admin.orders.tsx` + `OrderDetailSheet.tsx` | `Sheet side="left"` detail, 4-step stepper, postal tracking input, **print stylesheet invoice**, copy-address | **exists** (`admin.orders.tsx` + `components/admin/OrderDetailDrawer.tsx`, F4.4): per-row «مشاهده و پردازش» opens the left Sheet with the 4-step stepper (terracotta circles + advance button), receiver box with copy + method, itemised breakdown with signed thumbnails + totals, tracking input, cancel action, and «چاپ فاکتور رسمی» → portalled A4 invoice via the global print block; the list keeps selects + tracking (F2.8) |
| [FE-06] `admin.refunds.tsx` + `RefundActionDialog.tsx` | Tabs (pending/settled/all), claim cards with Sheba + copy, approve/reject dialog with bank tracking code | **exists** (`admin.refunds.tsx`, F2.4 + B5.3): the three tabs, terracotta-edge quote cards with claimant info, approve/reject/settle dialog where settlement requires the Paya/Satna bank code (backend-enforced); settled cards show the code + date. No Sheba column exists |
| [FE-07] `admin.coupons.tsx` | Ticket-styled coupon cards, usage progress bar, Jalali date pickers | **missing** — coupon CRUD exists in the API |
| [FE-08] `admin.users.tsx` | Avatar + tier badge, drawer tabs (orders/addresses/favorites), LTV, role change with confirmation | flat list with roles, order count, spend |

New admin work should follow the spec's *look* (B0 tokens, §2.6 spacing, §2.3 status
semantics, skeleton/empty states) while using this repo's data layer and routes.

### 3.4 Storefront form patterns (contact · checkout address · address book)

These live inside routes rather than `src/components/`, but they are conventions
now — reuse them instead of inventing a variant:

| Pattern | Recipe |
|---|---|
| Form submit | Controlled state + `useMutation`, submit button `disabled={isPending}` and a pending label (`در حال ارسال…`); success → Sonner toast **plus** one line under the button (`text-xs text-muted-foreground`) that clears on the next keystroke. `contact.tsx` is the reference. |
| Client validation | Mirror the API limits as HTML attributes (`required`, `minLength`) so the 422 never happens, instead of validating in JS state. |
| Metadata chip (e.g. «پیش‌فرض» on an address) | `bg-sand px-2 py-0.5 text-[11px] text-terracotta` inline next to the title — sand surface, terracotta text, no border. |
| Selectable chips (saved-address picker, multi-select shop filters) | `border px-3 py-1.5 text-xs` + `aria-pressed`; active = `border-terracotta bg-background`, inactive = `border-border text-muted-foreground hover:text-foreground`. No filled/`bg-primary` active state on storefront chips. |
| Secondary inline action (e.g. «انتخاب به‌عنوان پیش‌فرض») | Bare `<button>` with a 3.5-size lucide icon + `text-xs`, `text-muted-foreground hover:text-foreground`; destructive replaces the hover colour with `hover:text-destructive`. |
| Optional boolean field | Unchecked native checkbox with `size-4 accent-primary` and a `text-xs text-muted-foreground` label — `ui/checkbox` is only used where a visual switch is wanted. |
| Pre-filling an uncontrolled form (checkout address) | Keep the FormData-based fields uncontrolled, wrap them in a `<div key={pickedAddressId ?? "new"}>` so switching the picked address **remounts** with new `defaultValue`s. Never mix `defaultValue` and `value` on the same input. |
| Inline edit of a list row (`account.addresses.tsx`) | One `editingId` state — the matching card renders a form instead of its summary, pre-filled from the row. Share the field set with the create form through one component and give it a `prefix` prop so both can be mounted at once without duplicate input ids. Save sends **only the editable fields**, never the row's status flags; cancel is a `ghost` button at `h-9 text-xs`. |
| Row actions | Text + 3.5-size lucide icon (`Star` set-default, `Pencil` edit) in a `gap-4` cluster under the row summary; the destructive `Trash2` stays top-trailing, icon-only, with an Iranian `aria-label` (`«حذف آدرس»`). |

---

## 4. Conventions

Merged from the repo and spec B1 (global invariants); both are binding.

- **Class merging:** always `cn()` from `@/lib/utils` (clsx + tailwind-merge).
- **Variants:** CVA; export both the component and `xVariants`.
- **Refs:** `React.forwardRef` + `displayName` (matches shadcn style).
- **Imports:** `@/` alias for all intra-`src` imports; group external → internal.
- **Colors are semantic tokens only** (spec B1.1). Never `bg-black`, `bg-blue-500`,
  `bg-[#123456]`, `bg-emerald-50` — use §2.1/§2.2/§2.3 (§2.8 to add a new one).
- **Never install `react-router-dom`** (spec B1.2): routing is TanStack Router;
  `Link`, `useNavigate`, `useParams` come from `@tanstack/react-router`.
- **Never create `src/pages/` or `App.tsx`** (spec B1.3): routes live in
  `src/routes/` (see `src/routes/README.md`).
- **Numbers, currency, dates:** `toFa()`, `formatToman()`, `formatFaDate()` from
  `@/lib/format` (Persian digits, Jalali dates); `formatFaDateTime()` adds the
  24-hour time where the moment matters (audit log, F5.5). Never render raw Latin digits in
  UI. The spec names these `toPersianDigits` / `formatPrice` / `formatDate` — **the
  repo names win** (§5); the behaviour is identical.
- **RTL discipline** (spec B1.5): logical spacing (`ms-*`/`me-*`) and borders
  (`border-s-*`/`border-e-*`); in RTL `ChevronLeft` means *forward*, `ChevronRight`
  means *back*. `dir="ltr"` only for phone/URL/number inputs.
- **Mobile-first and responsive** on every screen (spec B1.6).
- **Images:** resolve references through `img()` / `resolveImageUrls()` /
  `resolveImageMap()` in `@/lib/catalog` — references are bundled asset keys
  (`cat-tshirt`), absolute URLs, or storage paths (`uploads/…`, signed via
  `POST /storage/sign`). Use `resolveImageMap()` when you need a reference → URL
  lookup (e.g. search hits and suggestions).
- **Data:** TanStack Query. Catalog reads go through `useCatalog()` /
  `catalogQuery` in `@/lib/catalog`, which maps API rows with `toProduct()` /
  `toProducts()`; `productQuery`, `variantsQuery`, `reviewsQuery`, `relatedQuery`
  and `recommendationsQuery` cover a single product, and `searchQuery()` maps
  `GET /search` hits with `hitToProduct()`. Mutations use `useMutation` +
  `queryClient.invalidateQueries`.
- **Admin screens** live under `routes/_authenticated/admin.*` (`admin.tsx` is the
  tab shell): dashboard, products (+ per-row `VariantEditor`), inventory, orders,
  reviews, users. They read the API directly through `api.*` (no `@/lib/catalog`
  mapping except `useCatalog()` for names), keep query keys `admin-*`, and
  invalidate the storefront caches (`catalog`, `product/{id}`,
  `product/{id}/variants`) after every write.
- **Variants:** never re-derive size×colour availability by hand — use
  `@/lib/variants` (`variantStockFor`, `comboStock`, `defaultColor`), which mirrors
  the backend's `app/services/variants.py`.
- **Stock truth comes from the API.** The cart validates with `POST /stock/check`
  (blocking «تکمیل خرید» on `ok: false`) and the product page uses `@/lib/variants`;
  never re-derive availability by hand — the server decides. Rejected lines are
  explained from `@/lib/stock-issues` (`stockIssueMessage` for the cart line,
  `stockIssueLabel` for a toast), which is the single copy per backend reason — add
  new reasons there, not inline.
- **Multi-select facets travel as repeated params.** The shop keeps `size`/`color`
  as `string[]` in the URL (`?size=M&size=L`); `api.products()` appends one param per
  value and the backend ORs within a facet, ANDs across them. Use the sidebar's
  `toggle()`/`clean()` helpers rather than writing comma-joined values.
- **Shop filters live in the URL.** `shop.tsx` reads every filter/sort from
  `validateSearch` and links to the next state (helper `clean()` drops empty
  values), so filters are shareable and the list is filtered by the backend — never
  re-filter `useCatalog()` client-side.
- **Client-side lists:** cart (`sandeh-cart-v1`) and compare
  (`sandeh-compare-v1`, cap 4) are localStorage providers in `@/lib` wrapped around
  the app in `__root.tsx`; use their hooks (`useCart`, `useCompare`) rather than
  reading storage directly.
- **Forms:** plain controlled state + `useMutation` today (RHF/zod installed but
  unused). **Target (spec [FE-04]):** RHF + zod validation on admin forms; adopt it
  per-form, don't half-migrate an existing one.
- **Feedback:** `toast.success` / `toast.error` from `sonner` (top-center, §2.7).
- **Every content route defines its own `head()`** with a unique Persian title,
  description and `og:*`; private screens add `robots: noindex`.

---

## 5. Precedence: spec vs repo (Rule 0.2)

Conflicts found so far, and which side is binding. Do **not** "fix" the repo to
match the spec without an explicit user decision:

| # | Spec says | Repo does | Binding here |
|---|---|---|---|
| 1 | Backend: Lovable Cloud / Supabase SDK, `createServerFn`, `src/integrations/supabase/client` | FastAPI in `../backend` (sole backend), `src/lib/api.ts`, own JWT; no Supabase import anywhere | **Repo** — see `AGENTS.md` architecture + `plan/feature-roadmap.md` |
| 2 | `src/lib/order-actions.functions.ts` (`cancelOrder`, `requestRefund`, `resolveRefundRequest`) | deleted in F1.8; same operations are API calls (`POST /orders/{id}/cancel`, `POST /orders/{id}/refunds`, `PATCH /refunds/{id}`) | **Repo** — a spec sentence naming that file is stale |
| 3 | `formatPrice` / `toPersianDigits` / `formatDate` | `formatToman` / `toFa` / `formatFaDate` in `@/lib/format` | **Repo names** (identical behaviour) |
| 4 | Status badges: `bg-emerald-50 text-emerald-700`, `bg-amber-50`, `bg-rose-50`, `bg-blue-50`, `bg-purple-50` | one terracotta/sand chip per status today; tokens are terracotta/sage/sand/gold + `destructive` | **Repo rule** (semantic tokens, §2.3) — the *meaning* is adopted, the raw classes are not |
| 5 | Toasts bottom-left | `<Toaster position="top-center" />` | **Repo** (§2.7) |
| 6 | Corners `rounded-xl`/`rounded-2xl`, never `rounded-none`/`rounded-3xl` on data widgets | storefront uses `rounded-3xl`/`rounded-[1.25rem]` and square `rounded-none` buttons/inputs | **Repo for existing screens**; spec's rule **target for new admin data widgets** (§2.4) |
| 7 | Admin sidebar shell `components/admin/AdminLayout.tsx`, `AdminDataTable.tsx`, `OrderDetailSheet.tsx`, `RefundActionDialog.tsx`, `admin.refunds.tsx`, `admin.coupons.tsx` | tab-shell `admin.tsx`; none of those files exist | **Target** — tracked as F4.1–F4.5 in `plan/frontend-tasks.md` |
| 8 | Skeleton color `bg-muted` | `bg-clay animate-pulse` (warmer, brand-tinted) | **Repo** (§2.7) |
| 9 | `font-serif` / `font-mono` utilities | `font-display` exists; no mono token or utility exists | **Target** — add `--font-mono` before using `font-mono` (§2.5) |
| 10 | Invoice printing via `@media print` ([FE-05]) | no print stylesheet in `styles.css` | **Target** — F4.4 |

Rule of thumb: if a spec line touches the data layer, a status string, the cart
money rules or an existing screen's shape, the repo wins and the deviation goes in
the task's audit (Rule 0.3).

---

## 6. Data-layer types (two `Product` types)

| Type | File | Shape | Consumer |
|---|---|---|---|
| `Product` | `@/data/products` | `oldPrice`, `isNew`, `CategoryId` | `ProductCard`, `ShopPage`, `product.$id`, seeds |
| `Product` (API) | `@/lib/api` | `old_price`, `is_new`, snake_case | raw backend rows |
| `AdminProduct` | `@/lib/catalog` | local `Product` + `stock, active, rawImages, tags, badge, availability, availableAt, lowStockThreshold, avgRating, reviewCount` | admin pages, product page |

`toProduct()` bridges API → local shape (and `hitToProduct()` in the same module
does the same for `GET /search` hits). `src/data/products.ts` also still holds
a **static 20-product seed** and the `categories` / `palette` constants — the
icons' `CategoryId` union lives there too.

Search hits carry only id/name/category/price/old_price/image/stock/is_new, so
`hitToProduct()` fills the remaining local `Product` fields with empty values —
`ProductCard` is the only intended consumer.

---

## 7. Reusable code blocks (spec B4, adapted)

### 7.1 Number & currency formatting

```tsx
import { formatToman, toFa } from "@/lib/format";

// ۳۵۰٬۰۰۰ تومان
<span>{formatToman(amount)} تومان</span>

// ۱۲۳۴۵
<span>{toFa(count)}</span>
```

### 7.2 Status badge (spec B4.2, using §2.3) — **exists** (`src/components/StatusBadge.tsx`, F4.1)

One component for order / payment / refund state, driven by the §2.3 table. No raw
Tailwind palette classes; `title` keeps the Latin status available for support.
The shipped component also maps `succeeded`/`failed` (payments) and `new`
(contact inbox); unknown statuses degrade to the brand tone with the raw string
as label.

```tsx
import { ORDER_STATUS, PAYMENT_STATUS } from "@/lib/orders";
import { cn } from "@/lib/utils";

const TONES = {
  positive: "border-sage/40 bg-sage/20 text-sage-deep",
  progress: "border-gold/50 bg-gold/15 text-foreground",
  waiting: "border-border bg-sand text-foreground",
  negative: "border-destructive/30 bg-destructive/10 text-destructive",
  meta: "border-terracotta/30 bg-terracotta/10 text-terracotta",
} as const;

const STATUS_TONE: Record<string, keyof typeof TONES> = {
  delivered: "positive", paid: "positive", approved: "positive", refunded: "positive",
  processing: "progress", shipped: "progress",
  pending: "waiting", unpaid: "waiting",
  cancelled: "negative", rejected: "negative",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = TONES[STATUS_TONE[status] ?? "meta"];
  const label =
    ORDER_STATUS[status] ?? PAYMENT_STATUS[status] ?? REFUND_STATUS[status] ?? status;
  return (
    <span
      title={status}
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        tone,
      )}
    >
      {label}
    </span>
  );
}
```

### 7.3 Skeleton & empty states (spec B4.3, repo tokens)

```tsx
if (isLoading) {
  return (
    <div className="space-y-3 p-6">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-2xl bg-clay" />
      ))}
    </div>
  );
}

if (!data?.length) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-card/40 p-12 text-center">
      <p className="text-sm text-muted-foreground">موردی برای نمایش وجود ندارد.</p>
    </div>
  );
}
```

---

## 8. Observations / gaps

1. **Dark mode is off-palette.** The `.dark` block still contains default
   shadcn slate tokens (purple-ish charts), not the terracotta/sage values from
   `:root`. `@custom-variant dark` exists but there is **no theme toggle** — dark
   mode is a roadmap item (spec Part C #14).
2. **RTL not declared to shadcn.** `components.json` has `"rtl": false`, yet the
   app is RTL. Primitives can generate LTR-only styles (e.g. `command`, `sheet`
   animations). Worth setting `rtl: true` if you add Radix-heavy components.
3. **Status colour semantics are unimplemented** — every chip is terracotta/sand
   (§2.3); the mapping is specified and ready to build (F4.1).
4. **Static seed vs API catalog.** `src/data/products.ts` still holds the static
   20-product seed and the `categories` constants; every page now reads the API
   (`useCatalog()`/`productQuery`), so only `categories`, `categoryTitle` and the
   `CategoryId` union are really used. The legacy local `Product` type carries the
   catalog fields optionally (`tags`, `badge`, `availability`, `avgRating`, …).
5. **The spec's admin surface is mostly built** — sidebar shell (F4.2), order
   drawer + invoice printing (F4.4), refunds centre (F2.4/B5.3) exist; still
   missing: the data grid (`@tanstack/react-table`, F4.3), coupons manager (F4.5)
   and CRM 360 (F4.8/F4.6). `recharts` is now used (F2.6); RHF/zod remain unused.
6. **Leftover dependency.** `@supabase/supabase-js` remains in `package.json`
   (no imports) — kept only to avoid lockfile churn.
7. **Error/404 copy is English** (`__root.tsx`) despite the Persian UI.
8. **Print stylesheet exists** (F4.4): `styles.css` carries the `@media print`
   block — while the order drawer is open, `body[data-order-print-open]` hides the
   app and shows only the portalled `#__se_invoice_root` invoice (A4 `@page`, no
   nav/buttons/backgrounds); Ctrl+P elsewhere prints normally.
9. **The two "backend ready, screen missing" admin inboxes are built** — the
   contact inbox is `/admin/messages` (F2.1b, with `PATCH
   /admin/contact-messages/{id}` to mark answered) and the refunds centre is
   `/admin/refunds` (F2.4 + B5.3, with the required bank-tracking code on
   settlement). Both are plain card lists in the tab shell; the spec's drawer
   chrome stays open for F4.x. The audit-log viewer `/admin/audit` (F5.5,
   admin/super_admin only) follows the same card-list pattern, with a
   `<details>` old→new value table per entry and «جدیدتر/قدیمی‌تر» offset paging
   (the endpoint returns no total).
10. **Province is free text everywhere** — both the address book and the checkout
   shipping box take a plain string; the spec implies a province list (and real
   carrier rates need one). No task logged yet — it belongs with shipping rates.

---

## 9. Authoring checklist for new components

Repo checklist, then the spec's pre-flight list (B5) — both must pass.

- [ ] Persian copy, RTL-safe layout (logical spacing; `dir="ltr"` only for
      phone/number/URL inputs).
- [ ] Use existing `ui/*` primitives before creating new ones.
- [ ] `cn()` for className, CVA for variants, `@/` imports.
- [ ] Colors via tokens (`text-terracotta`, `bg-sand`, §2.3 for state), never raw
      palette classes or hex.
- [ ] Numbers via `toFa` / `formatToman` / `formatFaDate` / `formatFaDateTime`.
- [ ] Data via TanStack Query; images via `@/lib/catalog` helpers.
- [ ] Loading/empty/error states (`bg-clay animate-pulse` skeletons, §7.3).
- [ ] Toasts via `sonner` for mutations.
- [ ] Route defines `head()` with a unique Persian title + description
      (`robots: noindex` for private screens).
- [ ] Admin routes keep the `_authenticated` guard and the `isAdmin` check
      (`admin.tsx`); a non-admin sees the Persian permission notice.
- [ ] Chevron/icon direction correct for RTL (`ChevronLeft` = forward).
- [ ] New data widgets follow §2.6 spacing/shadow and §2.4 radii; state is shown
      through §2.3, not through colour alone (the label always names the status).
