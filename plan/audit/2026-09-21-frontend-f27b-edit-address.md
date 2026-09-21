# Audit — edit a saved address in place (F2.7b)

**Date:** 2026-09-21
**Task:** let customers edit the fields of a saved address in the account tab
(`account.addresses.tsx`). The endpoint (`PATCH /addresses/{id}`) shipped with
B3.10 in the previous task; only the screen was missing.

## Spec check (Rule 0)

| Spec section | Taken? | Note |
|---|---|---|
| B3 `[FE-08]` customer tabs — «تاریخچه سفارشات · **آدرس‌های ثبت‌شده** · علاقه‌مندی‌ها» | **followed** | The customer-facing half of that tab is now a full CRUD surface (add / edit / delete / set default). The CRM drawer around it stays admin work. |
| B3 `[FE-05]` shipping box field list | **reused** | The edit form is the same field set as the checkout box (name, phone, province, city, full address, postal code) plus the address title. |
| B0/B1 UI invariants | **followed** | `rounded-3xl` card + `bg-background` inputs as the surrounding tab already does, terracotta/sand for the «پیش‌فرض» chip, Persian copy, `ghost` cancel button, no new raw colour classes. |
| Contact / other spec sections | **untouched** | Nothing else in this task. |
| Spec file | **not edited** (Rule 0.4) | Unchanged by this task. |

## What was done

- Extracted the seven address inputs into an **`AddressFields`** component shared
  by the create form and the edit form, with a `prefix` prop so label/input ids stay
  unique while both are on screen (previously the ids were the bare field keys).
- Each address card gained a **«ویرایش»** action (`Pencil`) that swaps the card into
  an inline form pre-filled from that address, with «ذخیره تغییرات» (pending label
  «در حال ذخیره…») and «انصراف». Only one card can be open at a time; deleting the
  open card closes it.
- The edit patch carries **fields only** — no `is_default` — so saving an edit can
  never move or clear the default flag; that stays the separate
  «انتخاب به‌عنوان پیشفرض» action. The `«پیشفرض»` chip stays visible while editing.
- `backend/tests/api_smoke.py`: new live assertion **`PATCH fields only edits
  without touching is_default`** — a fields-only patch on the default address keeps
  `is_default: true` while changing title/receiver/phone/province/city/line/postal
  code. This is the exact request the UI now sends, so the flag rule is guarded
  against a future regression in the router.

No backend change was needed: `AddressUpdateIn` already treats every field as
optional (`None` = leave alone), which is what makes the fields-only patch safe.

## Files changed

- `vogue-vintage-vibes/src/routes/_authenticated/account.addresses.tsx`
- `backend/tests/api_smoke.py`
- `plan/frontend-tasks.md` (F2.7b ticked), `plan/session-log.md` (Session 19),
  `plan/feature-roadmap.md`, `plan/README.md`
- `vogue-vintage-vibes/FEATURES.md` (۳.۵), `vogue-vintage-vibes/DESIGN_SYSTEM.md`
  (§3.4 pattern + §8 gap)

## How to verify

```bash
cd backend
./.venv/bin/python -m pytest -q          # 39 passed
./.venv/bin/python -m ruff check app tests
./.venv/bin/python tests/api_smoke.py    # 99 routes/checks, 0 failed (live stack)

cd ../vogue-vintage-vibes
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/eslint src/routes/_authenticated/account.addresses.tsx
```

The live check to read first is
`PATCH fields only edits without touching is_default`; the delete-promotes-successor
and single-default assertions still pass around it, so the invariant is intact after
an edit.

## What is NOT done / open

- **No browser pass** — `vite` still cannot start in this environment (pre-existing
  Node/rolldown binding issue noted in earlier audits), so the edit form is verified
  by `tsc` + eslint + the API contract it calls, not by clicking. Interaction
  details (focus after opening the form, scroll into view) are therefore unverified.
- **No "edit" of `is_default` inside the edit form** — deliberate: the default is a
  separate action so a typo fix can never silently demote the address checkout
  pre-fills. If the form should own it, that is a small follow-up decision.
- **Province is still free text** (both here and in checkout) — unchanged from the
  previous task; a fixed province list belongs with real carrier rates.
- The unrelated open items are unchanged: **F2.1b** contact inbox, **F2.4** refunds
  screen, **F2.5** pagination, **F2.6** charts, **F2.8** tracking number, **B3.11**
  contact spam guard, and Milestone **B2**.
- `backend/README.md` and `infra/README.md` were left untouched on purpose: no
  endpoint, setup step, script or stack changed (`PATCH /addresses/{id}` was already
  documented, including "edits fields and/or moves the default").
