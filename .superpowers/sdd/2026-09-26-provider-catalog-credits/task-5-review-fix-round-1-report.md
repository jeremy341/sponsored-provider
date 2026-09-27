# Task 5 review fix round 1

## Findings addressed

- Added a CSRF-protected operator endpoint to map one exact, active discovered upstream ID to an existing offer in the same mapped provider brand. The connection model stores the manual canonical ID and source; subsequent syncs reuse it. The existing raw-ID offer and its pricing/history remain stored, while its route moves to the canonical offer so the orphan offer is not published.
- Added persistent `review_required` route state. Missing models on successful syncs and failed/stale syncs require operator review. Rediscovery refreshes discovery state without clearing review. Explicitly enabling the route through its existing availability action confirms it and clears the review requirement.
- Added every route to operator offer responses, including disabled, stale, and review-required routes. Responses include only management metadata: route ID, connection ID/label, raw upstream ID, order, switch state, freshness, review, and price status. No connection URL or credential is returned.
- Added migration 7 for canonical mapping and route review state. Same-brand aliases remain route-local by raw ID; cross-brand mappings are rejected. Route resolution continues to require exact discovery and matching approved user-facing price.

## RED checkpoint

Added and ran these tests before production changes:

- `test_operator_maps_alias_to_existing_same_brand_offer_and_mapping_survives_sync`
- `test_operator_cannot_map_discovered_model_to_another_brand`
- `test_manual_model_mapping_requires_operator_role_and_csrf`
- `test_stale_route_requires_reconfirmation_after_rediscovery`
- `test_operator_offer_response_lists_manageable_route_ids_without_credentials`

RED result: 5 failed. The mapping and authorization paths returned 404, rediscovery incorrectly restored availability (`True` instead of `False`), and the offer response lacked `routes` (`KeyError`).

## Verification

- New regressions after implementation: 5 passed.
- `py -3.11 -m pytest tests/test_routing.py tests/test_portal_api.py tests/test_portal_db_catalog.py -q -p no:cacheprovider` — 70 passed.
- `py -3.11 -m pytest -q -p no:cacheprovider` — 166 passed.
- `git diff --check` — passed.
- Both test runs report the existing Starlette/httpx deprecation warning.

The changes are ready for the separate fix-round commit. Task 5 commit `37c53c1` was not amended. No Nest/data wipe, deployment, restart, or push was performed.
