# Implement Universal Provider Portals

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the existing single-owner gateway into an invite-only, multi-user OpenAI-compatible provider with separate operator and developer portals, user-owned keys, enforceable aggregate limits, and durable usage history.

**Architecture:** Keep one FastAPI process and stable `/v1` contract. Add identity/session, invitations, role-bound APIs, provider catalog and per-user policies around the existing gateway. Serve a React/Vite SPA from the same origin. Retain SQLite for the single-process pilot with additive migrations, transactions, and backup/restore checks.

**Design system:** `.ulpi/design/DESIGN.md` and `.ulpi/design/provider-portals.md` are authoritative. Preserve the approved technical/utilitarian visual direction and separate operator/developer task flows.

## Global Constraints

- Preserve all current local changes, especially `app/static/app.js`, `app/static/style.css`, and `security_best_practices_report.md`.
- Preserve `/v1/models` and `/v1/chat/completions` compatibility; do not deploy to Nest in this plan.
- Never expose provider secrets, prompts/completions, or another developer's identifiers/activity.
- Derive identity and role only from validated server-side sessions. Scope all user APIs by authenticated subject.
- No public signup, payments, wallet, marketplace, prompt storage, or native vendor protocol support.
- Usage history is append-only; disabling/archive changes future access, not prior event facts.
- No unpriced model traffic when a spend policy applies. Unknown usage is not zero.
- Run implementation test-first: a focused failing test precedes every behavior change.
- Parallel agents use GPT-6 Luna at medium effort and disjoint write scopes; main agent owns integration and cross-cutting routing.

## Review Focus

- OIDC callback state/nonce/issuer/audience/signature, cookie flags, CSRF, session rotation and revocation.
- Cross-user IDOR matrix for key, policy, activity, and allowance endpoints.
- Atomic global/user/key spend reservations and aggregate RPM across every user's keys.
- Historical ownership and snapshots after key/model/provider archive.
- Provider URL validation/SSRF, encrypted write-only secrets, and redacted logs/errors.
- UI: design-token compliance, desktop/mobile keyboard/touch workflows, no prompt visibility, no hidden ownership boundary, honest estimate/unknown labels.
- Existing `/v1` response behavior, streaming completion accounting, and current dashboard local workflow.

## Execution Tasks

### Phase 1: Baseline, product truth and contracts

- [x] Record approved product facts in `PRODUCT.md` and architecture/design contracts in this plan.
- [x] Inspect the current route and database behavior and run baseline tests without changing the dirty legacy UI files. Fixed the pre-existing spend-cap regression and reran the suite under Python 3.11.
- [x] Define stable API response contracts for `/api/session`, `/api/developer/*`, and `/api/operator/*` before splitting UI work.
- [x] Write migration and rollout/rollback notes for OIDC bootstrap, user ownership backfill, backups, and existing admin-token compatibility.

### Phase 2: Identity, ownership, and policy foundation

- [x] Add failing tests for OIDC state/nonce, invite expiry/use, role guards, session cookie/CSRF behavior, and user-scoped key/activity access.
- [x] Add additive user/invite/session/ownership/policy/audit schema migrations and secure repository methods.
- [x] Implement Hack Club OIDC discovery/callback with cryptographic ID-token validation, stable `sub` mapping, one-time invite, rotated opaque HttpOnly session, CSRF protection, and sign-out/revocation.
- [x] Implement operator and developer API dependencies; retain an owner-only migration/bootstrap route without browser-stored admin tokens.
- [x] Backfill legacy key snapshots and usage events to the one-time verified-email-bootstrap operator without modifying measured event facts; test existing `/v1` API keys remain valid.

### Phase 3: Enforceable per-user gateway and retained ledger

- [x] Add failing tests for user-wide RPM across multiple keys, period allowance, lower per-key policy, concurrency-safe reservations, pricing missing/unknown, disabled users, and event snapshots.
- [x] Enforce owner-derived key resolution, user-wide and key-specific constraints, approved model catalog, provider hard stop, and configured trusted-proxy client IP.
- [x] Append immutable events for forwarded and authenticated rejected attempts with token availability, latency, outcome, cost estimate/source, IDs and snapshots; never store prompt/response.
- [x] Ensure archival/revocation and model/provider removal preserve events and reporting totals; historical legacy events use stable import IDs and do not double count the cap.
- [x] Add operator audit events with redacted before/after policy and secret-free diagnostic paths.

### Phase 4: Web application and portals (parallel, disjoint directories)

- [x] Create `frontend/` Vite/React/TypeScript shell with Radix primitives, Lucide icons, locked CSS tokens, and responsive routing.
- [x] Implement developer portal routes: Home, API Keys (create, reveal-once, edit/revoke/archive), Models, Activity, and Quickstart.
- [x] Implement operator portal routes: Overview, People & Keys, Models & Providers, Usage, and Guardrails & Audit.
- [x] Implement role-aware navigation and same-origin session API client; the SPA never reads/writes upstream credentials or trusts a client user ID.
- [x] Add accessible loading/empty/error states; searchable model multi-select; paginated activity API; mobile bottom navigation and `More` panel.
- [x] Install/configure vendored anti-slop Oxlint plugin in `frontend/`; existing dirty legacy UI files were preserved.

### Phase 5: Integration, review, and release readiness

- [x] Integrate built SPA into FastAPI same-origin serving without replacing the existing gateway routes.
- [x] Exercise the test-first suite plus full project test/build/lint; record the baseline spend-cap defect and the Starlette/httpx deprecation warning.
- [ ] Browser-review operator and developer flows at desktop, tablet, and phone sizes; desktop flows have been reviewed, mobile breakpoints/touch sizing are coded, but an emulated phone viewport capture is still outstanding.
- [ ] Audit motion conservatively (dashboard motion intensity 2), honor reduced motion, and fix only verified issues. Read-only audit completed; wait for the user's selection before creating motion plans.
- [x] Run frontend design review and Impeccable detector once after visual implementation; one layout-animation warning was fixed. No blocking visual or interaction defect remains in the reviewed desktop screens.
- [x] Write production setup and operator runbook: Hack Club OAuth app registration, secrets, secure DB backup/restore, trusted proxy, migrations, smoke/rollback. Do not deploy until explicit production cutover authorization and credentials are available.

## Agent write scopes

- Backend identity/persistence/gateway agent: `app/identity.py`, `app/portal_api.py`, `app/portal_db.py`, `tests/test_portal_auth.py`, `tests/test_portal_api.py` only; report any required edits to `app/main.py` for integration rather than editing it.
- Frontend foundation agent: new `frontend/` scaffold, package and build config only.
- Developer portal agent: `frontend/src/developer/**` only, after foundation contracts are published.
- Operator portal agent: `frontend/src/operator/**` only, after foundation contracts are published.
- Main agent: existing `app/main.py`, database migration/gateway integration, `frontend/src/app/**`, deployment/rollout docs, integration and review.

Parallelism must not create duplicate auth/session implementations or race on shared route and shell files. Use typed API contracts checked into `frontend/src/contracts/` by the foundation phase before portal agents begin.
