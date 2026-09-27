# Task 6 Report: Shared Credits and Provider Budgets

## Delivered

- Added schema migration 8 for operator-assigned integer nano-USD user allowances, connection budgets/reserves, and reservation settlement snapshots. Existing allowance amounts and history are retained; allowance reset semantics migrate to `Europe/Berlin`.
- Added audited allowance assignment and per-connection daily, weekly, monthly, and lifetime budget configuration. Reservations check the shared user allowance, key cap, selected connection cap/reserve, and optional global cap in one `BEGIN IMMEDIATE` SQLite transaction.
- Current-window spend includes active reservations and imported legacy usage, independent of key archive or provider disable state. Timestamps are compared as instants. Unknown-cost delivered history blocks a capped reservation instead of being counted as zero.
- Added immutable approved-price snapshots at reservation time. Settlement prices reported tokens from that snapshot, records no invented token counts when usage is missing, settles only an active reservation once, and conservatively settles expired reservations at their reserved estimate. Reservation release requires explicit confirmation that delivery is known absent.
- Added conservative preflight estimation: finite request/model/configured output bounds are required; text input uses UTF-8 byte length plus framing overhead; vision needs an explicit offer input bound. Missing bounds fail with `budget_estimate_unavailable`.
- Added `POST /api/operator/connections/{connection_id}/budget`, nano-USD allowance/reset fields in the developer dashboard, and operator people allowance/reset fields.

Gateway dispatch, retry/fallback, and live settlement wiring remain Task 7 work as scoped by the approved plan.

## TDD and Verification

- Added all 12 named Task 6 tests. Their focused RED run produced 12 expected failures at the missing Task 6 repository interfaces; all 12 later passed.
- Added API, preflight, offset-time, unknown-cost, disabled-connection, expiry, and settlement-exit regressions. New behavior tests were run RED before their respective fixes.
- Focused portal suites: **93 passed**, 1 existing Starlette/httpx deprecation warning.
- Full suite: `py -3.11 -m pytest -q -p no:cacheprovider` — **193 passed**, 1 existing Starlette/httpx deprecation warning.
- `git diff --check` passed. The first sandboxed full-suite attempt could not create fixture files in the checkout root; the exact command was rerun with reviewed worktree access and passed.

## Scope Notes

Only `app/portal_db.py`, `app/portal_api.py`, and the three Task 6 portal test files are included with this report. `app/catalog.py` and all other pre-existing dirty files were left out of the Task 6 commit.
