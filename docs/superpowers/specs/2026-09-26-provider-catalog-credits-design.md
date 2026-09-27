# Provider Catalog, Routing, and Shared Credits Design

## Status

Draft for owner review. This design extends the approved universal provider portals; it does not authorize implementation or production deployment.

## Summary

Extend Sponsored Provider into a multi-provider OpenAI-compatible gateway with a provider-scoped model catalog, multiple upstream connections per provider, approved USD price schedules, provider and user spending controls, and a shared expiring credit allowance per user.

The public catalog keeps different provider brands distinct (for example, `nebius/deepseek-v4-flash` and `openrouter/deepseek-v4-flash`). Connections belonging to the same brand that expose the same canonical model merge behind one public model. Each public model uses an operator-selected primary connection and an explicitly ordered fallback list. A fallback cannot be enabled if its approved user-facing price differs from the catalog offer's price.

Keep the existing FastAPI + React/Vite single deployment, OpenAI-compatible `/v1` contract, and SQLite pilot. Active portal authentication changes to local username/password accounts with invite-gated signup. Hack Club Auth code and documentation remain in the repository but are disabled from active routes and UI. Add database migrations and preserve all existing usage history until a separately approved app-data reset. No production cutover is part of this design.

## Goals and success criteria

1. An operator can add an OpenAI-compatible connection through the UI, save its upstream credential encrypted, and immediately discover its models through `/models`.
2. Each model is matched against Models.dev as the primary price source where possible. Unmatched or uncertain prices require operator entry and approval. Missing prices never imply free use.
3. Price approval and user availability are independent controls.
4. Multiple connections of the same provider and canonical model appear as one user-facing model. Different provider brands remain distinct.
5. The operator can assign each provider connection a USD spend cap and selectable reset period; an optional reserve reduces the local stop threshold.
6. Each user has one operator-assigned USD allowance shared across all of their keys and provider models. The allowance resets daily or weekly in Europe/Berlin time; unused credits expire.
7. Per-key caps and model selections can only narrow the user’s access; adding keys never multiplies their allowance.
8. Concurrent requests reserve budget atomically before upstream dispatch and settle against reported usage or a clearly marked estimate.
9. Provider keys, prompts, and completions are never exposed to users or persisted in request history.
10. Disabling or renaming a user, key, model, provider offer, or connection never rewrites or deletes historical usage.

## Confirmed product decisions

- Product is universal and provider-neutral, not Alibaba-specific.
- Initial gateway compatibility remains OpenAI-compatible `/v1/models` and `/v1/chat/completions`; provider keys and base URLs are configured in the operator UI.
- Provider brand and provider connection are separate concepts. A connection is a base URL plus a credential and private operator label.
- Model identity is scoped to provider brand plus a canonical model identity. Same-provider duplicate connections merge into one catalog offer; different brands do not merge.
- Public model identifier is stable and provider-scoped, such as `nebius/deepseek-v4-flash`. UI display labels can be more readable but do not change the API identifier.
- `/models` discovery happens immediately after connection setup and can also be manually refreshed.
- Models.dev is the primary suggested price source. Provider-reported prices, when available, appear as comparison data. Operator prices are explicit USD per million tokens (input, output, and optional cached input).
- Price suggestions and price changes are never silently applied. Operator approval creates the active immutable price version. User availability requires a separate explicit switch.
- An unresolved or unverified price makes a model unavailable. A rate mismatch across candidate routes blocks that route from the fallback chain until reconciled.
- User-facing usage is charged 1:1 against the active approved route price by default, with an explicit operator override available. No automatic markup.
- User allowance is one shared pool across all the user’s keys, provider brands, and model offers. It is operator-assigned, daily or weekly, resets in Europe/Berlin time, and has no rollover.
- User-created API keys inherit all enabled offers by default, or may be restricted to a selected subset. Optional per-key caps are stricter sublimits, never additional allowance.
- Provider connection caps may be daily, weekly, monthly, or lifetime, and may have an optional reserve.
- Model routing uses one primary connection and manually ordered eligible fallbacks. Do not load-balance automatically. Only fail over when it is clear the request was not delivered upstream; do not retry ambiguous timeouts or after a response/stream starts.
- Every request reserves estimated maximum cost against all applicable global, user, key, and provider-connection limits before dispatch. Reconcile from upstream token usage when supplied; otherwise store a marked estimate. Reject before dispatch when the estimate cannot fit.
- Reports must distinguish gateway estimates from provider invoices. The local stop threshold is not a guarantee of the provider’s eventual invoice amount.
- Detailed request records contain time, provider/model/connection snapshot, request outcome, input/output/total/cached token counts where available, latency, estimated charge, safe error category, request ID, and client IP subject to role/privacy policy. Prompts and completions are not stored.
- Active authentication is local username/password; Hack Club Auth remains dormant in code/docs only.
- Signup requires an invitation. Operator-issued invitations have an operator-selected maximum-use count and expiry; operator can revoke them. Each developer can issue one single-use invite, and each newly created developer receives the same one-invite allowance.
- Usernames are unique case-insensitively. Passwords are stored with Argon2id hashes; auth endpoints are rate-limited, sessions use secure HTTP-only same-site cookies, and state-changing requests retain CSRF protection.
- The first operator is bootstrapped through a one-time server-side setup secret/command, never an open public registration path. The bootstrap is disabled once an operator exists.

## Considered architecture options

### Chosen: provider-scoped offers with connection routes

Catalog offer identity is `(provider brand, canonical model ID)`. Multiple matching connections attach as ordered routes. Benefits: simple user-facing catalog, no duplicate listings from multiple credentials, clear price separation between vendors, and explicit operator control over route choice.

### Rejected: connection-scoped offers

Each credential creates its own catalog entry. This is operationally explicit but duplicates the same model for one provider, contrary to the desired catalog.

### Deferred: global cross-provider canonical offers

One model ID would span vendors and route across them. This hides vendor-specific availability/pricing and complicates the user’s ability to choose a provider. Cross-brand routing is not in the initial release.

### Runtime shape

Use the existing modular monolith. Keep identity, operator control plane, developer self-service, provider connections, catalog/pricing, gateway/policy, usage ledger, and audit as distinct modules within one FastAPI service. The React/Vite app remains a static same-origin frontend. SQLite remains acceptable for the invite-only, single-process pilot with short `BEGIN IMMEDIATE` budget reservations, migrations, and tested backups. PostgreSQL becomes a rollout prerequisite before multiple write workers or sustained contention, not a premature second service.

## Domain model additions

Logical entities; exact SQL and migration steps belong in the later implementation plan.

- **ProviderBrand:** canonical vendor slug/name, logo/metadata if available, created/updated state.
- **ProviderConnection:** brand, operator label, OpenAI-compatible base URL, encrypted secret, test/sync status, enabled state, and per-connection spend policy.
- **ConnectionModel:** raw upstream model ID as returned by `/models`, canonical model reference, advertised metadata, last-seen sync, and route eligibility.
- **CatalogOffer:** provider brand plus canonical model identity, stable public ID, display name, capabilities, approved/available state.
- **OfferRoute:** catalog offer, provider connection, exact upstream model ID, priority, enabled/health state.
- **PriceVersion:** immutable input/output/cached-input rates in USD per million, source (`models.dev`, operator, provider-reported comparison), match confidence/evidence, approver, effective time, and superseded state.
- **UserAllowance:** operator-assigned amount, daily/weekly period, period start/end, Europe/Berlin reset semantics, and status.
- **ProviderBudget:** per connection amount, daily/weekly/monthly/lifetime period, optional reserve amount/ratio, period boundaries, and enable/stop state.
- **BudgetReservation:** one atomic preflight reservation associated with user, key, selected offer, chosen connection, global/user/key/provider scopes, estimate, price snapshot, status, creation, expiry, and settlement.
- **UsageEvent:** append-only request row with stable IDs and human-readable snapshots so deletion/rename of current entities cannot corrupt old reports.
- **AuditEvent:** actor, action, target, timestamp, redacted before/after policy summaries, outcome. Never store raw provider keys or prompts.
- **Local account credentials:** unique normalized username, password hash and algorithm parameters, account status, timestamps, and credential-change/recovery metadata. Raw passwords and reset tokens are never persisted.
- **Invitation:** token hash, issuer, max uses, uses consumed, expiry, revocation state, and audit timestamps. Operator invitations can have a configured use count; developer-issued invitations are single-use, with at most one issued invitation per developer.
- **Portal session:** opaque high-entropy token hash, owner, CSRF secret hash, creation/expiry, and revocation metadata. Authentication sessions do not depend on Hack Club Auth.

For user allowances, represent the active-period grant and consumption as a balance calculation, not a purchasable wallet or a transferable cash balance. Each request debit is one time-ordered ledger event; reset changes the active allowance window and does not erase historical consumption.

## Model discovery and pricing lifecycle

### Add connection

1. Operator enters provider brand (select known brand or define custom compatible brand), private label, HTTPS base URL, and API key.
2. Backend validates URL scheme and host, blocks loopback/private/link-local/reserved addresses, revalidates resolved addresses at connection time, and handles redirects without allowing SSRF. Secret is encrypted before persistence and write-only thereafter.
3. Operator chooses **Test & fetch models**. The adapter requests the compatible `/models` endpoint and validates the response shape. A failed test does not create a falsely healthy connection.
4. Discovery is idempotent. Persist exact upstream IDs and metadata, last successful sync, and new/changed/missing records. Do not delete prior model or usage rows.
5. Match provider + upstream ID to Models.dev records. Exact matches are suggested; ambiguous matches are marked unresolved and require operator selection/manual pricing. Do not scrape a website if no supported data interface exists; implementation must verify the supported Models.dev data source/API and its terms.

### Model and price states

`discovered → needs match or price → price review → priced/approved → enabled for users`

Other conditions are orthogonal: `stale`, `disabled offer`, `disabled route`, `route price mismatch`, `unsupported capability`, and `provider unavailable`. This avoids conflating “has a price” with “available to users.”

- New prices and changed prices are pending versions; the previous approved version stays active until operator approval.
- Models.dev is primary. Provider-reported price metadata is shown as a secondary comparison and does not silently override the primary suggestion.
- Manual values must be entered in USD per million tokens. If a source is in another currency, show the source amount and require explicit normalized USD pricing in the first release; do not apply an unreviewed live exchange rate.
- Price version stores its source, match, approver, and effective timestamp. Request events snapshot the rates used.
- If a model is absent from a successful sync, mark the connection-model mapping stale/unconfirmed and notify the operator; do not delete history. Require review before routing that stale connection again. Another healthy, price-compatible route may continue to serve the offer.
- If `/models` fetch fails, keep the last known catalog, mark sync stale/error, and make no destructive catalog updates.
- Model capability is explicit and operator-verified; never assume vision or other features based only on a model name.

## Routing and OpenAI-compatible API

1. Developer sends the stable public model ID to the existing `/v1/chat/completions` endpoint.
2. Gateway authenticates the issued key, derives its owner and policy from server-side records, and verifies that the public offer is enabled, approved/priced, and allowed by this key.
3. Gateway resolves the offer’s primary eligible connection and maps the public model ID to that route’s exact upstream model ID. Public names are never sent upstream unless they happen to match.
4. If primary is unavailable before delivery, evaluate fallbacks in configured priority order, skipping disabled, stale, unhealthy, or price-mismatched routes. Do not fall back across provider brands.
5. Never retry if request delivery is ambiguous, an upstream response has begun, or stream output has started. A future provider idempotency capability may refine this, but is not assumed.
6. `/v1/models` returns only offers available to that caller’s key, using the public provider-scoped IDs. It does not expose base URLs, connection labels that are private, credentials, or internal routing order.
7. Continue to support established OpenAI-compatible request fields, streaming only when available; report unsupported capabilities plainly.

## Limits, credit accounting, and settlement

### Enforcement hierarchy

Every eligible request is checked against:

1. Global emergency/owner stop (existing guardrail).
2. User allowance for the active daily/weekly Europe/Berlin period, shared across all user keys/providers.
3. Optional per-key cap and key RPM; cannot relax user policy.
4. Selected provider connection’s own cap and reserve.
5. Existing user-wide RPM and IP/model safeguards.

All applicable budget scopes are reserved in one database transaction before upstream dispatch. The request is rejected with an OpenAI-compatible structured error if its worst-case approved-price estimate cannot fit. Use token counts from the request where possible, including maximum requested output; use a configured conservative output bound when omitted. The implementation plan must ensure there is no path that forwards an unbounded-cost request past a hard cap.

### Settlement

- If upstream reports input/output/cached token usage, calculate user charge from the active public offer’s approved user-facing rate and chosen route’s price snapshot. Cache discount only applies when cached-token count and an approved cached-input rate are both known; otherwise charge cached tokens at the regular input rate and label that rule.
- If token usage is unavailable, preserve unknown token fields and settle using the reserved/conservative gateway estimate. Never fabricate zero tokens or free spend.
- Provider connection exposure uses the same approved route price schedule unless a separately verified provider cost schedule exists. This is still gateway-estimated exposure, not a provider invoice.
- Settle or release reservations atomically. Reservation expiry is a crash-recovery mechanism, not a way to erase completed spend. Streaming settlement occurs at completed stream; interrupted streams retain a conservative estimate if usage is absent.
- Period resets use `Europe/Berlin`; timestamps are stored in UTC, and reset boundaries must account for DST changes.
- A reserve reduces the stop point under the selected provider limit. UI shows configured cap, reserve, consumed amount, active reservations, and effective remaining headroom separately.

## Portal interaction and data visibility

See `.ulpi/design/provider-catalog-credits.md` for the detailed UX state and component handoff. In brief:

- Operator sees provider brands with connection rows, connection health/sync, model offer counts, cap progress, and last sync. Provider detail separates the **offer available to users** switch from each **connection route enabled** switch.
- Operator can review model discovery and price matching in batches, set USD rates, approve a price version, separately publish an offer, order fallback routes, and resolve route-price mismatch alerts.
- Operator assigns per-user allowance amount/period and RPM, views current balance/reset, and may disable a user. Operator usage/audit filters by user, key, brand, connection, model, date, result, and estimate/report source.
- Developer sees assigned allowance and reset, the enabled provider-scoped catalog, their own keys, and their own request logs. New keys default to all enabled offers, optionally restricted to selected offers. Optional key cap and RPM are tighter sublimits.
- Developer log includes time, model/provider, token fields (unknown stays unknown), estimated charge, latency, status, safe error category, and their request source IP. No prompt/response viewer.
- A model detail page identifies the provider-qualified model and API ID, shows input and output USD per 1M tokens (plus cached-input pricing when verified), and includes context window, max output, modalities, price source/freshness, and OpenAI-compatible code samples only when the underlying values are known. Unknown metadata is omitted or explicitly marked unavailable; it is never inferred from model names.
- Catalog cards stay scannable and show provider, model, input/output pricing, availability, and verified capability badges. Search, provider/capability filters, and price sorting lead to a detail view rather than expanding every model inline.
- Search, filters, clear loading/empty/stale/error/success states, small-screen layouts, keyboard operation, and WCAG AA contrast remain required.

## Security and privacy boundaries

- Provider credentials are encrypted at rest and write-only in operator UI. They never appear in `/v1/models`, developer portal data, logs, errors, or HTML/client state.
- Outbound base URL validation must resist DNS rebinding and redirect-based SSRF. Do not trust user-provided forwarded headers except the configured proxy chain.
- Browser control APIs use same-origin local-account sessions, CSRF, role/ownership checks. Developer APIs never accept caller-supplied owner IDs as authority. Hack Club Auth routes are not mounted/usable in the active runtime and its controls are absent from the UI; the dormant implementation and docs are preserved for a future explicitly approved reactivation.
- Password hashes use Argon2id with current OWASP-recommended parameters, per-password random salt, and constant-time verification. Enforce reasonable password length limits and reject common/known-compromised choices without imposing arbitrary composition rules.
- Login and signup are rate-limited by account identifier and network source; responses do not reveal whether a username exists. Session cookies are Secure in production, HttpOnly, SameSite=Lax/Strict as flow permits, rotated on authentication/privilege change, and revocable on logout/password reset.
- Invite consumption and account creation are one atomic transaction. Usage cannot exceed `max_uses` under concurrent signups. Invite tokens are high entropy, stored only as hashes, single-view on creation, expirable and revocable.
- First-operator bootstrap is a one-time server-side procedure protected by a setup secret; disable it once an operator exists. No public route can self-assign operator role.
- Local password recovery is operator-assisted for the initial release; require a one-time forced password change/reset token and audit it. Do not claim email recovery until an email delivery and abuse-control design exists.
- Request content is not persisted. Scrub authorization headers and upstream bodies from error details. Store request correlation IDs and safe error classes.
- Source IP has abuse-prevention purpose and role-scoped display; define retention/erasure in the rollout policy before external onboarding.
- Audit records capture who changed prices, approval, model availability, route order, budget, reserve, user allowance, and connection state.

## Failure modes and operator recovery

| Failure | Behavior |
|---|---|
| Provider credential/base URL invalid | Test fails with redacted category; do not mark connection healthy or expose upstream body. |
| `/models` timeout or malformed response | Keep last known data, mark sync failed/stale, offer retry; no deletions. |
| Models.dev exact match unavailable/ambiguous | Keep model unavailable pending manual match and approved USD rates. |
| Models.dev price changes | Keep active version; show pending diff and require approval. |
| One route goes stale or fails before delivery | Skip it and consider next manually ordered eligible fallback. |
| Request delivery uncertain | Return safe error; do not retry automatically. |
| User/provider/global budget exhausted | Reject before dispatch; show which scope stopped it and next reset where applicable. |
| Upstream usage absent/incomplete | Show unknown token fields and clearly labeled estimate; no free/zero substitution. |
| Price mismatch in fallback | Block that route and show remediation in operator UI. |
| Provider/model disabled or archived | Stop new use; retain historical labels, pricing, and usage. |

## Migration and release sequence

This plan extends the current portal and its SQLite schema. Preserve existing provider and historical usage data; map each legacy provider profile to a brand + connection without changing old event values. New canonical IDs apply to new requests; legacy event labels remain snapshots.

1. **Schema and migration:** introduce brand/connection/offer/route/price-version/budget structures; add indexes and migration integrity tests; take a backup and restore-test copy.
2. **Discovery and pricing:** immediate `/models` sync, idempotent state, Models.dev matching, manual fallback, immutable price approvals; no public availability yet.
3. **Catalog and routing:** provider-scoped stable IDs, duplicate merging, explicit offer/route controls, primary/fallback settings, price equality gate, compatibility tests for `/v1/models` and completions.
4. **Credits and budgets:** Europe/Berlin grants, provider connection budgets/reserves, atomic reservation across all scopes, settlement and concurrency stress tests.
5. **Portals and history:** operator/user screens, filters and own-user privacy tests, historical snapshot migration and post-archive tests.
6. **Staging and cutover:** deploy side-by-side only if Nest permits a safe isolated port/domain; backup/restore, smoke test existing `/v1`, test OAuth, provider test key, cap enforcement, rollback. Do not stop/restart the existing Nest service without explicit cutover approval.

## Verification and measurable release gates

- Duplicate model IDs across two connections of one brand create one public offer; same IDs from different brands create distinct public offers.
- `/v1/models` exposes only enabled/approved/price-ready models allowed by the key.
- Connection-specific upstream ID mapping is correct for every primary and fallback route.
- A pricing update never alters prior usage; mismatches block fallback; unpriced models never pass a completion call.
- Concurrent requests cannot exceed locally configured global/user/key/provider limits, including simultaneous final-credit requests.
- Test preflight rejection, exact-boundary amount, reserve amount, request with large max completion, missing token usage, partial stream, disconnect, timeouts before/after dispatch, and failed fallback.
- Failed sync and removed model preserve history and never silently erase catalog state.
- Cross-user access tests prove users cannot see another user’s allowance, keys, usage, IP, or provider details.
- Security tests cover SSRF, DNS changes, redirects, secret redaction, CSRF, session expiry, and connection secret handling.
- Backup restore on staging succeeds, existing `/v1` compatibility tests pass, and rollback procedure is rehearsed before production cutover.

## Out of scope for first release

- Public registration, paid credit purchase, money transfer, resale, or a public marketplace.
- Cross-provider automatic routing or load balancing.
- Native proprietary provider protocols; initial providers need OpenAI-compatible endpoints.
- Automatic model price changes or unreviewed FX conversion.
- Prompt/completion storage, chat history, file/RAG/tool services.
- Claiming gateway estimates are exact provider invoices or an externally guaranteed financial hard cap.
- Replacing the current Nest deployment/database topology before measured need and safe migration.

## Risks and follow-up checks

1. **Models.dev integration:** implementation must verify a supported API/dataset, exact provider naming, price units, update cadence, and usage terms. Fuzzy matching must never auto-publish a model.
2. **Price-vs-invoice divergence:** current provider deals, cache discounts, free quotas, and billing rounding can diverge. Expose estimate source and retain a safety reserve; do not claim invoice-exact limits.
3. **SQLite write concurrency:** atomic multi-scope reservation is safe only for one application writer process. Move to PostgreSQL before multiple write workers or contention; don’t scale workers first.
4. **Duplicate identity:** a vendor may publish aliases or change IDs. Operator mapping and stable historical labels are required.
5. **Stale model availability:** discovery may be account/region scoped. Show region, last sync, and sync error where available; stale routes require review.
6. **Provider brand/connection terminology:** UI needs explicit examples and private connection labels to avoid confusing a vendor brand with a credential profile.

## Decisions still subject to written-spec review

- Exact Models.dev supported access method and match confidence thresholds.
- Whether to provide a built-in reasonable default output cap if a client omits `max_tokens`; until decided, never let an uncapped request bypass budget reservation.
- Detailed retention duration for source IP and low-level request records.
- Pricing display precision and minimum charge rounding (internal arithmetic must use decimal-safe fixed precision, not floating point).
- When to require PostgreSQL based on request volume/write contention before provider expansion.
