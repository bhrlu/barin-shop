# Audit — AB-FE-01 Admin topbar completion (2026-09-23)

## Task

`AB-FE-01` (P2, Batch D). Build on the existing F4.2 shell. Required:

- breadcrumbs;
- staff profile/avatar actions;
- command/quick actions where appropriate;
- a storefront preview link;
- responsive details.

Do not rewrite `AdminLayout` or replace the role-gated shell. Verification: desktop,
mobile and multiple roles. Part of the "continue the whole backlog" run.

## Spec check (Rule 0)

Followed:

- **`[FE-01].2` top bar:**
  - `h-16 border-b bg-background/95 backdrop-blur` (unchanged);
  - hamburger on the right;
  - centre: breadcrumbs + global quick search with `Cmd+K`/`Ctrl+K`;
  - far left: admin avatar, role badge «مدیر ارشد…», logout.
- **`B1`:** Persian copy, RTL, tone recipes only (terracotta/sage tokens, no raw
  palette classes).

Deliberately not followed:

- The spec's file location `components/admin/AdminLayout.tsx`. The shell lives in
  `routes/_authenticated/admin.tsx` and the task forbids moving or rewriting it.
- The stack header, as always.

## Recon (Rules 6–9)

- **Owning module:** `routes/_authenticated/admin.tsx` (F4.2 shell): `ALL_TABS`,
  `ROLE_TAB_KEYS` (mirrors backend `ROLE_CAPABILITIES`), `currentTab`/`tabAllowed`,
  quick search → `/shop?q=`, role badge, logout.
- **UI primitives already in `components/ui`:** `breadcrumb`, `avatar`,
  `dropdown-menu`. They were unused in the app, so Vite pre-bundled
  `@radix-ui/react-avatar` and `@radix-ui/react-dropdown-menu` on first use.
- **Gap found:** the search placeholder has advertised «(Ctrl+K)» since F4.2, but
  nothing listened for it.
- **Data:** `useAuth().user` (`full_name`, `email`, `role`). `avatar_url` is never
  displayed anywhere and has no upload UI; it may also be an unsigned storage path.
  The avatar therefore shows initials only.
- **Security:** nothing new is authorised by the UI. The avatar menu links only to
  the user's own `/account` pages. Role gating (tabs and the permission notice)
  is untouched.

## What was done (`admin.tsx` only, additive)

- **Breadcrumbs:** «پنل مدیریت › <section>», with a `ChevronLeft` separator for RTL.
  The page crumb is the only `aria-current="page"`:
  - on the dashboard the root crumb is plain text;
  - elsewhere it is a `Link` with `activeOptions={{ exact: true }}`.

  This is needed because TanStack's `Link` marks itself current when active, and
  without `exact` `/admin` is active on every admin page. The browser test caught
  two "current" crumbs before this fix. On phones only the section crumb shows,
  truncated.
- **Avatar menu** (`DropdownMenu dir="rtl"`):
  - trigger: initials avatar (first letters of up to two name words, else the
    email's first letter);
  - content: name, email (LTR, right-aligned), role label;
  - links: «حساب کاربری من» (`/account`) and «اعلان‌ها» (`/account/notifications`).

  The existing logout button stays next to it, as the spec lists them separately.
- **Storefront preview:** `<a href="/" target="_blank" rel="noopener noreferrer">`
  «مشاهدهٔ فروشگاه», icon-only below `md`. The sidebar's same-tab «بازگشت به
  فروشگاه» is unchanged.
- **Ctrl+K / ⌘K** focuses and selects whichever quick-search box is visible: the
  header box from `lg` up, the in-page box below. It matches `event.code === "KeyK"`,
  because on the Persian layout the key reports `«ن»`. Alt/Shift combinations are
  ignored.
- **Responsive:** the role badge hides below `sm` and appears in the avatar menu
  instead. The header keeps `h-16` at 390 px with no horizontal overflow.

## Files changed

- `vogue-vintage-vibes/src/routes/_authenticated/admin.tsx`
- docs:
  - `vogue-vintage-vibes/DESIGN_SYSTEM.md` (FE-01 row);
  - `vogue-vintage-vibes/FEATURES.md` (row ۴.۱.۱);
  - this audit;
  - `plan/MASTER-BACKLOG.md` (+F5.17), `plan/frontend-tasks.md` (+F5.17),
    `plan/session-log.md`, `plan/README.md`.

## How to verify

Browser script (Playwright, dev server): **70 checks, 0 failed**. It covers three
staff roles (admin «مدیر», order_manager «مدیر سفارش‌ها», support «پشتیبانی») at
1366 px and 390 px, plus a customer.

- **Crumbs:**
  - `/admin` reads «پنل مدیریت داشبورد», with exactly one current crumb;
  - on an allowed page (`/admin/users`, `/admin/orders`, `/admin/messages`) the root
    crumb links to `/admin` and the section crumb is the only current one;
  - clicking the root crumb goes to the dashboard;
  - forbidden page (order_manager → `/admin/users`, support → `/admin/orders`):
    correct crumb plus the existing «نقش «…» به این بخش دسترسی ندارد» notice.
- **Role badge and avatar:**
  - the role badge text is right for each role;
  - avatar initials match the name from `/auth/login`;
  - the menu shows the email and role and stays on screen;
  - «حساب کاربری من» → `/account`.
- **Preview:** `href="/"`, `target=_blank`, `rel` contains `noopener`. The click
  opens `/` in a new tab and the admin tab stays on `/admin`.
- **Shortcut and search:**
  - Ctrl+K, ⌘K and Ctrl+K with the key reported as «ن» all focus the header search;
  - the quick search still submits to `/shop?q=…`.
- **Mobile:**
  - the root crumb is hidden and the section crumb shown;
  - the role badge is not in the header but is in the menu, and the menu fits
    390 px;
  - the preview link is icon-only;
  - Ctrl+K focuses the in-page search;
  - the header is 64 px with no overflow.
- **Logout and customer:** logout still clears the token and goes to `/`. The
  customer on `/admin` still gets «حساب شما دسترسی مدیریت ندارد».
- No page errors.
- Screenshots were reviewed: desktop `/admin/orders`, mobile `/admin/users`, and the
  mobile menu open.

Gates (frontend container):

- `prettier --check` clean;
- `tsc --noEmit` clean;
- `bun run lint` 0 errors / 16 warnings (unchanged);
- `bun run build` OK.

No backend change.

**Verification level:** browser tested.

## Found on the way

- **F5.17 (new, P3):** `admin.coupons.tsx` exports its page component
  (`export function AdminCoupons`). Nothing imports it, but the export stops TanStack
  from route-splitting the page (dev warning: «These exports … will not be
  code-split»). The production build confirms that the whole coupons page (list,
  card and dialog) sits in the shared `index-*.js` that every storefront visitor
  downloads. Not fixed here (R12).

## What is NOT done / open

- **No command palette.** "Command/quick actions where appropriate" was met with
  the real Ctrl/⌘+K search shortcut. A cmdk palette listing admin actions was not
  built: the quick search is the only global action the shell has, and one
  shortcut to it covers the spec.
- **Quick search target unchanged.** It still searches the storefront
  (`/shop?q=`). An admin-side search needs a backend admin search endpoint; that
  was not in scope.
- **No avatar image.** `avatar_url` has no upload UI and may be a storage path.
- `README.md`, `feature-roadmap.md`: untouched.
