# UX Context Map — SÂNDÉ

> Task-scoped selection of UX rules, the counterpart of the rule-topic map in
> [`CONTEXT-MAP.md`](./CONTEXT-MAP.md) (which selects the Part B engineering
> rules 6–15). Rule content lives only in [`UX-RULES.md`](./UX-RULES.md) —
> this map lists section IDs, never rule text.
>
> How to use: find the row(s) matching the task's surfaces, union the listed
> sections with **UX-CORE** (always), and write the task's **UX Acceptance
> Criteria** from those sections (template below). If no row fits, load
> UX-CORE only and add sections as the task's concern becomes clear.

```text
task surface / concern            -> applicable UX sections (plus UX-CORE)
static display component          -> (UX-CORE only)
list/grid of remote data          -> UX-TABLE, UX-ASYNC, UX-DATA-FRESHNESS
form (create/update)              -> UX-FORM, UX-ASYNC, UX-A11Y
async mutation (any)              -> UX-ASYNC, UX-NOTIFICATION, UX-DATA-FRESHNESS
destructive mutation              -> UX-DESTRUCTIVE, UX-CONFIRM, UX-ASYNC, UX-NOTIFICATION
high-consequence typed confirm    -> UX-CONFIRM (Level 2), UX-DESTRUCTIVE, UX-ASYNC, UX-KEYBOARD
modal dialog                      -> UX-DIALOG, UX-A11Y, UX-KEYBOARD
drawer / sheet                    -> UX-DRAWER, UX-ASYNC, UX-A11Y
admin data table                  -> UX-TABLE, UX-ASYNC, UX-DATA-FRESHNESS
searchable table                  -> UX-TABLE, UX-SEARCH, UX-ASYNC
paginated list/table              -> UX-TABLE, UX-PAGINATION, UX-ASYNC
search / filter surface           -> UX-SEARCH, UX-ASYNC, UX-DATA-FRESHNESS
toast / notification copy         -> UX-NOTIFICATION
permission-sensitive UI           -> UX-PERMISSION, UX-A11Y
responsive-critical surface       -> UX-RESPONSIVE
keyboard-heavy interaction        -> UX-KEYBOARD, UX-A11Y
freshness-critical data (money,   -> UX-DATA-FRESHNESS, UX-ASYNC
stock, status)
```

Rules:

* **UX-CORE is always in scope** for frontend tasks; every other section only
  when a row above selects it.
* Union the rows when a task spans surfaces (e.g. an admin CRUD screen with a
  search + delete → UX-TABLE + UX-SEARCH + UX-PAGINATION + UX-DESTRUCTIVE +
  UX-CONFIRM + UX-ASYNC + UX-NOTIFICATION + UX-DATA-FRESHNESS + UX-A11Y +
  UX-RESPONSIVE + UX-KEYBOARD as applicable).
* Applicability is per behavior, not per file: a table without row mutations
  does not pull UX-DESTRUCTIVE; a read-only drawer does not pull UX-ASYNC.

## UX Acceptance Criteria — required pattern for frontend tasks

Frontend task entries and audits include a **UX Acceptance Criteria** block
listing only the applicable criteria, each stated as a checkable sentence and
verified at the level Rule 13 prescribes (tsc/lint/build/runtime — browser E2E
stays deferred per D10 until `ACTIVATE PLAYWRIGHT`).

```text
UX Acceptance Criteria (from UX-CONTEXT-MAP selection)
- Loading:       <what shows while the initial fetch runs; refetch behavior>
- Empty:         <empty-resource state + recovery action; no-results distinct>
- Error:         <fetch-error state + retry; failure preserves user input>
- Success:       <what invalidates/updates; toast or inline, per UX-NOTIFICATION>
- Disabled:      <which controls disable, when, and how the reason is shown>
- Validation:    <timing, first-invalid-focus, server-error mapping>
- Duplicate:     <how double submission is prevented>
- Confirmation:  <level 1 or typed; the exact rules that apply>
- Keyboard/focus:<escape behavior, initial focus, focus return>
- Accessibility: <labels, error association, accessible names>
- Responsive:    <narrow-viewport behavior of the new surface>
```

A static display component legitimately lists only Loading/Empty/Error — the
template is conditional, never padded. Audits record each criterion as
verified at its stated level or explicitly open (e.g. browser click-through
under D10).

## Design-system boundary

Visual language, tokens, component inventory and copy conventions live in
[`vogue-vintage-vibes/DESIGN_SYSTEM.md`](../vogue-vintage-vibes/DESIGN_SYSTEM.md).
Where that file describes a behavior rule, link it — do not copy it here.
A rule that describes interaction independent of styling belongs in
[`UX-RULES.md`](./UX-RULES.md).

## Maintenance

New rule → prefer an existing section in `UX-RULES.md`; a genuinely new
section ID gets a row here in the same task. This file is navigation, not
rules: it stays short enough to read whole.
