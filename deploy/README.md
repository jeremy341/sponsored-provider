# Nest rollout runbook

This runbook is deliberately staged. Do not replace or restart the existing Nest service until its current process, port mapping, database and runtime secrets have been backed up and a restore has been tested. This repository update has **not** been deployed.

## Before changing the running container

1. Inspect the existing service command, working directory, bound port, reverse-proxy target, database path, and `runtime-secrets.json`. Preserve any other service/domain mappings in the container.
2. Build and test the portal in a staging checkout. Build the frontend into `frontend/dist` (`cd frontend && npm ci && npm run build`) before starting FastAPI.
3. Back up the live SQLite database and `runtime-secrets.json` to a protected location outside the checkout. Restore both to a staging copy and confirm the old `/v1` key and the portal login still work.
4. Keep the existing Nest domain target on its current port (the current service template uses 8090). Do not change the unrelated service mapped to 8080.
5. SQLite migrations and budget reservations use short write transactions. Keep the provider at one worker for the invite pilot, or move to PostgreSQL before intentionally running multiple workers or opening registration. Do not copy the existing four-worker template blindly without load/lock testing.

## Local auth bootstrap and recovery

For a clean database, build the portal and run `python -m app.cli auth bootstrap` from the application environment. The command prompts for the first operator's username and password and refuses to create a second initial operator. Operators issue invite links from **People & keys**; the default is five uses and seven days. Developers can create one single-use invite from Home. Invite tokens are shown only once, and the status API never returns them.

When hosted behind Nest's HTTPS proxy, set `PORTAL_PUBLIC_ORIGIN` to the exact public origin (for example, `https://provider.jeremy-d.hackclub.app`). Same-origin checks must compare the browser origin to the public HTTPS site, not the app's internal HTTP listener.

For an existing identity-backed operator who needs a local password, run `python -m app.cli auth adopt-operator --user-id USER_ID` from the protected console. For password recovery, run `python -m app.cli auth reset --username USERNAME`, authenticate with the operator account, and set a new password for the active account. Keep `runtime-secrets.json` persistent because it contains the database key pepper and encryption key for upstream credentials.

### Hack Club Auth (dormant historical integration)

HCA OAuth settings and callback instructions describe the earlier integration only. Local username/password auth is active; the running application does not mount `/auth/callback`, and the portal provides no HCA control. Existing HCA environment values are not needed for local sign-in. See the [Hack Club Auth OIDC guide](https://auth.hackclub.com/docs/oidc-guide) for historical reference.

## Credit and exposure scopes

- Operator-assigned developer allowance is a shared daily or weekly USD budget across all of that developer's keys. It resets in `Europe/Berlin`; unused credit does not roll over.
- A key may add a stricter spend cap or model allowlist. It cannot increase the developer's allowance or model access.
- Each upstream connection may have a separate spend cap and safety reserve. A connection's headroom is independent from the user's remaining allowance; both must permit a request.
- The portal serializes monetary values as decimal USD strings and enforces budgets using integer nano-USD reservations. Displayed cost is a local estimate, not an upstream invoice. Missing token or price data must remain “not reported,” not be presented as free.
- Do not set a key to “unlimited” as a way to bypass a user allowance or connection cap. The gateway checks every applicable scope before dispatch and settles from reported usage or the conservative reservation estimate.

## Persistent storage and rollback

The service defaults to `./provider.db` and stores generated `runtime-secrets.json` beside that database. If moving either into a shared directory, stop the service, back up both files, copy them together, update `DATABASE_PATH`, and verify the restored staging copy before changing the live working directory. Starting with a new empty database would make old key/usage records appear to vanish.

Keep `/v1/models` and `/v1/chat/completions` unchanged. A rollback may restore the prior portal UI, but do not delete the additive portal tables or usage ledger. Re-enable the old release only after confirming the database remains readable and no request process still uses the new checkout.

For a staging restore rehearsal, copy the database and its matching `runtime-secrets.json` together into a disposable staging directory, preserve the original pair, start only the staging process against those copies, and verify login plus the existing `/v1` and portal paths. Do not restore a production backup into the live path during a code rollback, and do not generate replacement secrets for an existing encrypted database: the saved encryption key is required to decrypt configured upstream credentials.

## Smoke checks before switching the public domain

- Operator can sign in with the bootstrapped local username/password; a new developer without an invite is rejected.
- Operator can add one upstream, sync models, set a verified price, and approve one text-chat model.
- A developer invited through the portal can create a key, call `/v1/models`, and send a small `/v1/chat/completions` request.
- A second developer cannot read the first user's keys or activity; per-user RPM and allowance apply across the first user's keys.
- Revoking/archiving keys, disabling a user, blocking a model/IP, and removing a model do not erase historical usage.
- Global stop, per-user/key limits, error paths, streaming accounting, backup and restore all behave as intended.

Only switch the existing public domain target after those checks and an explicit cutover decision. This runbook does not authorize a production restart or domain change.
