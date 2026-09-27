# Task 7: Provider offer gateway routing

## Delivered

- Portal keys resolve only published, priced, key-eligible provider-scoped offers. `/v1/models` exposes public offer IDs without provider credentials, connection labels, base URLs, or route order. Legacy keys retain their existing model projection and completion path.
- Portal completions translate the public offer ID to the selected route's exact raw model ID and use `OpenAICompatibleClient` with the selected encrypted profile's server-side base URL and decrypted credential.
- Portal requests require a finite output-token cap. The reservation estimate uses UTF-8 request bytes plus framing; image input is rejected without an explicit verified bound. Budget and model rejections write safe metadata only and never persist prompts.
- Every portal dispatch reserves nano-USD against the selected connection and applicable user, key, and global scopes. Only the typed pre-send connect failure releases that reservation and advances to another eligible route. Streaming obtains the first upstream result before returning the downstream stream, so it cannot fail over after response headers begin. Ambiguous failures are not retried.
- Reservation-time snapshots preserve the public and canonical model IDs, raw route model ID, provider/brand, connection, offer route, and price version through settlement. If usage is absent, settlement uses the reservation estimate and leaves token counts unknown.
- Added idempotent nullable route-snapshot columns to the schema-8 reservation table; existing databases gain the columns without rewriting records or changing the migration version history.

## Verification

- `py -3.11 -m pytest -p no:cacheprovider tests/test_portal_gateway.py tests/test_provider.py -q`: **36 passed**, one existing Starlette/httpx deprecation warning.
- `py -3.11 -m pytest -p no:cacheprovider -q`: **202 passed**, one existing Starlette/httpx deprecation warning.
- `git diff --check`: passed. Python AST parsing passed for `app/main.py`, `app/portal_db.py`, `app/openai_compatible.py`, and `app/errors.py`.
- The concrete tests were not edited. In particular, no `tests/test_provider.py` changes are included.

## Self-review

- Dispatch and credential lookup remain server-side; public responses and rejection records contain no upstream secret or prompt content.
- The legacy-key route remains separate from portal offer dispatch. Route review, price match, enablement, and discovery eligibility checks remain enforced by the offer resolver.
- The full suite retains one pre-existing dependency deprecation warning; there are no failing tests.
