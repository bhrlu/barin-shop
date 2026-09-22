# Audit — 2026-09-21 — B5.1a audit IP capture + F4.1 token-driven status badges

## Task

Two quick tasks from the lists:

- **B5.1a** (backend): populate `audit_logs.ip_address` — the column existed but
  was always NULL (B5.1 split this off deliberately).
- **F4.1** (frontend): one `StatusBadge` component using the status semantics
  table (DESIGN_SYSTEM §2.3/§7.2), replacing the uniform terracotta/sand chips.

## Spec check (Rule 0)

- **[BE-04] B5.1a:** the spec's `ip_address VARCHAR NULLABLE` column is now
  populated on every audit write. The spec doesn't say *how* to capture it; the
  middleware + contextvar approach keeps all 17 audit call sites
  signature-compatible.
- **[B0.2/B4.2] F4.1:** followed exactly — semantics (positive/progress/
  waiting/negative/meta) drive the colour via repo tokens; the label always
  names the status; `title` keeps the Latin status for support; no raw palette
  classes. The spec's own hardcoded `bg-emerald-50`-style recipes are the known
  self-contradiction documented in §2.3 — the repo's token translation wins.

## What was done

### B5.1a

- `app/services/audit.py`: `client_ip_ctx` (contextvar, default None) —
  `record_audit` falls back to it when the caller passes no explicit
  `ip_address`.
- `app/main.py`: `capture_client_ip` HTTP middleware (registered before the
  Zarinpal mapper so it runs first): trusts `X-Forwarded-For`'s first hop when
  present, else the socket peer. Rationale: the backend always sits behind the
  compose proxy / loopback; a spoofed XFF from a direct client would only pollute
  its own audit entries, which is acceptable for this stack and noted below.
- Verified live: an audited mutation with `X-Forwarded-For: 198.51.100.7` stores
  exactly that IP; the smoke asserts entries now carry IPs (via the Docker
  gateway address).

### F4.1

- **New `src/components/StatusBadge.tsx`** — the §7.2 component, extended with
  `succeeded`/`failed` (payment rows) and `new` (contact inbox) tones; unknown
  statuses degrade to the brand tone with the raw string as label.
- Call sites converted:
  - `account.orders.tsx` — order + payment chips (was terracotta/sand pair)
  - `admin.orders.tsx` — drawer header chips were already converted; list keeps
    its selects (controls, not state display)
  - `admin.refunds.tsx` — refund status chip (was 3-way hand-rolled ternary)
  - `admin.index.tsx` — latest-orders status chip
  - `OrderDetailDrawer.tsx` — header order/payment chips
- Deleted now-unused `REFUND_STATUS`/`ORDER_STATUS`/`PAYMENT_STATUS` imports
  where the badge replaced them.

## Files changed

- `backend/app/services/audit.py`, `backend/app/main.py`
- `backend/tests/api_smoke.py`
- `vogue-vintage-vibes/src/components/StatusBadge.tsx` (new)
- `vogue-vintage-vibes/src/routes/_authenticated/account.orders.tsx`,
  `admin.refunds.tsx`, `admin.index.tsx`
- `vogue-vintage-vibes/src/components/admin/OrderDetailDrawer.tsx`
- docs: audit (this file), task lists, session log, DESIGN_SYSTEM, plan README

## How to verify

```bash
cd backend && ./.venv/bin/python -m pytest -q && ./.venv/bin/python -m ruff check app tests
cd backend && ./.venv/bin/python tests/api_smoke.py    # 152 checks, 0 failed
curl -s -X POST .../coupons -H "X-Forwarded-For: 203.0.113.9" …   # then:
docker exec sandeh-postgres-1 psql -U sande -d postgres \
  -c "SELECT action, ip_address FROM audit_logs ORDER BY created_at DESC LIMIT 3;"
cd vogue-vintage-vibes && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vite build
```

Visual: customer order list, admin refunds/orders/dashboard and the drawer now
show green (delivered/paid/refunded), amber (processing/shipped), sand
(pending/unpaid), red (cancelled/rejected) pills instead of uniform terracotta.

## What is NOT done / open

- **B5.1b** (DB-level tamper-resistance) remains open — REVOKE UPDATE/DELETE on
  `audit_logs` needs a decision about which role the app uses (single-role app
  user would lock itself out; needs `SET ROLE` plumbing or a separate initdb
  grant for the current role).
- XFF is trusted unconditionally (no trusted-proxy allowlist). Fine behind the
  compose proxy; revisit only if the backend ever faces the internet directly.
- The Zarinpal callback path (browser redirect) also captures an IP now — that's
  correct, but note gateway callbacks and customer actions share the table with
  admin actions; filtering by `action` remains the way to isolate admin activity.
