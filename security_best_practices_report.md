# Security best-practices audit

## Executive summary

The proxy does not currently return Alibaba credentials or upstream encrypted secrets through its API responses. Upstream credentials are encrypted at rest and only decrypted inside the server-side forwarding path. The main remaining risk is dashboard administration: the dashboard is internet-reachable and uses a bearer admin token, while the known admin password/token has been shared in chat and has no failed-attempt throttling.

## Findings

### S1 — High: rotate the exposed admin credential

The dashboard accepts the admin token directly in `X-Admin-Token` (`app/main.py:74-76`). The current credential has been shared in the conversation, so anyone with access to that conversation could operate the dashboard, create keys, change limits, block models, or stop the provider.

Action: rotate the admin token immediately, keep it out of chat, and use a long random value stored only in Nest’s private environment/runtime secret file.

### S2 — Medium: no admin authentication throttling

All admin operations rely on a direct token comparison (`app/main.py:74-76`), but there is no failed-attempt rate limit or lockout. An attacker who can reach the public dashboard can repeatedly guess the token.

Action: add a dedicated admin-auth limiter and optionally restrict dashboard/admin routes to a private access path or allowlisted IPs.

### S3 — Medium: encryption key and encrypted database share the same host secret boundary

Provider credentials are encrypted before storage (`app/database.py:199-206`) and are decrypted server-side (`app/database.py:213-223`). This protects against a database-only leak, but a full Nest filesystem compromise can expose both the database and `runtime-secrets.json`, allowing decryption.

Action: for production, move the Fernet key and admin credential to a separate secret manager or at least a root-readable file outside the application directory with restrictive permissions.

### S4 — Low/Medium: admin-controlled and upstream-returned strings are inserted into dashboard HTML

The dashboard renders provider names and model IDs into `innerHTML` (`app/static/app.js`). A compromised or malicious upstream catalog could theoretically inject markup into the admin dashboard.

Action: escape text before HTML insertion or build these labels with `textContent` and DOM nodes; add a strict Content-Security-Policy after the dashboard is made compatible with it.

## Verified protections

- Public `/v1/models` exposes only model IDs, not upstream credentials.
- Admin key listings now omit `key_hash`.
- Upstream listings omit `encrypted_api_key`.
- API responses use `Cache-Control: no-store`.
- HTTPS is required for dashboard-managed upstream URLs.
- The user-facing provider key is hashed and cannot be recovered from the database.
