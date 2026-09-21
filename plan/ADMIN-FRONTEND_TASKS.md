# Front-End Development & UI/UX Design Specifications (Back-Office)

This document contains task breakdowns, architectural component definitions, and UI/UX design system specifications for the "SÂNDÉ" luxury e-commerce admin panel.

---

## 🎨 Section 0: Design System & Visual Guidelines

### 1. Visual Direction & Brand Alignment
- **Aesthetic:** Editorial Minimal Luxury. Clean, high-whitespace layouts avoiding the sterile, gray look of legacy ERPs. Uses soft contrast surfaces, subtle borders (`border-border/60`), and rounded cards (`rounded-xl` to `rounded-2xl`).
- **Orientation & Typography:**
  - Full Right-to-Left (RTL) support.
  - Cormorant Garamond / Luxury Serif for brand titles and KPI counters.
  - Clean Persian sans-serif (Vazirmatn / Shabnam) for data grids and tabular numbers.
  - Tabular monospace numbers for prices, SKUs, and tracking IDs with standard thousand separators (۳۵۰,۰۰۰ تومان).

### 2. Semantic Color Palette
- **Brand Identity Tokens:**
  - **Terracotta** (`--terracotta`): Primary brand action color, active buttons, and key highlight badges.
  - **Sage & Sage-Deep** (`--sage`, `--sage-deep`): Growth metrics, positive trend chips, and success states.
  - **Sand & Warm Cream** (`--sand`, `--card`): Background for cards, drawers, and secondary containers to eliminate eye strain.
- **Status Color Coding:**
  - **Completed / Paid / Delivered:** Soft Emerald (`bg-emerald-50 text-emerald-700 border-emerald-200`)
  - **Processing / Shipped:** Warm Amber (`bg-amber-50 text-amber-700 border-amber-200`)
  - **Cancelled / Rejected / Out-of-Stock:** Muted Terracotta/Rose (`bg-rose-50 text-rose-700 border-rose-200`)
  - **Pending Review / Draft:** Neutral Slate (`bg-muted text-muted-foreground border-border`)

### 3. Micro-Interactions & Usability Patterns
- **Table Density & Rhythm:** Row height set to a generous `h-14` or `h-16` with smooth hover states (`hover:bg-muted/40`).
- **Feedback & Transitions:**
  - 200ms ease-out transitions (`transition-all duration-200 ease-out`).
  - Shimmering skeleton loaders rather than jarring spinners during data fetches.
  - Floating toast notifications (Sonner) positioned at the bottom-left corner.

---

## Epic 1: Admin Shell & Core Infrastructure

### [FE-01] Responsive Admin Layout & Interactive Sidebar (`AdminLayout`)
- **Design Specifications:**
  - **Sidebar:** Subtle border on the separator side (`border-l border-border/70`), luxury brand mark at top, grouped navigation with 18px linear Lucide icons.
  - **Navigation Items:** Hover state gives a soft background tint with a 3px terracotta edge indicator; active route features 10% terracotta background and semibold text.
  - **Counter Badges:** Mini pill chips next to "Orders" and "Refunds" showing counts of actionable items.
  - **Top Navigation Bar:** Collapsible sidebar toggle, global quick-search bar (`Cmd+K` / `Ctrl+K`), quick link to preview the live storefront, and staff profile avatar with sign-out dropdown.
- **Technical Requirements:** Responsive sheet drawer for mobile viewports, role-based menu filtering, and unread badge listeners.

### [FE-02] Editorial Data Table Component (`AdminDataTable`)
- **Design Specifications:**
  - Muted table header (`bg-muted/30`) with uppercase caption styling and dual-arrow sorting indicators.
  - Toolbar with integrated real-time search input, multi-select dropdown chips for status/category, and CSV export trigger.
  - **Floating Bulk Action Bar:** Slides up smoothly from screen bottom when multiple checkboxes are selected, providing batch status update triggers.
- **Technical Requirements:** TanStack Table v8 integration, server-side pagination, sorting, filtering, and single-click copy for tracking codes and customer phones.

---

## Epic 2: Core Management Modules & Views

### [FE-03] Executive KPI Dashboard (`/admin`)
- **Design Specifications:**
  - **KPI Bento Grid:** 4 top cards displaying: Today's Revenue, New Orders, Average Order Value (AOV), and Low-Stock Warnings. Each card includes a primary figure, month-over-month delta badge (green up-arrow / red down-arrow), and a watermark icon.
  - **Sales Revenue Area Chart:** Smooth spline area chart with gradient terracotta-to-transparent fill, formatted dates, and Persian tooltip hover cards.
  - **Order Status Distribution:** Donut chart breakdown with an inline color-coded legend below.
  - **Urgent Action Items Widget:** Border-highlighted container surfacing immediate operational tasks (e.g., "3 pending refund requests", "2 items with < 3 units remaining").
- **Technical Requirements:** Recharts integration styled with Tailwind variables, query caching with TanStack Query.

### [FE-04] Product & Inventory Catalog Management (`/admin/products`)
- **Design Specifications:**
  - Product list showing rounded thumbnail (`rounded-lg object-cover w-12 h-12`), SKU in monospace, and color-coded stock alerts.
  - **Product Editor Form (Dedicated Route / Full Modal):**
    - Two-column layout: wide primary column for Title, Category, and Rich Description; narrow secondary column for Pricing, Visibility Switch, and Badges.
    - **Interactive SKU & Variant Matrix:** Dynamic row generator for Color (with visual color swatch picker), Size, Quantity, and SKU code.
    - **Image Gallery Manager:** Drag-and-drop upload zone, reorderable preview cards, primary image star toggle, and hover delete actions.
- **Technical Requirements:** React Hook Form with Zod schemas, direct Supabase storage bucket upload with progress indication.

### [FE-05] Order Processing & Detail Drawer (`/admin/orders` + Side Drawer)
- **Design Specifications:**
  - Clicking any order opens a **Wide Side Sheet from the left** without losing table context.
  - **Visual Status Stepper:** 4 sequential stages (Placed ➔ Paid ➔ Processing ➔ Shipped) with a one-click "Advance to Next Stage" button.
  - **Customer & Shipping Card:** Buyer name, full address, postal code, phone number, with single-click copy buttons for parcel label printing.
  - **Itemized Breakdown:** Clean rows showing thumbnail, product title, chosen size/color chips, unit price, quantity, and subtotal.
  - **Official Invoice Printing:** Clean print trigger formatted with `@media print` CSS for standard A4/A5 receipts without headers, sidebars, or page artifacts.
- **Technical Requirements:** TanStack server function mutations, optimistic cache invalidation, postal tracking number input with immediate validation.

### [FE-06] Refund & Returns Processing Center (`/admin/refunds`)
- **Design Specifications:**
  - Split cards categorized by priority and resolution status.
  - Customer IBAN / Sheba / Card details rendered in monospace with quick-copy clipboard triggers.
  - Status badges (`Pending` in amber, `Approved` in emerald, `Rejected` in rose).
  - **Resolution Modal:** Action dialog with mandatory "Bank Transfer / SATNA Tracking ID" input, optional customer explanation note, and dual "Approve & Settle" / "Reject" triggers.
- **Technical Requirements:** Connect to `resolveRefundRequest` server function, automatic order payment status synchronization, query cache refresh.

### [FE-07] Promotion & Discount Campaign Manager (`/admin/coupons`)
- **Design Specifications:**
  - Coupon cards designed with a ticket aesthetic (scalloped/notched borders).
  - Big bold discount metric (e.g. `25% OFF` or `50,000 Toman`), status toggle switch.
  - Mini usage progress bar (e.g., "42 used out of 100 limit").
  - Date-picker popover for campaign start and end windows.
- **Technical Requirements:** Code uniqueness check, active toggle optimistic mutation, expiration badge calculation.

### [FE-08] Customer 360° Profile & CRM (`/admin/users`)
- **Design Specifications:**
  - Customer avatar with initials, customer tier badge (New / VIP / Wholesale), registration date.
  - Tabbed overview inside drawer/page: Order History, Saved Addresses, Wishlist Items.
  - Lifetime Value (LTV) metric card and average days between purchases.
  - Role management trigger (Promote to Admin / Demote) with two-step security confirmation dialog.
