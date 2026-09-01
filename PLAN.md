# Sponsored Alibaba Cloud Provider — Delivery Plan

> Terminology: this plan assumes **Hack Club Nest**, not Heroku. Nest is Hack Club's Linux hosting service. The project will use GitHub as the source repository, Figma as the design/specification workspace, and SSH for deployment/operations.

## 1. Goal

Run a small OpenAI-compatible provider on Hack Club Nest that uses the owner's Alibaba Cloud Model Studio account, keeps the Alibaba credential private, and allows an explicitly approved student client such as CamberCloud Chat to use an allowlisted model.

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
CamberCloud / approved OpenAI client
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

Rejected for v1: Kubernetes, Docker orchestration, Redis, Postgres, a multi-provider abstraction, and a custom dashboard. They increase operational surface without helping the first safety and integration milestones.

## 3A. Dashboard-first product plan

Skip Figma. The first interface is the working `/dashboard` page served by the provider itself. It shows local usage, estimated cost, budget remaining, request activity, model breakdown, and provider-key state. The dashboard is operational rather than decorative: every displayed number comes from the SQLite usage ledger or current configuration.

The dashboard is read-only in v1. Key creation, enable, disable, and revoke remain CLI/admin-token operations until the authentication boundary has been tested in deployment.

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

Normal stop: disable the provider key in SQLite. This blocks CamberCloud immediately while preserving the Alibaba credential for investigation.

Emergency stop: set `EMERGENCY_STOP=true`, stop the systemd service, and disable or delete the dedicated Alibaba API key in Alibaba's console. This is used for leakage, unexpected traffic, or billing anomalies—not merely normal quota exhaustion.

### Reconciliation job

For v1, run a manual billing check at least daily during the pilot. A later version can query Alibaba monitoring/billing data, but must not depend on delayed billing to authorize a request. Local usage controls are the pre-call gate; Alibaba billing is the reconciliation source.

## 4. Trust and data model

### Secrets

- Alibaba API key exists only in a protected `.env`/secret store on Nest.
- Never put it in CamberCloud settings, source control, reports, issue posts, or logs.
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

### Phase 6 — CamberCloud integration

First identify whether CamberCloud supports a custom OpenAI-compatible base URL, model name, API key, and streaming. If it does, configure it with the provider URL and the dedicated provider key. If it does not, do not attempt to scrape or impersonate the chat UI; use a documented API/integration path or treat CamberCloud as a manual client.

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
| CamberCloud lacks custom provider support | no base URL/API-key settings or documented API | validate first; do not automate against undocumented UI |
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
2. Confirm CamberCloud's supported custom-provider/API settings from its student documentation or account UI.
3. Choose a Nest hostname, TLS approach, and private access policy.
4. Implement Phases 0–2 with mocks.
5. Run discovery only and review `results/models.md`.
6. Pause for explicit approval before any paid probe.
7. Select one eligible model, set a conservative budget, and run a one-key private pilot.

## 15. Explicitly out of scope for v1

Frontend dashboard, registration, customer billing, subscriptions, multi-tenant organizations, image/video/speech proxying, embeddings, arbitrary tool calls, prompt persistence, automatic model routing, benchmark suites, public admin endpoints, multi-replica deployment, and public anonymous access.
