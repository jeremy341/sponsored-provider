# Provider Catalog, Routing, and Shared Credits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-scoped model catalog with UI-managed upstream connections, reviewed USD pricing, same-provider primary/fallback routing, per-connection budgets, and shared expiring user allowances across keys and providers.

**Architecture:** Extend the existing FastAPI + React/Vite modular monolith and OpenAI-compatible gateway. Separate provider brand, connection, catalog offer, and route in SQLite; retain immutable price/usage snapshots. Use atomic preflight reservations across global, user, key, and selected connection scopes. Implement backend contracts before connecting the operator and developer UI.

**Tech Stack:** Python 3.11, FastAPI, SQLite, httpx/respx, pytest, React 19, TypeScript, Vite, Radix UI, shadcn/ui primitives, Oxlint.

**Spec:** `docs/superpowers/specs/2026-09-26-provider-catalog-credits-design.md` and `.ulpi/design/provider-catalog-credits.md`; preserve `.ulpi/design/DESIGN.md`.

## Global Constraints

- Keep `/v1/models` and `/v1/chat/completions` OpenAI-compatible and preserve existing legacy keys/history.
- Active portal authentication is local username/password only. Preserve Hack Club Auth code/docs but keep its routes and UI dormant.
- Signup requires an invite. Each developer may issue one single-use invite; each new developer receives one. Operators can create an invite with a configured positive use limit, expiry, and revocation.
- Bootstrap the first operator only through a one-time server-side procedure; never expose public operator registration.
- Hash passwords with Argon2id, rate-limit authentication, use secure HTTP-only sessions, and atomically consume invite capacity during signup.
- Keep all effective prices and limits in USD; record immutable request-time price versions and label estimates separately from provider invoices.
- The user allowance is shared across that user’s keys/providers, resets daily or weekly in `Europe/Berlin`, and does not roll over.
- Provider connection caps are daily, weekly, monthly, or lifetime and support an optional reserve.
- Same provider brand + canonical model is one offer; different provider brands are distinct offers.
- `/models` discovers exact upstream IDs; Models.dev is the primary price suggestion; ambiguous/unpriced models are never made available automatically.
- Price approval and offer availability are separate. A route with a price mismatch cannot be used as a fallback.
- Use one primary route plus manually ordered same-brand fallbacks; retry only when delivery to the previous upstream is known not to have occurred.
- Reserve budgets atomically before upstream dispatch; never store prompts/completions or expose provider credentials.
- Preserve historical records on disable/archive/rename; all destructive provider/model/key operations require tests proving history retention.
- Follow `.ulpi/design/DESIGN.md`; keep operator and developer layouts responsive, keyboard accessible, and within the existing visual system.
- Do not deploy, stop/restart Nest, push, or make production changes as part of implementation.
- Execution starts on an isolated `development/` worktree/branch, not the currently dirty `main`. Preserve the existing in-progress portal changes and unrelated user edits; decide explicitly how to carry required portal code into the isolated checkout before implementation.

## Review Focus

1. **Ambiguous model match or model alias:** expected behavior is unresolved/manual mapping, never a guessed price or accidental cross-brand merge. Pin in catalog matching tests.
2. **Very small prices and exact cap boundaries:** expected behavior is no floating-point undercount that bypasses reservations. Pin in decimal arithmetic and reservation tests.
3. **Large requests, omitted output caps, and multimodal input:** expected behavior is reject before forwarding when cost cannot be conservatively bounded; pin in preflight tests. Use a request output cap or verified model maximum/configured hard maximum; reject if none exists. Reject vision input under capped budgets unless its pricing/estimation policy is explicitly configured.
4. **Concurrent requests at user/provider/global boundaries:** expected behavior is no aggregate overspend across separate keys or connections. Pin with concurrent reservation tests.
5. **Fallback timeout after possible delivery or incomplete streaming usage:** expected behavior is no automatic retry after ambiguous delivery; retain a conservative estimate and release/settle reservations correctly. Pin in gateway integration tests.

---

## File Map

| File | Responsibility |
|---|---|
| Create `app/money.py` | Decimal-safe USD rate arithmetic and smallest internal cost unit. |
| Create `app/periods.py` | Europe/Berlin user-credit windows and provider-cap windows, including DST. |
| Create `app/catalog.py` | `/models` normalization and Models.dev lookup/matching; no DB writes. |
| Create `app/routing.py` | Resolve public offer IDs to eligible connection routes; no HTTP or persistence. |
| Create `app/openai_compatible.py` | Provider-neutral `/models`, non-streaming completion, and streaming client for any OpenAI-compatible connection. |
| Modify `app/alibaba.py` | Keep a compatibility re-export for existing imports/config during migration; no new provider feature may depend on Alibaba-specific naming. |
| Modify `app/portal_db.py` | Versioned schema migrations, catalog/route/price/budget persistence, atomic reservation and snapshots. |
| Modify `app/portal_api.py` | Operator connection/catalog/budget routes and developer allowance/model responses. |
| Modify `app/main.py` | `/v1/models` offer projection and chat-completion route mapping/failover. |
| Modify `app/database.py` | Keep the existing encrypted upstream-credential vault and legacy profile IDs; preserve cached model IDs after failed syncs and legacy accounting. |
| Create focused `tests/test_money.py`, `tests/test_periods.py`, `tests/test_catalog.py`, `tests/test_routing.py`, and `tests/test_portal_db_catalog.py` | Pure logic and repository/migration regression tests. |
| Modify `tests/test_portal_api.py`, `tests/test_portal_gateway.py`, `tests/test_provider.py` | HTTP authorization, discovery, catalog, routing, limit, compatibility, and legacy regression coverage. |
| Modify `frontend/src/contracts/api.ts`, `frontend/src/lib/api.ts` | Typed API contracts and same-origin calls. |
| Create `frontend/src/lib/money.ts` | Format decimal USD/rate strings without changing server-side budget arithmetic. |
| Create `frontend/src/ui/operator/providers/` components | Provider list, connection form/detail, price review, offer switches, route editor. |
| Create `frontend/src/ui/operator/people/AllowanceEditor.tsx` | Operator-assigned user allowance and reset summary. |
| Create `frontend/src/ui/operator/usage/OperatorUsagePage.tsx` | Provider/connection-aware aggregate usage filters and history. |
| Modify `frontend/src/ui/App.tsx` | Wire existing navigation/routes to the focused new operator/developer screens; do not grow the file with all component internals. |
| Create `frontend/src/ui/developer/` components | Allowance, model catalog/key selection, and own-activity presentation. |
| Create `frontend/src/ui/developer/ModelDetailPage.tsx` | Provider-qualified detail, verified token pricing/metadata, and OpenAI-compatible examples. |
| Modify `frontend/src/ui/styles.css` | Only scoped styles using locked tokens, responsive behavior, focus and reduced-motion rules. |
| Modify `frontend/package.json` and lockfile only if needed | Add frontend test runner and DOM testing utilities if not already available. |
| Modify `README.md`, `deploy/README.md` | Describe operator setup, Models.dev review limitations, restore-tested staged rollout, and no exact-invoice guarantee. |

## Task 1: Lock money units and period semantics

**Files:**
- Create: `app/money.py`
- Create: `app/periods.py`
- Test: `tests/test_money.py`
- Test: `tests/test_periods.py`

**Interfaces:**
- Produce `rate_cost_nano_usd(uncached_input_tokens: int, cached_input_tokens: int, output_tokens: int, input_rate: Decimal, output_rate: Decimal, cached_rate: Decimal | None = None) -> int`; input counts are non-overlapping.
- Produce `period_window(period: Literal["daily", "weekly", "monthly", "lifetime"], now: datetime, timezone_name: str = "Europe/Berlin") -> PeriodWindow` with UTC-aware `start_utc`, `end_utc | None`, and `reset_at_utc | None`.
- Internal request cost uses integer nano-USD (`1 USD = 1_000_000_000 nano-USD`); convert configured decimal rates with `Decimal`, round cost upward to the next nano-USD for reservations/debits, and never use binary float for new budget decisions.
- Persist per-million-token rates as canonical decimal text, not SQLite `REAL`. API price/rate fields use decimal strings; budget amounts use integer nano-USD and are serialized as decimal USD strings for display.
- UI formats retain sub-cent values up to nine fractional USD digits; browser rounding is presentation only and never participates in cap checks.

- [ ] **Step 1: Write failing arithmetic tests**

Add tests named `test_input_and_output_rates_are_charged_per_million`, `test_cached_tokens_use_cache_rate_only_when_reported_and_configured`, `test_missing_cache_rate_uses_normal_input_rate`, `test_fractional_cost_rounds_up_to_nano_usd`, and `test_negative_nonfinite_or_boolean_inputs_are_rejected`.

- [ ] **Step 2: Run `py -3.11 -m pytest tests/test_money.py -q` and verify the new imports/behavior fail.**

- [ ] **Step 3: Implement `rate_cost_nano_usd` in `app/money.py`**

Use `Decimal(str(value))` at the API boundary, reject invalid token counts/rates, and perform non-overlapping uncached-input/cached-input/output multiplication at precision sufficient for configured decimal rates. Preflight treats all input tokens as uncached because cache hits are not known in advance.

- [ ] **Step 4: Run `py -3.11 -m pytest tests/test_money.py -q` and verify all arithmetic tests pass.**

- [ ] **Step 5: Write failing period-boundary tests**

Add `test_daily_window_resets_at_berlin_midnight`, `test_weekly_window_starts_monday_in_berlin`, `test_monthly_window_handles_month_end`, `test_dst_short_day_has_correct_utc_duration`, and `test_lifetime_window_has_no_reset`.

- [ ] **Step 6: Run `py -3.11 -m pytest tests/test_periods.py -q` and verify failures before implementation.**

- [ ] **Step 7: Implement `period_window` in `app/periods.py`**

Use `zoneinfo.ZoneInfo("Europe/Berlin")`; daily starts local midnight, weekly starts Monday local midnight, monthly starts local first-of-month, and the returned boundaries are converted to UTC. User allowance only accepts daily/weekly; provider caps also accept monthly/lifetime.

- [ ] **Step 8: Run `py -3.11 -m pytest tests/test_periods.py -q` and verify all boundaries pass.**

- [ ] **Step 9: Commit Task 1 on the isolated feature branch**

Stage only `app/money.py`, `app/periods.py`, `tests/test_money.py`, and `tests/test_periods.py`; commit as `feat: add precise budget math and periods`.

## Task 2: Add versioned schema and lossless legacy migration

**Files:**
- Modify: `app/portal_db.py`
- Test: `tests/test_portal_db_catalog.py`
- Test: `tests/test_portal_api.py`

**Interfaces:**
- Add `portal_schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)` and ordered migration functions called by `PortalDatabase.init_schema()`.
- Add repository types/dataclasses in `app/portal_db.py`: `ProviderBrand`, `ProviderConnection`, `CatalogOffer`, `OfferRoute`, `PriceVersion`, `ProviderBudget`, and `BudgetReservation`.
- Store new monetary fields as integer nano-USD; leave legacy `estimated_cost_usd` rows untouched and project them as historic float-compatible values only at the API boundary.

- [ ] **Step 1: Write migration tests against a database created by the current schema**

Add `test_migration_preserves_legacy_catalog_and_all_usage_snapshots`, `test_migration_maps_each_legacy_profile_to_brand_connection`, `test_migrations_are_idempotent`, `test_migration_converts_caps_without_changing_usd_values`, and `test_new_offer_routes_and_prices_enforce_unique_identity`.

- [ ] **Step 2: Run `py -3.11 -m pytest tests/test_portal_db_catalog.py -q` and verify migration tests fail on the pre-migration schema.**

- [ ] **Step 3: Implement additive schema migrations in `PortalDatabase.init_schema()`**

Create `provider_brands`, `provider_connections` (with a reference to the legacy encrypted profile ID, never a duplicate secret), `connection_models`, `catalog_offers`, `offer_routes`, `price_versions`, `provider_budgets`, `user_allowances`, and `portal_budget_reservations_v2`. Store rate-card values as canonical decimal text; add integer nano-USD fields for new grants, caps, reservations, and usage charges. Convert existing configured cap/allowance values without changing their displayed amount; set active allowance windows to Europe/Berlin without rewriting historical events. Add immutable route/brand/model/price snapshots to new usage events without rewriting old snapshot values. Add unique/index constraints for `(brand_id, canonical_model_id)`, `(connection_id, upstream_model_id)`, `(offer_id, connection_id)`, and active price versions.

- [ ] **Step 4: Migrate legacy provider profiles idempotently**

Do not infer a provider brand from a user-entered profile label or generic OpenAI-compatible type. Preserve each legacy profile as an isolated, explicitly unknown/unmapped record; do not merge or route it until an operator maps and approves its brand. Preserve its old provider ID as a stable migration reference. Map existing `(provider_id, model_id)` rows only under that isolated state and do not make them user-routable. Keep legacy usage labels/prices exactly as recorded.

- [ ] **Step 5: Run the migration test file and existing `tests/test_portal_api.py`; verify all old historical assertions remain unchanged.**

- [ ] **Step 6: Commit Task 2 on the isolated feature branch**

Stage only `app/portal_db.py`, `tests/test_portal_db_catalog.py`, and `tests/test_portal_api.py`; commit as `feat: migrate provider catalog schema safely`.

## Task 3: Implement `/models` discovery normalization and Models.dev matching

**Files:**
- Create: `app/catalog.py`
- Test: `tests/test_catalog.py`
- Modify: `pyproject.toml` only if an already-installed HTTP dependency cannot support the adapter

**Interfaces:**
- `normalize_openai_models(payload: Mapping[str, Any]) -> list[DiscoveredModel]` preserves exact upstream IDs and only extracts provider-advertised metadata that is explicitly present.
- `ModelsDevCatalog.lookup(provider_slug: str, upstream_model_id: str) -> PriceMatch` returns exactly one of `exact`, `ambiguous`, or `not_found`, plus an optional USD price suggestion and source metadata.
- No function in this module writes to SQLite or marks any offer approved/available.

- [ ] **Step 1: Verify the supported Models.dev data interface and price units from its current primary documentation/source before writing the client**

Record the verified endpoint/data format and attribution/update metadata in a fixture. If there is no supported stable interface or access is unavailable, do not scrape HTML; keep the adapter returning `not_found` and preserve manual pricing as the working fallback.

- [ ] **Step 2: Add fixture-based tests**

Add `test_model_list_keeps_exact_ids_and_deduplicates_identical_rows`, `test_malformed_model_list_is_rejected_without_emptying_catalog`, `test_models_dev_exact_vendor_model_match_returns_usd_suggestion`, `test_ambiguous_alias_does_not_return_auto_match`, and `test_unknown_model_requires_manual_price`.

- [ ] **Step 3: Run `py -3.11 -m pytest tests/test_catalog.py -q` and verify expected failures.**

- [ ] **Step 4: Implement the pure normalizer and read-only Models.dev adapter**

Use `httpx` with bounded timeout, no redirects to arbitrary hosts, explicit response validation, and fixture-controlled tests. A provider `/models` response may update discovered IDs but is never interpreted as pricing unless its schema explicitly reports pricing metadata.

- [ ] **Step 5: Re-run `py -3.11 -m pytest tests/test_catalog.py -q`; verify exact, ambiguous, absent, and malformed cases.**

- [ ] **Step 6: Commit Task 3 on the isolated feature branch**

Stage only `app/catalog.py` and `tests/test_catalog.py` (plus a dependency manifest only if required); commit as `feat: add provider model price matching`.

## Task 4: Persist provider connections, discoveries, prices, and offer controls

**Files:**
- Create: `app/openai_compatible.py`
- Modify: `app/alibaba.py`
- Modify: `app/catalog.py`
- Modify: `app/database.py`
- Modify: `app/portal_db.py`
- Modify: `app/portal_api.py`
- Test: `tests/test_portal_api.py`
- Test: `tests/test_portal_db_catalog.py`
- Test: `tests/test_provider.py`
- Test: `tests/test_openai_compatible.py`

**Interfaces:**
- `OpenAICompatibleClient(base_url: str, api_key: str, timeout: float = 60.0, transport: httpx.AsyncBaseTransport | None = None)` exposes `list_models()`, `chat_completion(payload: dict)`, and `stream_chat_completion(payload: dict)` with the existing `ProviderError` contract.
- `Database.create_upstream(name: str, provider_kind: str, base_url: str, api_key: str) -> dict` remains the sole writer/decryptor of upstream credentials; its returned profile ID is the stable connection ID and never contains the raw key.
- `PortalDatabase.register_connection(secret_profile_id: str, brand_slug: str, brand_name: str, connection_label: str) -> ProviderConnection` stores nonsecret brand/connection metadata referencing that encrypted profile. Do not duplicate the credential in portal tables.
- `PortalDatabase.apply_discovery(connection_id: str, discovered: list[DiscoveredModel], synced_at: datetime) -> SyncSummary` is idempotent and marks missing connection-model rows stale without deleting them.
- `PortalDatabase.save_price_suggestion(offer_id: str, price: PriceSuggestion) -> PriceVersion` creates a pending immutable version.
- `PortalDatabase.approve_price_version(actor_id: str, offer_id: str, version_id: str) -> None` activates exactly one approved version and writes audit history.
- `PortalDatabase.set_offer_available(offer_id: str, enabled: bool, actor_id: str) -> None` remains independent from price approval.
- Operator APIs: extend `POST /api/operator/providers`, existing `POST /api/operator/providers/{connection_id}/sync`, add `GET /api/operator/offers`, `PATCH /api/operator/offers/{offer_id}/price`, `POST /api/operator/offers/{offer_id}/prices/{version_id}/approve`, and `PATCH /api/operator/offers/{offer_id}/availability`.
- Extend provider-create input with `brandSlug` and `connectionLabel`; retain current provider name as a migration-compatible alias during rollout.

- [ ] **Step 1: Write tests for connection create, one-time model discovery, pending price, price approval, and publish switch**

Add `test_create_connection_never_returns_provider_secret`, `test_sync_models_runs_on_connection_setup`, `test_repeated_sync_is_idempotent`, `test_failed_sync_keeps_last_discovery_and_marks_stale`, `test_new_offer_is_unavailable_until_price_approved_and_enabled`, `test_price_change_remains_pending_until_approval`, and `test_disabled_offer_is_not_returned_to_developer_catalog`.

Also add `test_openai_compatible_client_lists_models_and_completes_for_non_alibaba_provider` and `test_legacy_alibaba_client_import_remains_compatible`.

- [ ] **Step 2: Run the named tests and confirm failures before implementation.**

- [ ] **Step 3: Implement repository methods and operator endpoints**

Require operator role and CSRF on mutations. Create the encrypted legacy upstream profile first, register nonsecret portal metadata using the same profile ID, and disable the legacy profile if metadata registration fails so an orphan credential cannot remain active. Validate HTTPS/public base URL and the resolved destination before outbound fetch; revalidate redirects/DNS so model discovery cannot reach private or reserved addresses. Keep the last good model list on errors. Trigger initial `sync_connection_models` after successful connection creation; expose a distinct error if credential test or discovery fails.

Use `OpenAICompatibleClient` for `/models` discovery from any provider brand. Keep `AlibabaClient` as a compatibility alias while existing env-based deployment and tests are migrated; do not remove its old config in this catalog change.

- [ ] **Step 3a: Add a legacy cache-preservation regression test**

Add `test_failed_provider_sync_preserves_last_successful_model_ids` in `tests/test_provider.py`. Change `Database.update_upstream_models` so health/error state can update without replacing `models_json` with an empty list on a failed sync.

- [ ] **Step 4: Implement price provenance and offer state transitions**

Models.dev suggestion, provider-reported comparison, and manual operator rates remain separately sourced. Manual accepted values are USD per million input/output and optional cached input. Every approval creates an immutable effective version; price refresh creates pending data only.

- [ ] **Step 5: Run `py -3.11 -m pytest tests/test_portal_api.py tests/test_portal_db_catalog.py tests/test_provider.py tests/test_openai_compatible.py -q`; verify role/CSRF, failed-sync preservation, price states, legacy behavior, generic provider compatibility, and secret non-disclosure.**

- [ ] **Step 6: Commit Task 4 on the isolated feature branch**

Stage only `app/openai_compatible.py`, `app/alibaba.py`, `app/database.py`, `app/portal_db.py`, `app/portal_api.py`, `tests/test_openai_compatible.py`, `tests/test_portal_api.py`, `tests/test_portal_db_catalog.py`, and `tests/test_provider.py`; commit as `feat: add provider discovery and price review`.

## Task 5: Resolve same-provider duplicate models into stable catalog offers and routes

**Files:**
- Create: `app/routing.py`
- Modify: `app/portal_db.py`
- Modify: `app/portal_api.py`
- Test: `tests/test_routing.py`
- Test: `tests/test_portal_api.py`

**Interfaces:**
- `public_model_id(brand_slug: str, canonical_model_id: str) -> str` returns a stable provider-scoped ID; upstream raw model IDs remain route-local.
- `resolve_offer_routes(offer: CatalogOffer, routes: Sequence[OfferRoute]) -> list[OfferRoute]` returns primary then ordered eligible same-brand routes; skips disabled, stale, unconfirmed, or price-mismatched routes.
- Add operator APIs `PATCH /api/operator/offers/{offer_id}/routes` (ordered connection route IDs) and `PATCH /api/operator/routes/{route_id}/availability`.

- [ ] **Step 1: Write failing catalog identity and route-order tests**

Add `test_same_brand_duplicate_upstream_model_merges_to_one_offer`, `test_same_model_from_different_brands_stays_distinct`, `test_public_model_id_is_stable_and_provider_scoped`, `test_route_order_skips_disabled_or_stale_connections`, `test_offer_with_missing_or_unmapped_connection_never_resolves`, `test_price_mismatch_route_is_ineligible_for_fallback`, and `test_route_can_only_reference_exact_discovered_upstream_model`.

- [ ] **Step 2: Run `py -3.11 -m pytest tests/test_routing.py -q` and verify failures.**

- [ ] **Step 3: Implement the pure route resolver and database grouping**

Canonical match uses explicit Models.dev exact identity or an operator-approved manual mapping. Do not fuzzy-merge two upstream IDs. One `(brand, canonical model)` creates one `CatalogOffer`; each connection keeps its own raw upstream ID and route state.

- [ ] **Step 4: Implement ordered route editing with price-equality validation and audit events**

Reject route-order updates if a selected candidate’s active user-facing price differs from the offer price. Keep offer-level availability separate from each route-level availability.

- [ ] **Step 5: Run `py -3.11 -m pytest tests/test_routing.py tests/test_portal_api.py -q`; verify duplicate merging, distinct vendors, owner access, and route mutation audit.**

- [ ] **Step 6: Commit Task 5 on the isolated feature branch**

Stage only `app/routing.py`, catalog/route repository and API changes, and their tests; commit as `feat: merge provider offers and configure routes`.

## Task 6: Enforce provider budgets and shared expiring user credits

**Files:**
- Modify: `app/portal_db.py`
- Modify: `app/portal_api.py`
- Modify: `app/periods.py`
- Test: `tests/test_portal_db_catalog.py`
- Test: `tests/test_portal_gateway.py`
- Test: `tests/test_portal_api.py`

**Interfaces:**
- `PortalDatabase.assign_user_allowance(user_id: str, amount_nano_usd: int | None, period: Literal["daily", "weekly"] | None, actor_id: str) -> None` stores operator-set allowance and audits the change.
- `PortalDatabase.set_connection_budget(connection_id: str, limit_nano_usd: int | None, period: Literal["daily", "weekly", "monthly", "lifetime"] | None, reserve_nano_usd: int, actor_id: str) -> None` stores per-connection exposure policy.
- `PortalDatabase.reserve_request_budget(owner_user_id: str, key_id: str, offer_id: str, connection_id: str, estimated_nano_usd: int, now: datetime, global_limit_nano_usd: int | None) -> BudgetReservation | None` atomically checks and reserves all active scopes.
- `PortalDatabase.settle_request_budget(reservation_id: str, charged_nano_usd: int, usage_fields: UsageFields | None) -> None` appends usage snapshot and settles/releases reservation in one transaction.
- Current-period usage queries include prior events from the same user/key/provider connection, including idempotently imported legacy events; archived/disabled resources do not erase current-period consumption.
- Add `POST /api/operator/connections/{connection_id}/budget`; add user allowance/reset fields to `/api/developer/dashboard` and `/api/operator/people`.

- [ ] **Step 1: Write failing period and scope tests**

Add `test_user_allowance_is_shared_across_keys_and_connections`, `test_allowance_resets_at_berlin_boundary_and_expires_old_credit`, `test_current_period_includes_legacy_usage_after_key_archive`, `test_provider_cap_includes_connection_usage_from_current_period`, `test_provider_cap_is_scoped_to_selected_connection_and_period`, `test_reserve_is_subtracted_from_provider_available_headroom`, `test_key_cap_only_tightens_user_allowance`, `test_all_budget_scopes_reserve_atomically`, `test_concurrent_last_credit_requests_allow_only_one`, `test_released_reservation_does_not_count_as_spent`, `test_settlement_uses_actual_reported_tokens_and_approved_price_snapshot`, and `test_missing_usage_settles_estimate_without_claiming_zero`.

- [ ] **Step 2: Run named tests and demonstrate failures before implementation.**

- [ ] **Step 3: Implement allowance and provider-budget repository policies**

Credits are operator-assigned period allowances, not purchasable/transferable cash wallets. Usage debit is shared across all of one owner’s keys/providers. Provider cap belongs to the selected concrete connection. Store caps/reservations/charges as integer nano-USD. During migration, set existing operator-configured user allowances to Europe/Berlin reset semantics without changing allowance amounts or historical usage.

- [ ] **Step 4: Implement conservative preflight estimate and reservation**

Use the request output limit where supplied; if absent, use a verified model maximum or configured hard maximum. If no finite output ceiling exists, reject with `budget_estimate_unavailable` before dispatch. Text input estimation must be conservative and documented. If a multimodal request cannot be bounded using an explicitly configured offer policy, reject before upstream dispatch. Do not allow an unbounded request through a capped scope.

- [ ] **Step 5: Test settlement and every reservation exit path at repository/service level**

Cover success, upstream error, connect failure, provider timeout, client disconnect, partial stream, and process reservation expiry. Release only when delivery did not occur or unused reservation is known; otherwise settle a conservative estimate. Prevent double settlement and double legacy-history mirroring.

- [ ] **Step 6: Run concurrency and repository tests; then `py -3.11 -m pytest tests/test_portal_api.py tests/test_portal_gateway.py -q`.**

- [ ] **Step 7: Commit Task 6 on the isolated feature branch**

Stage only allowance/provider-budget persistence, API, and tests; commit as `feat: enforce shared credits and provider caps`.

## Task 7: Route the existing OpenAI-compatible gateway through offers

**Files:**
- Modify: `app/main.py`
- Modify: `app/portal_api.py`
- Test: `tests/test_portal_gateway.py`
- Test: `tests/test_provider.py`

**Interfaces:**
- `PortalDatabase.get_offer_for_request(public_model_id: str, key_id: str) -> ResolvedOffer | None` enforces enabled, approved, priced, and key-allowed state.
- `PortalDatabase.record_route_usage(..., connection_id: str, offer_id: str, upstream_model_id: str, price_version_id: str, ...) -> int` writes immutable routing/price snapshots.
- Existing `GET /v1/models` emits stable provider-scoped public IDs for portal keys; existing legacy-key behavior remains unchanged.
- Existing `POST /v1/chat/completions` translates public ID to selected route’s exact upstream model ID.

- [ ] **Step 1: Add failing gateway tests**

Add `test_models_endpoint_returns_provider_scoped_offer_ids`, `test_models_endpoint_never_leaks_connection_credentials_or_labels`, `test_completion_maps_public_model_to_exact_upstream_id`, `test_disabled_or_unpriced_offer_is_rejected_before_upstream`, `test_out_of_budget_rejection_is_logged_without_upstream_dispatch`, `test_same_brand_fallback_is_used_only_when_first_route_is_known_undelivered`, `test_ambiguous_timeout_is_not_retried`, `test_stream_started_is_never_retried`, and `test_usage_snapshots_keep_provider_connection_and_price_version_after_disable`.

- [ ] **Step 2: Run `py -3.11 -m pytest tests/test_portal_gateway.py tests/test_provider.py -q` and verify the new cases fail.**

- [ ] **Step 3: Implement key-scoped offer resolution and `/v1/models` projection**

All-approved keys see currently published offers; selected keys retain explicit public IDs but inactive offers are rejected. Do not expose raw connection IDs, credentials, base URLs, or route priority in developer output.

Budget/model-policy rejections are appended to the request ledger with safe metadata and no prompt body; they must not call an upstream.

- [ ] **Step 4: Implement provider route dispatch and narrow failover semantics**

Before upstream dispatch, invoke `reserve_request_budget` from Task 6. A failed connect before request send may move to next eligible route only after releasing the first route’s reservation and successfully reserving against the candidate connection. Once request bytes may have been delivered, return the safe error and do not retry. Once response headers/body/stream begin, never fail over.

- [ ] **Step 5: Run targeted tests, then `py -3.11 -m pytest tests/test_portal_gateway.py tests/test_provider.py -q`; verify old legacy routes and responses still pass.**

- [ ] **Step 6: Commit Task 7 on the isolated feature branch**

Stage only gateway routing/usage integration and its tests; commit as `feat: route openai requests through provider offers`.

## Task 8: Build operator connection/catalog/pricing/routing UI

**Files:**
- Modify: `frontend/src/contracts/api.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/money.ts`
- Create: `frontend/src/ui/operator/providers/ProviderListPage.tsx`
- Create: `frontend/src/ui/operator/providers/ConnectionDialog.tsx`
- Create: `frontend/src/ui/operator/providers/OfferDetailSheet.tsx`
- Create: `frontend/src/ui/operator/providers/PriceReviewPanel.tsx`
- Create: `frontend/src/ui/operator/providers/RoutePriorityEditor.tsx`
- Create: `frontend/src/ui/operator/people/AllowanceEditor.tsx`
- Create: `frontend/src/ui/operator/usage/OperatorUsagePage.tsx`
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/styles.css`
- Test: `frontend/src/ui/operator/**/*.test.tsx`
- Modify: `frontend/package.json` and lockfile if adding Vitest/Testing Library is needed

**Interfaces:**
- Add typed records for `ProviderBrandRecord`, `ProviderConnectionRecord`, `CatalogOfferRecord`, `PriceVersionRecord`, and `OfferRouteRecord` to `frontend/src/contracts/api.ts`.
- Extend `CreateProviderInput` with `brandSlug` and `connectionLabel`; send rate and USD amount values as decimal strings in the JSON contract. Use `formatUsd()` from `frontend/src/lib/money.ts` for display only.
- `formatUsd(value: string | null, maxFractionDigits = 9): string` preserves small nonzero amounts instead of rendering them as `$0.00`.
- Add `listProviders`, `createProvider`, `syncProvider`, `listOperatorOffers`, `updateOfferPrice`, `approveOfferPrice`, `setOfferAvailable`, `setRouteAvailability`, `updateRouteOrder`, and `updateConnectionBudget` methods to `PortalApi` and implement same-origin calls in `frontend/src/lib/api.ts`.
- Extend existing `updatePersonPolicy` and operator usage APIs to show Europe/Berlin reset time and filter history by provider brand, connection, model, date, and outcome. Filters are enforced server-side, not just on the currently loaded page.
- Components receive typed data and callbacks; no component issues requests directly except through `PortalApi`.

- [ ] **Step 1: Add component tests for empty, loading, partial match, failed sync, pending price, mismatch, and publish/route switches**

Test names: `renders_empty_provider_state`, `shows_sync_error_without_erasing_existing_models`, `keeps_unpriced_offer_off_user_catalog`, `shows_pending_price_beside_active_price`, `blocks_mismatched_fallback_with_reason`, `offer_toggle_is_distinct_from_connection_toggle`, `route_order_is_keyboard_controllable`, `operator_can_edit_user_allowance_period`, `allowance_editor_displays_berlin_reset`, `operator_usage_filters_by_connection`, and `format_usd_keeps_small_nonzero_charges_visible`.

- [ ] **Step 2: Add frontend test runner only if absent and run the tests red.**

- [ ] **Step 3: Extend contracts and `PortalApi` methods**

Keep all state mutations CSRF-protected by existing `request()` helpers and preserve preview mode’s read-only behavior.

- [ ] **Step 4: Implement the focused operator provider components**

Use the existing Radix/shadcn themed primitives and locked tokens. The connection flow separates test from fetch results; the offer sheet compares active/pending prices; route editor uses accessible Move Up/Down buttons and never drag-only controls. The allowance editor clarifies that the allowance is shared across keys and credits expire at reset; usage filters distinguish provider brand from private connection.

- [ ] **Step 5: Wire Providers navigation and per-connection detail into `App.tsx`**

Preserve the five-item operator navigation limit. Show brand and private connection labels separately; never display or retain the raw key in client state after create/test completes.

- [ ] **Step 6: Run frontend tests, `npm run lint`, and `npm run typecheck`; verify success before styling review.**

- [ ] **Step 7: Add responsive styles and capture desktop/tablet/phone views**

Use nested table scrolling only; no body-level horizontal overflow. Verify safe areas, focus, 44px touch targets, error/loading/empty states, and reduced-motion behavior against `.ulpi/design/provider-catalog-credits.md`.

- [ ] **Step 8: Commit Task 8 on the isolated feature branch**

Stage only operator components, API contracts/client, route wiring, tests, and styles; commit as `feat: add operator provider catalog controls`.

## Task 9: Build developer allowance, catalog, key, and activity UI

**Files:**
- Modify: `frontend/src/contracts/api.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/money.ts`
- Create: `frontend/src/ui/developer/AllowanceSummary.tsx`
- Create: `frontend/src/ui/developer/ModelCatalogPage.tsx`
- Modify: `frontend/src/ui/App.tsx`
- Modify: `frontend/src/ui/styles.css`
- Test: `frontend/src/ui/developer/*.test.tsx`

**Interfaces:**
- `DeveloperDashboard.allowance` includes `limitUsd`, `usedUsd`, `reservedUsd`, `period`, `resetAt`, and source label.
- `ModelRecord.id` is stable provider-scoped public ID; price fields include effective version and source; display name is separate from API ID.
- `ActivityEvent` gains route-safe provider/model snapshots, reserved vs settled amount, and token-source completeness without any prompt/response fields.
- Serialize effective rates and USD amounts as decimal strings; use fixed nano-USD arithmetic only on the server and never recompute enforcement in the browser.

- [ ] **Step 1: Add tests for allowance presentation, catalog filters, model detail pricing, key scope, activity privacy, and unknown usage**

Test names: `shows_allowance_reset_in_berlin_time`, `expires_unused_allowance_at_reset`, `groups_models_by_provider_and_sorts_usd_price`, `shows_input_and_output_usd_per_million`, `shows_cached_input_price_only_when_verified`, `omits_unverified_context_and_modality_metadata`, `shows_openai_compatible_example_with_public_model_id`, `new_key_defaults_to_all_published_offers`, `selected_key_uses_stable_public_model_ids`, `per_key_cap_is_labeled_as_sub_limit`, `unknown_tokens_render_not_reported`, and `developer_activity_contains_no_other_user_or_prompt_data`.

- [ ] **Step 2: Run developer UI tests and verify failures before implementation.**

- [ ] **Step 3: Extend typed dashboard/model/activity contracts and API rendering**

Keep unknown tokens as `null`; never coerce missing token fields to zero. Format USD from nano-USD consistently and label local estimates.

- [ ] **Step 4: Implement allowance, provider-aware browsing, and model detail**

Show shared allowance/reset, provider + model identity, input/output price per million USD, and verified capabilities. Provide a model detail view with the public API ID, verified context/max output/modalities, cache rate when known, price source/freshness, and copyable OpenAI-compatible examples. Search/filter does not imply that unpriced/disabled offers are accessible. Never fabricate fields absent from catalog evidence.

- [ ] **Step 5: Update key create/edit flow and activity UI**

Default to all enabled offers; selected mode groups by provider. Key cap copy explains that it can only tighten account allowance. Keep one-time secret reveal behavior. Activity only returns and renders the authenticated user’s events and safe metadata.

- [ ] **Step 6: Run UI tests, lint/typecheck, and review mobile/tablet/desktop screenshots.**

- [ ] **Step 7: Commit Task 9 on the isolated feature branch**

Stage only developer components, contracts/client, route wiring, tests, and styles; commit as `feat: add developer credits and model catalog`.

## Task 10: Finish cross-system verification, operator runbook, and staged rollout gate

**Files:**
- Modify: `README.md`
- Modify: `deploy/README.md`
- Test: `tests/test_provider.py`, `tests/test_portal_api.py`, `tests/test_portal_gateway.py`, frontend test suite

**Interfaces:** no new runtime interface; this task verifies the preceding public contracts and operational rollback.

- [ ] **Step 1: Run the complete Python suite**

Run: `py -3.11 -m pytest -q`

Expected: all existing and new tests pass; report the known Starlette/httpx deprecation separately rather than suppressing it.

- [ ] **Step 2: Run all frontend checks**

Run from `frontend`: `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`.

Expected: all pass; verify compiled `frontend/dist` is served by FastAPI in the integration smoke test.

- [ ] **Step 3: Run security/regression matrix**

Verify invalid/private/resolving-to-private URLs and unsafe redirects are rejected; no secret appears in API responses/logs; non-operator requests cannot mutate providers/prices/routes; one developer cannot see another’s activity/IP; prompts and completions are absent from logs/DB.

- [ ] **Step 4: Run compatibility and cap smoke tests on a disposable local database**

Test old legacy key `/v1/models` and `/v1/chat/completions`, new `provider/model` public IDs, same-brand fallback mapping, final-credit concurrent requests, provider reserve, reset boundary, changed price snapshot, stale sync, and incomplete stream settlement.

- [ ] **Step 5: Document staging-only provider setup, local auth/bootstrap, reset scope, and rollback steps**

State that operator credentials are UI-managed; local account setup and one-time operator bootstrap use the local CLI; HCA stays dormant in code/docs. Document operator multi-use invites, developer single-use invites, password reset, app-data-only backup/restore rehearsal, and the exact future cutover checklist. No production Nest data wipe, stop/restart, deploy, or cutover command is run in this task.

- [ ] **Step 6: Review exact changes on an isolated feature branch/worktree before any commit or push**

Keep pre-existing dirty files out of implementation commits. The existing `main` checkout is already dirty; execution must begin from a clean isolated branch or a user-approved workspace strategy. Review the exact final diff before any push or merge.

- [ ] **Step 7: Commit runbook and integration-test changes on the isolated feature branch**

Stage only the final documentation/tests; commit as `docs: document provider catalog rollout and recovery`.

## Plan self-review

- **Spec coverage:** provider discovery and Models.dev pricing (Tasks 3–4); merge/availability/routing (Tasks 5, 7); shared allowance, provider caps, reserves, request/price snapshots (Tasks 1–2, 6); operator and developer UX (Tasks 8–9); privacy, migration, staging and rollback (Tasks 2, 10).
- **Step scan:** each task has an independently runnable test cycle; API shapes used by the frontend are declared before those UI tasks.
- **Type consistency:** monetary values are nano-USD in repository/service methods and converted to decimal USD in API records; model IDs are stable public IDs in frontend contracts and raw upstream IDs remain route fields.
- **Review Focus:** all five cases map to tests in Tasks 3, 6, and 7. When a request/verified model/configured hard output cap is absent, the plan requires preflight rejection; unsupported multimodal estimation is rejected before dispatch.
- **Scope:** one ordered plan is appropriate because route identity, model pricing, reservations, and the two portals share one catalog and gateway contract; tasks are sequenced, and no independent service is introduced.
