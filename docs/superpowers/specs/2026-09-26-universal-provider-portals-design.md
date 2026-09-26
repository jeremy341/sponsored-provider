# Universal Provider Portals: Product and Architecture Design

## Executive summary

Evolve Sponsored Provider from an owner-only dashboard into one OpenAI-compatible gateway with two role-specific portals: an Operator portal for service control, and a Developer portal where invited Hack Club users create their own API keys and inspect only their own request history. Keep one FastAPI deployment and the existing `/v1` contract. Make provider profiles generic OpenAI-compatible upstreams instead of Alibaba-specific. Preserve request history permanently when users, keys, models, or providers are disabled or archived.

This document is the architecture/product specification. Visual interaction and component details live in `.ulpi/design/provider-portals.md`; the locked visual language is `.ulpi/design/DESIGN.md`.

## User intent and success

The product owner connects arbitrary OpenAI-compatible providers and sponsors access for classmates. Each user gets an independent login, allowance, RPM bucket, key inventory, and private usage view. The operator controls the global cost ceiling, approved provider/model catalog, user budgets, abuse response, and audit.

Success means:

1. Existing coding tools continue calling the same `/v1/chat/completions` and `/v1/models` endpoints.
2. Each user's keys and usage are server-enforced as user-owned resources.
3. Provider keys remain server-only and encrypted; developer accounts never receive them.
4. Limits apply across concurrent requests at global, user, and optional key scopes.
5. Historical records remain accurate after access changes and show local estimates separately from provider-reported billing.

## Decisions and alternatives

### Chosen: one modular monolith with two web portals

One FastAPI service remains the runtime boundary. A React/Vite static SPA is built and served from that same app. Backend modules have explicit responsibilities: identity/session, operator administration, developer self-service, provider catalog/adapters, gateway/policy, usage ledger, and billing reconciliation.

Why: this fits the present single Nest deployment and small user group, preserves one API origin, and avoids a second service/database operation burden. Keep stable API and database boundaries so modules can be separated later if actual scale or team ownership requires it.

### Rejected for initial release

- Separate operator and user apps/services: adds deployment and identity synchronization before independent release/scaling is needed.
- Public OpenRouter-style marketplace: public onboarding, provider fallbacks, billing, reviews, ranking, and wallet features exceed the sponsored-gateway need.
- Native integrations for every vendor at launch: first support arbitrary OpenAI-compatible base URLs and bearer-key auth. A provider adapter interface can accommodate native protocol connectors later.
- Persisting prompts/completions: not needed for quota/accountability and increases exposure of user data.

## Runtime topology

```text
Browser ──HTTPS──▶ Nest domain / FastAPI app
                       ├── `/` and `/app/*`: role-aware static React SPA
                       ├── `/auth/*`: Hack Club OIDC callback/session endpoints
                       ├── `/api/*`: authenticated portal control/data APIs
                       └── `/v1/*`: OpenAI-compatible client gateway
                                 │
                                 └── selected OpenAI-compatible provider profile

FastAPI ──transactional access──▶ persistent database
                                  ├── users / invites / sessions
                                  ├── provider profiles / catalog / prices
                                  ├── issued API keys / policies
                                  ├── immutable usage ledger / reservations
                                  ├── audit events / billing snapshots
                                  └── rate-limit windows
```

The frontend is static build output, not a second production web service. `/v1` stays stable. The frontend's session authentication does not replace bearer auth for coding agents.

### Data store decision

Retain SQLite during an invite-only pilot if the Nest service remains single-process and uses short write transactions for budget reservations, rate windows, and usage append. Add schema migrations and scheduled backups before onboarding users. A PostgreSQL move is a scale gate before multiple app workers, sustained write contention, or open registration; do not introduce a separate database runtime preemptively.

## Identity, roles, and tenant boundaries

### Authentication

Use Hack Club Auth OpenID Connect. Create an OAuth app, validate state/nonce and the signed ID token via the advertised JWKS/discovery metadata, then map the stable `sub` to a local user. Request only `openid`, `profile`, and `email` unless a documented membership gate truly needs another scope. Browser sessions are opaque, server-managed, rotated on login, revocable, and carried in `Secure`, `HttpOnly`, `SameSite` cookies. State-changing browser routes use CSRF protection. The OAuth client secret stays in server secrets.

Official Hack Club Auth documents describe the OIDC discovery, authorization-code exchange, ID-token validation, and community-accessible scopes. [OIDC guide](https://auth.hackclub.com/docs/oidc-guide) · [OAuth guide](https://auth.hackclub.com/docs/oauth-guide)

### Roles and onboarding

- `operator`: exactly the owner/operator role; manage users, providers, approved catalog, global policies, reconciliation, and audit.
- `developer`: read/update own profile, keys, and usage; cannot see upstream credentials, other users, global budgets, or account billing.
- `pending/disabled`: may authenticate but cannot create/use gateway keys until activated; disabled users' keys stop immediately.

Onboarding is invite-only. Operator creates a one-time, expiring invite. The invite binds to the Hack Club identity after sign-in. User status and allowance are set before API key creation. Day one requires a valid Hack Club Auth identity plus an invite; do not require a separate verification-status scope. No unbounded public sign-up in the initial release.

### Authorization invariant

Never trust `user_id`, `owner_id`, role, key owner, or tenant selector sent by the client as proof of access. Derive actor identity from the server session. For every user request, scope database reads/writes by that authenticated user. API-key calls resolve the key hash to a key and its owner before applying policy. Admin access uses a distinct role gate, not a browser-visible admin token kept in local storage.

OWASP's multi-tenant guidance emphasizes object-level authorization for each resource and tenant-aware rate limits. [OWASP Multi-Tenant Security](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)

## Domain model

Logical entities (exact SQL schema is an implementation-plan decision):

- `User`: random internal ID, unique OIDC subject, minimal profile, role/status, created/last-login timestamps, operator-assigned budget and user-wide RPM.
- `Invite`: hashed token, expiry, use count/state, issuer, optional bound email/subject; token shown only at creation.
- `Session`: hashed opaque session token, user, issue/expiry/revocation timestamps, device/session metadata.
- `ProviderProfile`: random ID, display name, OpenAI-compatible base URL, encrypted write-only API credential, enabled/test state, last sync.
- `ProviderModel`: provider ID + canonical model ID, capabilities, operator approval, input/output/cache rate card, price source/effective time, health/catalog freshness.
- `ProviderKey`: public random ID, owner user ID, label, prefix, salted hash, creation/expiry/disable/archive state.
- `KeyPolicy`: allowed-model mode (`all approved` or fixed list), optional lower spend cap/reset, optional lower RPM, status. All-approved is dynamic over the operator-approved, priced catalog; explicit model selection stays pinned.
- `UsageEvent`: immutable request record with stable user/key/provider/model identifiers and label snapshots, timestamp, request outcome class, status/error category, measured latency, input/output/total/cached tokens where upstream supplies them, estimated cost and price snapshot, client IP, and request correlation ID. Never contains request prompt or completion content.
- `BudgetReservation`: in-flight estimated cost/token reservation linked to user/key/provider/model, status and timestamps; prevents concurrent calls from overshooting local caps.
- `BillingSnapshot`: operator-imported/provider-reported bill amount, source, period, observed timestamp, currency, and adjustments. It is separate from gateway event estimates.
- `AuditEvent`: actor, operation, target, timestamp, redacted policy changes, and result. Never stores raw secrets or user prompts.
- `RateWindow`: persistent user, key, provider safety scope and fixed-window/sliding-window counter data, atomically updated.

No user/key/model/provider archive operation cascades to usage events. Access removal only disables future traffic. Account closure uses disable/anonymize retention policy; any regulated deletion requirement must be designed separately from the financial ledger.

## Request processing and limit hierarchy

1. Resolve provider key from bearer credential and reject unknown, disabled, archived, or unapproved keys.
2. Resolve its owner; reject inactive users. Resolve client IP using only the configured trusted Nest proxy chain; never trust arbitrary forwarded headers.
3. Enforce IP abuse block and RPM scopes: user-wide aggregate bucket across their keys, optional lower key bucket, and optional per-provider safety ceiling. Different users never share a quota bucket merely because they use the same upstream key.
4. Validate body, API route support, selected model membership in the key's effective policy, and provider/model health.
5. Require verified input/output pricing for budgeted calls. Compute preflight cost estimate and reserve against global, user-period, and per-key-period budget atomically. The tightest cap wins.
6. Forward to the selected provider through an OpenAI-compatible adapter. Keep upstream credentials server-side.
7. Record one immutable outcome with response usage fields, latency, status, request ID, and local estimated cost. Release or settle the reservation. If provider usage is missing, mark estimate/provisional clearly.
8. Return the compatible response and safe request ID; never echo credentials or internal error bodies.

Limit semantics:

- **Global hard stop:** owner-controlled maximum provider exposure; prevents additional requests after reservations/usage reach the stop threshold.
- **User allowance:** operator assigns a daily or weekly maximum shared across all of that user's keys. Users cannot increase it themselves.
- **Per-key cap:** developer may leave it inheriting the user allowance or choose a stricter daily/weekly/monthly/lifetime cap, bounded by remaining user allowance.
- **RPM:** operator-assigned per-user request ceiling shared across keys; developers may choose a lower per-key cap but cannot increase the user limit. Provider RPM/TPM controls are upstream safety ceilings, not user identity buckets.
- Use reservation headroom and preflight estimation; never promise accounting to the exact upstream cent because provider pricing, cache hits, free quotas, and bill timing can differ.

## Usage and billing truth

The UI always labels data source:

- `Gateway estimate`: calculated from measured tokens and the request-time price snapshot; cache-hit discount is applied only when cached-token counts and a verified cache rate exist.
- `Provider-reported usage`: upstream usage/token values returned with the call.
- `Reconciled provider bill`: import/manual or future authorized billing integration from the provider. It is not backfilled into or substituted for per-request estimates unless a mapping is supported.
- `Provider account balance/coupon`: a last-observed provider-account snapshot; it can include other products/usage and is not the sum of this proxy's users.

Screens provide an optional time window and user/key/model/provider/status filters. A user sees only their own activity. Operators see aggregate and drilldown views, including client IP for abuse investigation. Requests without provider usage show `Usage not reported` and a conservative estimate; they are not mislabeled `Free`.

### Metric definitions

- **Authenticated request attempts:** calls with a valid active key and resolved user. Count policy/validation rejections separately so denied requests do not inflate upstream-forwarded totals.
- **Forwarded requests:** requests actually sent to an upstream.
- **Successful requests:** upstream calls completing successfully. For streams, success is finalized at stream completion; interrupted streams receive their own outcome.
- **Rejected requests:** validation, model policy, budget, or RPM stops before forwarding; show a reason category.
- **Input/output/total tokens:** use upstream usage fields. Missing values remain unknown, never zero. Derive total only if input and output counts are both available and upstream total is absent.
- **Latency:** gateway elapsed time from upstream dispatch through completion. Show p50/p95 only with at least 20 forwarded events in the selected period; otherwise show sample count and omit percentiles.
- **Estimated spend:** request-time input/output price snapshot. Apply cached input rates only when the provider reports cache-hit tokens and a verified cache rate exists; otherwise use normal input rate and label it estimated.
- **Allowance usage:** sum local event estimates across active and archived keys owned by the user in the current period, plus active reservations. A per-key cap is a stricter sublimit, not extra allowance.

## Provider/model onboarding

Operator enters a profile name, OpenAI-compatible base URL, and API key. Validate HTTPS/public host and resist SSRF, save the credential encrypted, then explicitly test credentials and fetch `/models`. Sync creates/updates a discovered catalog as `unapproved`. Operator sets/verifies input/output rates and capabilities, then approves the model. All-model user keys inherit newly approved and priced models; keys with fixed selections do not. Removed/renamed models are marked unavailable for new calls but retained in existing usage history.

Initial compatibility target: `/v1/models`, `/v1/chat/completions`, streaming where available, and standard bearer key auth. Providers that need proprietary request protocols or lack compatible endpoints are out of initial scope. Add a provider adapter interface so native adapters can be introduced independently later.

## UI and UX contract

The locked identity and all screen/component specifications are in `.ulpi/design/DESIGN.md` and `.ulpi/design/provider-portals.md`. Top navigation is role-specific, the request ledger is table-first, spend and token units are never conflated, and every async interaction has loading/empty/stale/error/success states. User Activity rows include time, model, input/output tokens, estimated cost label, result, and latency; details show request ID and safe failure category. No prompt/response viewer.

## Success criteria

- Zero cross-user record access in the authorization regression matrix.
- Zero upstream credential values in operator or developer API payloads.
- Authenticated request attempts, upstream-forwarded requests, successes, and rejections have distinct counts.
- Token fields are measured or marked unknown, never silently displayed as zero.
- Usage remains visible after key/model/provider/user disable or archive.
- Global, user-wide, and optional per-key spend/RPM limits reject concurrent over-limit requests at the correct scope.
- Existing OpenAI-compatible client calls continue on `/v1` during portal rollout.
- A protected backup restores to staging before the first invite pilot.
- An invited user can sign in, create a key, make a compatible request, and inspect their own usage without operator assistance.

## Operability and rollout

### Phase 0: protect and baseline

- Back up the production SQLite database and runtime secrets to a protected off-host location; test restore on a copy.
- Record current key IDs, provider profiles, model policies, spend limits, request/usage totals, global stop, and `/v1` smoke behavior.
- Do not delete/migrate historical usage; add schema migration checks.

### Phase 1: identity and ownership

- Add user/invite/session schema and Hack Club OIDC callback.
- Add owner links to keys. Map the current operator key and existing historical events to the owner account without rewriting event facts.
- Enforce role and object-level authorization. Add cross-user denial tests before rendering user routes.

### Phase 2: key policies and reliable usage

- Add aggregate user budgets/RPM, per-key lower limits, reservations, durable rate windows, archive-only semantics, audit events, and price snapshots.
- Preserve existing `/v1` clients; key requests still resolve the issued provider key.
- Validate concurrent reservation and usage ownership behavior with non-production keys.

### Phase 3: portal surfaces

- Build role-specific React/Vite UI using locked Radix/shadcn tokens; serve static assets from FastAPI in the same Nest service.
- Deliver developer keys/catalog/activity/quickstart and operator people/providers/guardrails/usage/audit.
- Pilot with invited accounts, not open registration. Keep a rollback switch to the current owner-only portal until data isolation and login are verified.

### Phase 4: billing reconciliation and scale gates

- Add CSV/manual provider billing snapshots with explicit provenance, then consider read-only billing API integration only if its credentials can be scoped safely.
- Move to PostgreSQL before multiple app workers or measured SQLite lock contention; do not add Redis or microservices without demonstrated need.

### Rollback

Take an SQLite/secret backup before schema migration. Keep backward-compatible `/v1` routes. During beta, portal/auth UI can be rolled back while API key verification and request ledger remain available. Migrations are additive first; destructive schema cleanup is not in MVP.

## Risks and early detection

| Risk | Detection / control |
|---|---|
| Cross-user usage/key disclosure | Automated object-level authorization matrix: user A requests user B's IDs and must receive 404/403; test every list/detail/mutation route |
| User creates extra keys to evade caps | User-wide reservation, spend and RPM counters aggregate all owned keys |
| OIDC session or OAuth callback weakness | Validate issuer/audience/signature/state/nonce, rotate session on login, short revocation path, cookie/CSRF validation |
| Provider credential leakage/SSRF | Write-only credential API; encryption at rest; HTTPS, DNS/IP validation, redirects/private address block, no secret-bearing logs |
| Limit overshoot under parallel requests | DB transaction reservation and concurrent boundary tests at global/user/key scopes |
| Provider bill differs from estimate | Label estimate/source; reconciliation snapshots; alert on drift; keep original events immutable |
| Model catalog changes alter access unexpectedly | Approval + price prerequisite; sync diffs; audit event; selected lists remain fixed |
| SQLite write lock/limit counters inconsistent | Monitor busy/lock errors and write latency; retain a preplanned PostgreSQL migration threshold |
| UI hides unsupported/stale models or status | Catalog freshness, provider health, and capability states displayed; no silent fallback |

## Product defaults confirmed during brainstorming

- Every developer signs in with Hack Club Auth and requires an operator-issued invite.
- Operator assigns each user's daily or weekly allowance and user-wide RPM.
- Developers can set lower per-key spend/RPM caps, never higher than their user policy.
- No separate Hack Club verification-status scope is required at launch.
- Default model access is all operator-approved, priced models; restricted selections remain fixed.

## Spec self-review

- Scope is the selected one-app/two-portal architecture; no microservices, marketplace payments, prompt storage, or native provider protocols have slipped into MVP.
- OpenAI-compatible API path stays stable while portal sessions are independent of API keys.
- User and key policy limits are nested, so additional keys cannot multiply a user allowance.
- Local estimate, provider bill, and account coupon snapshot are distinctly named.
- Historical usage has stable ownership snapshots and no cascading delete behavior.
- The spec points to one locked design system and gives engineering measurable rollout/rollback criteria.
