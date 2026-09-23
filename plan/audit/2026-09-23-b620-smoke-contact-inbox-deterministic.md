# Audit — B6.20 Smoke contact-inbox checks skipped silently under the rate limit (2026-09-23)

## Task

`B6.20` (P3, Batch C), found during B5.1c. `tests/api_smoke.py` ran its
contact-inbox checks (mark answered, bogus-status 422, cleanup) only when a `new`
message existed. Its own `POST /contact` is limited to 5 per 10 minutes per IP
(B3.11), so on back-to-back runs the block vanished: 6 entries, with no FAIL. Two
runs minutes apart reported 247 and 245 entries. Part of the "continue the whole
backlog" run.

## Spec check (Rule 0)

No spec section covers the smoke harness. RULES R13 ("never claim a suite you didn't
run") is the reason for this task: a check that silently does not run reads as green.

## Recon

- `POST /contact` returns 201 with the message `id`; 429 when the window is spent.
- Attempts are counted in `public.contact_attempts` (DB, per IP).
- The old block also **deleted whichever message was `new`**, which on a shared dev
  database could be someone else's.
- The rate limit itself is correct and was not touched (no weakened validation, R13).

## What was done (`tests/api_smoke.py` only)

- The block exercises **this run's message when its POST succeeded, else any existing
  message**, and restores that message's original status afterwards.
- A new explicit check, «contact inbox has a message to exercise», FAILs when there is
  nothing to test instead of skipping.
- **One smoke message is kept as the fixture** for later throttled runs. The run's own
  message is deleted only when an older smoke message exists, and a message the run
  did not create is never deleted.

## Files changed

- `backend/tests/api_smoke.py`
- docs: this audit, `plan/MASTER-BACKLOG.md`, `plan/backend-tasks.md`,
  `plan/session-log.md`, `plan/README.md`

## How to verify

1. **Before the fix was complete:** with the dev inbox empty and the IP throttled,
   the first version reported the new check as **FAIL** (`own=rate-limited inbox=0`),
   not a silent skip.
2. After clearing this dev machine's `contact_attempts` (a spent window), **four
   back-to-back runs**:
   - run 1: `own=yes`, the message is kept;
   - runs 2–3: `own=yes`, a second smoke message is deleted;
   - run 4: `own=rate-limited`, the kept fixture is exercised.

   All 4 are **0 failed**, and the **set of checks is identical across the four runs**
   (same hash). The only difference in totals (251/252) is the conditional cleanup
   `DELETE` call.
3. `ruff` clean. No product code changed, so pytest is unaffected.

**Verification level:** locally tested (the smoke harness itself).

## What is NOT done / open

- **An empty inbox and a throttled IP can still FAIL.** That is on purpose: honest
  instead of silent. On a clean environment the first run's POST always succeeds, and
  the kept message covers every later run.
- Product code and docs: untouched.
