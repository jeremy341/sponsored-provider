import json
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .alibaba import AlibabaClient
from .config import Settings, get_settings
from .database import Database
from .errors import ProviderError
from .rate_limit import RateLimiter

app = FastAPI(title="Sponsored Provider", version="0.1.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
rate_limiter = RateLimiter()


def get_db(settings: Settings = Depends(get_settings)):
    return Database(settings.database_path, settings.provider_key_pepper)


def provider_key(authorization: str | None, db: Database):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ProviderError("A provider API key is required.", "invalid_api_key", 401)
    key = db.find_key(authorization[7:].strip())
    if not key or not key["enabled"] or key["revoked_at"]:
        raise ProviderError("The provider API key is invalid or disabled.", "invalid_api_key", 401)
    return key


def error_response(exc: ProviderError):
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.message, "type": "invalid_request_error", "code": exc.code}})


def require_admin(token: str | None, settings: Settings):
    if not settings.admin_token or token != settings.admin_token:
        raise ProviderError("Admin authentication is required.", "admin_unauthorized", 401)


@app.exception_handler(ProviderError)
async def provider_error_handler(_, exc: ProviderError):
    return error_response(exc)


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    return {"ok": not settings.emergency_stop, "service": "sponsored-provider", "stopped": settings.emergency_stop}


@app.get("/dashboard")
async def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/dashboard")
async def dashboard_data(x_admin_token: str | None = Header(default=None), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
    require_admin(x_admin_token, settings)
    summary = db.usage_summary()
    used = float(summary["totals"]["estimated_cost_usd"])
    return {"budget": {"hard_stop_usd": settings.provider_hard_stop_usd, "warning_usd": settings.provider_warning_usd, "used_usd": used, "remaining_usd": max(0, settings.provider_hard_stop_usd - used), "percent": min(100, used / settings.provider_hard_stop_usd * 100 if settings.provider_hard_stop_usd else 0)}, "stopped": settings.emergency_stop or used >= settings.provider_hard_stop_usd, **summary}


@app.get("/api/admin/keys")
async def admin_keys(x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    return {"keys": db.list_keys()}


@app.post("/api/admin/keys")
async def admin_create_key(request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    raw, metadata = db.create_key(str(payload.get("label") or "client"))
    return {"key": raw, **metadata}


@app.post("/api/admin/keys/{key_id}/disable")
async def admin_disable_key(key_id: int, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    db.set_key_state(key_id, False)
    return {"ok": True, "id": key_id, "enabled": False}


@app.post("/api/admin/keys/{key_id}/enable")
async def admin_enable_key(key_id: int, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    db.set_key_state(key_id, True)
    return {"ok": True, "id": key_id, "enabled": True}


@app.get("/v1/models")
async def models(settings: Settings = Depends(get_settings), authorization: str | None = Header(default=None), db: Database = Depends(get_db)):
    provider_key(authorization, db)
    return {"object": "list", "data": [{"id": model, "object": "model", "owned_by": "sponsored-provider"} for model in sorted(settings.model_allowlist)]}


@app.post("/v1/chat/completions")
async def chat(request: Request, settings: Settings = Depends(get_settings), authorization: str | None = Header(default=None), db: Database = Depends(get_db)):
    key = provider_key(authorization, db)
    if settings.emergency_stop:
        raise ProviderError("The provider is temporarily stopped.", "provider_stopped", 503)
    if not rate_limiter.allow(key["id"], settings.rate_limit_requests_per_minute):
        raise ProviderError("Too many requests for this provider key.", "rate_limited", 429)
    used = db.usage_summary()["totals"]["estimated_cost_usd"]
    if used >= settings.provider_hard_stop_usd:
        db.set_key_state(key["id"], False)
        raise ProviderError("The provider budget has been exhausted.", "budget_exhausted", 429)
    raw = await request.body()
    if len(raw) > settings.max_request_bytes:
        raise ProviderError("Request body is too large.", "request_too_large", 413)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("Request body must be valid JSON.", "invalid_request", 400) from exc
    model = payload.get("model")
    if model not in settings.model_allowlist:
        raise ProviderError("The requested model is not allowlisted.", "model_not_found", 404)
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ProviderError("messages must be a non-empty list.", "invalid_request", 400)
    if sum(len(str(item.get("content", ""))) for item in messages if isinstance(item, dict)) > settings.max_input_chars:
        raise ProviderError("Input content is too large.", "input_too_large", 413)
    if settings.input_price_per_million <= 0 or settings.output_price_per_million <= 0:
        raise ProviderError("Official model input/output prices must be configured before live requests.", "pricing_not_configured", 503)
    payload["max_tokens"] = min(int(payload.get("max_tokens", settings.max_output_tokens)), settings.max_output_tokens)
    current_input_estimate = sum(len(str(item.get("content", ""))) for item in messages if isinstance(item, dict)) / 4
    projected_cost = estimate_cost(current_input_estimate, payload["max_tokens"], settings)
    if used + projected_cost + settings.provider_estimate_reserve_usd >= settings.provider_hard_stop_usd:
        db.set_key_state(key["id"], False)
        raise ProviderError("The provider budget cannot safely accept this request.", "budget_exhausted", 429)
    payload["model"] = model
    client = AlibabaClient(settings.normalized_base_url, settings.alibaba_api_key, settings.upstream_timeout_seconds)
    if payload.get("stream"):
        async def stream_body():
            try:
                async for chunk in client.stream_chat_completion(payload):
                    yield chunk
                db.record_usage(key["id"], model=model, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=projected_cost, latency_ms=None, status="success", stream=True)
            except ProviderError as exc:
                db.record_usage(key["id"], model=model, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=projected_cost, latency_ms=None, status="failed", stream=True, error_category=exc.code)
                yield f'data: {json.dumps({"error": {"message": exc.message, "code": exc.code}})}\n\n'
        return StreamingResponse(stream_body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    started = time.perf_counter()
    try:
        body, latency = await client.chat_completion(payload)
    except ProviderError as exc:
        db.record_usage(key["id"], model=model, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=0, latency_ms=int((time.perf_counter() - started) * 1000), status="failed", stream=bool(payload.get("stream")), error_category=exc.code)
        raise
    usage = body.get("usage") or {}
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    estimated_cost = estimate_cost(input_tokens, output_tokens, settings)
    db.record_usage(key["id"], model=model, input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens, estimated_cost_usd=estimated_cost, latency_ms=latency, status="success", stream=bool(payload.get("stream")))
    if db.usage_summary()["totals"]["estimated_cost_usd"] >= settings.provider_hard_stop_usd:
        db.set_key_state(key["id"], False)
    return body


def estimate_cost(input_tokens, output_tokens, settings: Settings) -> float:
    return round((input_tokens or 0) / 1_000_000 * settings.input_price_per_million + (output_tokens or 0) / 1_000_000 * settings.output_price_per_million, 6)
