# Audit — merge `SANDE_FULL_DEV_SPEC.md` into `DESIGN_SYSTEM.md` — 2026-09-21

**Task (user request):** update `vogue-vintage-vibes/DESIGN_SYSTEM.md` with the
contents of `design/SANDE_FULL_DEV_SPEC.md`.

**Spec check (Rule 0.3):** every part of the spec that governs UI was read and,
where it applies, folded in — **B0.1–B0.5** (visual direction, palette, typography,
spacing/radii/elevation, micro-interactions), **B1.1–B1.6** (global invariants),
**B2** (directory layout / routing), **B3 [FE-01]–[FE-08]** (module specs), **B4.1–B4.3**
(reusable blocks) and **B5** (pre-flight checklist). Deliberately **not** adopted,
because the live repo wins (Rule 0.2) — and each is now written down in the new §5
precedence table instead of being silently dropped:

| Spec text | Repo reality | Verdict |
|---|---|---|
| Stack header: Lovable Cloud / Supabase SDK, `createServerFn`, `src/integrations/supabase/client` | FastAPI in `../backend` is the sole backend, `src/lib/api.ts` is the data layer, own JWT, no Supabase import | repo |
| `@/lib/order-actions.functions.ts` (`resolveRefundRequest`, …) | that file was deleted in F1.8; the same operations are API calls | repo |
| `formatPrice` / `toPersianDigits` / `formatDate` | `formatToman` / `toFa` / `formatFaDate` | repo names (same behaviour) |
| Status badge colours `bg-emerald-50 text-emerald-700` / `bg-amber-50` / `bg-rose-50` / `bg-blue-50` / `bg-purple-50` (B0.2, B4.2) | token palette is terracotta/sage/sand/gold + `destructive`; B1.1 of the same spec forbids raw palette classes | adopted as **semantics**, implemented with tokens (§2.3) |
| Toasts bottom-left (B0.5) | `<Toaster position="top-center" />` | repo |
| Never `rounded-none`/`rounded-3xl` on data widgets (B0.4) | storefront is deliberately square (`rounded-none`) and uses `rounded-3xl`/`rounded-[1.25rem]` cards | repo for existing screens; **target** for new admin widgets |
| `font-serif` / `font-mono` (B0.3) | `font-display` exists; **no mono token** in `styles.css` | target — add `--font-mono` first |
| Skeleton `bg-muted` (B4.3) | `bg-clay animate-pulse` | repo (semantic, brand-tinted) |
| Admin sidebar shell + `AdminDataTable` + `OrderDetailSheet` + `admin.refunds` + `admin.coupons` + invoice printing (B2/B3) | tab shell, no data grid, no drawer, no coupons/refunds screen, no print CSS | **target**, now tracked as F4.1–F4.5 / B5.1–B5.4 |

`design/SANDE_FULL_DEV_SPEC.md` itself was **not modified** (Rule 0.4 — it is the
user's document).

---

## What was done

Rewrote `DESIGN_SYSTEM.md` so it is one document with two clearly-labelled layers
(**Now** = true of the code · **Target** = from the spec, for new work), and made the
precedence explicit instead of leaving two contradicting documents side by side:

1. **Header** explains the two sources, the precedence rule and the Now/Target
   convention, linking `plan/RULES.md` Rule 0.2.
2. **§1 Stack** keeps the repo facts and adds a *source* column plus the spec-only
   rows (`@tanstack/react-table` **not installed**; `react-hook-form` + `zod`
   installed but unused — only the shadcn `ui/form.tsx` wrapper imports RHF; `recharts`
   unused; Supabase/Lovable/`createServerFn` explicitly marked *not part of this
   project*).
3. **§2 Tokens** — existing palette/semantic/radii/utilities kept unchanged, and the
   spec's visual rules folded in:
   - **new §2.3 status semantics** — the spec's green/amber/red *meaning* mapped onto
     this project's tokens, with the class recipe per meaning and a note that
     `terracotta` stays the brand/CTA colour while `destructive` carries negative
     state; if literal colours are wanted, add `--status-*` tokens first (§2.8);
   - **§2.5 typography** — spec's `font-serif`/`font-mono` intent mapped to
     `font-display` and the missing mono token;
   - **new §2.6 spacing/borders/elevation** (padding scale, `border-border/60`,
     `shadow-sm`/`shadow-lg`, `h-14`/`h-16` `hover:bg-muted/40` rows);
   - **new §2.7 micro-interactions** — transition timing, skeletons-never-spinners,
     the toast-position conflict, sonner reporting.
4. **§3.3 (new) admin panel: spec target vs today** — a table mapping [FE-01]…[FE-08]
   to what exists, so `admin.refunds.tsx`/`admin.coupons.tsx`/`AdminDataTable.tsx`
   read as missing rather than as if they were built.
5. **§4 Conventions** merged: the repo conventions plus the spec's B1 invariants
   (no `react-router-dom`, no `src/pages/` or `App.tsx`, semantic tokens only,
   Persian-only copy, RTL logical properties + chevron direction, mobile-first),
   forms guidance (plain state today → RHF+zod target per form), and every
   route owns a `head()`.
6. **§5 (new) Precedence: spec vs repo** — a 10-row conflict table with the binding
   side, so no future task has to re-derive Rule 0.2 for the same questions.
7. **§7 Reusable code blocks** — the spec's B4 snippets rewritten against this repo:
   `formatToman`/`toFa` instead of `formatPrice`/`toPersianDigits`, a real
   `StatusBadge` built from §2.3 tones and `ORDER_STATUS`/`PAYMENT_STATUS`, and
   skeleton/empty states using `bg-clay` + `rounded-2xl`.
8. **§8 gaps** and **§9 checklist** updated: the spec's pre-flight list (B5) merged
   into the authoring checklist, plus new gaps recorded (status semantics
   unimplemented, spec's admin surface unbuilt, no print stylesheet, missing mono
   token).
9. **New work logged** (Rule 2): `plan/frontend-tasks.md` gained **Milestone F4**
   (F4.1 status badges → F4.5 coupons manager, each with its spec reference and the
   cross-links to F2.4/F2.5/F2.6/F2.8) and `plan/backend-tasks.md` gained
   **Milestone B5** (B5.1 audit log, B5.2 KPI aggregation, B5.3 refund bank-tracking
   columns *and* the `requested` vs `pending` vocabulary mismatch, B5.4 granular
   staff roles).

Verified while writing so the doc stays truthful: `__root.tsx` mounts the toaster
`top-center`; `package.json` has no `@tanstack/react-table`; `zod` is imported
nowhere and RHF only by the unused `ui/form.tsx`; `styles.css` defines
`--font-display/--font-sans/--font-latin` and no `--font-mono`; there is no
`@media print` rule; `rounded-none` is used across checkout/cart/product/contact;
`account.orders.tsx` renders both status chips in terracotta/sand;
`refund_requests` (in `infra/initdb/02-public-schema.sql`) has only
`status`/`admin_note` — no bank tracking / resolver columns, with `status` defaulting
to `requested`.

---

## Files changed

| File | Change |
|---|---|
| `vogue-vintage-vibes/DESIGN_SYSTEM.md` | rewritten as the merged guide (Now/Target layers, §2.3 status semantics, §2.6/§2.7, §3.3 admin map, §5 precedence table, §7 repository-accurate code blocks, §8/§9 updates) |
| `plan/frontend-tasks.md` | new Milestone F4 (F4.1–F4.5) |
| `plan/backend-tasks.md` | new Milestone B5 (B5.1–B5.4) |
| `plan/audit/2026-09-21-design-system-spec-merge.md` | **this file** |
| `plan/README.md` | audit index |
| `plan/session-log.md` | Session 17 |

Doc-only change: **no code, no schema, no endpoint and no test was touched**, so
`backend/README.md`, `infra/README.md`, `vogue-vintage-vibes/README.md`,
`FEATURES.md` and `plan/feature-roadmap.md` were left untouched — no capability,
endpoint or setup step was added or removed (per Rule 5's "say so" clause).
`design/SANDE_FULL_DEV_SPEC.md` untouched (Rule 0.4).

---

## How to verify

```sh
cd vogue-vintage-vibes
grep -n "^## \|^### " DESIGN_SYSTEM.md        # section map survives the merge
grep -n "Target\|Now" DESIGN_SYSTEM.md | head  # the two layers are labelled
sed -n '/## 5. Precedence/,/^---/p' DESIGN_SYSTEM.md   # the conflict table
grep -rn "emerald\|amber-50\|rose-50" DESIGN_SYSTEM.md # only inside §5 as the spec's text
```

Then check the two spot claims that the doc makes about the code:

```sh
grep -n "Toaster" src/routes/__root.tsx                     # position="top-center"
grep -n "react-table" package.json || echo "not installed"  # → not installed
grep -n "font-mono" src/styles.css || echo "no mono token"   # → no mono token
grep -rn "@media print" src/styles.css || echo "no print css"
```

Anything newer than this task should update §3.3/§5 when a spec module lands — the
tables are the single place that knows which spec section is real.

---

## What is NOT done / open

- **The spec is still not reconciled at the source.** Its stack header, its
  `order-actions.functions.ts`/`formatPrice`/`toPersianDigits` references, its raw
  palette status classes and its Part C status table remain stale in
  `design/SANDE_FULL_DEV_SPEC.md` — §5 of `DESIGN_SYSTEM.md` now carries the
  corrections, but anyone reading the spec alone still sees the old stack. Editing it
  is the user's call (Rule 0.4).
- **No implementation.** §2.3 status semantics, `--font-mono`, the print stylesheet,
  the sidebar shell, the data grid, the refunds/coupons screens and the audit log are
  all specified but **not coded**; they are now F4.1–F4.5 and B5.1–B5.4.
- **The spec's own internal contradiction is resolved by convention, not by the
  spec:** B0.2/B4.2 prescribe raw Tailwind palette classes while B1.1 forbids them.
  §2.3 documents the adopted reading (meaning from the spec, tokens from the repo);
  if the user prefers literal green/amber/rose, that is a one-line change to the
  token set plus a §2.3 rewrite.
- **`rounded-*` and toast-position decisions are recorded but not enforced** — no
  lint rule stops a new admin widget from using `rounded-none`; the checklist (§9) is
  the only guardrail.
- **No screenshots or visual diff** — this task touched only markdown.
