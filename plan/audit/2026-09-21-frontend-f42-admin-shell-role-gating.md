# Audit — 2026-09-21 — F4.2 admin shell + per-tab role gating (spec [FE-01])

## Task

**F4.2** from `plan/frontend-tasks.md`: the admin shell — sidebar layout per
spec **[FE-01]** — replacing the tab bar in `admin.tsx`, with the B5.4 follow-up:
each staff role sees only the tabs it can actually act on.

## Spec check (Rule 0)

Read `design/SANDE_FULL_DEV_SPEC.md` §[FE-01] before starting.

- **Followed:** right `w-64` sidebar (first flex child in RTL); 18px linear
  lucide icons; hover soft tint + active `bg-terracotta/10`; topbar
  `h-16 border-b bg-background/95 backdrop-blur` with mobile hamburger, quick
  search, role badge («مدیر ارشد») and logout; auth guard renders the Persian
  permission error; the seven nav destinations (dashboard, products+inventory,
  orders with badge, refunds with badge, users, back-to-store).
- **Adapted:** spec's breadcrumb centre-header and admin *avatar* are not built —
  the topbar has quick search + role badge + logout only. The spec's «بازگشت به
  فروشگاه» Store item is kept. Sidebar sits in a rounded-border card (repo B0.4
  widget styling) instead of a hard `border-l` rail. `Cmd+K` opens the browser
  search focus but is not a command palette — the input is a plain search that
  navigates to `/shop?q=…` (product search already exists; a true palette would
  need the `command` primitive and is noted below).
- **Beyond spec:** per-tab role gating (the task's actual point) — the spec
  predates granular roles.

## What was done

`vogue-vintage-vibes/src/routes/_authenticated/admin.tsx` rewritten:

- **Sidebar navigation** (desktop aside + mobile right-side Sheet behind a
  hamburger) with the [FE-01] icon set (LayoutDashboard/Package/ShoppingBag/
  RotateCcw/Users + MessageSquare/Star for the two routes shipped since the spec),
  active terracotta tint, «بازگشت به فروشگاه» Store link.
- **Per-role tab gating** — `ROLE_TAB_KEYS` maps the B5.4 roles to visible tabs,
  mirroring the backend `ROLE_CAPABILITIES`:
  - `super_admin` / `admin` → all 8 tabs
  - `order_manager` → dashboard, products, inventory, orders, refunds, messages
  - `support` → dashboard, messages, reviews
  - unknown roles degrade to the read-mostly trio. The role shown comes from
    `/auth/me` (`resolve_role` → highest-privilege role). **The API remains the
    authority** — this hides what a role cannot use; it is not the security
    boundary.
- **Live badges** on سفارش‌ها (pending+processing orders) and بازپرداخت‌ها
  (pending refunds) from `api.adminKpis("all")` (60s refetch, `retry: false` so
  a 403 just means no badges), rendered with Persian digits via `toFa`.
- **Topbar**: sticky blurred bar with quick search (submits to `/shop?q=…`,
  reused on mobile above the content), role badge, logout button.
- Gate flash fixed: renders nothing while auth `loading`, then the permission
  notice for non-staff.

## Files changed

- `vogue-vintage-vibes/src/routes/_authenticated/admin.tsx` (rewritten)
- `vogue-vintage-vibes/DESIGN_SYSTEM.md` (§3.3 [FE-01] row → exists; stale [FE-03]
  row corrected)
- `plan/frontend-tasks.md`, `plan/README.md`, `plan/session-log.md`,
  `vogue-vintage-vibes/FEATURES.md`

## How to verify

```bash
cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vite build
# role matrix live (stack must be up, staff seeded via db-init):
for u in "support@sande.local staff1234" "ordermgr@sande.local staff1234"; do ...; done
# support: /admin/orders 403, /admin/contact-messages 200, /admin/kpis 200
# order_manager: /admin/orders 200, inbox 200, kpis 200
```

Sign in as `support@sande.local` / `staff1234` → only داشبورد، پیام‌ها، نظرات
appear; `ordermgr@sande.local` / `staff1234` → adds محصولات، انبار، سفارش‌ها،
بازپرداخت‌ها (with badges); `admin@sande.local` → everything.

## What is NOT done / open

- **Breadcrumbs** in the topbar centre — not built (`breadcrumb` primitive
  exists, needs a per-route title map).
- **Command palette** (`Cmd+K` overlay listing products/orders/admin actions) —
  the input navigates to shop search; palette needs `components/ui/command.tsx`.
- **Admin avatar** in the header — role badge + logout only.
- Direct URL access to a hidden tab (e.g. `/admin/users` as support) still
  renders the page shell; its data calls 403 and the screens show error/empty
  states. Route-level `beforeLoad` guards are the clean fix — deferred (needs a
  small `context` wiring through the router).
- Backend unchanged in this task; capability enforcement stays as shipped in
  B5.4 (156-check smoke).
