# Sponsored Provider

Small, budget-controlled OpenAI-compatible proxy for an approved Alibaba Cloud Model Studio model.

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
copy .env.example .env
pytest
uvicorn app.main:app --reload
```

For a zero-configuration start, `.env` is optional. On first launch the app generates `runtime-secrets.json` beside the database (ignored by Git) and uses the saved values for dashboard authentication, upstream-secret encryption, and provider-key hashing. Keep that file private and persistent on Nest. You can then add providers from the `Upstreams` dashboard tab.

Open http://127.0.0.1:8000/dashboard for the usage dashboard.

The dashboard accepts the `ADMIN_TOKEN` in its unlock field. It can create one-time provider keys, disable/enable/revoke keys, update the in-process model/budget/rate settings, and trigger or clear the emergency stop. For Nest, keep the service on localhost and use an SSH tunnel so the dashboard is available in your local browser without public admin exposure.

Create a provider key locally:

```bash
python -m app.cli keys create --label local-client
```

The key is shown once. Do not commit `.env`, the database, or any real credentials.

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

Set `PROVIDER_SECRET_KEY` once in the server environment. It encrypts upstream credentials stored by the dashboard. After that bootstrap step, use the `Upstreams` tab to add providers with a name, base URL, API key, model discovery, and health check. Provider secrets are never returned by the API.

## Safety status

The server does not call Alibaba at startup. Tests use mocked HTTP responses. Configure `ALLOWED_MODELS` and official input/output prices before making live calls. The dashboard reports local estimated usage, not a replacement for Alibaba's delayed billing view.

## API

- `GET /health`
- `GET /dashboard`
- `GET /api/dashboard`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `GET/POST /api/admin/keys` with `X-Admin-Token`
- `POST /api/admin/keys/{id}/disable|enable|revoke` with `X-Admin-Token`
