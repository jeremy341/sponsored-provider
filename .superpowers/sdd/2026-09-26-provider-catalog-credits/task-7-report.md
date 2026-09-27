# Task 7: Provider-offer gateway routing

## Implementation

- Portal API keys list only key-visible, provider-scoped public offer IDs; legacy keys retain the legacy model list and dispatch path.
- Portal completions resolve an approved offer to an eligible route, send that route's exact raw upstream model ID through `OpenAICompatibleClient`, and keep decrypted credentials/base URLs server-side.
- Portal requests reserve Task 6 nano-USD budgets against the selected concrete connection. Only a typed pre-send connect failure releases that reservation and tries the next eligible route with a new reservation. Ambiguous failures and all failures after the stream starts are never retried.
- Preflight requires a finite output-token bound and conservatively estimates text input from encoded request bytes. Unsupported image input is rejected before dispatch. Safe rejection events contain no prompt body.
- Settlement preserves public/canonical model ID, raw model ID, brand, selected connection, route, and immutable price version. Missing usage is charged at the reservation estimate while token counts remain unknown.

## RED/GREEN evidence

RED command:

```text
py -3.11 -m pytest tests/test_portal_gateway.py tests/test_provider.py -q -p no:cacheprovider
```

Output before production changes: **6 failed, 30 passed**, 1 existing Starlette/httpx warning. Failures were in public-ID completion mapping, safe budget rejection, pre-send failover, ambiguous timeout behavior, stream no-retry, and immutable route/price snapshots; no fixture/setup errors remained.

GREEN verification:

- Focused gateway/provider suite: **36 passed**, 1 existing warning.
- Full Python suite: `py -3.11 -m pytest -q -p no:cacheprovider` — **202 passed**, 1 existing warning.
- `git diff --check` passed.

Regression tests and pytest temp-directory support are committed separately from the production change because the initial implementation commit omitted them. The existing unrelated `tests/test_provider.py` precision-estimate hunk remains outside these commits; it was present during the full-suite run.

## Scope

Production commit: `5cb29a6` (`feat: route openai requests through provider offers`). No Nest/data wipe, deploy, restart, or push occurred.

## Review fix round 1

The independent review identified two safety gaps and one legacy-contract concern. Added regressions and fixed:

- Input preflight now serializes the full chat request, not only `messages`, so tool definitions/response schemas contribute to the conservative byte/token estimate.
- The budget reservation transaction reruns the route resolver while holding its write transaction and requires the same route ID; a route that became stale, review-required, disabled, mismatched, or otherwise ineligible between resolution and reservation cannot be dispatched.
- A pre-existing legacy spend-cap guard and its `key_budget_exhausted` response were preserved. The new `budget_estimate_unavailable` behavior remains on portal keys; see the Task 7 compatibility ruling in the SDD ledger.
- Added a gateway-level selected-connection-cap rejection test. Updated the shared budget test fixture to represent real mapped connections with exact profile and discovery rows, rather than bypassing Task 7 route eligibility.

RED: `py -3.11 -m pytest tests/test_portal_gateway.py -q -p no:cacheprovider -k "tool_schemas or reservation_rechecks or connection_budget or spend_capped_legacy"` — 3 failed (tool-schema estimate, route-state race, legacy error contract), 1 passed (connection-cap dispatch guard), 12 deselected, 1 warning.

GREEN:

- Review regressions: 4 passed, 12 deselected.
- Focused gateway/provider suite: 40 passed, 1 warning.
- Task 6 budget repository suite after fixture alignment: 44 passed, 1 warning.
- Full Python suite: 206 passed, 1 warning.
- The warning is the existing Starlette/httpx `TestClient` deprecation.
