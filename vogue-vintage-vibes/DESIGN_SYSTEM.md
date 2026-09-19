# SÂNDÉ — Frontend Design System & Component Guide

Reference for building UI in `vogue-vintage-vibes/`. Describes the stack,
design tokens, component inventory, and the conventions to follow.

---

## 1. Stack

| Concern | Choice |
|---|---|
| Framework | TanStack Start (Vite 8) + React 19, SSR via `src/server.ts` |
| Routing | TanStack Router (file-based, `src/routes/`, generated `routeTree.gen.ts`) |
| Data fetching | TanStack React Query (`QueryClientProvider` in `__root.tsx`) |
| Styling | Tailwind CSS **v4** (CSS-first `@theme`, no `tailwind.config.js`) |
| Component kit | **shadcn/ui**, style `new-york`, base color `slate` (`components.json`) |
| Primitives | Radix UI (`@radix-ui/react-*`) |
| Variants | `class-variance-authority` (CVA) |
| Icons | `lucide-react` |
| Toasts | `sonner` (`<Toaster position="top-center" />`) |
| Forms | `react-hook-form` + `zod` + `@hookform/resolvers` |
| Charts | `recharts` (installed, currently **unused**) |
| Carousel | `embla-carousel-react` → `ui/carousel.tsx` |
| Package manager | **Bun** (`bun.lock`, `bunfig.toml`) |

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
| `--sand` | `bg-sand` | `oklch(0.938 0.018 68)` | section backgrounds, inputs |
| `--clay` | `bg-clay` | `oklch(0.885 0.03 62)` | image placeholders |
| `--terracotta` | `text/bg-terracotta` | `oklch(0.585 0.115 34)` | brand primary, links, accents |
| `--terracotta-soft` | `bg-terracotta-soft` | `oklch(0.79 0.085 52)` | soft accents |
| `--apricot` | `bg-apricot` | `oklch(0.845 0.07 62)` | gradients |
| `--sage` | `bg-sage` | `oklch(0.7 0.055 138)` | `accent` |
| `--sage-deep` | `text-sage-deep` | `oklch(0.45 0.055 140)` | eyebrow text, step-done |
| `--gold` | `text-gold` | `oklch(0.76 0.105 88)` | highlights / chart |

### 2.2 Semantic tokens

Registered in `@theme inline` so they become utilities (`bg-primary`,
`text-muted-foreground`, …): `background, foreground, card, popover, primary,
secondary, muted, accent, destructive, border, input, ring`, `chart-1..5`,
`sidebar*`.

Key mappings: `--primary` = terracotta, `--secondary`/`--muted` = sand,
`--accent` = sage, `--border`/`--input` = `oklch(0.885 0.022 62)`.

### 2.3 Radii

`--radius: 0.25rem` → `rounded-sm|md|lg|xl|2xl|3xl|4xl` derived. In practice the
app uses large custom radii like `rounded-3xl` and `rounded-[1.25rem]`.

### 2.4 Brand utilities (custom `@utility`)

| Utility | Effect |
|---|---|
| `surface-warm` | terracotta→apricot gradient background, primary-foreground text |
| `surface-courtyard` | sand→sage gradient background |
| `shadow-soft` | soft terracotta-tinted drop shadow |
| `rule-terracotta` | terracotta-tinted border color |

### 2.5 Typography

| Token | Stack | Use |
|---|---|---|
| `--font-display` | Cormorant Garamond → Vazirmatn → serif | headings, logo (`font-display`) |
| `--font-sans` | Vazirmatn → Karla → system | body (default) |
| `--font-latin` | Karla → Vazirmatn | Latin-only runs |

Fonts loaded via Google Fonts `<link>` in `__root.tsx`.

### 2.6 Adding a new semantic color

Per the comment at the top of `styles.css`:
1. Add the variable to `:root` (light) **and** `.dark` (dark).
2. Register it in `@theme inline` as `--color-<name>: var(--<name>)`.

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
| `product/VariantPicker.tsx` | Size × colour selection with per-combination availability (disabled sold-out/deactivated combos, disabled colours) and an `aria-live` stock line. Uses `@/lib/variants` — never re-implement the rule. |
| `product/ReviewsSection.tsx` | Rating summary + 1–5 distribution, review list (seller replies, Jalali dates), star-input write/edit form; one review per customer per product (backend upserts). |
| `product/ProductRail.tsx` | RTL embla carousel rail (`ui/carousel`, `direction: "rtl"`) with header arrow buttons tracking `canScrollPrev/Next`; used for related, recommended and recently-viewed products. |
| `product/RecentlyViewedRail.tsx` | `ProductRail` fed by `recentlyViewedQuery`; hidden for guests and while the list is empty (home + shop). |

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

---

## 4. Conventions

- **Class merging:** always `cn()` from `@/lib/utils` (clsx + tailwind-merge).
- **Variants:** CVA; export both the component and `xVariants`.
- **Refs:** `React.forwardRef` + `displayName` (matches shadcn style).
- **Imports:** `@/` alias for all intra-`src` imports; group external → internal.
- **Numbers/currency/dates:** use `toFa()`, `formatToman()` and `formatFaDate()`
  from `@/lib/format` (Persian digits, Jalali dates). Never render raw Latin
  digits in UI.
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
- **Variants:** never re-derive size×colour availability by hand — use
  `@/lib/variants` (`variantStockFor`, `comboStock`, `defaultColor`), which
  mirrors the backend's `app/services/variants.py`.
- **Shop filters live in the URL.** `shop.tsx` reads every filter/sort from
  `validateSearch` and links to the next state (helper `clean()` drops empty
  values), so filters are shareable and the list is filtered by the backend —
  never re-filter `useCatalog()` client-side.
- **Client-side lists:** cart (`sandeh-cart-v1`) and compare
  (`sandeh-compare-v1`, cap 4) are localStorage providers in `@/lib` wrapped
  around the app in `__root.tsx`; use their hooks (`useCart`, `useCompare`)
  rather than reading storage directly.
- **Feedback:** `toast.success` / `toast.error` from `sonner`.
- **Styling color usage:** prefer semantic/brand tokens over raw hex/oklch.

---

## 5. Data-layer types (two `Product` types)

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

## 6. Observations / gaps

1. **Dark mode is off-palette.** The `.dark` block still contains default
   shadcn slate tokens (purple-ish charts), not the terracotta/sage values from
   `:root`. `@custom-variant dark` exists but there is **no theme toggle** —
   dark mode is a roadmap item.
2. **RTL not declared to shadcn.** `components.json` has `"rtl": false`, yet the
   app is RTL. Primitives can generate LTR-only styles (e.g. `command`, `sheet`
   animations). Worth setting `rtl: true` if you add Radix-heavy components.
3. ~~**Search is a stub.**~~ **Done (F3.1 / F3.1b):** `HeaderSearch.tsx` drives
   `GET /search/suggest` + history, `/shop?q=` runs `GET /search`, and the backend
   matches `tags` too (the starter catalog is tagged). Open: results are not
   SSR-prefetched, and the results view has no filter sidebar (F3.3).
4. **Static seed vs API catalog.** `src/data/products.ts` still holds the static
   20-product seed and the `categories` constants; every page now reads the API
   (`useCatalog()`/`productQuery`), so only `categories`, `categoryTitle` and the
   `CategoryId` union are really used. The legacy local `Product` type carries the
   catalog fields optionally (`tags`, `badge`, `availability`, `avgRating`, …).
5. **Leftover dependency.** `@supabase/supabase-js` remains in `package.json`
   (no imports) — kept only to avoid lockfile churn.
6. **`recharts` installed but unused** — reserved for admin dashboard charts.
7. **Error/404 copy is English** (`__root.tsx`) despite the Persian UI.

---

## 7. Authoring checklist for new components

- [ ] Persian copy, RTL-safe layout (use logical spacing; `dir="ltr"` only for
      phone/URL inputs — see addresses page).
- [ ] Use existing `ui/*` primitives before creating new ones.
- [ ] `cn()` for className, CVA for variants, `@/` imports.
- [ ] Colors via tokens (`text-terracotta`, `bg-sand`, …), not raw values.
- [ ] Numbers via `toFa` / `formatToman`.
- [ ] Data via TanStack Query; images via `@/lib/catalog` helpers.
- [ ] Loading/empty/error states (skeletons use `bg-clay animate-pulse`).
- [ ] Toasts via `sonner` for mutations.
