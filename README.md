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

Open http://127.0.0.1:8000/dashboard for the usage dashboard.

Create a provider key locally:

```bash
python -m app.cli keys create --label local-client
```

The key is shown once. Do not commit `.env`, the database, or any real credentials.

## Safety status

The server does not call Alibaba at startup. Tests use mocked HTTP responses. Configure `ALLOWED_MODELS` and official input/output prices before making live calls. The dashboard reports local estimated usage, not a replacement for Alibaba's delayed billing view.

## API

- `GET /health`
- `GET /dashboard`
- `GET /api/dashboard`
- `GET /v1/models`
- `POST /v1/chat/completions`
- `GET/POST /api/admin/keys` with `X-Admin-Token`
