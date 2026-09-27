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
