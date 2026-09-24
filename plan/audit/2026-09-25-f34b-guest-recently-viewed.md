# Audit — 2026-09-25 · F3.4b Guest recently viewed

## Task

Continuous backlog execution, task selected from the canonical JSON index
(`agent_start_task` / START HERE): **F3.4b — Guest recently viewed** — store up
to 8 guest product ids/timestamps in `localStorage` and merge deterministically
into the account history on sign-in (resolved decision D7(c)).

## Spec check (Rule 0)

- Section-scoped: D7(c) is the governing decision (8 entries, dedupe, newest
  wins, server authoritative after merge, no DELETE endpoint required). The
  storefront rail conventions follow the existing `RecentlyViewedRail` /
  `ProductRail` pattern. The spec file was not edited.
- Followed: Rules 0–5; Part B 6, 6a, 7, 8, 12, 13, 15 (no new endpoint, no
  authz change, no money/stock).
- Deliberately ignored: none.

## What was done

1. **New canonical store** `vogue-vintage-vibes/src/lib/recently-viewed.ts`
   (no prior lib existed for this — nothing duplicated):
   - `recordGuestView(id)` — dedupe by product id, newest view wins, capped at
     8 (`RECENTLY_VIEWED_LIMIT`), timestamped epoch ms;
   - `readGuestHistory()` — tolerant reader (corrupt/unparsable JSON resets to
     empty, shape-validated entries, sorted newest-first);
   - `mergeGuestHistoryOnSignIn()` — deterministic D7(c) merge: replays the
     ≤8 guest ids through the **existing** `POST /products/{id}/view`
     (oldest-first, so the newest guest view is written last and wins in the
     server table too), drops unknown ids silently (404), then clears the
     local list — the server history is authoritative afterwards;
   - `guestHistoryProducts(limit)` — resolves guest ids through the catalogue.
2. **Product page** (`product.$id.tsx`): the existing view effect now branches
   — signed-in visitors keep calling the server view endpoint; guests write
   `recordGuestView` and invalidate the rail key. No new fetch, no new API
   method.
3. **Rail** (`RecentlyViewedRail.tsx`): now renders for everyone — signed-in
   reads the authoritative `GET /recently-viewed`; guests read their
   localStorage history. Query key `[\"recently-viewed\", limit, user?.id ??
   \"guest\"]`. Import cycle deliberately avoided: the store module does not
   import auth; the hook lives in the rail (its only consumer).
4. **Sign-in merge** (`auth.tsx`): `signIn` awaits `mergeGuestHistoryOnSignIn()`
   **before** setting user state, so the rail's first server fetch is already
   the merged result (best-effort: a merge failure never blocks sign-in).

No new backend endpoint, no `api.ts` change, no dependency, no schema change —
the merge reuses the canonical view endpoint exactly as D7(c) intended.

## Files changed

- `vogue-vintage-vibes/src/lib/recently-viewed.ts` (new canonical store)
- `vogue-vintage-vibes/src/components/product/RecentlyViewedRail.tsx` (guest-aware)
- `vogue-vintage-vibes/src/routes/product.$id.tsx` (guest view recording)
- `vogue-vintage-vibes/src/lib/auth.tsx` (merge on sign-in, one call)
- `plan/frontend-tasks.md`, `plan/MASTER-BACKLOG.md`, `plan/session-log.md`,
  `plan/audit/2026-09-25-f34b-guest-recently-viewed.md` (this file)

## How to verify

- `bun run lint` → 0 errors (14 pre-existing warnings unchanged);
  `tsc --noEmit` → 0 errors; `bun run build` → exit 0.
- Merge semantics on the live stack: guest views replayed oldest-first through
  `POST /products/{id}/view` → `GET /recently-viewed` contains both ids and
  orders by newest replayed view (verified with real seed products: newest
  guest view first).
- Manual browser path (D10 still deferred — no automation): browse signed out →
  open 2–3 product pages → «بازدیدهای اخیر» appears for the guest from
  localStorage → sign in → the same products appear from the merged server
  history; viewing a product while signed in keeps the server history current.

## What is NOT done / open

- Interactive browser click-through (D10 gate unchanged).
- The `GET /recently-viewed` endpoint still has no DELETE; D7(c) explicitly
  rules that out of scope for this task.
- Verification level: **integration tested + build verified**.
