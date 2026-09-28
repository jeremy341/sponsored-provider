# Sponsored Provider

Invite-only, budget-controlled OpenAI-compatible gateway with operator and developer portals. Operator-managed providers and their credentials are entered through the portal; developers create personal keys and see only their own request history.

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
copy .env.example .env
pytest
uvicorn app.main:app --reload
```

For a local start, `.env` is optional. On first launch the app generates `runtime-secrets.json` beside the database (ignored by Git) and uses the saved values for upstream-secret encryption and provider-key hashing. Keep that file private and persistent. The portal is served from the same FastAPI process after you build `frontend/`.

The portal at `/` uses local usernames, passwords, and server-side secure session cookies; browser code does not store session tokens.

Create a provider key locally:

```bash
python -m app.cli keys create --label local-client
```

The key is shown once. Do not commit `.env`, the database, or any real credentials.

## Build the portal

```bash
cd frontend
npm ci
npm run build
cd ..
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

FastAPI serves the built portal from `/` and its hashed assets from `/assets/`; existing `/v1` paths are unchanged. The development-only preview is `npm run dev -- --host 127.0.0.1` with `?preview=developer` or `?preview=operator`. Preview mode never calls account APIs or displays sample usage.

## Local account bootstrap and recovery

Build the portal, then create the first operator locally. The command prompts twice for the password and succeeds only when no operator exists:

```bash
python -m app.cli auth bootstrap
```

Operators create invite links in **People & keys**. Each link has a configurable use limit (default five) and expiry (default seven days). Share the link privately; its token is shown once. A developer follows the link, chooses a username and password, and signs in through the same-origin portal. A developer may issue one one-use invite from Home; after issuance, its safe usage and expiry status remain visible, but its token cannot be recovered.

For an existing identity-backed operator that needs a local password, adopt that account from the protected console. For a forgotten password, an operator can reset an active local account after authenticating at the console:

```bash
python -m app.cli auth adopt-operator --user-id USER_ID
python -m app.cli auth reset --username USERNAME
```

Keep the database and generated `runtime-secrets.json` private, persistent, and backed up. Provider credentials are configured from the operator portal, not environment variables.

### Hack Club Auth (dormant historical integration)

Hack Club Auth environment settings and OIDC validation were used by the earlier portal design. They are dormant: the running application mounts local username/password authentication, `/auth/login` serves the SPA, and `/auth/callback` is not mounted. No HCA button is presented to users. Old HCA environment values may remain in legacy configuration but are not required for local auth.

## Provider profiles

The operator portal accepts OpenAI-compatible HTTPS base URLs and API keys. Credentials are encrypted at rest using the generated upstream-secret key and are write-only in the portal. Discovered models start unapproved; an operator must verify and enter per-million input/output pricing before approval. Models without verified prices cannot be used by developer keys.

## Safety status

The server does not call any upstream at startup. Tests use mocked HTTP responses. Usage is a gateway estimate based on request token usage and the price card recorded for the model; it is not a provider invoice or exact upstream balance. Spend reservations and input/output token limits reduce overshoot but cannot guarantee the upstream's exact bill if it reports different usage or ignores generation bounds.

## API

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
