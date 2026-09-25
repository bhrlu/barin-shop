# UX Rules — SÂNDÉ frontend behavior contract

> Canonical UX **behavioral** rules. They govern interaction states, async
> behavior, confirmation, accessibility — not visual styling (that is
> [`vogue-vintage-vibes/DESIGN_SYSTEM.md`](../vogue-vintage-vibes/DESIGN_SYSTEM.md);
> tokens, component look and copy conventions stay there).
>
> **Selection, not full reads.** A task loads only the sections picked for it by
> [`UX-CONTEXT-MAP.md`](./UX-CONTEXT-MAP.md), exactly as the Part B rules are
> selected through [`CONTEXT-MAP.md`](./CONTEXT-MAP.md). `UX-CORE` applies to
> every frontend task; everything else only when the map selects it.
>
> **Verification**: browser E2E is deferred (decision D10 — activation phrase
> `ACTIVATE PLAYWRIGHT`). Until then, rules marked ⟦PW⟧ carry a *future
> executable assertion* comment so they can become browser acceptance criteria
> verbatim after activation. Current verification levels per Rule 13 (tsc,
> lint, build, runtime/manual probes) still apply.

---

## UX-CORE — states every surface must define (all frontend tasks)

Every data surface must be explicit about these five states; "blank while
loading / nothing while empty" is not an implementation.

1. **Loading** — the initial fetch shows an in-place loading treatment
   (skeleton, spinner or `aria-busy` placeholder in the affected region — the
   design system's skeleton classes are the default visual). Already-loaded
   content stays visible and usable during background refetches
   (`keepPreviousData`-style behavior); a refetch never blanks a populated
   screen. Full-page blocking loaders only for first auth bootstrap.
2. **Empty vs. error vs. not-loaded are distinct states** — an empty resource
   renders a purposeful empty state (what this is, why it may be empty, one
   recovery action); it must never render as an error, and an error must never
   render as empty.
3. **Error** — a failed fetch shows an in-place error state with a retry
   control where a retry can succeed. Error copy is user-actionable Persian;
   raw statuses, stack traces, SQL/internal detail never surface (Rule 13's
   error-path list applies to UI too).
4. **Disabled** — a disabled control is visually distinct and explained
   (`title`/`aria-label`/helper text or an adjacent message: *why* it is
   disabled and, where one exists, how to change it). If a control cannot
   become enabled by user action in this view, prefer removing or hiding it
   (see UX-PERMISSION).
5. **Regional refresh** — mutations and refetches invalidate and refresh only
   the affected data regions (React Query key invalidation, canonical keys),
   never a full-page reload for state that a targeted refetch can update.

Every list/table/detail surface states which of these apply; a task's UX
Acceptance Criteria (see UX-CONTEXT-MAP) lists them explicitly.

---

## UX-FORM — forms and validation

1. **Initial state** — a form opens clean: empty/initial values, no error
   messages, submit enabled iff the form is valid by default (or disabled with
   a visible reason until required input exists).
2. **Validation timing** — validate a field after first blur or first
   submit attempt, then live on change for that field. Never show a required
   error before the user has interacted with the field or attempted submit.
3. **Invalid submit** — submitting an invalid form shows the errors, focuses
   the first invalid field, and performs no request. ⟦PW⟧
   *assertion: no network request fired; first invalid field is focused.*
4. **Error association** — each field error is associated with its input
   (`aria-describedby`/`aria-invalid`) and is human-readable Persian; server
   validation errors map back to their fields where the API identifies them.
5. **Input preservation** — validation or submission failure preserves all
   user input exactly. No rule may clear a form as a side effect of a failed
   submit.
6. **Server-side validation is reported, not invented** — a 4xx field error
   surfaces in/near the field; a 5xx/network failure surfaces as a form-level
   error with a retry. The client never claims success the server did not
   confirm, and never silently drops the submission.
7. **Submit state** — while pending, the submit control shows its pending
   state and further submits are ignored (see UX-ASYNC). Cancel/close during
   pending either aborts cleanly or is blocked with a visible pending reason —
   pick one per form and state it.
8. **Reset/cancel** — cancel leaves committed state untouched; navigation
   away from a dirty form either confirms or is explicitly documented as safe
   (autosaved forms state this).
9. **Required fields** — marked accessibly (`aria-required` or equivalent)
   and visually; the definition of "required" comes from the API contract,
   not invented client-side.

---

## UX-ASYNC — async mutations

Every mutation has the explicit state model:

```text
idle → pending → success | error
```

1. **One canonical mutation mechanism** — TanStack Query `useMutation` +
   the canonical `src/lib/api.ts` client. No ad-hoc fetch-and-setState
   mutation paths, no second notification mechanism.
2. **Pending** — the triggering control enters its pending state (spinner or
   disabled-with-pending-label) and further activations are ignored while
   pending. ⟦PW⟧ *assertion: double-click issues exactly one API call.*
3. **Duplicate submission** — every mutating action is idempotent from the
   user's perspective: a second click, Enter or double submission produces one
   request or a guarded repeat, never two visible effects.
4. **Input during pending** — form inputs stay editable unless the operation
   is short and idempotent; if inputs are frozen during pending, that is
   stated in the task's UX Acceptance Criteria.
5. **Success** — reflected in actual state first (canonical invalidation of
   the affected keys), then optionally communicated (`UX-NOTIFICATION`); a
   success message must never contradict server state.
6. **Error** — surfaced per UX-FORM.6/UX-CORE.3; the mutation surface remains
   usable for a retry; no partial local state writes on failure.
7. **No optimistic writes without a task-level decision** — pessimistic is
   the default; if a task adopts optimistic updates, its acceptance criteria
   must state the rollback behavior on error.

---

## UX-CONFIRM — confirmation

Two levels; a task states which one applies (per
[`UX-CONTEXT-MAP.md`](./UX-CONTEXT-MAP.md)).

**Level 1 — normal confirm dialog** (default for low-risk mutations):
consequence is stated, Cancel is the safe default, confirm performs the
mutation per UX-ASYNC.

**Level 2 — typed confirmation** (high-consequence: irreversible, security,
or bulk-affecting actions). The canonical in-repo implementation is the
`RolesDialog` two-step pattern in `admin.users.tsx`. Rules:

1. Confirmation input MUST start empty. ⟦PW⟧ *assertion: `toHaveValue("")`*
2. The required phrase MUST be displayed explicitly next to the input.
3. The required phrase MUST NOT be prefilled, hinted as autofill value, or
   remembered by the browser (`autocomplete="off"` where supported). ⟦PW⟧
   *assertion: input has no autofill value*
4. Submit MUST remain disabled until the exact required phrase is entered.
   ⟦PW⟧ *assertions: disabled initially → disabled after a wrong phrase →
   enabled only after the exact phrase*
5. Incorrect input MUST NOT enable submit; matching is defined by the
   component (the `RolesDialog` convention: trim + case-insensitive) and MUST
   be stated in the component, not improvised per task.
6. Pending state MUST be visible on the confirm control.
7. Duplicate submission MUST be prevented (UX-ASYNC.2).
8. Cancel/close MUST leave the mutation uncommitted — no partial effects, no
   background request. ⟦PW⟧ *assertion: cancel → no API call fired*
9. Escape/outside-click during pending MUST NOT silently drop the request:
   either block dismissal while pending or let it close and surface the
   outcome — one behavior, stated, per component.

---

## UX-DESTRUCTIVE — destructive actions

Applies to deletes, cancels of committed resources, role/tier revocations,
and any action the user cannot undo in the UI.

1. **Consequence visibility** — the trigger or dialog states what will be
   lost ("حذف", "لغو سفارش", affected count/name), never a generic "confirm".
2. **Confirmation** — per UX-CONFIRM; typed confirmation only when justified
   (irreversible, security, or bulk); do not add typing friction to low-risk
   actions.
3. **Pending** — the action shows pending and cannot be re-triggered.
4. **Failure** — an error leaves the resource intact and states that it is
   intact; the destructive flow is retryable.
5. **Post-success sync** — on success the affected rows/items disappear or
   update via canonical invalidation; counts and summaries refresh; the
   mutated row's stale state is never displayed as current.

---

## UX-DIALOG — modal dialogs

Implementation: the repo's `components/ui/dialog` / `alert-dialog` primitives
(no second modal system).

1. Open/close is explicit state; `Escape` closes unless pending or unless a
   step in progress requires explicit cancel (then `Escape` is inert or
   blocked, stated per component).
2. Initial focus lands on the first interactive field/control; focus stays
   trapped while open and returns to the opener on close.
3. Background content is inert while open (native primitive behavior — do
   not rebuild it).
4. Cancel never commits; submit follows UX-ASYNC; pending state visible on
   the triggering control.
5. Validation errors render inside the dialog and do not close it.
6. Accidental-dismissal protection: forms with meaningful user input require
   explicit cancel or a confirm-lose-changes step; read-only dialogs may
   close freely.

---

## UX-DRAWER — drawers / sheets

Implementation: the repo's `components/ui/sheet` primitive (canonical: the
admin order drawer, `CustomerProfileDrawer`).

1. **Parent page state is preserved** — the page behind the drawer keeps its
   scroll, filters, selection and query cache; closing returns to it exactly.
2. **Each section inside states its own state** — loading, error (with
   retry), and empty per UX-CORE; a failing section must not blank the whole
   drawer.
3. **Mutations inside a drawer** follow UX-ASYNC and invalidate the drawer's
   data and the parent list it came from.
4. **Close behavior** — `Escape`/scrim closes when safe; while a mutation is
   pending the same rule as UX-CONFIRM.9 applies.
5. **Focus** — initial focus enters the drawer; focus returns to the opener
   row/control on close.
6. **Narrow viewports** — the drawer becomes full-width (or full-height)
   rather than clipping content; content scrolls within the panel.

---

## UX-TABLE — data tables

Canonical component: `components/admin/AdminDataTable.tsx`. No second table
system (Rule 7).

1. **States** — the table implements loading (rows or skeleton region),
   empty (`emptyMessage`), no-results-after-filter (distinct from empty —
   offer clearing the filter), and error (with retry) per UX-CORE.
2. **Row actions** — every action is enabled, pending, or disabled-with-
   reason; a pending row action locks only its own row, not the table.
3. **Mutation sync** — a mutation through a table (delete, status change,
   toggle) invalidates the table's query key; the row updates or leaves the
   current page truthfully. Pending state is visible on the row/control.
4. **State persistence** — search, filters, sorting and page survive row
   mutations and detail open/close; they reset only by explicit user action
   (unless URL state dictates otherwise — see UX-SEARCH/UX-PAGINATION).
5. **Selection** (bulk) — selection is visible, count-labelled, and cleared
   on data reload that invalidates it; bulk actions follow UX-DESTRUCTIVE
   when irreversible.

---

## UX-SEARCH — search and filtering

1. **Empty query** — an empty/cleared search shows the default (unfiltered)
   listing, never an error or a frozen previous result.
2. **No results** — a no-result state offers clearing the search/filters;
   it is visually distinct from an empty resource.
3. **Debounce** — free-text search is debounced (~300ms) or
   request-cancelled; stale responses never overwrite newer ones. The
   canonical implementation is `HeaderSearch`'s debounced pattern.
4. **Filter persistence** — filter state lives in the URL when the route
   already uses URL search params (`validateSearch`, e.g. `/shop`,
   `/admin/inventory`); a surface without URL state does not gain it as a
   side effect of this rule.
5. **Clearing** — one control or affordance clears the active filters; the
   cleared state is the default listing.

---

## UX-PAGINATION — pagination

Canonical envelope: backend `pagination.py` / frontend `toPage()`; the
canonical UI is the `Pager` component.

1. **Page state** — current page is part of the route state (URL param where
   the route uses `validateSearch`) and survives refresh and navigation.
2. **Loading transitions** — page changes keep the table shell and show the
   loading region (UX-CORE.1); they never blank the whole screen.
3. **Invalidation** — mutations that add/remove items invalidate the list
   query; counts/pages update truthfully.
4. **Invalid current page** — if the current page exceeds the last page
   (after deletion/filtering), the UI lands on the nearest valid page (or
   shows the empty-page state with a way back to page 1); it must not render
   a perpetually empty grid.
5. **Filters/search preserved** — page changes preserve active
   filters/search; filter changes reset to page 1.

---

## UX-A11Y — accessibility

1. **Keyboard reachability** — every interactive control is reachable and
   operable by keyboard in a logical order; no keyboard trap outside
   intentional modal patterns (UX-DIALOG.2).
2. **Focus visibility** — focus is always visible (the design system's focus
   ring); focus is never removed without a replacement.
3. **Accessible names** — icon-only controls carry an `aria-label` (the
   in-repo convention: all icon buttons do); interactive elements have names
   that survive translation.
4. **Labels & errors** — inputs have associated labels; errors are
   programmatically associated (UX-FORM.4); state changes that matter are
   announced via `aria-live` where the primitive does not already do it.
5. **Semantics** — real buttons/links/inputs (not styled `div`s with click
   handlers); a control that navigates is a link, one that acts is a button.
6. **Disabled vs. unavailable** — a disabled control is excluded from
   interaction but still discoverable (title/aria-label explanation,
   UX-CORE.4); do not disable-to-hide.
7. **RTL** — direction-safe layouts (logical properties) and Persian-first
   copy per spec B1; digits through the canonical `toFa`.

---

## UX-KEYBOARD — keyboard interaction

1. Primary actions respond to `Enter` in forms (submit) and `Space`/`Enter`
   on buttons (native); custom widgets implement the same activation.
2. `Escape` closes the topmost dialog/drawer per UX-DIALOG.1/UX-DRAWER.4.
3. Increment steppers and quantity controls are keyboard-operable
   (`+`/`−` buttons are real buttons, not pointer-only).
4. Focus order matches visual/reading order (RTL-aware).
5. Keyboard shortcuts (if any are added) must be documented in the
   component and must not shadow browser/AT defaults.

---

## UX-RESPONSIVE — responsive behavior

1. **Narrow viewport** — every screen is usable at mobile width: content
   reflows or scrolls, no horizontal page scroll (overflowing tables scroll
   or collapse to cards, per the existing admin pattern).
2. **Dialogs/drawers** — full-width or near-full-width at small sizes, never
   clipped (UX-DRAWER.6).
3. **Action groups** — wrap or collapse on narrow screens without losing
   access to any action (no action becomes unreachable at mobile width).
4. **Forms** — single-column where the existing forms do; inputs keep ≥
   touch-target size and their labels visible.
5. **Long content** — names, emails, IDs and prices wrap/truncate with a
   usable fallback (title/expand) rather than breaking layout.
6. Behavior rules only — breakpoints/tokens stay in the design system.

---

## UX-NOTIFICATION — toasts & notifications

Canonical mechanisms: `sonner` toasts for immediate action feedback; the
D2 in-app/SMS/email notification system (backend) for record-scoped events.
Never introduce a second mechanism (Rule 7).

1. **When** — a toast confirms/fails a user-initiated mutation (UX-ASYNC.5)
   or explains a blocked action. Local visual state (tab opened, panel
   collapsed) does not get toasts.
2. **Not for trivial local state** — no toasts for UI-only state changes.
3. **Truthful** — success copy only after the server confirms; error copy
   reflects the actual failure class (403 gets its own message per the
   `RolesDialog` convention) and never invents a reason.
4. **No spam** — repeated identical failures do not stack identical toasts
   unboundedly (dedupe or replace); lists of errors are summarized, not
   one-toast-per-item, when items exceed a handful.
5. **Record-scoped events** (order shipped, notification created) belong to
   the D2 notification system, not toasts; toasts never substitute for it.

---

## UX-PERMISSION — permission-controlled UI

Backend authorization is authoritative (Rule 9). This layer is UX only and
never a boundary.

1. **Visibility follows capability** — hide or disable actions the current
   actor's capabilities cannot perform (the admin shell's capability gating
   is canonical); hidden nav and disabled buttons are not authorization
   (AGENTS.md invariant, unchanged).
2. **401** — an expired/absent session routes to sign-in (the F5.15
   convention: a failed `/auth/me` signs the user out).
3. **403** — surfaces a permission-specific message (canonical: the
   `RolesDialog` 403 copy pattern), not a generic failure, and never a
   silent no-op.
4. **Unauthorized direct entry** — direct URL access to a gated route
   renders the guarded shell/redirect per the existing route guards
   (`_authenticated`, admin role guard); the UI never relies on nav-hiding.
5. **Disabled vs hidden** — an action the user could gain capability for in
   this view may stay visible-disabled with a reason; one they can never
   perform should be hidden (UX-CORE.4).

---

## UX-DATA-FRESHNESS — data freshness & staleness

1. **Authoritative source** — displayed money/stock/status come from server
   payloads (`/stock/check` quote, order payloads), never from stale client
   computation (Rule 11 / F5.18 convention).
2. **Refetch on focus/visibility** — list and detail queries refetch on
   window focus (the cart-quote convention) so a second tab/actor's change
   becomes visible.
3. **Mutation invalidation** — every mutation invalidates the canonical
   query keys of everything it changes (including derived views, e.g.
   admin list + audit log after a role change).
4. **Stale display guard** — when showing data that may be stale during a
   refetch, keep the old data visually marked as refreshing
   (`keepPreviousData` + subtle pending affordance), never swap in a
   skeleton over populated content (UX-CORE.1).
5. **Timestamps** — relative/freshness hints use the canonical formatters;
   raw ISO strings never surface to users.

---

### Cross-cutting writing rules for this file

- MUST/SHOULD language is contractual; each rule is phrased to be checkable
  in review or (later) by a browser assertion.
- Persian copy examples are illustrative; the copy source of truth is the
  components themselves.
- New rules get added to existing sections when possible; a new section ID
  requires updating `UX-CONTEXT-MAP.md` in the same task.
