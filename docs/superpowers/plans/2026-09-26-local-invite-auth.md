# Local Invite-Only Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace active Hack Club Auth login/signup with secure local username/password accounts and configurable invite-use quotas, while preserving the dormant HCA implementation and documentation.

**Architecture:** Keep identity, sessions, and invitations in the existing FastAPI/SQLite portal. Store password hashes and invite token hashes only; use existing same-origin session and CSRF patterns. The first operator is provisioned only by a local CLI command. HCA routes and UI are not enabled in the active runtime.

**Tech Stack:** Python 3.11, FastAPI, SQLite, Argon2id password hashing, pytest, React 19, TypeScript, Vite, Radix UI.

**Spec:** `docs/superpowers/specs/2026-09-26-provider-catalog-credits-design.md`; preserve `.ulpi/design/DESIGN.md` and the HCA source/docs for future use.

## Global Constraints

- Active login is username/password; HCA callbacks and login routes are disabled and not linked in the UI.
- Signup requires a valid, unexpired, unrevoked invite with remaining uses.
- Each developer can issue at most one single-use invitation; newly created developers each receive this one-invite entitlement.
- Operators can create an invite with a configurable maximum-use count, expiry, and revoke action.
- Invite consumption and account creation are atomic; concurrent signups cannot exceed `max_uses`.
- Usernames are unique case-insensitively. Passwords are never stored or logged in plaintext.
- Use Argon2id password hashes, auth rate limits, secure HTTP-only session cookies, CSRF protection, generic login errors, and least-privilege roles.
- Provision the first operator through a local-only CLI command, not a public setup endpoint; refuse bootstrap once an operator exists.
- Do not delete production/Nest data, deploy, restart, push, or merge in this plan.

## Review Focus

1. Concurrent consumption at the final invite slot must create no more accounts than permitted; test with competing transactions.
2. Duplicate usernames differing only by case must not create separate accounts; test the DB constraint and signup response.
3. Unknown usernames and wrong passwords must return the same public error and be rate-limited; test without leaking account existence.
4. HCA routes must be unreachable when local auth is active while the dormant HCA verifier remains importable/tested.
5. Session fixation/CSRF and password reset paths must revoke or rotate sessions; test security-sensitive lifecycle transitions.

---

## File Map

| File | Responsibility |
|---|---|
| Modify `app/portal_db.py` | Migration for normalized usernames, password hashes, invite use quotas/revocation, and user invite entitlement. |
| Create `app/password_auth.py` | Password policy, Argon2id hash/verify, and generic credential verification primitives. |
| Modify `app/portal_api.py` | Local login/signup/logout/session APIs, invite lifecycle APIs, operator/developer authorization. |
| Modify `app/main.py` | Start portal routes independently of HCA configuration; keep HCA route mounting disabled. |
| Modify `app/config.py` | Auth throttling/session settings and bootstrap environment; no OAuth secrets required to start local-auth portal. |
| Modify `app/cli.py` | Local-only first-operator bootstrap and operator-assisted password reset. |
| Modify `pyproject.toml` | Add a maintained Argon2 implementation if not already present. |
| Modify `frontend/src/contracts/api.ts`, `frontend/src/lib/api.ts` | Local auth and invite API contracts. |
| Modify `frontend/src/ui/App.tsx` | Login/signup screens, authenticated routing, developer invite view, operator invite quota controls. |
| Modify `frontend/src/ui/styles.css` | Responsive auth forms and invite-use status, using existing locked tokens. |
| Modify `tests/test_portal_auth.py`, `tests/test_portal_api.py` | Authentication, invite quota, rate-limit, CSRF, bootstrap and HCA-disabled regressions. |
| Create frontend auth tests under `frontend/src/ui/` | Login/signup validation and operator/developer invite states. |
| Modify `README.md`, `deploy/README.md` | Local-auth setup, one-time operator bootstrap, password reset, invitation policy and rollout steps; retain HCA docs as future integration reference. |

## Task 1: Migrate account and invite persistence

**Files:** `app/portal_db.py`, `tests/test_portal_auth.py`, `tests/test_portal_db_catalog.py`

**Interfaces:** Add an ordered schema migration with case-insensitive unique normalized usernames, nullable legacy `oidc_subject`, password hash metadata, invite `max_uses`, `uses_count`, revocation fields, and one-invite entitlement tracking for developers. Keep old HCA identity values for future reactivation, but do not require them for local accounts.

- [ ] Add failing tests for case-insensitive uniqueness, multiple operator invite uses, one-use developer invites, expired/revoked/exhausted invites, and migration idempotence/history preservation.
- [ ] Run focused tests and confirm they fail for the missing schema/behavior.
- [ ] Implement the migration and transactional repository methods. Account creation and `uses_count` increment happen in one `BEGIN IMMEDIATE` transaction; rollback both if any validation/insert fails.
- [ ] Test that concurrent signups against an invite with five uses create exactly five accounts and leave the invite exhausted.
- [ ] Run the full Python suite and commit the migration.

## Task 2: Implement local credentials and secure session endpoints

**Files:** `app/password_auth.py`, `app/portal_db.py`, `app/portal_api.py`, `app/main.py`, `app/config.py`, `app/cli.py`, `pyproject.toml`, backend auth tests.

**Interfaces:** `hash_password(password: str) -> str`, `verify_password(password: str, encoded_hash: str) -> bool`; local auth endpoints `POST /auth/login`, `POST /auth/signup`, `POST /auth/logout`, and `GET /api/session`. `POST /auth/signup` receives invite token, username, and password. `POST /auth/login` receives username/password and issues the existing opaque session/CSRF cookie pair. Operator invite API accepts `max_uses` and expiry. Developer invite API issues one single-use invite and atomically marks the entitlement used.

Repository responsibilities in `app/portal_db.py`: persist auth-attempt windows keyed by HMAC of normalized username and client IP, atomically bootstrap only the first operator, look up normalized local usernames, record login time, and reset a user password while revoking that user's sessions.

- [ ] Write failing tests for valid/invalid credentials, generic error behavior, login/signup rate limits, CSRF-protected logout, secure cookie attributes, session rotation, invite-gated signup, developer one-invite limit, configurable operator invite count, and HCA route absence.
- [ ] Verify the tests fail before implementation.
- [ ] Add Argon2id hashing and constant-time verification with a bounded password length and clear policy errors; never log passwords or raw invite tokens.
- [ ] Implement generic login responses, persistent rate limits by normalized username and IP, same-origin checks, and atomic invite-account creation.
- [ ] Add local CLI bootstrap: prompt for username/password without echo, allow only when no operator exists, and provide operator-assisted reset that rotates/revokes sessions. Never expose bootstrap via HTTP.
- [ ] Make app startup initialize/serve the portal without OAuth environment values. Do not mount HCA routes; retain `app/identity.py` and its tests/docs as dormant code.
- [ ] Run auth tests and the full Python suite; commit.

## Task 3: Build local-auth and invite user interfaces

**Files:** `app/portal_db.py`, `app/portal_api.py`, `app/main.py`, frontend contracts/client, `frontend/src/ui/App.tsx`, `frontend/src/ui/styles.css`, frontend tests, README/deploy docs.

**Interfaces:** Add `GET /api/developer/invites` that returns the developer's one-invite entitlement and, if issued, safe invite status (`uses_count`, `max_uses`, `expires_at`, `revoked_at`) without returning the raw token. Add operator `POST /api/operator/invites/{invite_id}/revoke`; return `used/max`, expiry, and revocation status from `GET /api/operator/invites`. A developer's raw token is returned only when first created by `POST /api/developer/invites`.

`GET /auth/login` serves the SPA login/signup shell for invitation links; `POST /auth/login` remains the credential endpoint. Only the identity-less runtime route is mounted, so `/auth/callback` stays absent.

Invitation URLs carry their one-time token in the URL fragment (`#invite=...`) rather than a query string, so browsers do not send it in the HTTP request or Referer. The SPA sends it to signup in the POST body and replaces the fragment after a successful account creation.

- [ ] Add failing repository/API/component tests for login, invite signup, invalid/expired/exhausted invite, operator configurable max uses/expiry/revocation, a developer’s one invite and used state, and session expiry.
- [ ] Implement accessible username/password forms with password-manager-friendly autocomplete and no HCA links. Keep the created invite token visible only once with a copy action.
- [ ] Replace operator invite dialog email-binding controls with a positive max-use count and expiry; show used/max and revocation state; wire revoke action through a protected endpoint. Developer home/account area shows their one invite entitlement, safe status, and the token only once after creation.
- [ ] Document clean bootstrap and operator-assisted recovery; keep historical HCA docs but label integration dormant.
- [ ] Run frontend tests, lint, typecheck, build, and responsive keyboard/mobile checks; commit.

## Task 4: Security and integration verification

**Files:** auth tests and deployment docs.

- [ ] Run full backend and frontend suites.
- [ ] Verify the existing OIDC verifier tests still pass as dormant code, while active app routing never exposes HCA entrypoints.
- [ ] Verify request logs never contain passwords, password hashes, session tokens, CSRF tokens, or raw invite tokens.
- [ ] Verify first-operator CLI refuses when an operator exists and cannot be invoked remotely.
- [ ] Verify clean backup/restore on a disposable local database. No Nest wipe/deploy/restart is performed.

## Self-review

- **Coverage:** local auth, invite quotas, operator bootstrap/recovery, portal UI, dormant HCA preservation, and safe rollout are covered by the four tasks.
- **Ordering:** schema precedes auth service; service precedes UI; integration/security follows both.
- **Constraints:** no external production mutation is part of execution.
