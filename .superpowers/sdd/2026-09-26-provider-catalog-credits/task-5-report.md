# Task 5 report: provider offer merging and routing

## Implemented

- Added `public_model_id` and the pure ordered route resolver in `app/routing.py`.
- Kept catalog identity exact within a mapped provider brand. Exact same-brand model IDs share one offer, with a distinct route retaining each connection and raw upstream model ID. Equal model IDs under different brands remain separate offers.
- Added migration 6 with persistent route order. Route availability is independent of offer availability; stale discovery, unmapped or missing connections, disabled connections, unconfirmed prices, and price mismatches are excluded from route resolution.
- Added operator APIs to update a route order and toggle one route. Both enforce operator authorization and CSRF; route mutations are audited. Route selection validates the exact active discovery association and exact decimal price equality when the upstream reports a price.
- Left the pre-existing dirty `app/catalog.py` hunk unchanged.

## RED checkpoint

The seven named regressions were added before implementation:

- `test_same_brand_duplicate_upstream_model_merges_to_one_offer`
- `test_same_model_from_different_brands_stays_distinct`
- `test_public_model_id_is_stable_and_provider_scoped`
- `test_route_order_skips_disabled_or_stale_connections`
- `test_offer_with_missing_or_unmapped_connection_never_resolves`
- `test_price_mismatch_route_is_ineligible_for_fallback`
- `test_route_can_only_reference_exact_discovered_upstream_model`

The initial routing run failed collection with `ModuleNotFoundError: No module named 'app.routing'`. The three initial API regressions each failed as expected because the new endpoints returned HTTP 404. The focused suite subsequently passed.

## Verification

- `py -3.11 -m pytest tests/test_routing.py tests/test_portal_api.py tests/test_portal_db_catalog.py -q -p no:cacheprovider` — 65 passed, one existing Starlette/httpx deprecation warning.
- `py -3.11 -m pytest -q -p no:cacheprovider` — 161 passed, one existing Starlette/httpx deprecation warning. The final run used worktree write access because the sandbox-only run could not create test databases/directories inside the managed checkout.
- `git diff --check` — passed.

## Scope

No Nest/data wipe, deployment, restart, or push was performed. Existing unrelated dirty files remain outside the Task 5 commit.
