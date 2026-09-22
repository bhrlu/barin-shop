# B3.11 — Contact-form spam guard

**Date:** 2026-09-22 · **Task:** `B3.11` (P1, Batch F, `plan/MASTER-BACKLOG.md`,
`plan/backend-tasks.md`; product decision **D1**) · **Layer:** backend + DB, plus
the honeypot field in the contact form, compose/env wiring, and a fix to the
shared client-IP resolver

## Task

`POST /contact` was a public, unauthenticated, unbounded INSERT. D1 fixed the
remedy:
* a PostgreSQL-backed per-IP throttle of **5 attempts per 10 minutes**, where
  accepted and rejected attempts both count;
* a honeypot field;
* no Redis, no CAPTCHA, no second rate-limit framework;
* the same boundary for guests and signed-in users;
* responses that do not expose the mechanism.

## Spec check (Rule 0)

* **Spec** — no section covers contact-form abuse. Part C lists no such feature.
  The governing documents are D1 in the Master Backlog and the full-backlog audit
  (it calls this "a public-deploy blocker"). **B1.4** was followed: every new
  user-visible string is Persian.
* **Deliberately not followed** — the spec's stack header (Supabase RLS/Edge
  Functions). The throttle is plain FastAPI + Postgres, as D1 requires.

## Architecture check (Rules 6–11)

* **Owning modules:**
  * `app/routers/contact.py`;
  * new `app/services/contact_guard.py` (the throttle — no existing rate-limit
    primitive; `grep -rn "rate.limit\|throttle" app` was empty);
  * new `app/services/client_ip.py` (IP resolution);
  * `app/db.py` (`CONTACT_DDL`), `app/config.py`, `app/schemas.py`;
  * `src/routes/contact.tsx` + `api.contact`.
* **Data flow:** contact form → `api.contact()` → `POST /contact` → middleware
  resolves the client IP into `audit.client_ip_ctx` → `contact_guard.record_attempt`
  (advisory lock, window count, attempt row) → message INSERT or 429/400.

### Contract

Additive only; the existing shape is unchanged.

* **Body:** `{name, contact, message}` plus the optional honeypot `website`
  (≤200 chars). The OpenAPI schema carries no description of it, because the
  schema is public.
* **201:** `ContactMessageOut`, as before.
* **422:** schema errors, as before. They never reach the handler, so they are not
  counted.
* **400:** `{"detail": "ارسال پیام ممکن نشد؛ لطفاً دوباره تلاش کنید."}` when the
  honeypot is filled. Nothing is stored.
* **429:** `{"detail": "تعداد پیام‌های ارسالی زیاد است؛ لطفاً کمی بعد دوباره تلاش
  کنید."}` when throttled. No `Retry-After`, no counts, no mechanism words
  (asserted).

### Security (R9): the IP is the whole control

* **What recon found:** the only client-IP resolver, the B5.1a audit middleware,
  took the **first `X-Forwarded-For` entry unconditionally**. Its docstring
  justified that with "the backend always sits behind the compose proxy". But
  there is no proxy in the repo: compose publishes the backend on
  `0.0.0.0:8000`, and browsers call it directly (`VITE_API_URL`). So XFF is
  entirely client-controlled. A throttle keyed on it could be bypassed by
  rotating the header, and the audit trail's IPs could be forged.
* **Fix, in place (R7):** `resolve_client_ip()` believes XFF only when the socket
  peer is inside `TRUSTED_PROXIES`. That setting is a comma-separated list of IPs
  and CIDRs, empty by default. The chain is walked **right to left**, and the first
  hop that isn't a trusted proxy is the client. Malformed hops fall back to the
  peer. If every hop is trusted, it's an internal client and the leftmost hop wins.
* **One resolver for both uses:** the middleware in `main.py` calls it, so the
  audit trail and the throttle share one definition of "client IP".
* **Behaviour change to B5.1a:** audit rows now hold the true peer unless a trusted
  proxy is configured. Browsers never send XFF, so the audit viewer sees no
  difference in practice. A client that forged XFF now fails. Verified live: an
  admin PATCH with `X-Forwarded-For: 203.0.113.77` was recorded as `172.23.0.1`.
* **Dev-stack note:** in docker, every request from the host reaches the backend
  from the bridge gateway (`172.23.0.1`), so local browsers and `api_smoke.py` share
  one bucket.
* **Deploying behind a real reverse proxy:** set `TRUSTED_PROXIES` to the proxy's
  address. Otherwise every visitor shares the proxy's bucket.

### State and repeats (R10)

* `record_attempt` takes `pg_advisory_xact_lock(hashtextextended('contact:<ip>'))`,
  counts the IP's attempts in the window, and inserts the attempt with its outcome
  (`accepted` / `honeypot` / `throttled`). It also prunes attempts older than
  max(window, 1 day).
* The lock serialises same-IP requests until commit. Without it, parallel requests
  all read "4 so far" and slip through. Measured: removing the lock turns the
  10-way burst test red 3 runs out of 3.
* **Why the handler commits before raising:** `get_session` rolls back on any
  exception, and D1 says rejected attempts count. So the handler commits the
  attempt row *before* raising the 429/400. Removing that commit reddens 4 tests.
* **What a repeat does:** a sixth identical submission is rejected and recorded.
  Hammering keeps the window full, because throttled attempts count too.

### Canonical homes, blast radius and money

* **Canonical homes:** client IP → `services/client_ip.py`; contact throttle →
  `services/contact_guard.py`. Both were added to the RULES.md Rule 7 table.
* **Blast radius:**
  * `client_ip_ctx` consumers: `main.py`, `audit.py` and now `contact.py`;
  * `ContactMessageIn`: only `POST /contact`;
  * `api.contact`: only `contact.tsx`.
* **Money and stock (R11):** not touched.

## What was done

1. **`app/services/client_ip.py`** (new) — `parse_networks`, `TRUSTED_PROXIES` from
   settings, `resolve_client_ip(peer, forwarded_for, trusted=None)`. The
   `main.py` middleware uses it; the `audit.py` docstring was corrected.
2. **`app/services/contact_guard.py`** (new) — `record_attempt(session, ip,
   honeypot)` → `ACCEPTED | HONEYPOT | THROTTLED`, with the advisory lock, the
   sliding-window count, the attempt row and retention pruning.
3. **`app/db.py`** — `contact_attempts (id BIGSERIAL, ip TEXT, outcome TEXT CHECK
   (accepted|honeypot|throttled), created_at)` with indexes `(ip, created_at
   DESC)` and `(created_at)`, in `CONTACT_DDL` (created by `startup_ddl()`, which
   every seed stage also runs).
4. **`app/config.py`** — `trusted_proxies=""`, `contact_rate_limit=5`,
   `contact_rate_window_seconds=600`. `infra/docker-compose.yml` passes
   `TRUSTED_PROXIES`, `CONTACT_RATE_LIMIT` and `CONTACT_RATE_WINDOW_SECONDS` with
   those defaults; `infra/.env.example` documents them.
5. **`app/schemas.py`** — `ContactMessageIn.website` (honeypot).
   **`app/routers/contact.py`** — guard first, commit rejected attempts, then a
   generic 429/400, else store as before.
6. **Frontend `contact.tsx`:**
   * an off-screen `name="website"` input inside an `aria-hidden` `sr-only`
     wrapper, with `tabIndex=-1` and `autoComplete="off"`;
   * it sits in the SSR HTML, so bots that never run JS still see it;
   * the form sends it (empty for people);
   * a 429 shows the server's Persian message, and the form keeps the typed text.
   **`api.contact`** — the body type gains `website?`.
7. **Tests:** `tests/test_contact_guard.py` (20 tests) and one new
   `api_smoke.py` check. All are described under Verification below.

## Files changed

* `backend/app/services/client_ip.py` (new), `backend/app/services/contact_guard.py`
  (new)
* `backend/app/main.py`, `backend/app/services/audit.py`,
  `backend/app/routers/contact.py`, `backend/app/schemas.py`, `backend/app/db.py`,
  `backend/app/config.py`
* `backend/tests/test_contact_guard.py` (new), `backend/tests/api_smoke.py`
* `infra/docker-compose.yml`, `infra/.env.example`, `infra/README.md`,
  `backend/README.md`
* `vogue-vintage-vibes/src/routes/contact.tsx`, `vogue-vintage-vibes/src/lib/api.ts`
* `plan/RULES.md` (Rule 7 table), `plan/MASTER-BACKLOG.md`,
  `plan/backend-tasks.md`, `plan/session-log.md`, `plan/README.md`,
  `plan/feature-roadmap.md`, `vogue-vintage-vibes/FEATURES.md`
* this audit

## Tests / verification (all executed in this session)

| Check | Result |
| --- | --- |
| `pytest -q tests/test_contact_guard.py` (live DB) | 20 passed; 3 consecutive runs leave 0 rows behind |
| Mutation checks (see below) | each mechanism reddens its tests; restored → 20/20 |
| full `pytest -q` against the live DB | 92 passed (72 + 20) |
| `ruff check app tests` | clean |
| **Clean environment** — `docker compose down -v && up -d --build` | `db-init` exit 0 through all four seed stages (auth, products, demo, coupons); postgres/minio/backend healthy; `/health` OK; `contact_attempts` + CHECK + both indexes present on the fresh DB; the three env vars in the container with their defaults |
| `tests/api_smoke.py` on the clean stack | 199 checks, 0 failed (honeypot check passed as 429 on the third run — the host bucket used by three smoke runs) |
| Live curl, clean stack | 7 posts each with a different spoofed XFF → `201 ×5, 429 ×2`, all keyed to `172.23.0.1`; admin coupon PATCH with XFF `203.0.113.77` → audit `ip = 172.23.0.1` |
| frontend `tsc` / `bun run lint` / `prettier` / `bun run build` | clean / 0 errors (15 pre-existing warnings) / clean / OK |
| Headless Chromium `/contact` | **10/10, 6 consecutive runs** (after the hydration fix below) |
| Regression browser suites on the rebuilt stack | F5.6 40/40, AB-FE-02 45/45, AB-FE-05 36/36 |

### What the 20 tests cover

* **Resolver (8 pure tests):**
  * no header → peer;
  * spoofed header from an untrusted peer → ignored;
  * the default config trusts nothing;
  * a trusted chain is walked right to left (a prepended spoof is ignored);
  * IPv6;
  * malformed hop → peer;
  * all hops trusted → leftmost;
  * no peer → None.
* **HTTP (12 tests)**, each with its own documentation-range IPv6 peer:
  * 5 → 201 then a generic 429 (no digits or mechanism words, no `Retry-After`)
    with outcomes `accepted ×5, throttled`;
  * throttled attempts keep counting;
  * sliding window (5 rows 1 s outside the window → 201; inside → 429);
  * honeypot → 400, not stored, outcome `honeypot`;
  * empty and blank honeypot → normal 201;
  * 3 honeypot + 2 valid → the next is 429;
  * a 422 records no attempt;
  * the limit is per IP;
  * a spoofed XFF opens no new buckets;
  * a trusted proxy's XFF gives each real client its own bucket (monkeypatched
    `TRUSTED_PROXIES`);
  * signed-in and guest posts share the limit;
  * a 10-way concurrent burst → exactly 5 × 201 + 5 × 429 and 5 stored.

### Mutation checks

Each change was temporarily applied, run, then restored:

| Change | Result |
| --- | --- |
| advisory lock removed | burst test red 3/3 |
| commit-before-raise removed | 4 tests red |
| "trust any XFF" restored | 6 tests red |
| honeypot ignored | 2 tests red |

### Browser (`/contact`, rebuilt stack)

* the `name="website"` input is present in the SSR HTML;
* it is absent from the accessibility tree;
* Tab from «نام» lands on «ایمیل یا شماره تماس»;
* five real submissions → success message, 5 stored, honeypot sent as `""`;
* the sixth → toast with the server's 429 text, form text kept, not stored,
  outcomes `accepted ×5, throttled`;
* a bot filling every input (incl. `website`) → generic failure toast, nothing
  stored, outcome `honeypot`;
* 375 px → no horizontal scroll;
* the host bucket and test messages are cleaned up afterwards.

### Honest notes from development

* **Public OpenAPI leak, caught before commit:** my first version put "429 … /
  400 when the honeypot field is filled" in the endpoint docstring. FastAPI
  publishes docstrings as the public OpenAPI description, so the mechanism would
  have been advertised. It was moved to a code comment. Checked against the
  running app afterwards: `/openapi.json` contains none of `honeypot`,
  `throttle`, `rate limit`, `contact_attempts`, `advisory`, `x-forwarded`.

* **My test bugs, fixed in the tests (the code was fine):**
  * a trusted-proxy test leaked a row, because the resolver canonicalises IPv6
    (`::0af1` → `::af1`) while the cleanup used the raw string. The live DB
    showed the stray row;
  * a shell-quoting error in the browser helper;
  * a Latin-vs-Persian digit mistake in one assertion.
* **Hydration race in the harness:** the browser script first clicked before React
  had hydrated the SSR form, which does a native submit. An intermittent
  honeypot-check failure (1 of 8 runs) most likely had the same cause but was not
  reproduced with diagnostics. The script now waits until React props are
  attached to the submit button. 6/6 runs have passed since.
* **F5.5 suite not re-run:** it needs ≥26 pre-existing audit rows, which the wiped
  database doesn't have. B3.11 changes only the IP value written to those rows.

## Verification level

**fully verified** — unit + integration tests (with mutation checks), live
`api_smoke.py`, a live curl abuse check, browser tested, and clean-environment
tested (`down -v`, `db-init` exit 0 through all four stages, `/health`).

## What is NOT done / open

* No new backlog items. The deployment caveat is documented instead: behind a
  real reverse proxy, `TRUSTED_PROXIES` must be set, otherwise everyone shares the
  proxy's bucket and audit IPs show the proxy.
* **Local non-docker runs:** uvicorn's own `--proxy-headers` defaults to trusting
  `127.0.0.1`. When the backend runs directly on the host (not in docker), a
  local caller could still set XFF at the uvicorn layer. That is an exposure only
  on localhost; compose is unaffected, because the peer is the bridge gateway.
* **Other public endpoints** (login, register, checkout) have no throttle. D1
  covers only `/contact`. The unscheduled "rate limiting on checkout/payment" idea
  from the full-backlog audit stays unscheduled.
* A person whose browser autofills a hidden field named `website` would get the
  generic 400. `autoComplete="off"` plus an off-screen field makes that unlikely;
  no occurrence was seen.
* The DB-level pruning runs on every attempt (1-day retention); there is no
  separate cleanup job (B2.5 territory if volume ever warrants it).
* **Docs deliberately untouched:** `vogue-vintage-vibes/README.md`,
  `DESIGN_SYSTEM.md` (no component or token change) and the spec.
