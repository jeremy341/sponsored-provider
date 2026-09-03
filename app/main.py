import json
import ipaddress
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .alibaba import AlibabaClient
from .config import Settings, get_settings
from .database import Database
from .errors import ProviderError
from .rate_limit import RateLimiter

@asynccontextmanager
async def lifespan(_app):
    settings = get_settings()
    print("Dashboard ready at /dashboard")
    if settings._bootstrap_generated:
        print(f"First-run dashboard token: {settings.admin_token}")
    yield


app = FastAPI(title="Sponsored Provider", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
rate_limiter = RateLimiter()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith(("/api/", "/v1/")):
        response.headers["Cache-Control"] = "no-store"
    return response


def get_db(settings: Settings = Depends(get_settings)):
    return Database(settings.database_path, settings.provider_key_pepper, settings.provider_secret_key)


def upstream_client(profile_id: str | None, db: Database, settings: Settings):
    if not profile_id or profile_id == "configured":
        if not settings.alibaba_api_key:
            raise ProviderError("No default upstream credential is configured.", "upstream_not_configured", 503)
        return AlibabaClient(settings.normalized_base_url, settings.alibaba_api_key, settings.upstream_timeout_seconds), "configured"
    profile = db.get_upstream(profile_id)
    if not profile or not profile["enabled"]:
        raise ProviderError("The selected upstream is unavailable.", "upstream_not_found", 404)
    return AlibabaClient(profile["base_url"], profile["api_key"], settings.upstream_timeout_seconds), profile_id


def provider_key(authorization: str | None, db: Database):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ProviderError("A provider API key is required.", "invalid_api_key", 401)
    key = db.find_key(authorization[7:].strip())
    if not key or not key["enabled"] or key["revoked_at"]:
        raise ProviderError("The provider API key is invalid or disabled.", "invalid_api_key", 401)
    if not key["risk_approved"]:
        raise ProviderError("This provider API key is awaiting operator approval.", "key_not_approved", 403)
    return key


def error_response(exc: ProviderError):
    return JSONResponse(status_code=exc.status_code, content={"error": {"message": exc.message, "type": "invalid_request_error", "code": exc.code}})


def require_admin(token: str | None, settings: Settings):
    if not settings.admin_token or token != settings.admin_token:
        raise ProviderError("Admin authentication is required.", "admin_unauthorized", 401)


def client_ip_for(request: Request):
    peer = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for", "")
    # Nest is the trusted private reverse-proxy peer; ignore spoofed forwarding headers from direct public clients.
    if forwarded and peer:
        try:
            if ipaddress.ip_address(peer).is_private:
                candidate = forwarded.split(",")[0].strip()
                ipaddress.ip_address(candidate)
                return candidate
        except ValueError:
            pass
    return peer


@app.exception_handler(ProviderError)
async def provider_error_handler(_, exc: ProviderError):
    return error_response(exc)


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    return {"ok": not settings.emergency_stop, "service": "sponsored-provider", "stopped": settings.emergency_stop}


@app.get("/dashboard")
async def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/api/dashboard")
async def dashboard_data(x_admin_token: str | None = Header(default=None), db: Database = Depends(get_db), settings: Settings = Depends(get_settings)):
    require_admin(x_admin_token, settings)
    summary = db.usage_summary()
    pricing_by_model = {}
    for profile in db.list_upstreams():
        for model, price in (profile.get("pricing") or {}).items():
            pricing_by_model.setdefault(model, {"input": price.get("input", 0), "output": price.get("output", 0), "source": profile["name"]})
    for item in summary.get("by_model", []):
        item["pricing"] = pricing_by_model.get(item["model"], {"input": settings.input_price_per_million, "output": settings.output_price_per_million, "source": "global fallback"})
    used = float(summary["totals"]["estimated_cost_usd"])
    return {"budget": {"hard_stop_usd": settings.provider_hard_stop_usd, "warning_usd": settings.provider_warning_usd, "used_usd": used, "remaining_usd": max(0, settings.provider_hard_stop_usd - used), "percent": min(100, used / settings.provider_hard_stop_usd * 100 if settings.provider_hard_stop_usd else 0)}, "stopped": settings.emergency_stop or used >= settings.provider_hard_stop_usd, "billing": {"source": "local_estimate", "reconciled": False, "note": "Reconcile against upstream billing before treating spend as final."}, "config": {"allowed_models": sorted(settings.model_allowlist), "input_price_per_million": settings.input_price_per_million, "output_price_per_million": settings.output_price_per_million, "rate_limit_requests_per_minute": settings.rate_limit_requests_per_minute}, **summary}


@app.get("/api/admin/keys")
async def admin_keys(x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    return {"keys": db.list_keys()}


@app.post("/api/admin/keys")
async def admin_create_key(request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    policy = {field: payload[field] for field in ("spend_limit_usd", "requests_per_minute", "token_limit", "allowed_models", "allowed_upstreams", "risk_profile", "risk_approved") if field in payload}
    for field in ("spend_limit_usd", "requests_per_minute", "token_limit"):
        if field in policy and policy[field] is not None and (not isinstance(policy[field], (int, float)) or policy[field] < 0):
            raise ProviderError(f"{field} must be a non-negative number or null.", "invalid_key_policy", 400)
    if policy.get("risk_profile") not in (None, "strict", "standard", "trusted"):
        raise ProviderError("risk_profile must be strict, standard, or trusted.", "invalid_key_policy", 400)
    raw, metadata = db.create_key(str(payload.get("label") or "client"), policy)
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


@app.post("/api/admin/keys/{key_id}/revoke")
async def admin_revoke_key(key_id: int, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    db.set_key_state(key_id, False, revoke=True)
    return {"ok": True, "id": key_id, "revoked": True}


@app.post("/api/admin/keys/{key_id}/archive")
async def admin_archive_key(key_id: int, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    db.archive_key(key_id)
    return {"ok": True, "id": key_id, "archived": True, "usage_history_preserved": True}


@app.post("/api/admin/keys/{key_id}/policy")
async def admin_key_policy(key_id: int, request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    values = {}
    clear_fields = [field for field in payload.get("clear_fields", []) if field in {"spend_limit_usd", "requests_per_minute", "token_limit", "allowed_models"}] if isinstance(payload.get("clear_fields", []), list) else []
    for field in ("spend_limit_usd", "requests_per_minute", "token_limit"):
        if field in payload:
            value = payload[field]
            if value is None:
                clear_fields.append(field)
                continue
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                raise ProviderError(f"{field} must be a non-negative number or null.", "invalid_key_policy", 400)
            values[field] = value
    if "allowed_models" in payload:
        if not isinstance(payload["allowed_models"], str):
            if payload["allowed_models"] is None:
                clear_fields.append("allowed_models")
            else:
                raise ProviderError("allowed_models must be a comma-separated string.", "invalid_key_policy", 400)
        else:
            values["allowed_models"] = payload["allowed_models"]
    if "allowed_upstreams" in payload:
        if not isinstance(payload["allowed_upstreams"], str):
            raise ProviderError("allowed_upstreams must be a comma-separated string.", "invalid_key_policy", 400)
        values["allowed_upstreams"] = payload["allowed_upstreams"]
    if "risk_profile" in payload:
        if payload["risk_profile"] not in ("strict", "standard", "trusted"):
            raise ProviderError("risk_profile must be strict, standard, or trusted.", "invalid_key_policy", 400)
        values["risk_profile"] = payload["risk_profile"]
    if "risk_approved" in payload:
        values["risk_approved"] = bool(payload["risk_approved"])
    db.update_key_policy(key_id, clear_fields=clear_fields, **values)
    return {"ok": True, "id": key_id, "key": next((item for item in db.list_keys() if item["id"] == key_id), None)}


@app.post("/api/admin/config")
async def admin_config(request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    if "allowed_models" in payload:
        models_value = payload["allowed_models"]
        if not isinstance(models_value, str):
            raise ProviderError("allowed_models must be a comma-separated string.", "invalid_config", 400)
        settings.allowed_models = models_value
    for field in ("provider_hard_stop_usd", "provider_warning_usd", "input_price_per_million", "output_price_per_million", "rate_limit_requests_per_minute"):
        if field in payload:
            try:
                value = float(payload[field]) if field != "rate_limit_requests_per_minute" else int(payload[field])
            except (TypeError, ValueError) as exc:
                raise ProviderError(f"{field} must be numeric.", "invalid_config", 400) from exc
            if value < 0:
                raise ProviderError(f"{field} cannot be negative.", "invalid_config", 400)
            setattr(settings, field, value)
    if "emergency_stop" in payload:
        settings.emergency_stop = bool(payload["emergency_stop"])
    return {"ok": True, "config": {"allowed_models": sorted(settings.model_allowlist), "provider_hard_stop_usd": settings.provider_hard_stop_usd, "provider_warning_usd": settings.provider_warning_usd, "input_price_per_million": settings.input_price_per_million, "output_price_per_million": settings.output_price_per_million, "rate_limit_requests_per_minute": settings.rate_limit_requests_per_minute, "emergency_stop": settings.emergency_stop}}


@app.get("/api/admin/upstream-models")
async def admin_upstream_models(profile_id: str | None = None, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    client, resolved_id = upstream_client(profile_id, db, settings)
    payload = await client.list_models()
    items = payload.get("data", payload if isinstance(payload, list) else [])
    model_ids = sorted({item.get("id") for item in items if isinstance(item, dict) and item.get("id")})
    if resolved_id != "configured":
        db.update_upstream_models(resolved_id, model_ids, "healthy" if model_ids else "empty_catalog")
    return {"profile_id": resolved_id, "models": model_ids}


@app.get("/api/admin/upstreams")
async def admin_upstreams(x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    profiles = db.list_upstreams()
    if settings.alibaba_api_key:
        profiles.insert(0, {"id": "configured", "name": "Configured environment upstream", "provider_kind": "configured", "base_url": settings.normalized_base_url, "enabled": True, "secret_configured": True, "models": sorted(settings.model_allowlist), "health_status": "configured"})
    return {"upstreams": profiles}


@app.post("/api/admin/upstreams")
async def admin_create_upstream(request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    name, provider_kind, base_url, api_key = (str(payload.get(field, "")).strip() for field in ("name", "provider_kind", "base_url", "api_key"))
    parsed = urlparse(base_url)
    if not name or not api_key or parsed.scheme != "https" or not parsed.netloc:
        raise ProviderError("Provider name, HTTPS base URL, and API key are required.", "invalid_upstream", 400)
    if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        raise ProviderError("Local upstream URLs are not allowed in provider profiles.", "invalid_upstream", 400)
    try:
        profile = db.create_upstream(name, provider_kind or "openai_compatible", base_url, api_key)
    except ValueError as exc:
        raise ProviderError(str(exc), "secret_storage_not_configured", 503) from exc
    return profile


@app.post("/api/admin/upstreams/{profile_id}")
async def admin_update_upstream(profile_id: str, request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    base_url = str(payload.get("base_url", "")).strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        raise ProviderError("Provider base URL must be a public HTTPS URL.", "invalid_upstream", 400)
    with db.connect() as conn:
        conn.execute("UPDATE upstream_profiles SET base_url=? WHERE id=?", (base_url, profile_id))
    return {"ok": True, "profile_id": profile_id, "base_url": base_url}


@app.post("/api/admin/upstreams/{profile_id}/pricing")
async def admin_upstream_pricing(profile_id: str, request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    pricing = payload.get("pricing", payload)
    if not isinstance(pricing, dict):
        raise ProviderError("Pricing must be a model-to-price object.", "invalid_pricing", 400)
    normalized = {}
    for model, values in pricing.items():
        if not isinstance(model, str) or not isinstance(values, dict):
            raise ProviderError("Each model needs input and output prices.", "invalid_pricing", 400)
        try:
            input_price, output_price = float(values.get("input", 0)), float(values.get("output", 0))
        except (TypeError, ValueError) as exc:
            raise ProviderError("Model prices must be numeric.", "invalid_pricing", 400) from exc
        if input_price < 0 or output_price < 0:
            raise ProviderError("Model prices cannot be negative.", "invalid_pricing", 400)
        normalized[model] = {"input": input_price, "output": output_price}
    if not db.get_upstream(profile_id):
        raise ProviderError("Upstream profile not found.", "upstream_not_found", 404)
    db.update_upstream_pricing(profile_id, normalized)
    return {"ok": True, "profile_id": profile_id, "pricing": normalized}


@app.get("/api/admin/blocked-ips")
async def admin_blocked_ips(x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    return {"blocked_ips": db.list_blocked_ips()}


@app.post("/api/admin/blocked-ips")
async def admin_block_ip(request: Request, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    payload = await request.json()
    ip = str(payload.get("ip", "")).strip()
    reason = str(payload.get("reason", "manual operator block")).strip() or "manual operator block"
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise ProviderError("Enter a valid IPv4 or IPv6 address.", "invalid_ip", 400)
    db.block_ip(ip, reason)
    return {"ok": True, "blocked_ips": db.list_blocked_ips()}


@app.post("/api/admin/blocked-ips/{ip}/remove")
async def admin_unblock_ip(ip: str, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    db.unblock_ip(ip)
    return {"ok": True, "ip": ip}


@app.post("/api/admin/models/{model}/block")
async def admin_block_model(model: str, x_admin_token: str | None = Header(default=None), settings: Settings = Depends(get_settings), db: Database = Depends(get_db)):
    require_admin(x_admin_token, settings)
    model = model.strip()
    if not model or len(model) > 200:
        raise ProviderError("Enter a valid model ID.", "invalid_model", 400)
    changed = db.remove_model_from_keys(model)
    settings.allowed_models = ", ".join(item for item in settings.model_allowlist if item != model)
    return {"ok": True, "model": model, "keys_updated": changed}


@app.get("/v1/models")
async def models(request: Request, settings: Settings = Depends(get_settings), authorization: str | None = Header(default=None), db: Database = Depends(get_db)):
    client_ip = client_ip_for(request)
    if db.is_ip_blocked(client_ip):
        raise ProviderError("Requests from this IP address are blocked.", "ip_blocked", 403)
    key = provider_key(authorization, db)
    key_models = {item.strip() for item in (key["allowed_models"] or "").split(",") if item.strip()}
    effective_models = key_models or settings.model_allowlist
    return {"object": "list", "data": [{"id": model, "object": "model", "owned_by": "sponsored-provider"} for model in sorted(effective_models)]}


@app.post("/v1/chat/completions")
async def chat(request: Request, settings: Settings = Depends(get_settings), authorization: str | None = Header(default=None), db: Database = Depends(get_db)):
    client_ip = client_ip_for(request)
    if db.is_ip_blocked(client_ip):
        raise ProviderError("Requests from this IP address are blocked.", "ip_blocked", 403)
    key = provider_key(authorization, db)
    if settings.emergency_stop:
        raise ProviderError("The provider is temporarily stopped.", "provider_stopped", 503)
    key_rate_limit = settings.rate_limit_requests_per_minute if key["requests_per_minute"] is None else key["requests_per_minute"]
    if not rate_limiter.allow(f"{db.path}:{key['id']}:{client_ip or 'unknown'}", key_rate_limit):
        raise ProviderError("Too many requests for this provider key.", "rate_limited", 429)
    used = db.usage_summary()["totals"]["estimated_cost_usd"]
    key_usage = db.key_usage(key["id"])
    if key["spend_limit_usd"] is not None and key["spend_limit_usd"] > 0 and key_usage["estimated_cost_usd"] >= key["spend_limit_usd"]:
        db.set_key_state(key["id"], False)
        raise ProviderError("This provider key has reached its spend limit.", "key_budget_exhausted", 429)
    if key["token_limit"] is not None and key["token_limit"] > 0 and key_usage["total_tokens"] >= key["token_limit"]:
        db.set_key_state(key["id"], False)
        raise ProviderError("This provider key has reached its token limit.", "key_token_limit_exhausted", 429)
    if used >= settings.provider_hard_stop_usd:
        db.set_key_state(key["id"], False)
        raise ProviderError("The provider budget has been exhausted.", "budget_exhausted", 429)
    raw = await request.body()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("Request body must be valid JSON.", "invalid_request", 400) from exc
    model = payload.get("model")
    key_models = {item.strip() for item in (key["allowed_models"] or "").split(",") if item.strip()}
    if model not in (key_models or settings.model_allowlist):
        raise ProviderError("The requested model is not allowlisted.", "model_not_found", 404)
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ProviderError("messages must be a non-empty list.", "invalid_request", 400)
    upstream_ids = [item.strip() for item in (key["allowed_upstreams"] or "").split(",") if item.strip()]
    client, upstream_id = upstream_client(upstream_ids[0] if upstream_ids else "configured", db, settings)
    input_price, output_price = db.model_pricing(upstream_id, model, settings.input_price_per_million, settings.output_price_per_million)
    if input_price <= 0 or output_price <= 0:
        raise ProviderError("Official model input/output prices must be configured before live requests.", "pricing_not_configured", 503)
    if "max_tokens" in payload and payload["max_tokens"] is not None:
        try:
            payload["max_tokens"] = int(payload["max_tokens"])
        except (TypeError, ValueError):
            pass
    current_input_estimate = sum(len(str(item.get("content", ""))) for item in messages if isinstance(item, dict)) / 4
    _max_tokens_estimate = payload.get("max_tokens")
    projected_cost = estimate_cost(current_input_estimate, _max_tokens_estimate, settings, input_price, output_price)
    projected_tokens = current_input_estimate + (_max_tokens_estimate or 0)
    if key["spend_limit_usd"] is not None and key["spend_limit_usd"] > 0 and key_usage["estimated_cost_usd"] + projected_cost >= key["spend_limit_usd"]:
        db.set_key_state(key["id"], False)
        raise ProviderError("This provider key cannot safely accept the request within its spend limit.", "key_budget_exhausted", 429)
    if key["token_limit"] is not None and key["token_limit"] > 0 and key_usage["total_tokens"] + projected_tokens >= key["token_limit"]:
        db.set_key_state(key["id"], False)
        raise ProviderError("This provider key cannot safely accept the request within its token limit.", "key_token_limit_exhausted", 429)
    if used + projected_cost + settings.provider_estimate_reserve_usd >= settings.provider_hard_stop_usd:
        raise ProviderError("The provider budget cannot safely accept this request.", "budget_exhausted", 429)
    payload["model"] = model
    reservation_id = db.reserve_budget(key["id"], upstream_id, model, projected_cost, projected_tokens, settings.provider_hard_stop_usd, key["spend_limit_usd"])
    if not reservation_id:
        raise ProviderError("The provider budget cannot safely accept this request.", "budget_exhausted", 429)
    if payload.get("stream"):
        payload.setdefault("stream_options", {"include_usage": True})
        async def stream_body():
            started_stream = time.perf_counter()
            stream_input_tokens = None
            stream_output_tokens = None
            stream_total_tokens = None
            try:
                async for chunk in client.stream_chat_completion(payload):
                    if '"usage"' in chunk:
                        try:
                            data_part = chunk.strip()
                            if data_part.startswith("data:"):
                                data_part = data_part[5:].strip()
                                if data_part and data_part != "[DONE]":
                                    parsed = json.loads(data_part)
                                    usage = parsed.get("usage") or parsed.get("choices", [{}])[0].get("usage") if isinstance(parsed, dict) else None
                                    if isinstance(usage, dict):
                                        stream_input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                                        stream_output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                                        stream_total_tokens = usage.get("total_tokens")
                                        if stream_input_tokens is not None or stream_output_tokens is not None:
                                            continue
                        except Exception:
                            pass
                    yield chunk
                latency_stream = int((time.perf_counter() - started_stream) * 1000)
                if stream_input_tokens is not None or stream_output_tokens is not None:
                    actual_cost = estimate_cost(stream_input_tokens, stream_output_tokens, settings, input_price, output_price)
                    db.record_usage(key["id"], model=model, input_tokens=stream_input_tokens, output_tokens=stream_output_tokens, total_tokens=stream_total_tokens or ((stream_input_tokens or 0) + (stream_output_tokens or 0) if stream_input_tokens is not None or stream_output_tokens is not None else None), estimated_cost_usd=actual_cost, latency_ms=latency_stream, status="success", stream=True, client_ip=client_ip, upstream_profile_id=upstream_id, reservation_id=reservation_id)
                else:
                    db.record_usage(key["id"], model=model, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=projected_cost, latency_ms=latency_stream, status="success", stream=True, client_ip=client_ip, upstream_profile_id=upstream_id, reservation_id=reservation_id)
            except ProviderError as exc:
                db.record_usage(key["id"], model=model, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=projected_cost, latency_ms=int((time.perf_counter() - started_stream) * 1000), status="failed", stream=True, client_ip=client_ip, upstream_profile_id=upstream_id, reservation_id=reservation_id, error_category=exc.code)
                yield f'data: {json.dumps({"error": {"message": exc.message, "code": exc.code}})}\n\n'
        return StreamingResponse(stream_body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    started = time.perf_counter()
    try:
        body, latency = await client.chat_completion(payload)
    except ProviderError as exc:
        db.record_usage(key["id"], model=model, input_tokens=None, output_tokens=None, total_tokens=None, estimated_cost_usd=0, latency_ms=int((time.perf_counter() - started) * 1000), status="failed", stream=bool(payload.get("stream")), client_ip=client_ip, upstream_profile_id=upstream_id, reservation_id=reservation_id, error_category=exc.code)
        raise
    usage = body.get("usage") or {}
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    estimated_cost = estimate_cost(input_tokens, output_tokens, settings, input_price, output_price)
    db.record_usage(key["id"], model=model, input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens, estimated_cost_usd=estimated_cost, latency_ms=latency, status="success", stream=bool(payload.get("stream")), client_ip=client_ip, upstream_profile_id=upstream_id, reservation_id=reservation_id)
    if db.usage_summary()["totals"]["estimated_cost_usd"] >= settings.provider_hard_stop_usd:
        db.set_key_state(key["id"], False)
    return body


def estimate_cost(input_tokens, output_tokens, settings: Settings, input_price=None, output_price=None) -> float:
    input_price = settings.input_price_per_million if input_price is None else input_price
    output_price = settings.output_price_per_million if output_price is None else output_price
    return round((input_tokens or 0) / 1_000_000 * input_price + (output_tokens or 0) / 1_000_000 * output_price, 6)
