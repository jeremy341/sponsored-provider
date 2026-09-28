# Sponsored Alibaba Cloud Provider — Delivery Plan

> Terminology: this plan assumes **Hack Club Nest**, not Heroku. Nest is Hack Club's Linux hosting service. The project will use GitHub as the source repository and SSH for deployment/operations.

## 1. Goal

Run a small OpenAI-compatible provider on Hack Club Nest that uses the owner's Alibaba Cloud Model Studio account, keeps the Alibaba credential private, and allows explicitly approved clients to use an allowlisted model.

The provider is a controlled proxy, not a billing system. The $40 coupon remains attached to the Alibaba account. The service must stop or reject traffic before the account can create unexpected paid charges.

## 2. Important account and policy boundary

Before implementation, inspect the exact coupon details in Alibaba Cloud's Coupons/Benefits page:

- applicable product and model list;
- whether Model Studio API calls are eligible;
- expiration date and remaining balance;
- pay-as-you-go and region requirements;
- whether the benefit is account-bound or shareable under the relevant Alibaba organization rules.

Do not sell, transfer, or represent the coupon as transferable credit. Alibaba's current documentation says student coupons can offset eligible pay-as-you-go AI model bills, but are not deposited into an account/token balance and do not apply to models outside the designated student list. The final checkout/billing page and the campaign's terms control.

## 3. Recommended topology

```text
Approved OpenAI-compatible client
              |
      HTTPS + provider API key
              |
   Hack Club Nest: one FastAPI app
      |       |        |
   auth   quota/db   audit logs
              |
      Alibaba Model Studio API
       private key, fixed base URL
```

### Deployable units

Start with one Python modular monolith and one CLI. Use SQLite for the first single-process deployment. Do not introduce microservices, Redis, a frontend, or a public admin API until real usage proves the need.

### Technology choices

- Python 3.12+
- FastAPI + Uvicorn
- `httpx` for upstream HTTP and streaming
- Pydantic Settings for configuration
- SQLAlchemy 2 + SQLite
- Argon2id or SHA-256/HMAC with a server-side pepper for provider-key storage
- Pytest + respx/httpx mocks; no real upstream calls in tests
- Caddy or Nginx for TLS if Nest networking requires a reverse proxy
- systemd user service or the hosting platform's documented process supervisor

Rejected for v1: Kubernetes, Docker orchestration, Redis, Postgres, a multi-provider abstraction, and a separate dashboard service. They increase operational surface without helping the first safety and integration milestones.

> **Historical note (2026-09-28):** the `/dashboard` Control Room and admin-token API described in this section were removed; the React portal at `/` is the interface. The rest of this section is preserved as history.

## 3A. Dashboard-first product plan

The first interface is the working `/dashboard` page served by the provider itself. It shows local usage, estimated cost, budget remaining, request activity, model breakdown, and provider-key state. The dashboard is operational rather than decorative: every displayed number comes from the SQLite usage ledger or current configuration.

The dashboard is read-only for usage data in the current slice. Key creation, enable, disable, and revoke are available through CLI/admin-token operations; the next dashboard slice can expose those same operations behind a protected admin session.

## 3B. GitHub repository plan

Create one private GitHub repository, for example `sponsored-provider`. The repository contains source, tests, deployment scripts, documentation, and non-secret configuration examples.

Never commit:

- Alibaba API keys;
- provider API keys;
- `.env` files;
- SQLite production database;
- exported billing data containing account identifiers;
- SSH private keys.

Recommended branches and protections:

- `main` — deployable and protected;
- short-lived feature branches;
- pull request required for changes to auth, quota, deployment, and upstream code;
- GitHub secret scanning and Dependabot enabled;
- tagged releases such as `v0.1.0` for Nest deployments.

Add `README.md`, `PLAN.md`, `SECURITY.md`, `.env.example`, `.gitignore`, `LICENSE`, and a GitHub Actions workflow that runs formatting, type checks, tests, and a secret scan. CI must use mocked Alibaba responses only.

## 3C. Nest deployment model

Use SSH for one-time setup and controlled operations. Use systemd to keep the application running permanently; an SSH terminal or `tmux` session must not be the process supervisor.

### Nest host layout

```text
~/apps/sponsored-provider/current/   checked-out release
~/apps/sponsored-provider/shared/    .env and provider.db
~/apps/sponsored-provider/releases/  optional versioned releases
~/apps/sponsored-provider/logs/      service logs if needed
```

Use a dedicated Unix user where Nest permits it, least-privilege file permissions, and a separate virtual environment. Bind the application to localhost and put TLS/reverse proxy access in front of it only after private testing succeeds.

### Deployment sequence

1. Create/verify the Nest account and read its acceptable-use, limitations, privacy, and data-retention rules.
2. Create an SSH key pair locally; install only the public key on Nest.
3. Connect over SSH and install the required Python runtime.
4. Clone the GitHub repository using a deploy key or GitHub CLI; do not store a personal access token in shell history.
5. Create the virtual environment and install pinned dependencies.
6. Create `shared/.env` with restrictive permissions.
7. Run local-only tests on Nest.
8. Run `scan --no-probe` only after the Alibaba credential is installed.
9. Create and enable the systemd service only after the provider passes local tests.
10. Add HTTPS and external access only for the approved client.
11. Record the deployed commit, configuration version, and rollback command.

### Permanent service operations

The runbook must include:

```bash
systemctl --user status sponsored-provider
systemctl --user restart sponsored-provider
systemctl --user stop sponsored-provider
journalctl --user -u sponsored-provider -f
```

If Nest does not support user-level systemd persistence for the account, use the platform-supported persistent process method documented by Nest. Do not use `nohup`, an unattended `screen`, or an interactive SSH session as the permanent deployment mechanism.

## 3D. Exact $35 stop design

Yes, the intended policy is: once the controlled usage estimate reaches **$35**, disable the provider key immediately and reject all new upstream requests.

However, this is not sufficient by itself to guarantee the Alibaba account never exceeds $35. Alibaba bills model inference by usage, and billing visibility is delayed. Its documentation says bills may appear minutes later and some bill data can lag further. Therefore implement a conservative two-layer control:

### Layer 1 — local hard stop

Before each Alibaba request:

1. estimate cost from the requested model, input estimate, and `max_tokens`;
2. add a safety reserve for unknown usage and rounding;
3. compare against the local cumulative budget;
4. reject before upstream if the request would cross the configured threshold;
5. atomically set `provider_key.enabled=false` when the threshold is reached;
6. write an audit event and expose only `quota_exhausted` to the client.

Recommended configuration:

```env
PROVIDER_HARD_STOP_USD=35
PROVIDER_WARNING_USD=25
PROVIDER_ESTIMATE_RESERVE_USD=5
EMERGENCY_STOP=true
```

Because of billing delay, the implementation should actually stop estimated new usage before the raw $35 boundary—for example at `$30` until real billing reconciliation proves the estimate is reliable. The exact operating threshold is an explicit owner decision; `$35` is the absolute ceiling policy, not permission to spend right up to the delayed boundary.

### Layer 2 — Alibaba-side protection

- use a dedicated Alibaba Model Studio API key for this provider;
- use a dedicated workspace if available;
- disable web search, plugins, tools, image/video/speech, and deployments unless explicitly needed;
- configure Alibaba billing alerts at lower thresholds;
- inspect billing by Model Studio, model, workspace, and API key;
- if unexpected activity appears, immediately stop the Nest service and delete/disable the dedicated Alibaba API key as an emergency action.

Deleting an Alibaba API key is irreversible, so it must be documented as emergency-only. The local provider key's disable action is reversible; the Alibaba credential should be rotated after any incident.

### What “stop the key” means

Normal stop: disable the provider key in SQLite. This blocks the client immediately while preserving the Alibaba credential for investigation.

Emergency stop: set `EMERGENCY_STOP=true`, stop the systemd service, and disable or delete the dedicated Alibaba API key in Alibaba's console. This is used for leakage, unexpected traffic, or billing anomalies—not merely normal quota exhaustion.

### Reconciliation job

For v1, run a manual billing check at least daily during the pilot. A later version can query Alibaba monitoring/billing data, but must not depend on delayed billing to authorize a request. Local usage controls are the pre-call gate; Alibaba billing is the reconciliation source.

## 4. Trust and data model

### Secrets

- Alibaba API key exists only in a protected `.env`/secret store on Nest.
- Never put it in client settings, source control, reports, issue posts, or logs.
- Create a separate provider key for each approved client/person.
- Show each provider key only once; store only its hash and a short prefix.
- Rotate the Alibaba key if it is ever exposed.

### Provider key table

`provider_api_keys`: `id`, `key_prefix`, `key_hash`, `label`, `enabled`, `revoked_at`, `created_at`, `last_used_at`, `request_count`, `input_tokens`, `output_tokens`.

Disable is reversible. Revoke is permanent. There is no anonymous access.

### Usage table

`usage_records`: `id`, `provider_key_id`, `timestamp`, `model`, reported token fields, `latency_ms`, `status`, `stream`, and normalized `error_category`.

Do not store prompts or message content by default. Store only aggregate usage and operational metadata.

## 5. Public API contract

Implement only:

- `GET /health` — local liveness; never calls Alibaba.
- `GET /v1/models` — returns only configured, working, allowlisted models.
- `POST /v1/chat/completions` — OpenAI-compatible non-streaming and streaming proxy.

Authentication is `Authorization: Bearer sp_sk_...`.

Enforce, before any Alibaba call:

1. request body byte limit;
2. provider-key hash lookup and enabled/revoked check;
3. per-key quota and rate limit;
4. model allowlist;
5. message count/content and output-token limits;
6. `stream` and request-shape validation.

The Alibaba base URL is configured server-side and cannot be overridden by a request.

## 6. Hard spending controls

Because token pricing and coupon eligibility can vary by model, the application must fail closed when cost cannot be estimated safely.

Configuration should include:

```env
ALLOWED_MODELS=
MAX_REQUEST_BYTES=1048576
MAX_INPUT_TOKENS_ESTIMATE=12000
MAX_OUTPUT_TOKENS=1024
RATE_LIMIT_REQUESTS_PER_MINUTE=10
DAILY_REQUEST_LIMIT_PER_KEY=100
MONTHLY_TOKEN_LIMIT_TOTAL=
SPEND_STOP_USD=32
EMERGENCY_STOP=true
```

The initial stop threshold should be below $40 to reserve room for billing delay, rounding, non-model charges, and uncertainty. Usage estimates are a guardrail, not a replacement for Alibaba billing. Check Alibaba billing frequently during the pilot.

For v1, default to one approved key and one low-cost chat model. Do not automatically enable every discovered model.

## 7. Model discovery and paid-request gates

### Gate A — local-only

Run mocked tests and CLI help. No credentials and no network calls are required.

### Gate B — discovery only

After credentials are installed, run `python -m app scan --no-probe`. Save model IDs, heuristic categories, and `NOT_PROBED` status to `results/models.json` and `results/models.md`.

### Gate C — explicit probe approval

Only after reviewing the discovery report, run a cheap probe for selected general chat/coding/reasoning candidates. One request per model, sequentially, with `Reply with exactly: OK` and a small output limit. Never automatically probe image, video, speech, or generation models.

### Gate D — allowlist

Select a model based on actual availability, latency, reliability, context limits, model quality, price, rate limits, and coupon eligibility. Put only that model in `ALLOWED_MODELS`.

### Gate E — private pilot

Use one provider key, one trusted client, very low quotas, and monitor Alibaba bills. Only expand after a complete billing cycle or an equivalent verified spend check.

## 8. Repository layout

```text
app/
  main.py cli.py config.py errors.py logging.py
  alibaba/client.py scanner.py classifier.py models.py errors.py
  api/health.py models.py chat.py middleware.py
  auth/api_keys.py dependencies.py
  database/database.py models.py repositories.py
  usage/tracker.py limiter.py
results/
tests/
.env.example
.gitignore
README.md
PLAN.md
```

## 9. Delivery phases

### Phase 0 — Dashboard and foundation

Create the GitHub repository, working dashboard, configuration, redacted logging, package layout, `.env.example`, and local README. Add startup checks that refuse unsafe production configuration but never probe Alibaba during server startup.

### Phase 1 — Alibaba adapter

Implement model listing, chat completion, streaming, timeout handling, URL normalization, structured error parsing, and narrowly scoped retries only for temporary failures. Normalize errors to `AUTH_ERROR`, `MODEL_NOT_FOUND`, `MODEL_NOT_AUTHORIZED`, `RATE_LIMITED`, `REGION_UNAVAILABLE`, `SERVER_ERROR`, `TIMEOUT`, `NETWORK_ERROR`, and related categories.

### Phase 2 — Scanner

Implement `scan --no-probe`, explicit `scan --probe`, and `scan --model`. Generate JSON and Markdown reports with working, failed, and untested models; reported usage must remain `null` when Alibaba omits it.

### Phase 3 — Provider core

Implement SQLite migrations/repositories, provider-key CLI commands, `/health`, `/v1/models`, non-streaming proxying, request validation, quota checks, and usage records.

### Phase 4 — Streaming and hardening

Forward SSE chunks incrementally, record final/interrupted/failed status, close upstream connections on client disconnect, redact logs, add rate limiting, and enforce body/message/output limits.

### Phase 5 — Nest deployment

Deploy from a tagged GitHub commit over SSH on Hack Club Nest, restrict inbound access where possible, terminate TLS, run as a non-root/dedicated user, protect the database and `.env`, configure systemd restart behavior, and test reboot/recovery. Do not expose an admin route.

### Phase 6 — Client integration

Configure any approved OpenAI-compatible client with the provider URL, a dedicated provider key, and the selected allowlisted model. Do not couple the provider to a named client or scrape an undocumented UI.

## 10. Verification checklist

### Safety invariants

- server startup never calls Alibaba;
- `scan --no-probe` never calls chat completions;
- tests never reach the network;
- non-chat models are never automatically probed;
- provider requests cannot override the upstream URL;
- Alibaba credentials never appear in logs or responses;
- disabled/revoked keys cannot make upstream requests;
- an exhausted quota fails before an upstream call;
- no prompt content is persisted by default.

### Provider tests

Cover health, models, auth failures, allowlist rejection, malformed/oversized input, upstream error translation, non-streaming responses, SSE streaming, usage tracking, rate limiting, client disconnects, key lifecycle, and emergency stop behavior.

### Operational acceptance

- one trusted client can complete a short chat through the provider;
- Alibaba billing shows the expected model usage;
- the provider can be stopped immediately by setting `EMERGENCY_STOP=true` or disabling the key;
- the service restarts without corrupting SQLite;
- the owner can identify each key's last use and aggregate usage without seeing prompts.

## 11. Ownership and operating process

The owner controls the Alibaba account, coupon, secret, model allowlist, and emergency stop. The Nest deployment owner controls the host and process. These must be the same trusted operator initially, with no shared root access.

Keep a small change log for model allowlist, quotas, provider keys, and deployment versions. Every change affecting spend requires an explicit review. Later, add `CODEOWNERS` for configuration, auth, and deployment files if more contributors join.

## 12. Risks and early signals

| Risk | Early signal | Mitigation |
|---|---|---|
| Coupon does not cover selected model | billing line is not discounted or model unavailable in student center | verify eligibility before allowlisting; fail closed |
| Billing is delayed | usage appears without immediate deduction | keep threshold below coupon value and check bills on a schedule |
| Model list overstates access | discovery succeeds but probe fails | separate discovered/not-probed/working/failed states |
| Client sends expensive requests | high output limits, long prompts, unexpected model IDs | allowlist, caps, rate limits, per-key quotas |
| Alibaba key leaks | key appears in logs, client config, or repo | redaction, secret rotation, provider-only credential |
| Nest service is publicly abused | unfamiliar key use or traffic spike | unique keys, low quotas, TLS, access restriction, emergency stop |
| Client lacks custom provider support | no base URL/API-key settings or documented API | validate first; do not automate against undocumented UI |
| Single SQLite process becomes a bottleneck | lock errors or multiple replicas | remain single-instance; migrate to Postgres/Redis only with evidence |

## 13. Success metrics for the pilot

- 100% of tests pass without external network access;
- 0 secrets in Git or logs;
- 0 upstream calls from startup, health, or no-probe mode;
- 100% of upstream requests are attributable to a provider key;
- 0 allowlist bypasses;
- p95 proxy latency tracked separately from Alibaba latency;
- emergency stop blocks new upstream calls within one request;
- no unexpected Alibaba bill beyond the pre-approved pilot budget.

## 14. Immediate next actions

1. Confirm the Alibaba coupon's exact eligible Model Studio products/models and expiration.
2. Confirm the approved client's supported custom-provider/API settings from its documentation or account UI.
3. Choose a Nest hostname, TLS approach, and private access policy.
4. Implement Phases 0–2 with mocks.
5. Run discovery only and review `results/models.md`.
6. Pause for explicit approval before any paid probe.
7. Select one eligible model, set a conservative budget, and run a one-key private pilot.

## 14A. Dashboard access and next UI slice

### Private local-browser access through Nest

Keep Uvicorn bound to `127.0.0.1:8000` on Nest. From the owner's computer, create an SSH tunnel:

```bash
ssh -N -L 8000:127.0.0.1:8000 nest-user@your-nest-host
```

Then open `http://127.0.0.1:8000/` in a local browser. The browser is local, but traffic is carried through the encrypted SSH connection to the Nest service. (The legacy `/dashboard` Control Room was removed; operate through the portal.)

### Optional public access

Only after the private tunnel works, add a Nest hostname, HTTPS reverse proxy, and an additional access boundary. The legacy admin-token API was removed with the Control Room; operator actions go through the portal's session-authenticated API. Never expose credentials in a URL, source code, or client API key.

### Dashboard information architecture

The dashboard should have four focused areas:

1. `Overview` — current requests/minute, requests today, input/output/total tokens, estimated spend, remaining hard-stop budget, warning threshold, and live service status.
2. `Activity` — recent request ledger with time, model, duration, status, stream flag, tokens, and estimated cost; no prompt content.
3. `Keys` — create a key with a label, show the raw key exactly once, list masked prefixes, set per-key request/token budgets, disable/enable, and permanently revoke.
4. `Models & safeguards` — show allowlisted models, set the selected model's official input/output prices, configure warning/hard-stop values, toggle emergency stop, and show the last billing reconciliation time.

The page should refresh operational metrics every 10 seconds and show a clear `local estimate` label until Alibaba billing reconciliation is connected. Mutating controls require a separate confirmation and an audit entry. The first interactive dashboard slice should implement key creation, disable/enable, and emergency stop; model pricing and allowlist editing should remain owner-only configuration until tested.

## 15. Explicitly out of scope for v1

Frontend dashboard, registration, customer billing, subscriptions, multi-tenant organizations, image/video/speech proxying, embeddings, arbitrary tool calls, prompt persistence, automatic model routing, benchmark suites, public admin endpoints, multi-replica deployment, and public anonymous access.

## 16. Multi-provider router plan

### Custom base URL

The service already has the shape of a custom OpenAI-compatible base URL. Clients should call the provider, not Alibaba directly:

```text
Local:  http://127.0.0.1:8000/v1
Nest:   https://your-provider-host/v1
```

The client supplies a provider-issued `sp_sk_...` key and an allowlisted model. The provider chooses the upstream route. Alibaba's base URL and credential remain private server configuration.

### Key terminology

- **Client/provider key:** issued by this service to a person or application; supports spend, token, request-rate, model, approval, and IP policies.
- **Upstream credential:** owned by the operator for Alibaba or another provider; never returned to clients and never accepted from an ordinary request.
- **Admin credential:** controls the dashboard and router configuration; never usable as a model-invocation key.

### Upstream profile model

Replace the single Alibaba configuration with an admin-managed `upstream_profiles` registry:

```text
upstream_profiles
  id
  display_name
  provider_kind              # alibaba, openai_compatible, local
  base_url
  secret_reference           # reference to an environment/secret-store name
  enabled
  health_status
  allowed_models
  model_aliases              # optional client model -> upstream model mapping
  input_price_per_million
  output_price_per_million
  priority
  created_at
  last_checked_at
```

The first migration keeps Alibaba as the default profile. Adding another profile should not require changing client configuration; clients continue using the same `/v1` URL and provider key.

### Routing modes

Start with explicit routing, then add carefully bounded fallback:

1. **Pinned model route:** each client key may be limited to specific model aliases, and each alias maps to one upstream profile/model.
2. **Operator-selected profile:** the dashboard can enable/disable a profile and set its priority.
3. **Fallback:** only retry a request on a configured fallback when the failure is clearly transient; never fallback after auth, model-not-found, policy, or quota errors.
4. **No automatic cheapest/best routing initially:** it makes cost and behavior harder to explain and audit.

### Dashboard additions

Add an `Upstreams` tab with:

- profile name and provider kind;
- masked credential status;
- fixed base URL with hostname display;
- enabled/disabled state;
- model catalog and alias mapping;
- official input/output prices;
- health-check result and last checked time;
- priority/fallback order;
- per-profile and total usage.

Add routing fields to the existing key policy editor:

- allowed model aliases;
- allowed upstream profile IDs;
- maximum spend/tokens/requests per profile;
- approval/risk state.

### Security rules for arbitrary providers

“Plug in any key” must mean an operator adds a provider profile, not that a client can submit `base_url` or an upstream key in a request. Enforce:

- profile creation is admin-only;
- base URLs are HTTPS outside local development;
- reject localhost, link-local, private-network, metadata-service, and non-routable targets for remotely reachable deployments;
- use an explicit hostname/domain allowlist;
- do not follow arbitrary redirects;
- never log query strings or authorization headers;
- store only secret references in the database, with actual values in environment/secret storage;
- validate the profile with a controlled `/models` check before enabling it;
- keep per-profile budgets and a global hard stop;
- record profile ID, upstream model, provider key ID, client IP, latency, status, and reported usage for every request.

### Migration sequence

1. Extract the current Alibaba client behind an `UpstreamAdapter` interface without changing the public API.
2. Add the upstream profile table and migrate the current Alibaba environment values into a default profile.
3. Add profile-aware model discovery and pricing.
4. Add admin-only profile create/edit/enable/disable/health controls.
5. Add explicit model-to-profile routing.
6. Add per-profile dashboard usage and reconciliation.
7. Add transient-only fallback with tests proving policy/auth failures never fallback.
8. Only then consider multiple active providers in production.

### Recommended operating posture

Keep Alibaba as the first profile and use the custom provider URL for all clients. Add other providers only when their official API compatibility, pricing, terms, and secret-management path are verified. This preserves one stable client interface while keeping upstream choice under operator control.

## 16A. Mainstream provider compatibility matrix

The final router should support mainstream providers through official API credentials and documented protocols:

| Provider | Credential accepted | Protocols to support | Billing source |
|---|---|---|---|
| Alibaba Model Studio | Model Studio API key | OpenAI-compatible Chat/Responses or native adapter | Alibaba usage/billing |
| OpenAI API | OpenAI API key or project/service credential | Chat Completions and Responses | OpenAI Usage/Costs API |
| OpenCode Go | OpenCode Go API key | Chat Completions, Responses, and Anthropic Messages depending on model | OpenCode Go account limits plus provider telemetry |
| OpenRouter | OpenRouter API key | OpenAI-compatible Chat/Responses | OpenRouter credits/activity |
| Other compatible provider | Official API credential | Declared compatible protocol | Provider-specific usage API |
| ChatGPT Free/Plus/Pro subscription | Not an API credential | Not supported as a proxy upstream | Separate ChatGPT subscription billing |

ChatGPT subscription access and OpenAI API billing are separate products. The router must not ask for a ChatGPT login, session cookie, browser token, or subscription credential. A separate OpenAI API project/key is required for OpenAI API routing. OpenAI also recommends unique API keys and says API keys should not be shared; recipients should receive our scoped provider keys, never the upstream key.

### Protocol adapter requirement

Each model catalog entry must declare its protocol and upstream model ID:

```text
client_model: approved-model
upstream_profile: opencode-go
upstream_model: kimi-k3
protocol: chat_completions
```

The public provider can continue exposing one stable endpoint, but internally it needs adapters for:

- `/v1/chat/completions`;
- `/v1/responses`;
- Anthropic-compatible `/v1/messages` where the upstream model requires it;
- streaming translation for each protocol;
- usage extraction and cost calculation for each response shape.

If a client requests a model whose protocol adapter is unavailable, return `unsupported_protocol` before making an upstream call. Never guess a protocol from the model name.

### Provider onboarding checklist

For every new upstream added through the UI:

1. verify the credential type is an official API credential;
2. verify the base URL and region/account match the credential;
3. call the provider model catalog endpoint;
4. store protocol, model ID, context/output limits, and price metadata;
5. run one operator-approved low-cost health probe;
6. test non-streaming and streaming if supported;
7. configure provider-level and global budgets;
8. record terms/privacy acknowledgment and last reconciliation time;
9. only then make the profile selectable in sponsored-key creation.

This preserves the user-facing experience you want—choose a provider, discover its models, set a key budget, and issue a stable provider key—without treating consumer subscriptions or browser sessions as reusable API backends.

## 17. Sponsored access mode

### Goal

Allow the operator to add one upstream credential, create a separate limited client key for a recipient, and give that recipient a stable provider endpoint:

```text
Provider URL: https://your-provider-host/v1
Client key:   sp_sk_recipient...
Model:        operator-approved model
```

The recipient never receives the upstream OpenCode Go, Alibaba, or other provider credential. The provider key is the only credential they use.

### OpenCode Go compatibility

OpenCode Go currently exposes OpenAI-compatible endpoints for its listed models, and OpenCode supports custom OpenAI-compatible providers configured with a base URL and model IDs. That makes it technically suitable for an upstream profile. Compatibility does not establish permission to share or resell a subscription credential; before enabling it, verify the current OpenCode Go terms, account limits, and whether proxying usage to another person is allowed.

### Recipient policy

Each sponsored client key should have an explicit policy:

```text
enabled / disabled / revoked
risk_profile: strict | standard | trusted
risk_approved: true | false
allowed_upstreams: [profile ids]
allowed_models: [model ids or aliases]
spend_limit_usd
token_limit
requests_per_minute
requests_per_day
expires_at
allowed_ips / blocked_ips (optional)
```

Use conservative defaults: pending approval, one model, one upstream, low RPM, low token cap, short expiry, and no tool/search/image/video capability unless explicitly enabled.

### Request decision order

```text
client request
  -> source IP block check
  -> provider-key lookup
  -> enabled/revoked/approval check
  -> key expiry check
  -> key model/upstream policy check
  -> key RPM/day/token/spend check
  -> global budget and emergency-stop check
  -> upstream profile health check
  -> upstream request
  -> usage/cost/audit record
```

Every rejection should be cheap and happen before an upstream call. Every accepted request should record provider key ID, upstream profile ID, model ID, client IP as observed at the trusted edge, timestamps, latency, status, and reported usage. Never record prompts by default.

### Stable endpoint and client setup

The recipient configures one custom provider, for example in OpenCode:

```json
{
  "provider": {
    "sponsored": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Sponsored Provider",
      "options": { "baseURL": "https://your-provider-host/v1" },
      "models": { "approved-model": { "name": "Approved Model" } }
    }
  }
}
```

The recipient stores only the issued provider key in their client. The server maps `approved-model` to the configured upstream model. If the key is disabled, expired, over limit, or the IP is blocked, the endpoint returns a stable policy error without touching the upstream.

### Dashboard screens for sponsored access

Add these views to the dashboard:

1. `Overview` — global spend, request rate, token rate, hard stop, warning state, and upstream health.
2. `Sponsored keys` — recipient label, masked key, approval/risk badge, expiry, limits, current usage, last use, and actions.
3. `Key policy editor` — upstream/model selection, spend, token, RPM/day, expiry, IP restrictions, approval, and revoke.
4. `Usage explorer` — time range, key, upstream, model, IP, status, and stream filters; daily/hourly charts; exportable metadata only.
5. `Abuse & blocks` — blocked IPs, reason, timestamps, request/error counts, and unblock action.
6. `Upstreams` — credential status without revealing secrets, model catalog, prices, health, and routing priority.

### Budget behavior

Use two ceilings:

- **Per-key ceiling:** stops that recipient's key.
- **Global ceiling:** stops all sponsored keys before the upstream coupon/account budget is at risk.

Use a warning threshold and reserve. Do not authorize a request when its worst-case estimated input plus `max_tokens` plus reserve would cross either ceiling. Reconcile against delayed upstream billing separately; local estimates are the pre-call control, not proof of the final bill.

### Fallback policy

Do not silently move a recipient from OpenCode Go to Alibaba or another provider. If fallback is later enabled, it must be an explicit per-key policy with separate model compatibility, price, privacy, and budget checks. Never fallback on authentication, model policy, quota, or abuse blocks; only clearly transient upstream failures may qualify.

### Rollout stages

1. Add one upstream profile and one recipient key.
2. Test model discovery and a mocked request through the stable `/v1` endpoint.
3. Enable strict policy with a small spend/token/RPM cap and short expiry.
4. Observe usage, IPs, errors, and upstream billing.
5. Add a second profile only after attribution and emergency stop are reliable.
6. Add optional fallback only after explicit operator review and per-key opt-in.

## 18. Full OpenRouter-style operator system

The target is an OpenRouter-like control plane for this private sponsored service: one stable API endpoint, multiple operator-owned upstream connections, and many independently controlled client/agent keys. This is a capability map, not a promise to reproduce another service's private implementation or terms.

### Core objects

#### Upstream connection

An upstream connection represents a provider credential you own:

```text
id
name                         # e.g. Alibaba Student, OpenCode Go, OpenRouter
provider_kind
base_url
secret_ref / encrypted_secret
auth_scheme
enabled
models
model_aliases
input/output pricing
priority
fallback_enabled
health state
last model sync
```

The dashboard needs an `Add upstream` form with:

- display name;
- provider type;
- base URL;
- API key/credential input;
- authentication header mode;
- model discovery button;
- model selection and aliases;
- price fields;
- enabled/disabled toggle;
- health-check button;
- privacy/terms acknowledgment;
- save-and-test action.

The secret is submitted only over HTTPS or the private SSH tunnel, encrypted at rest with a `PROVIDER_SECRET_KEY`, never returned after save, and never shown in logs. A safer Nest deployment may store only a secret reference and keep the actual value in the environment/secret store. UI entry must not turn the request `base_url` into an arbitrary SSRF target: enforce HTTPS, hostname allowlists, and private-network rejection for remotely exposed deployments.

#### Sponsored client/agent key

A client key represents one agent, person, or application consuming the stable provider endpoint:

```text
id
label
description
key_prefix / key_hash
created_at / last_used_at / expires_at
enabled / revoked_at
risk_profile / risk_approved
allowed_upstreams
allowed_models
model_aliases
spend_limit_usd
spend_used_usd
token_limit / token_used
requests_per_minute
requests_per_day
tokens_per_minute
max_concurrency
max_input_tokens / max_output_tokens
allowed_ips / blocked_ips
budget_period: lifetime | daily | weekly | monthly
budget_reset_at
```

### Key creation wizard

The `Create key` flow should ask for:

1. agent/application name;
2. owner label and optional description;
3. upstream connection(s);
4. model(s) or aliases;
5. budget amount and reset period;
6. RPM, TPM, concurrency, and request-size limits;
7. expiry date;
8. risk profile and approval;
9. optional allowed IPs;
10. confirmation screen showing the effective policy.

After creation, show the complete client key exactly once with copy/download buttons and an explicit warning. Later views show only the prefix/hash and usage; the raw key cannot be retrieved. This mirrors the important operational behavior of provider key-management systems, where limits, expiry, and usage are attached to each key.

### Per-key “wallet” model

Use clear terminology in the UI:

- `Allocation` — maximum internal budget assigned to this key;
- `Used` — locally recorded estimated cost;
- `Available` — allocation minus used;
- `Reset` — daily/weekly/monthly/lifetime policy;
- `Upstream balance` — external provider state, read-only and reconciled separately.

Do not claim that an Alibaba or OpenCode Go coupon has been transferred into a key wallet. The key wallet is an internal gate that prevents this provider from sending more requests for that key.

### Dashboard information architecture

#### 1. Overview

- total spend and global allocation;
- requests/minute and active concurrency;
- tokens in/out and tokens/minute;
- budget runway;
- upstream health cards;
- top models, keys, agents, and IPs;
- recent policy blocks and errors;
- emergency stop.

#### 2. Upstreams

- add/edit/remove connection;
- enter credential and base URL;
- sync `/models`;
- show model availability and pricing;
- test one cheap request only after confirmation;
- view health, latency, errors, and spend by upstream;
- configure priority and explicit fallback.

#### 3. Keys / agents

- create key wizard;
- search/filter by owner, status, upstream, model, risk, and expiry;
- click a key to open a detail drawer/page;
- current allocation, used, available, reset time;
- request/token/concurrency limits;
- model/upstream permissions;
- last-used IPs and recent activity;
- disable, enable, rotate, and revoke;
- export a safe client configuration snippet without exposing upstream secrets.

#### 4. Usage explorer

- time range: last hour/day/week/month/custom;
- filters: key, agent, upstream, model, IP, status, stream;
- requests and tokens over time;
- spend over time;
- latency p50/p95 and time-to-first-token when available;
- success/4xx/5xx/429 rates;
- CSV/JSON export of metadata only;
- no prompt storage by default.

#### 5. Guardrails and abuse

- global budget and warning/hard-stop;
- per-key policies;
- IP blocklist and unblock;
- suspicious rate/error/spend signals;
- manual review queue;
- audit log of every policy change;
- provider-wide emergency stop.

#### 6. Settings and audit

- admin sessions and rotation;
- secret-store status;
- trusted proxy configuration;
- retention period;
- data export/delete;
- configuration history and rollback;
- deployment version and service health.

### Routing behavior

The incoming request contains only a client key and model alias. The router resolves:

```text
client key
  -> key policy
  -> requested model alias
  -> permitted upstream profile
  -> model mapping
  -> budget/rate/concurrency checks
  -> upstream adapter
  -> usage and audit record
```

If one key is assigned to multiple providers, the operator must choose either:

- pinned provider;
- ordered fallback;
- explicit per-model provider mapping.

The router must not silently switch a key to a more expensive or less private provider. Fallback is only allowed for explicitly configured transient failures.

### Live versus persistent configuration

Dashboard changes must eventually persist in SQLite/Postgres rather than only mutating the process environment. Every mutation needs:

- authenticated admin identity;
- before/after values with secrets redacted;
- timestamp and reason;
- audit record;
- validation before activation;
- rollback path.

The migration order is:

1. add encrypted upstream profile storage;
2. add profile-aware model discovery;
3. add key-to-profile assignments;
4. persist key policies and budget periods;
5. add usage explorer filters and time-series rollups;
6. add concurrency/TPM enforcement;
7. add provider health and explicit fallback;
8. migrate Nest from environment-only settings to persistent admin configuration.

### Reference alignment

This design takes the useful public concepts from OpenRouter: separate management credentials, one-time key display, key spending limits, expiry/reset periods, usage history, model/provider restrictions, and BYOK-style upstream connections. OpenRouter documents these as separate management, credits, guardrail, and BYOK concepts; our implementation should preserve that separation while keeping this project smaller and operator-owned.
