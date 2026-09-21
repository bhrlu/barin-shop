# SÂNDÉ — Complete E-Commerce Platform Development Specification

**Project:** SÂNDÉ Luxury Women's Apparel (Storefront + Back-Office Admin Panel)
**Language & Direction:** Persian (Farsi), full RTL (`dir="rtl"`)
**Currency:** Iranian Toman (تومان), Persian digits with thousand separators (`۳۵۰,۰۰۰ تومان`)

**Tech Stack**
- Framework: TanStack Start v1 (React 19, Vite 7)
- Routing: TanStack Router (`src/routes/*`) — React Router is forbidden
- Styling: Tailwind CSS v4 via `src/styles.css` (semantic CSS variables, OKLCH)
- UI primitives: shadcn/ui (`@/components/ui/*`)
- Icons: `lucide-react` · Toasts: `sonner`
- Data: TanStack Query + TanStack server functions (`createServerFn`)
- Backend: Lovable Cloud (Supabase SDK via `@/integrations/supabase/client`)

---

# PART A — BACK-END TASKS & SPECIFICATIONS

This part outlines required database schemas, RLS policies, RBAC, server functions/APIs, and integration workflows for the admin back-office.

## Epic A1: Database Architecture & Data Models

### [BE-01] Product Variants Matrix & Inventory Management
- **Goal:** Support multi-dimensional product variations (Size × Color) with independent inventory levels, pricing overrides, and SKUs.
- **Tables:**
  - `product_variants`:
    - `id` (UUID, PK, default `gen_random_uuid()`)
    - `product_id` (UUID, FK -> `products.id` ON DELETE CASCADE)
    - `sku` (VARCHAR, UNIQUE, indexed)
    - `size` (VARCHAR)
    - `color_name` (VARCHAR)
    - `color_hex` (VARCHAR)
    - `price_override` (NUMERIC, NULLABLE)
    - `stock_quantity` (INTEGER, NOT NULL DEFAULT 0)
    - `created_at` (TIMESTAMPTZ DEFAULT now())
  - `inventory_logs`:
    - `id` (UUID, PK)
    - `variant_id` (UUID, FK -> `product_variants.id`)
    - `change_amount` (INTEGER: positive for restock, negative for deduction)
    - `reason` (ENUM: `'purchase'`, `'restock'`, `'return'`, `'manual_adjustment'`)
    - `created_by` (UUID, FK -> `auth.users.id`)
    - `created_at` (TIMESTAMPTZ DEFAULT now())
- **Constraints & Indexes:** Unique composite key on `(product_id, size, color_name)`. Index on `sku` and `product_id`.

### [BE-02] Promotional Engine & Coupons
- **Goal:** Manage promotion campaigns, discount codes, usage limits, and expiration criteria.
- **Tables:**
  - `coupons`:
    - `id` (UUID, PK)
    - `code` (VARCHAR, UNIQUE, case-insensitive index)
    - `discount_type` (ENUM: `'percentage'`, `'fixed'`)
    - `value` (NUMERIC NOT NULL)
    - `min_order_amount` (NUMERIC DEFAULT 0)
    - `max_discount_cap` (NUMERIC NULLABLE)
    - `usage_limit` (INTEGER NULLABLE)
    - `used_count` (INTEGER DEFAULT 0)
    - `starts_at` (TIMESTAMPTZ NOT NULL)
    - `expires_at` (TIMESTAMPTZ NOT NULL)
    - `is_active` (BOOLEAN DEFAULT true)
  - `coupon_usages`:
    - `id` (UUID, PK)
    - `coupon_id` (UUID, FK -> `coupons.id`)
    - `user_id` (UUID, FK -> `auth.users.id`)
    - `order_id` (UUID, FK -> `orders.id`)
    - `used_at` (TIMESTAMPTZ DEFAULT now())
- **Acceptance Criteria:** Prevent race conditions on `usage_limit` using transactional counters or optimistic locking.

### [BE-03] Returns & Refund Requests Processing
- **Goal:** Customer cancellation/return requests, admin approval lifecycle, and accounting tracking.
- **Tables:**
  - `refund_requests`:
    - `id` (UUID, PK)
    - `order_id` (UUID, FK -> `orders.id`)
    - `user_id` (UUID, FK -> `auth.users.id`)
    - `amount` (NUMERIC NOT NULL)
    - `reason` (TEXT NOT NULL)
    - `status` (ENUM: `'pending'`, `'approved'`, `'rejected'`, `'refunded'`)
    - `bank_tracking_code` (VARCHAR NULLABLE)
    - `admin_notes` (TEXT NULLABLE)
    - `resolved_by` (UUID, FK -> `auth.users.id` NULLABLE)
    - `resolved_at` (TIMESTAMPTZ NULLABLE)
- **RLS Policies:**
  - Authenticated users may insert and select only their own records for orders they own.
  - Admins (via `has_role(auth.uid(), 'admin')`) have unrestricted SELECT and UPDATE privileges.

### [BE-04] Admin RBAC & Audit Logging
- **Goal:** Granular staff permissions and a tamper-resistant trail of system changes.
- **Tables:**
  - `user_roles`: `(id, user_id, role: 'super_admin' | 'order_manager' | 'support', UNIQUE(user_id, role))`
  - `audit_logs`:
    - `id` (UUID, PK)
    - `admin_id` (UUID, FK -> `auth.users.id`)
    - `action` (VARCHAR, e.g. `'update_order_status'`, `'product_price_change'`)
    - `entity_type` (VARCHAR: `'order'`, `'product'`, `'user'`)
    - `entity_id` (VARCHAR)
    - `old_values` (JSONB)
    - `new_values` (JSONB)
    - `ip_address` (VARCHAR NULLABLE)
    - `created_at` (TIMESTAMPTZ DEFAULT now())
- **Security rule:** Roles must NEVER be stored on `profiles`/users tables; always a separate table read through a `SECURITY DEFINER` function.

## Epic A2: Server Functions, APIs & Business Logic

### [BE-05] Order Lifecycle Management RPC (`updateOrderStatus`)
- **Signature:** `updateOrderStatus({ orderId, nextStatus, trackingCode?, internalNote? })`
- **Logic:**
  - Validate state machine transitions (e.g. `'cancelled'` orders cannot move to `'shipped'`).
  - Reserve/commit stock on payment success; restore stock on cancellation.
  - Insert an entry into `audit_logs`.
- **Execution:** Atomic database transaction to safeguard inventory consistency.

### [BE-06] Coupon Validation Engine (`validateCoupon`)
- **Signature:** `validateCoupon({ code, cartTotal, userId })`
- **Validation Rules:**
  - Code exists and `is_active = true`.
  - Date validity (`starts_at <= now() <= expires_at`).
  - Cart value meets `min_order_amount`.
  - Global `usage_limit` not exceeded.
  - Per-user cap enforced via `coupon_usages`.
- **Response:** Calculated discount amount, sanitized coupon payload, or standard error codes.

### [BE-07] SMS Notification Gateway Integration
- **Provider:** Transactional SMS service provider.
- **Triggers:**
  - Order status changed to `'processing'` or `'shipped'` (with postal tracking number).
  - Refund request approved/settled.
  - Immediate alert to operations team on high-value orders or new refund claims.

### [BE-08] Orders & Financial Data Export Service (`exportOrders`)
- **Signature:** `exportOrders({ fromDate, toDate, status?, format: 'csv' | 'xlsx' })`
- **Output:** Streamed CSV/XLSX with customer shipping details, SKU breakdown, payment reference, and tax/discount splits.

### [BE-09] Dashboard Aggregations RPC (`getDashboardKPIs`)
- **Signature:** `getDashboardKPIs({ timeRange: 'today' | '7d' | '30d' | 'all' })`
- **Metrics:** Gross Revenue, Net Revenue, Total Paid Orders, Average Order Value (AOV), Pending Refunds Count, Low-Stock Alert Count (< 5 units).

## Epic A3: Public/Webhook Endpoints
- Webhooks, cron and public APIs live under `src/routes/api/public/*` (this prefix bypasses site auth).
- Always verify the provider signature (HMAC + timing-safe compare) before processing payloads.
- Validate all input with Zod; never return user PII.

---

# PART B — FRONT-END TASKS & UI/UX SPECIFICATIONS

## Section B0: Design System & Visual Guidelines

### B0.1 Visual Direction & Brand Alignment
- **Aesthetic:** Editorial Minimal Luxury. Clean, high-whitespace layouts avoiding the sterile gray look of legacy ERPs. Soft contrast surfaces, subtle borders (`border-border/60`), rounded cards (`rounded-xl` to `rounded-2xl`).
- **Orientation & Typography:**
  - Full Right-to-Left (RTL) support.
  - Cormorant Garamond / luxury serif for brand titles and KPI counters.
  - Clean Persian sans-serif (Vazirmatn / Karla) for data grids and forms.
  - Tabular monospace for prices, SKUs, and tracking IDs.

### B0.2 Semantic Color Palette

| Visual Purpose | Semantic Tailwind Class | Context / Meaning |
| :--- | :--- | :--- |
| Primary Brand CTA | `bg-terracotta text-white hover:bg-terracotta/90` | Save, Submit, Create, Pay |
| Brand Accent / Highlight | `text-terracotta`, `bg-terracotta/10 text-terracotta` | Badges, active nav links, price highlights |
| Success / Growth | `bg-emerald-50 text-emerald-700 border-emerald-200` | Delivered orders, approved refunds, positive deltas |
| Warning / In Progress | `bg-amber-50 text-amber-700 border-amber-200` | Processing orders, pending refunds, shipped status |
| Danger / Cancelled | `bg-rose-50 text-rose-700 border-rose-200` | Cancelled orders, rejected refunds, out-of-stock |
| Neutral Surfaces | `bg-background` (page), `bg-card` (containers) | Main surface and container cards |
| Warm Neutral Accent | `bg-sand text-foreground` | Editorial bento panels, sidebar headers |
| Secondary Accent | `bg-sage-deep text-white`, `bg-sage/20 text-sage-deep` | Promo banners, editorial badges |
| Borders | `border-border/60` | Crisp 1px separators |

### B0.3 Typography Hierarchy
- **Editorial headings:** `font-serif` for brand logos, modal titles, large numeric indicators.
- **Body & data:** `font-sans` for reading text, tables, inputs, buttons.
- **Identifiers:** `font-mono tracking-wider` for Order IDs, SKUs, tracking numbers, IBAN/Sheba codes.

### B0.4 Spacing, Borders & Shadows
- **Corners:** `rounded-xl` (12px) or `rounded-2xl` (16px). Never `rounded-none` or `rounded-3xl` on data widgets.
- **Padding:** compact widgets `p-4`; standard cards `p-6`; modals/drawers `p-6`–`p-8`.
- **Elevation:** cards `shadow-sm border border-border/60`; floating elements `shadow-lg border border-border/80`. No harsh black shadows.

### B0.5 Micro-Interactions & Usability
- Table rows `h-14`/`h-16` with `hover:bg-muted/40`.
- Transitions `transition-all duration-200 ease-out`.
- Shimmering skeleton loaders instead of spinners.
- Sonner toasts anchored bottom-left.

## Section B1: Global Rules & Invariant Constraints

1. **Never hardcode colors** (`bg-black`, `text-white`, `bg-[#123456]`, `bg-blue-500`, `text-gray-900`). Use semantic tokens only.
2. **Never install or import `react-router-dom`.** Use `import { Link, useNavigate, useParams } from '@tanstack/react-router'`.
3. **Never create `src/pages/` or `App.tsx`.** Routes belong in `src/routes/`.
4. **All user-visible text in Persian**; numbers via `formatPrice` / `toPersianDigits` from `@/lib/format`.
5. **RTL discipline:** logical margins (`ms-*`/`me-*`), logical borders (`border-s-*`/`border-e-*`); in RTL `ChevronLeft` means forward, `ChevronRight` means back.
6. **Mobile-first and fully responsive** on every screen.

## Section B2: Directory Layout & Routing Conventions

```
src/
├── components/
│   ├── ui/                           # shadcn primitives (button, dialog, sheet, input...)
│   └── admin/
│       ├── AdminLayout.tsx           # Sidebar, topbar, mobile drawer wrapper
│       ├── AdminDataTable.tsx        # Reusable table: search, filter, pagination
│       ├── ProductImageManager.tsx   # Multi-image upload, reorder, primary selector
│       ├── OrderDetailSheet.tsx      # Side sheet for order inspection
│       └── RefundActionDialog.tsx    # Approve/reject refund with tracking code
├── lib/
│   ├── format.ts                     # formatPrice, toPersianDigits, formatDate
│   ├── order-actions.functions.ts    # cancelOrder, requestRefund, resolveRefundRequest
│   └── orders.ts                     # Order status labels/badges in Persian
└── routes/
    └── _authenticated/
        ├── admin.tsx                 # Layout route wrapping all /admin
        ├── admin.index.tsx           # /admin — Executive KPI Dashboard
        ├── admin.products.tsx        # /admin/products — Catalog & SKU manager
        ├── admin.orders.tsx          # /admin/orders — Fulfillment & invoices
        ├── admin.users.tsx           # /admin/users — Customer 360° CRM
        ├── admin.refunds.tsx         # /admin/refunds — Refund & return claims
        └── admin.coupons.tsx         # /admin/coupons — Discounts & campaigns
```

## Section B3: Module-by-Module Implementation Guide

### [FE-01] Admin Shell & Interactive Sidebar (`components/admin/AdminLayout.tsx`)
**Design:**
1. **Sidebar (right side in RTL):**
   - `w-64` desktop; hidden on mobile behind a sheet trigger.
   - Header: brand mark "SÂNDÉ" with subtitle «پنل مدیریت».
   - Separator: `border-l border-border/70`; 18px linear Lucide icons.
   - Navigation:
     - داشبورد (`/admin`) — `LayoutDashboard`
     - محصولات و انبار (`/admin/products`) — `Package`
     - سفارشات (`/admin/orders`) — `ShoppingBag` + pending-orders badge
     - مرجوعی و بازپرداخت (`/admin/refunds`) — `RotateCcw` + active-claims badge
     - تخفیف‌ها (`/admin/coupons`) — `Tag`
     - کاربران و مشتریان (`/admin/users`) — `Users`
     - بازگشت به فروشگاه (`/`) — `Store`
   - Item states: hover soft tint with a 3px terracotta edge indicator; active route `bg-terracotta/10` + semibold text.
2. **Top header bar:**
   - `h-16 border-b border-border/60 bg-background/95 backdrop-blur`.
   - Right: mobile hamburger (`SheetTrigger`).
   - Center: breadcrumbs + global quick search (`Cmd+K` / `Ctrl+K`).
   - Far left: admin avatar, role badge «مدیر ارشد», logout.
3. **Auth guard:** block non-admin users, redirect with a Persian permission error.

**Canonical nav item:**
```tsx
<Link
  to="/admin/orders"
  className="flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors hover:bg-muted/60 text-muted-foreground data-[status=active]:bg-terracotta/10 data-[status=active]:text-terracotta"
>
  <div className="flex items-center gap-3">
    <ShoppingBag className="w-4 h-4 text-inherit" />
    <span>سفارشات</span>
  </div>
  {unreadCount > 0 && (
    <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-terracotta text-white">
      {toPersianDigits(unreadCount)}
    </span>
  )}
</Link>
```

### [FE-02] Editorial Data Table (`components/admin/AdminDataTable.tsx`)
**Design:**
- Header `bg-muted/30`, caption styling, dual-arrow sort indicators.
- Toolbar: live search input with search icon, multi-select filter chips (status/category/date), CSV/Excel export on the far side.
- **Floating bulk-action bar:** dark floating bar slides up from the bottom when rows are checked, offering batch status updates.
**Technical:** `@tanstack/react-table` v8, server-side pagination/sorting/filtering, one-click copy for tracking codes and phone numbers.

### [FE-03] Executive KPI Dashboard (`routes/_authenticated/admin.index.tsx`)
**Layout:**
1. **Row 1 — four KPI cards in a bento grid:** فروش امروز · سفارش‌های جدید · میانگین سبد خرید (AOV) · درخواست‌های بازپرداخت منتظر. Each card: title, large figure, MoM delta badge (green up / red down arrow), watermark icon.
2. **Row 2 — two columns:**
   - 60%: **روند فروش هفتگی** — Recharts area chart, terracotta-to-transparent gradient, Persian tooltips.
   - 40%: **وضعیت سفارشات** — donut chart (paid, processing, shipped, cancelled) with color legend below.
3. **Row 3 — اقدامات فوری:** amber-highlighted callout listing low-stock items (< 5 units) and pending refunds.
**Technical:** Recharts styled with Tailwind tokens, aggregated fetch via `getDashboardKPIs`, TanStack Query caching.

### [FE-04] Product & SKU Inventory Management (`routes/_authenticated/admin.products.tsx`)
**Product list:**
- Thumbnail `w-12 h-12 rounded-lg object-cover`; name + Persian category badge; base and sale price; SKU in mono.
- Stock color alerts: `text-emerald-600` (> 10), `text-amber-600` (1–9), `text-rose-600` (0).
- Toggle switch «نمایش در فروشگاه» with optimistic update on `is_active`.

**Product editor (dedicated route or full modal):**
- Two columns: wide side for title, slug, category, rich description; narrow side for pricing, visibility, sale badges.
- **Size & color matrix generator:** dynamic rows with size selector (`S`, `M`, `L`, `XL`, `Free Size`), color name + hex swatch picker, stock quantity, custom SKU.
- **Image gallery manager (`ProductImageManager`):** drag-and-drop upload zone with dashed border, reorderable preview cards, star toggle for primary image, hover delete, upload progress bar, storage bucket `product-images`.
**Technical:** React Hook Form + Zod; direct bucket upload.

### [FE-05] Order Processing & Detail Drawer (`routes/_authenticated/admin.orders.tsx` + `OrderDetailSheet.tsx`)
**Table columns:** شماره سفارش (`#`, mono) · مشتری (name & phone) · تاریخ ثبت (Persian date) · مبلغ کل (`formatPrice`) · وضعیت پرداخت badge · وضعیت سفارش badge · عملیات («مشاهده و پردازش»).

**Side drawer:**
- shadcn `Sheet` with `side="left"` (opens from the leading edge in RTL) so the list context is preserved.
- **Visual stepper:** four circular steps — ثبت سفارش → تأیید پرداخت → در حال آماده‌سازی → تحویل به پست/پیک; advance button `bg-terracotta text-white` labelled «تغییر وضعیت به مرحله بعد».
- **Customer shipping box:** name, phone, province, city, full address, postal code; «کپی آدرس گیرنده» copies a formatted address and fires a Sonner toast.
- **Itemized breakdown:** thumbnail, title, size/color chips, unit price, quantity, subtotal.
- **Postal tracking input:** field + save action for the 24-digit Iran Post / Tipax code.
- **Invoice printing:** «چاپ فاکتور رسمی» with dedicated `@media print` CSS so only the A4/A5 invoice prints — no nav, background colors, or buttons.
**Technical:** server-function mutations, optimistic cache invalidation, tracking-code validation.

### [FE-06] Refund & Returns Processing Center (`routes/_authenticated/admin.refunds.tsx`)
**Data:** `refund_requests` — `id`, `order_id`, `user_id`, `amount`, `reason`, `status`, `created_at`.
Status labels: `pending` → در انتظار بررسی · `approved` → تأییدشده · `rejected` → ردشده · `refunded` → بازپرداخت‌شده.

**UI:**
1. **Tabs:** «در انتظار بررسی» · «تسویه‌شده» · «همه».
2. **Claim card:** order tracking number + customer name; refund amount `text-rose-600 font-bold font-mono`; customer reason in an editorial quote box (`bg-muted/40 p-3 rounded-lg border-s-4 border-terracotta`); Sheba/card number in mono with copy button; status badge.
3. **Action dialog (`RefundActionDialog.tsx`):** triggered by «رسیدگی به درخواست»; shows order summary; textarea «یادداشت مدیر»; required input «کد رهگیری بانکی (پایا/ساتنا)»; buttons «تأیید و ثبت بازگشت وجه» → `resolveRefundRequest({ requestId, status: 'refunded', ... })` and «رد درخواست» → `resolveRefundRequest({ requestId, status: 'rejected', ... })`.
**Technical:** sync order payment status to `refunded`, refresh related queries.

### [FE-07] Promotion & Discount Campaign Manager (`routes/_authenticated/admin.coupons.tsx`)
**Design:**
- Coupon cards with a ticket aesthetic (notched/scalloped borders).
- Bold discount metric (`۲۵٪ تخفیف` or `۵۰,۰۰۰ تومان`), active/inactive toggle switch.
- Usage progress bar («۴۲ استفاده از ۱۰۰ سقف مجاز»).
- Jalali date-picker popover for campaign start/end.
**Technical:** unique-code validation, optimistic active toggle, expiry badge computation.

### [FE-08] Customer 360° Profile & CRM (`routes/_authenticated/admin.users.tsx`)
**Design:**
- Avatar with initials, tier badge (جدید / وفادار / همکار), registration date.
- Tabs inside the drawer/page: تاریخچه سفارشات · آدرس‌های ثبت‌شده · علاقه‌مندی‌ها.
- Lifetime Value (LTV) metric card and average days between purchases.
- Role change trigger (promote/demote admin) behind a two-step security confirmation dialog.

## Section B4: Standard Reusable Code Blocks

### B4.1 Number & currency formatting
```tsx
import { formatPrice, toPersianDigits } from '@/lib/format';

// ۳۵۰,۰۰۰ تومان
<span>{formatPrice(amount)}</span>

// ۱۲۳۴۵
<span>{toPersianDigits(count)}</span>
```

### B4.2 Status badge helper
```tsx
export function StatusBadge({ status }: { status: string }) {
  const configs: Record<string, { label: string; className: string }> = {
    paid: { label: 'پرداخت شده', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
    unpaid: { label: 'در انتظار پرداخت', className: 'bg-amber-50 text-amber-700 border-amber-200' },
    refunded: { label: 'بازگشت داده شده', className: 'bg-rose-50 text-rose-700 border-rose-200' },
    processing: { label: 'در حال پردازش', className: 'bg-blue-50 text-blue-700 border-blue-200' },
    shipped: { label: 'ارسال شده', className: 'bg-purple-50 text-purple-700 border-purple-200' },
    cancelled: { label: 'لغو شده', className: 'bg-muted text-muted-foreground border-border' },
  };

  const current = configs[status] ?? { label: status, className: 'bg-muted text-muted-foreground' };

  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${current.className}`}>
      {current.label}
    </span>
  );
}
```

### B4.3 Skeleton & empty states
```tsx
if (isLoading) {
  return (
    <div className="space-y-4 p-6">
      <div className="h-8 w-48 bg-muted animate-pulse rounded-lg" />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-28 bg-muted/60 animate-pulse rounded-2xl" />
        ))}
      </div>
      <div className="h-96 bg-muted/40 animate-pulse rounded-2xl" />
    </div>
  );
}

if (!data || data.length === 0) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-border rounded-2xl p-8 bg-card/40">
      <PackageOpen className="w-12 h-12 text-muted-foreground/50 mb-3" />
      <h3 className="text-base font-semibold text-foreground">موردی یافت نشد</h3>
      <p className="text-sm text-muted-foreground mt-1">در حال حاضر داده‌ای برای نمایش در این بخش وجود ندارد.</p>
    </div>
  );
}
```

## Section B5: Pre-Flight Verification Checklist

- [ ] Does the page respect RTL layout (`dir="rtl"`, logical margins, correct chevron directions)?
- [ ] Are all labels, buttons, dialogs, and errors in natural, polite Persian?
- [ ] Are amounts formatted with `formatPrice` in Toman with thousand separators?
- [ ] Are all colors semantic tokens (`terracotta`, `sage`, `sand`, `card`, `border`, `muted`) rather than hardcoded utilities?
- [ ] Do all tables and forms have loading skeletons and empty states?
- [ ] Is an auth guard enforcing the `admin` role on every admin route?
- [ ] Does every content route define its own `head()` with a unique title and description?

---

# PART C — PLATFORM FEATURE BACKLOG (Priority Order)

| # | Feature | Layer | Status |
| :--- | :--- | :--- | :--- |
| 1 | Refund & returns admin center UI | FE-06 + BE-03 | Backend ready, UI pending |
| 2 | Size/color SKU matrix & stock control | FE-04 + BE-01 | Pending |
| 3 | Coupons & campaigns manager | FE-07 + BE-02 | Pending |
| 4 | Order side drawer + invoice printing | FE-05 + BE-05 | Pending |
| 5 | KPI dashboard charts & alerts | FE-03 + BE-09 | Basic stats only |
| 6 | Customer 360° CRM & LTV | FE-08 | List view only |
| 7 | Multi-role staff access & audit log | BE-04 | Pending |
| 8 | SMS notifications | BE-07 | Pending |
| 9 | Excel/CSV financial exports | BE-08 | Pending |
| 10 | Product reviews & ratings | FE + BE | Pending |
| 11 | Shipping methods & cost rules | FE + BE | Pending |
| 12 | Abandoned cart recovery | FE + BE | Pending |
| 13 | Banners/CMS & blog for SEO | FE + BE | Pending |
| 14 | Dark mode & PWA install | FE | Pending |
