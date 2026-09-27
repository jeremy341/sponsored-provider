"""Composable auth and portal routes; include these beside, never instead of, ``/v1``."""

from __future__ import annotations

import asyncio
import hmac
import secrets
import ipaddress
import math
import re
import socket
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse, urlsplit

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
import httpx

from app.identity import HackClubOIDC
from app.catalog import ModelsDevCatalog, PriceSuggestion, normalize_openai_models
from app.portal_db import PortalDatabase
from app.database import Database
from app.config import Settings
from app.openai_compatible import OpenAICompatibleClient
from app.password_auth import PasswordPolicyError, hash_password, normalize_username, verify_password_or_dummy


class PortalService:
    def __init__(
        self,
        repository: PortalDatabase,
        identity: HackClubOIDC | None,
        *,
        cookie_secure: bool = True,
        session_ttl_seconds: int = 8 * 60 * 60,
        bootstrap_operator_email: str | None = None,
        legacy_database: Database | None = None,
        settings: Settings | None = None,
        auth_rate_limit_attempts: int = 5,
        auth_rate_limit_window_seconds: int = 900,
        public_origin: str | None = None,
        models_dev_catalog: ModelsDevCatalog | None = None,
    ):
        if not 300 <= session_ttl_seconds <= 24 * 60 * 60:
            raise ValueError("Portal session lifetime must be between 5 minutes and 24 hours")
        self.repository = repository
        self.identity = identity
        self.cookie_secure = cookie_secure
        self.session_ttl_seconds = session_ttl_seconds
        self.bootstrap_operator_email = bootstrap_operator_email
        self.legacy_database = legacy_database
        self.settings = settings
        if auth_rate_limit_attempts < 1 or auth_rate_limit_window_seconds < 1:
            raise ValueError("Authentication rate limits must be positive")
        self.auth_rate_limit_attempts = auth_rate_limit_attempts
        self.auth_rate_limit_window_seconds = auth_rate_limit_window_seconds
        self.public_origin = public_origin.rstrip("/") if public_origin else None
        self.models_dev_catalog = models_dev_catalog


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {"id": user["id"], "displayName": user["display_name"], "email": user["email"], "username": user.get("username")}


def _key_record(key: dict[str, Any]) -> dict[str, Any]:
    model_access = {"mode": "all_approved"} if key["allowed_models_mode"] == "all_approved" else {"mode": "selected", "modelIds": key["allowed_models"]}
    period = {"daily": "day", "weekly": "week", "monthly": "month", "lifetime": "lifetime"}.get(key["spend_period"])
    status = "archived" if key.get("archived_at") else "disabled" if key.get("revoked_at") else "active"
    return {
        "id": key["id"], "label": key["label"], "prefix": key["key_prefix"], "modelAccess": model_access,
        "spendCapUsd": key["spend_limit_usd"], "spendUsedUsd": key.get("spend_used_usd"), "spendPeriod": period, "spendResetAt": key.get("spend_reset_at"), "rpmLimit": key["rpm_limit"],
        "createdAt": key["created_at"], "lastUsedAt": key.get("last_used_at"), "status": status,
    }


def _activity_record(event: dict[str, Any], *, operator: bool = False) -> dict[str, Any]:
    status = event["status"]
    status = "success" if status in {"ok", "success"} else status if status in {"error", "rejected", "interrupted"} else "error"
    row = {
        "id": event["id"], "occurredAt": event["occurred_at"], "modelId": event["model_id"],
        "providerName": event["provider_name_snapshot"] or "Unknown provider", "keyLabel": event["key_label_snapshot"],
        "inputTokens": event["input_tokens"], "outputTokens": event["output_tokens"], "totalTokens": event["total_tokens"],
        "estimatedCostUsd": event["estimated_cost_usd"],
        "costSource": "gateway_estimate" if event["estimated_cost_usd"] is not None else "unknown",
        "status": status, "errorCategory": event["error_category"], "latencyMs": event["latency_ms"],
        "cachedTokens": event["cached_tokens"], "requestIp": event.get("client_ip"),
    }
    if operator:
        row["userId"] = event.get("owner_user_id")
    return row


def _model_usage_record(item: dict[str, Any]) -> dict[str, Any]:
    return {"modelId": item["model_id"], "providerName": item["provider_name"] or "Unknown provider", "requests": item["requests"], "totalTokens": item["total_tokens"], "estimatedSpendUsd": item["estimated_spend_usd"]}


def _api_model(model: dict[str, Any], *, public_id: bool = False) -> dict[str, Any]:
    return {
        "id": model["public_model_id"] if public_id else model["model_id"], "upstreamModelId": model["model_id"], "providerId": model["provider_id"], "providerName": model["provider_name"], "capabilities": model["capabilities"],
        "inputUsdPerMillion": model["input_price_per_million"], "outputUsdPerMillion": model["output_price_per_million"],
        "cacheUsdPerMillion": model["cached_input_price_per_million"], "pricingVerified": bool(model["price_source"]),
        "priceSource": model["price_source"], "approved": bool(model["approved"]), "available": bool(model["active"]), "syncedAt": model["updated_at"],
    }


def _period_start(period: str | None, now: datetime) -> datetime | None:
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start - timedelta(days=start.weekday())
    if period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


def _public_https_base_url(value: str) -> str:
    parsed = urlparse(value.strip())
    host = parsed.hostname
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("The upstream URL contains an invalid port") from exc
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use a public HTTPS base URL without credentials, query, or fragment")
    if port not in (None, 443):
        raise ValueError("Custom upstream ports are not supported")
    if host.endswith(".") or host.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("Local and ambiguous upstream hosts are not allowed")
    try:
        address = ipaddress.ip_address(host)
        addresses = [address]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
        except (OSError, ValueError) as exc:
            raise ValueError("The upstream hostname could not be resolved safely") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Upstream host must resolve only to public IP addresses")
    return value.strip().rstrip("/")


def create_portal_router(service: PortalService) -> APIRouter:
    router = APIRouter()
    hca_router = APIRouter()
    repo = service.repository

    async def current_session(portal_session: str | None = Cookie(default=None)) -> tuple[dict[str, Any], str]:
        if not portal_session:
            raise HTTPException(status_code=401, detail="Sign-in required")
        found = repo.get_session(portal_session)
        if not found:
            raise HTTPException(status_code=401, detail="Sign-in required")
        return found

    async def developer(session=Depends(current_session)) -> tuple[dict[str, Any], str]:
        user, csrf_hash = session
        if user["role"] != "developer":
            raise HTTPException(status_code=403, detail="Developer role required")
        return session

    async def operator(session=Depends(current_session)) -> tuple[dict[str, Any], str]:
        user, csrf_hash = session
        if user["role"] != "operator":
            raise HTTPException(status_code=403, detail="Operator role required")
        return session

    def require_csrf(session: tuple[dict[str, Any], str], csrf_cookie: str | None, csrf_header: str | None) -> None:
        _user, expected_hash = session
        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header) or not repo.verify_csrf(expected_hash, csrf_cookie):
            raise HTTPException(status_code=403, detail="CSRF validation failed")

    async def sync_connection(connection_id: str, profile_id: str, actor_id: str) -> dict[str, Any]:
        if not service.legacy_database or not service.settings:
            raise HTTPException(status_code=503, detail="Provider storage is unavailable")
        upstream = service.legacy_database.get_upstream(profile_id)
        if not upstream:
            raise HTTPException(status_code=404, detail="Provider profile not found")
        try:
            payload = await OpenAICompatibleClient(
                upstream["base_url"], upstream["api_key"], service.settings.upstream_timeout_seconds,
            ).list_models()
            discovered = normalize_openai_models(payload)
        except Exception as exc:
            service.legacy_database.update_upstream_models(profile_id, [], "error")
            repo.mark_discovery_stale(connection_id)
            repo.audit(actor_id, "provider.sync_failed", "provider", connection_id)
            raise HTTPException(status_code=502, detail="Model discovery failed. Check the URL and upstream credential.") from exc

        model_ids = [model.id for model in discovered]
        service.legacy_database.update_upstream_models(profile_id, model_ids, "healthy" if model_ids else "empty_catalog")
        try:
            summary = repo.apply_discovery(connection_id, discovered, datetime.now(timezone.utc))
        except (LookupError, ValueError) as exc:
            repo.audit(actor_id, "provider.sync_failed", "provider", connection_id, {"reason": "connection_state"})
            raise HTTPException(status_code=409, detail="Provider connection is not eligible for model discovery.") from exc
        connection = repo.get_connection(connection_id)
        if service.models_dev_catalog is None:
            service.models_dev_catalog = await asyncio.to_thread(ModelsDevCatalog.fetch)
        for model in discovered:
            offer_id = repo.get_discovered_offer_id(connection_id, model.id)
            if not offer_id:
                continue
            match = service.models_dev_catalog.lookup(connection["brand_slug"], model.id)
            if match.status == "exact" and match.input_usd_per_million is not None and match.output_usd_per_million is not None:
                repo.save_price_suggestion(offer_id, PriceSuggestion(
                    match.input_usd_per_million, match.output_usd_per_million,
                    match.cached_input_usd_per_million, "models.dev", match.source_url,
                    match.evidence, match.confidence, match.fetched_at,
                ))
            reported = upstream.get("pricing", {}).get(model.id, {})
            if isinstance(reported, dict):
                input_rate, output_rate = reported.get("input"), reported.get("output")
                if input_rate is not None and output_rate is not None:
                    try:
                        repo.save_price_suggestion(offer_id, PriceSuggestion(
                            input_rate, output_rate, reported.get("cache"), "provider-reported",
                            evidence="Rates reported by the configured upstream profile.", confidence="provider-reported",
                        ))
                    except (TypeError, ValueError):
                        pass
        repo.audit(actor_id, "provider.synced", "provider", connection_id,
                   {"models_discovered": summary.discovered_count, "stale_models": summary.stale_count})
        return {"providerId": profile_id, "connectionId": connection_id,
                "modelsDiscovered": summary.discovered_count, "models": model_ids,
                "staleModels": summary.stale_count}

    def require_same_origin(request: Request) -> None:
        supplied = request.headers.get("origin")
        is_referer = False
        if not supplied:
            supplied = request.headers.get("referer")
            is_referer = True
        if not supplied or supplied == "null":
            raise HTTPException(status_code=403, detail="Same-origin request required")
        try:
            parsed = urlsplit(supplied)
            expected = urlsplit(service.public_origin or str(request.base_url))
            if parsed.username or parsed.password or not parsed.hostname or not expected.hostname:
                raise ValueError("Invalid origin")
            if parsed.scheme.lower() != expected.scheme.lower() or parsed.netloc.lower() != expected.netloc.lower():
                raise ValueError("Cross-origin request")
            if not is_referer and parsed.path not in {"", "/"}:
                raise ValueError("Invalid origin")
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Same-origin request required") from exc

    def rate_limit_auth(request: Request, username: Any) -> None:
        normalized = username.strip().casefold()[:256] if isinstance(username, str) else ""
        client_ip = request.client.host if request.client else "unknown"
        if not repo.allow_local_auth_attempt(
            normalized_username=normalized,
            client_ip=client_ip,
            limit=service.auth_rate_limit_attempts,
            window_seconds=service.auth_rate_limit_window_seconds,
        ):
            raise HTTPException(status_code=429, detail="Too many authentication attempts; try again later")

    async def auth_body(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Invalid authentication request") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Invalid authentication request")
        return body

    def issue_local_session(request: Request, response: Response, user_id: str) -> None:
        previous = request.cookies.get("portal_session")
        if previous:
            repo.revoke_session(previous)
        session = repo.create_session(user_id, ttl_seconds=service.session_ttl_seconds)
        response.set_cookie("portal_session", session.raw_token, max_age=service.session_ttl_seconds, httponly=True, secure=service.cookie_secure, samesite="lax", path="/")
        response.set_cookie("portal_csrf", session.csrf_token, max_age=service.session_ttl_seconds, httponly=False, secure=service.cookie_secure, samesite="lax", path="/")

    @router.post("/auth/signup", status_code=201)
    async def signup(request: Request):
        require_same_origin(request)
        data = await auth_body(request)
        rate_limit_auth(request, data.get("username"))
        username, password, token = data.get("username"), data.get("password"), data.get("invite")
        try:
            normalized = normalize_username(username)
            if not isinstance(password, str):
                raise PasswordPolicyError("Password must be text")
            encoded = hash_password(password)
        except (ValueError, PasswordPolicyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not isinstance(token, str) or not token or len(token) > 256:
            raise HTTPException(status_code=422, detail="A valid invitation token is required")
        try:
            user = repo.create_local_account_with_invite(
                raw_token=token, username=username.strip(), password_hash=encoded, display_name=username.strip()
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="Invitation is invalid, expired, revoked, exhausted, or requires verified email") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409 if "already in use" in str(exc).casefold() else 422, detail=str(exc)) from exc
        response = JSONResponse({"user": _public_user(user), "role": user["role"]}, status_code=201)
        issue_local_session(request, response, user["id"])
        return response

    @router.post("/auth/login")
    async def local_login(request: Request):
        require_same_origin(request)
        data = await auth_body(request)
        rate_limit_auth(request, data.get("username"))
        username, password = data.get("username"), data.get("password")
        try:
            normalized = normalize_username(username)
        except ValueError:
            normalized = ""
        if not isinstance(password, str):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        user = repo.get_local_user_by_username(normalized) if normalized else None
        if not verify_password_or_dummy(password, user.get("password_hash") if user else None) or not user or user["status"] != "active":
            raise HTTPException(status_code=401, detail="Invalid username or password")
        repo.record_local_login(user["id"])
        response = JSONResponse({"user": _public_user(user), "role": user["role"]})
        issue_local_session(request, response, user["id"])
        return response

    @hca_router.get("/auth/login")
    async def login(request: Request, invite: str | None = Query(default=None, max_length=256)):
        if service.identity is None:
            raise HTTPException(status_code=503, detail="Hack Club Auth is not configured on this server")
        invite_record = repo.find_invite(invite) if invite else None
        if invite and not invite_record:
            raise HTTPException(status_code=403, detail="Invitation is invalid or expired")
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        try:
            repo.create_oauth_transaction(state, nonce, invite_record["id"] if invite_record else None)
            authorize_url = await service.identity.authorization_url(state=state, nonce=nonce)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable") from exc
        response = RedirectResponse(authorize_url, status_code=302)
        response.set_cookie("portal_oauth_state", state, max_age=600, httponly=True, secure=service.cookie_secure, samesite="lax", path="/auth/callback")
        return response

    @hca_router.get("/auth/callback")
    async def callback(
        request: Request,
        code: str | None = Query(default=None, max_length=4096),
        state: str | None = Query(default=None, max_length=256),
        error: str | None = Query(default=None, max_length=128),
        state_cookie: str | None = Cookie(default=None, alias="portal_oauth_state"),
    ):
        if error or not code or not state or not state_cookie or not hmac.compare_digest(state, state_cookie):
            raise HTTPException(status_code=400, detail="Sign-in could not be verified; start again")
        transaction = repo.consume_oauth_transaction(state)
        if not transaction:
            raise HTTPException(status_code=400, detail="Sign-in expired or was already used; start again")
        try:
            if service.identity is None:
                raise HTTPException(status_code=503, detail="Hack Club Auth is not configured on this server")
            token = await service.identity.exchange_code(code)
            jwks = await service.identity.signing_keys()
            try:
                identity = service.identity.validate_id_token(token, expected_nonce=transaction["nonce"], jwks=jwks)
            except ValueError:
                # A signing-key rotation can make a cached JWKS stale; refresh once only.
                fresh_jwks = await service.identity.signing_keys(force_refresh=True)
                identity = service.identity.validate_id_token(token, expected_nonce=transaction["nonce"], jwks=fresh_jwks)
            existing = repo.get_user_by_subject(identity.subject)
            if existing or transaction["invite_id"]:
                user = repo.provision_identity(subject=identity.subject, email=identity.email, email_verified=identity.email_verified, name=identity.name, invite_id=transaction["invite_id"])
            else:
                user = repo.bootstrap_operator(verified_subject=identity.subject, verified_email=identity.email, email_verified=identity.email_verified, configured_email=service.bootstrap_operator_email, name=identity.name)
            if user["role"] == "operator" and service.legacy_database:
                repo.import_legacy_key_snapshots(user["id"], service.legacy_database.list_keys())
                repo.import_legacy_usage(user["id"], service.legacy_database.export_usage_history())
            session = repo.create_session(user["id"], ttl_seconds=service.session_ttl_seconds)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (ValueError, httpx.HTTPError, KeyError) as exc:
            raise HTTPException(status_code=400, detail="Hack Club sign-in could not be validated") from exc

        response = RedirectResponse("/", status_code=303)
        response.delete_cookie("portal_oauth_state", path="/auth/callback", secure=service.cookie_secure, httponly=True, samesite="lax")
        response.set_cookie("portal_session", session.raw_token, max_age=service.session_ttl_seconds, httponly=True, secure=service.cookie_secure, samesite="lax", path="/")
        response.set_cookie("portal_csrf", session.csrf_token, max_age=service.session_ttl_seconds, httponly=False, secure=service.cookie_secure, samesite="lax", path="/")
        return response

    @router.post("/auth/logout", status_code=204)
    async def logout(
        request: Request,
        session=Depends(current_session),
        portal_session: str | None = Cookie(default=None),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_same_origin(request)
        require_csrf(session, csrf_cookie, csrf_header)
        if portal_session:
            repo.revoke_session(portal_session)
        response = Response(status_code=204)
        response.delete_cookie("portal_session", path="/", secure=service.cookie_secure, httponly=True, samesite="lax")
        response.delete_cookie("portal_csrf", path="/", secure=service.cookie_secure, httponly=False, samesite="lax")
        return response

    @router.get("/api/session")
    async def get_session(session=Depends(current_session), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf")):
        user, csrf_hash = session
        if not csrf_cookie or not repo.verify_csrf(csrf_hash, csrf_cookie):
            raise HTTPException(status_code=401, detail="Session is invalid")
        return {"user": _public_user(user), "role": user["role"], "csrfToken": csrf_cookie}

    # Compatibility for early portal prototypes; new clients should use /api/session.
    @router.get("/api/me", include_in_schema=False)
    async def get_me(session=Depends(current_session), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf")):
        return await get_session(session, csrf_cookie)

    @router.get("/api/models")
    async def list_models(_session=Depends(current_session)):
        return [_api_model(item, public_id=True) for item in repo.list_models(approved_only=True)]

    @router.get("/api/developer/keys")
    @router.get("/api/keys", include_in_schema=False)
    async def list_keys(session=Depends(developer)):
        user, _csrf_hash = session
        return [_key_record(item) for item in repo.list_user_keys(user["id"])]

    @router.post("/api/developer/keys", status_code=201)
    @router.post("/api/keys", status_code=201, include_in_schema=False)
    async def create_key(
        request: Request,
        session=Depends(developer),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        user, _csrf_hash = session
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Invalid key request")
        label = data.get("label")
        access = data.get("modelAccess", {"mode": "all_approved"})
        if not isinstance(label, str) or not isinstance(access, dict):
            raise HTTPException(status_code=422, detail="A key label and model policy are required")
        mode = access.get("mode")
        models = access.get("modelIds", []) if mode == "selected" else []
        if mode not in {"all_approved", "selected"} or not isinstance(models, list) or any(not isinstance(model, str) for model in models):
            raise HTTPException(status_code=422, detail="Invalid model access policy")
        spend_cap = data.get("spendCapUsd")
        period = {"day": "daily", "week": "weekly", "month": "monthly", "lifetime": "lifetime", None: None}.get(data.get("spendPeriod"), "invalid")
        rpm = data.get("rpmLimit")
        try:
            key = repo.create_user_key(user["id"], label, allowed_models_mode=mode, allowed_models=models, spend_limit_usd=spend_cap, spend_period=period, rpm_limit=rpm)
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repo.audit(user["id"], "key.created", "key", key["id"], {"label": key["label"], "model_mode": mode})
        return {"key": _key_record(key), "secret": key["api_key"]}

    @router.get("/api/keys/{key_id}")
    async def get_key(key_id: str, session=Depends(developer)):
        user, _csrf_hash = session
        key = repo.get_user_key(user["id"], key_id)
        if not key:
            raise HTTPException(status_code=404, detail="Key not found")
        return _key_record(key)

    @router.post("/api/developer/keys/{key_id}/revoke", status_code=204)
    @router.post("/api/keys/{key_id}/revoke", status_code=204, include_in_schema=False)
    async def revoke_key(
        key_id: str,
        session=Depends(developer),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        user, _csrf_hash = session
        if not repo.revoke_user_key(user["id"], key_id):
            raise HTTPException(status_code=404, detail="Key not found")
        repo.audit(user["id"], "key.revoked", "key", key_id)
        return Response(status_code=204)

    @router.post("/api/developer/keys/{key_id}/archive", status_code=204)
    @router.post("/api/keys/{key_id}/archive", status_code=204, include_in_schema=False)
    async def archive_key(
        key_id: str,
        session=Depends(developer),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        user, _csrf_hash = session
        if not repo.archive_user_key(user["id"], key_id):
            raise HTTPException(status_code=404, detail="Key not found")
        repo.audit(user["id"], "key.archived", "key", key_id)
        return Response(status_code=204)

    @router.patch("/api/developer/keys/{key_id}")
    async def update_key(
        key_id: str,
        request: Request,
        session=Depends(developer),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        user, _csrf_hash = session
        data = await request.json()
        access = data.get("modelAccess", {"mode": "all_approved"})
        if not isinstance(access, dict):
            raise HTTPException(status_code=422, detail="Invalid model policy")
        mode = access.get("mode")
        models = access.get("modelIds", []) if mode == "selected" else []
        period = {"day": "daily", "week": "weekly", "month": "monthly", "lifetime": "lifetime", None: None}.get(data.get("spendPeriod"), "invalid")
        try:
            updated = repo.update_user_key_policy(
                user["id"], key_id,
                allowed_models_mode=mode,
                allowed_models=models,
                spend_limit_usd=data.get("spendCapUsd"),
                spend_period=period,
                rpm_limit=data.get("rpmLimit"),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="Key not found")
        repo.audit(user["id"], "key.policy_updated", "key", key_id, {"model_mode": mode, "spend_cap_usd": data.get("spendCapUsd"), "spend_period": data.get("spendPeriod"), "rpm_limit": data.get("rpmLimit")})
        return _key_record(repo.get_user_key(user["id"], key_id))

    @router.get("/api/activity")
    async def list_activity(
        session=Depends(developer),
        cursor: str | None = Query(default=None, max_length=100),
        limit: int = Query(default=50, ge=1, le=200),
        key_id: str | None = Query(default=None, max_length=64),
    ):
        user, _csrf_hash = session
        # Cursor is the opaque last-seen timestamp; scope is always the signed-in owner.
        rows = repo.list_usage(user["id"], limit=limit + 1, before=cursor, key_id=key_id)
        has_more = len(rows) > limit
        items = rows[:limit]
        return {"items": [_activity_record(item) for item in items], "nextCursor": items[-1]["occurred_at"] if has_more and items else None}

    def _dashboard_usage(owner_id: str | None) -> dict[str, Any]:
        if owner_id:
            raw = repo.user_usage_summary(owner_id)
            user = repo.get_user(owner_id)
        else:
            raw = repo.operator_usage_summary()
            user = None
        requests = int(raw["request_count"] or 0)
        known_cost = raw["estimated_cost_usd"]
        latency = repo.latency_percentile(owner_id)
        return {
            "requests": requests,
            "successfulRequests": raw["successful_requests"] or 0,
            "rejectedRequests": raw["rejected_requests"] or 0,
            "inputTokens": raw["input_tokens"], "outputTokens": raw["output_tokens"], "totalTokens": raw["total_tokens"],
            "estimatedSpendUsd": known_cost, "allowanceUsedUsd": repo.user_period_spend(owner_id, user["allowance_period"]) if user else None,
            "allowanceLimitUsd": user["allowance_usd"] if user else None,
            "p95LatencyMs": latency["p95"], "sampleCount": latency["sample_count"], "period": "all time", "source": "gateway_estimate" if known_cost is not None else "mixed",
        }

    @router.get("/api/developer/dashboard")
    async def developer_dashboard(session=Depends(developer)):
        user, _csrf_hash = session
        keys = repo.list_user_keys(user["id"])
        activity = repo.list_usage(user["id"], limit=8)
        summary = _dashboard_usage(user["id"])
        return {
            "usage": summary if summary["requests"] else None,
            "series": repo.usage_timeseries(user["id"], days=14),
            "topModels": [_model_usage_record(item) for item in repo.usage_by_model(user["id"], limit=8)],
            "keys": [_key_record(item) for item in keys],
            "recentActivity": [_activity_record(item) for item in activity],
            "allowance": {"usedUsd": summary["allowanceUsedUsd"], "limitUsd": summary["allowanceLimitUsd"], "period": user["allowance_period"], "resetAt": repo.period_reset_at(user["allowance_period"])},
        }

    @router.get("/api/operator/dashboard")
    async def operator_dashboard(session=Depends(operator)):
        activity = repo.list_all_usage(limit=8)
        return {
            "usage": _dashboard_usage(None),
            "series": repo.usage_timeseries(days=14),
            "topModels": [_model_usage_record(item) for item in repo.usage_by_model(limit=8)],
            "providers": repo.list_providers(),
            "recentActivity": [_activity_record(item, operator=True) for item in activity],
            "guardrails": {"globalSpendCapUsd": None, "globalSpendUsedUsd": None, "safetyReserveUsd": None, "globalStopped": False, "blockedIps": [], "recentAudit": []},
        }

    @router.get("/api/operator/people")
    async def list_people(session=Depends(operator)):
        return repo.list_people()

    @router.patch("/api/operator/people/{user_id}/policy")
    async def update_person_policy(
        user_id: str,
        request: Request,
        session=Depends(operator),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        user = repo.get_user(user_id)
        if not user or user["role"] != "developer":
            raise HTTPException(status_code=404, detail="Developer not found")
        data = await request.json()
        try:
            repo.set_user_policy(user_id, allowance_usd=data.get("allowanceUsd"), allowance_period={"day": "daily", "week": "weekly", None: None}.get(data.get("allowancePeriod"), "invalid"), rpm_limit=data.get("rpmLimit"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repo.audit(actor["id"], "person.policy_updated", "user", user_id, {"allowance_usd": data.get("allowanceUsd"), "allowance_period": data.get("allowancePeriod"), "rpm_limit": data.get("rpmLimit")})
        return {"ok": True}

    @router.post("/api/operator/people/{user_id}/disable", status_code=204)
    async def disable_person(user_id: str, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        if not repo.set_user_state(user_id, active=False):
            raise HTTPException(status_code=404, detail="Developer not found")
        repo.audit(actor["id"], "person.disabled", "user", user_id)
        return Response(status_code=204)

    @router.post("/api/operator/people/{user_id}/enable", status_code=204)
    async def enable_person(user_id: str, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        if not repo.set_user_state(user_id, active=True):
            raise HTTPException(status_code=404, detail="Developer not found")
        repo.audit(actor["id"], "person.enabled", "user", user_id)
        return Response(status_code=204)

    @router.get("/api/operator/providers")
    async def list_providers(_session=Depends(operator)):
        records = {item["id"]: item for item in repo.list_providers()}
        if service.legacy_database:
            for upstream in service.legacy_database.list_upstreams():
                provider = records.get(upstream["id"], {
                    "id": upstream["id"], "name": upstream["name"], "enabled": upstream["enabled"],
                    "health": upstream["health_status"], "lastSyncAt": upstream["last_checked_at"],
                    "discoveredModels": len(upstream["models"]), "approvedModels": 0,
                })
                provider["baseUrlDisplay"] = upstream["base_url"]
                provider["enabled"] = bool(upstream["enabled"])
                provider["health"] = upstream["health_status"] if upstream["health_status"] in {"healthy", "degraded", "disabled"} else "unknown"
                provider["lastSyncAt"] = upstream["last_checked_at"]
                provider["discoveredModels"] = max(provider["discoveredModels"], len(upstream["models"]))
                records[upstream["id"]] = provider
        return list(records.values())

    @router.get("/api/operator/models")
    async def list_operator_models(_session=Depends(operator)):
        return [_api_model(item) for item in repo.list_models(approved_only=False, include_inactive=True)]

    @router.get("/api/operator/offers")
    async def list_operator_offers(_session=Depends(operator)):
        return repo.list_operator_offers()

    @router.patch("/api/operator/offers/{offer_id}/price", status_code=201)
    async def suggest_offer_price(offer_id: str, request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        data = await request.json()
        try:
            for field in ("inputUsdPerMillion", "outputUsdPerMillion", "cachedInputUsdPerMillion"):
                value = data.get(field)
                if value is not None:
                    if not isinstance(value, str):
                        raise ValueError("Prices must be decimal strings in USD per million")
                    repo._canonical_rate(value)
            evidence = str(data.get("source", "")).strip()
            if not evidence or len(evidence) > 240:
                raise ValueError("A price source or evidence reference is required")
            suggestion = PriceSuggestion(
                input_usd_per_million=data.get("inputUsdPerMillion"),
                output_usd_per_million=data.get("outputUsdPerMillion"),
                cached_input_usd_per_million=data.get("cachedInputUsdPerMillion"),
                source="manual", evidence=evidence,
            )
            pending = repo.save_price_suggestion(offer_id, suggestion)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Offer not found") from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repo.audit(actor["id"], "offer.price_suggested", "offer", offer_id, {"suggestion_id": pending.id, "source": "manual"})
        return {"id": pending.id, "offerId": offer_id, "status": "pending"}

    @router.post("/api/operator/offers/{offer_id}/prices/{version_id}/approve", status_code=204)
    async def approve_offer_price(offer_id: str, version_id: str, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        try:
            repo.approve_price_version(actor["id"], offer_id, version_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Pending price version not found") from exc
        return Response(status_code=204)

    @router.patch("/api/operator/offers/{offer_id}/availability")
    async def update_offer_availability(offer_id: str, request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        data = await request.json()
        if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):
            raise HTTPException(status_code=422, detail="Offer enabled must be boolean")
        try:
            repo.set_offer_available(offer_id, data["enabled"], actor["id"])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Offer not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "enabled": data["enabled"]}

    @router.patch("/api/operator/offers/{offer_id}/routes")
    async def update_offer_routes(offer_id: str, request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        data = await request.json()
        if not isinstance(data, dict) or not isinstance(data.get("connectionIds"), list):
            raise HTTPException(status_code=422, detail="connectionIds must be an ordered array")
        try:
            repo.set_offer_route_order(offer_id, data["connectionIds"], actor["id"])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Offer not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "routes": data["connectionIds"]}

    @router.patch("/api/operator/routes/{route_id}/availability")
    async def update_route_availability(route_id: str, request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        data = await request.json()
        if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):
            raise HTTPException(status_code=422, detail="Route enabled must be boolean")
        try:
            repo.set_route_available(route_id, data["enabled"], actor["id"])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Route not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "enabled": data["enabled"]}

    @router.patch("/api/operator/connections/{connection_id}/models/mapping")
    async def map_discovered_model(connection_id: str, request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        data = await request.json()
        if not isinstance(data, dict) or not isinstance(data.get("upstreamModelId"), str) or not isinstance(data.get("offerId"), str):
            raise HTTPException(status_code=422, detail="upstreamModelId and offerId are required strings")
        try:
            repo.map_connection_model(connection_id, data["upstreamModelId"], data["offerId"], actor["id"])
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "connectionId": connection_id, "upstreamModelId": data["upstreamModelId"],
                "offerId": data["offerId"], "mappingSource": "manual"}

    @router.post("/api/operator/providers", status_code=201)
    async def create_provider(request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        if not service.legacy_database:
            raise HTTPException(status_code=503, detail="Provider storage is unavailable")
        actor, _csrf_hash = session
        data = await request.json()
        name = str(data.get("name", data.get("providerName", ""))).strip()
        api_key = str(data.get("apiKey", "")).strip()
        brand_slug = str(data.get("brandSlug", "")).strip().lower()
        if not brand_slug:
            brand_slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        connection_label = str(data.get("connectionLabel", "")).strip() or name
        try:
            base_url = _public_https_base_url(str(data.get("baseUrl", "")))
            if not name or len(name) > 80 or not api_key:
                raise ValueError("Provider name and API key are required")
            profile = service.legacy_database.create_upstream(name, "openai_compatible", base_url, api_key)
            try:
                registered = repo.register_connection(profile["id"], brand_slug, name, connection_label)
            except Exception:
                service.legacy_database.set_upstream_state(profile["id"], False)
                raise
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=409, detail="Provider metadata could not be registered; the encrypted profile was disabled.") from exc
        repo.audit(actor["id"], "provider.created", "provider", registered.id,
                   {"name": name, "base_url": base_url, "brand_slug": brand_slug})
        synced = await sync_connection(registered.id, profile["id"], actor["id"])
        return {"id": registered.id, "name": name, "provider_kind": "openai_compatible", "base_url": base_url,
                "enabled": registered.enabled, "secret_configured": True,
                "brandSlug": brand_slug, "connectionLabel": connection_label, "models": synced["models"]}

    @router.post("/api/operator/providers/{provider_id}/sync")
    async def sync_provider(provider_id: str, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        if not service.legacy_database or not service.settings:
            raise HTTPException(status_code=503, detail="Provider storage is unavailable")
        actor, _csrf_hash = session
        connection = repo.get_connection(provider_id)
        if not connection:
            raise HTTPException(status_code=404, detail="Provider connection not found")
        upstream = service.legacy_database.get_upstream(connection["legacy_profile_id"])
        if not upstream or not upstream["enabled"]:
            raise HTTPException(status_code=404, detail="Provider not found or disabled")
        return await sync_connection(connection["id"], connection["legacy_profile_id"], actor["id"])

    @router.put("/api/operator/providers/{provider_id}/models/{model_id:path}")
    async def set_model_policy(provider_id: str, model_id: str, request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        if not service.legacy_database:
            raise HTTPException(status_code=503, detail="Provider storage is unavailable")
        actor, _csrf_hash = session
        upstream = service.legacy_database.get_upstream(provider_id)
        if not upstream or model_id not in upstream["models"]:
            raise HTTPException(status_code=404, detail="Discovered model not found")
        data = await request.json()
        try:
            if isinstance(data.get("inputUsdPerMillion"), bool) or isinstance(data.get("outputUsdPerMillion"), bool) or isinstance(data.get("cacheUsdPerMillion"), bool):
                raise ValueError("Prices must be numeric")
            input_price = float(data["inputUsdPerMillion"])
            output_price = float(data["outputUsdPerMillion"])
            cache_price = float(data["cacheUsdPerMillion"]) if data.get("cacheUsdPerMillion") is not None else None
            price_source = str(data.get("priceSource", "")).strip()
            capabilities = data.get("capabilities", [])
            if not isinstance(capabilities, list) or any(value not in {"text", "vision"} for value in capabilities):
                raise ValueError("Capabilities must be text and/or vision")
            approved = bool(data.get("approved", False))
            if not math.isfinite(input_price) or not math.isfinite(output_price) or input_price < 0 or output_price < 0 or (cache_price is not None and (not math.isfinite(cache_price) or cache_price < 0)):
                raise ValueError("Prices must be finite and non-negative")
            if approved and not price_source:
                raise ValueError("Record a source for verified pricing before approving the model")
            if approved and "text" not in capabilities:
                raise ValueError("Models must support text chat to be approved by this gateway")
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Valid input/output prices and a price source are required.") from exc
        repo.add_catalog_model(provider_id=provider_id, model_id=model_id, provider_name=upstream["name"], capabilities=capabilities, input_price_per_million=input_price, output_price_per_million=output_price, cached_input_price_per_million=cache_price, price_source=price_source or None, approved=approved)
        service.legacy_database.update_upstream_pricing(provider_id, {model_id: {"input": input_price, "output": output_price, "cache": cache_price, "source": price_source or None}})
        repo.audit(actor["id"], "model.policy_updated", "model", model_id, {"provider_id": provider_id, "approved": approved, "input_usd_per_million": input_price, "output_usd_per_million": output_price, "price_source": price_source})
        model = next((item for item in repo.list_models(approved_only=False) if item["provider_id"] == provider_id and item["model_id"] == model_id), None)
        return {"ok": True, "model": _api_model(model) if model else None}

    @router.get("/api/operator/guardrails")
    async def get_guardrails(_session=Depends(operator)):
        if not service.legacy_database or not service.settings:
            raise HTTPException(status_code=503, detail="Guardrail configuration is unavailable")
        legacy_used = service.legacy_database.usage_summary()["totals"]["estimated_cost_usd"] or 0
        portal_used = repo.gateway_usage_summary()["estimated_cost_usd"] or 0
        used = legacy_used + portal_used
        limit = repo.get_runtime_setting("global_spend_cap_usd", service.settings.provider_hard_stop_usd)
        reserve = repo.get_runtime_setting("safety_reserve_usd", service.settings.provider_estimate_reserve_usd)
        stopped = bool(repo.get_runtime_setting("global_stopped", False) or service.settings.emergency_stop or used >= limit)
        blocked = [{"ip": item["ip"], "reason": item["reason"], "createdAt": item["created_at"]} for item in service.legacy_database.list_blocked_ips()]
        return {"globalSpendCapUsd": limit, "globalSpendUsedUsd": used, "safetyReserveUsd": reserve, "globalStopped": stopped, "blockedIps": blocked, "recentAudit": repo.list_audit_events(limit=20)}

    @router.patch("/api/operator/guardrails")
    async def update_guardrails(request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        if not service.settings:
            raise HTTPException(status_code=503, detail="Guardrail configuration is unavailable")
        actor, _csrf_hash = session
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="Invalid guardrail update")
        updates = {}
        for field, key in (("globalSpendCapUsd", "global_spend_cap_usd"), ("safetyReserveUsd", "safety_reserve_usd")):
            if field in data:
                if isinstance(data[field], bool):
                    raise HTTPException(status_code=422, detail=f"{field} must be numeric")
                try:
                    value = float(data[field])
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=422, detail=f"{field} must be numeric") from exc
                if value < 0 or not math.isfinite(value):
                    raise HTTPException(status_code=422, detail=f"{field} must be finite and non-negative")
                updates[key] = value
        if "globalStopped" in data:
            if not isinstance(data["globalStopped"], bool):
                raise HTTPException(status_code=422, detail="globalStopped must be boolean")
            updates["global_stopped"] = data["globalStopped"]
        for key, value in updates.items():
            repo.set_runtime_setting(key, value)
        if updates:
            repo.audit(actor["id"], "guardrails.updated", "global", None, updates)
        return {"ok": True, "guardrails": await get_guardrails(session)}

    @router.post("/api/operator/blocked-ips", status_code=201)
    async def block_client_ip(request: Request, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        if not service.legacy_database:
            raise HTTPException(status_code=503, detail="IP block storage is unavailable")
        actor, _csrf_hash = session
        data = await request.json()
        ip = str(data.get("ip", "")).strip()
        reason = str(data.get("reason", "operator block")).strip() or "operator block"
        try:
            ipaddress.ip_address(ip)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Enter a valid IPv4 or IPv6 address") from exc
        service.legacy_database.block_ip(ip, reason)
        repo.audit(actor["id"], "ip.blocked", "ip", ip, {"reason": reason})
        return {"ok": True}

    @router.delete("/api/operator/blocked-ips/{ip}", status_code=204)
    async def unblock_client_ip(ip: str, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        if not service.legacy_database:
            raise HTTPException(status_code=503, detail="IP block storage is unavailable")
        actor, _csrf_hash = session
        try:
            ipaddress.ip_address(ip)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid IP address") from exc
        service.legacy_database.unblock_ip(ip)
        repo.audit(actor["id"], "ip.unblocked", "ip", ip)
        return Response(status_code=204)

    @router.post("/api/operator/models/{model_id:path}/block", status_code=204)
    async def block_catalog_model(model_id: str, session=Depends(operator), csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"), csrf_header: str | None = Header(default=None, alias="X-CSRF-Token")):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        changed = repo.set_model_active(model_id, active=False)
        if not changed:
            raise HTTPException(status_code=404, detail="Model not found")
        repo.audit(actor["id"], "model.blocked", "model", model_id)
        return Response(status_code=204)

    @router.get("/api/operator/invites")
    async def list_invites(_session=Depends(operator)):
        now = datetime.now(timezone.utc).isoformat()
        rows = repo.list_invites()
        for invite in rows:
            invite["status"] = (
                "revoked" if invite["revoked_at"] else
                "exhausted" if invite["uses_count"] >= invite["max_uses"] else
                "expired" if invite["expires_at"] <= now else "active"
            )
            invite["email_bound"] = invite["bound_email"] is not None
        return rows

    @router.get("/api/developer/invites")
    async def developer_invite_status(session=Depends(developer)):
        user, _csrf_hash = session
        return repo.developer_invite_status(user["id"])

    @router.post("/api/operator/invites", status_code=201)
    async def create_invite(
        request: Request,
        session=Depends(operator),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        user, _csrf_hash = session
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid invite request")
            invite, token = repo.create_invite(issuer_user_id=user["id"], expires_in_seconds=data.get("expires_in_seconds", 7 * 24 * 60 * 60), bound_email=data.get("bound_email"), max_uses=data.get("max_uses", 5))
        except (ValueError, PermissionError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repo.audit(user["id"], "invite.created", "invite", invite["id"], {"bound_email": invite["bound_email"], "expires_at": invite["expires_at"]})
        return {"invite": invite, "invite_token": token}

    @router.post("/api/developer/invites", status_code=201)
    async def create_developer_invite(
        request: Request,
        session=Depends(developer),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        user, _csrf_hash = session
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid invite request")
            invite, token = repo.create_developer_invite(
                issuer_user_id=user["id"], expires_in_seconds=data.get("expires_in_seconds", 7 * 24 * 60 * 60)
            )
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail="Developer invite entitlement is unavailable or already used") from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repo.audit(user["id"], "invite.created", "invite", invite["id"], {"expires_at": invite["expires_at"], "max_uses": 1})
        return {"invite": invite, "invite_token": token}

    @router.post("/api/operator/invites/{invite_id}/revoke")
    async def revoke_invite(
        invite_id: str,
        session=Depends(operator),
        csrf_cookie: str | None = Cookie(default=None, alias="portal_csrf"),
        csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
    ):
        require_csrf(session, csrf_cookie, csrf_header)
        actor, _csrf_hash = session
        if not repo.revoke_invite(invite_id, revoked_by_user_id=actor["id"]):
            raise HTTPException(status_code=404, detail="Invite not found or already revoked")
        repo.audit(actor["id"], "invite.revoked", "invite", invite_id)
        invite = next((item for item in repo.list_invites() if item["id"] == invite_id), None)
        if not invite:
            raise HTTPException(status_code=404, detail="Invite not found")
        return {
            "id": invite["id"], "uses_count": invite["uses_count"], "max_uses": invite["max_uses"],
            "expires_at": invite["expires_at"], "revoked_at": invite["revoked_at"], "status": "revoked",
        }

    @router.get("/api/operator/usage")
    async def operator_usage(
        session=Depends(operator),
        cursor: str | None = Query(default=None, max_length=100),
        limit: int = Query(default=50, ge=1, le=200),
    ):
        rows = repo.list_all_usage(limit=limit + 1, before=cursor)
        has_more = len(rows) > limit
        page = rows[:limit]
        return {"items": [_activity_record(item, operator=True) for item in page], "nextCursor": page[-1]["occurred_at"] if has_more and page else None}

    return router
