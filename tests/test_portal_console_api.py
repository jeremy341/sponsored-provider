import hashlib
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import lifespan
from app.portal_db import PortalDatabase

ORIGIN = {"Origin": "https://portal.example"}


def _settings(tmp_path, **overrides):
    return Settings(
        database_path=str(tmp_path / f"console-{uuid4().hex}.db"),
        provider_key_pepper="p" * 40,
        provider_secret_key=Fernet.generate_key().decode(),
        portal_demo_mode=True,
        portal_public_origin="https://portal.example",
        _env_file=None,
        **overrides,
    )


def _console_client(settings):
    """Fresh app per test: the portal router binds routes to this test's service.

    Routes that live on the main app (health, playground) use the singleton via
    _main_client instead.
    """
    from contextlib import contextmanager

    from app.main import security_headers_middleware
    from app.portal_api import PortalService, create_portal_router

    @contextmanager
    def factory():
        repository = _portal(settings)
        service = PortalService(repository, identity=None, cookie_secure=True, public_origin="https://portal.example")
        local_app = FastAPI()
        local_app.include_router(create_portal_router(service))
        local_app.middleware("http")(security_headers_middleware)
        with TestClient(local_app, base_url="https://portal.example") as client:
            yield client
        local_app.state.portal_service = None

    return factory()


def _main_client(settings):
    from contextlib import contextmanager

    @contextmanager
    def factory():
        from app.main import app

        app.dependency_overrides[get_settings] = lambda: settings
        with TestClient(app, base_url="https://portal.example") as client:
            yield client
        app.dependency_overrides.clear()

    return factory()


def _session_cookies(repo, user, role="developer"):
    if role != user["role"]:
        repo.set_user_role(user["id"], role) if hasattr(repo, "set_user_role") else None
    session = repo.create_session(user["id"])
    return {"portal_session": session.raw_token, "portal_csrf": session.csrf_token}, session


def _portal(settings):
    pepper = hashlib.sha256(("sponsored-provider:portal:v1:" + settings.provider_key_pepper).encode()).hexdigest()
    return PortalDatabase(settings.database_path, key_pepper=pepper)


def _seed_event(repo, owner_id, key_id, *, request_id, provider="Acme AI", status="success", latency=100):
    repo.record_usage(
        owner_id, key_id, model="test-provider::raw-model", input_tokens=10, output_tokens=5, total_tokens=15,
        latency_ms=latency, status=status, estimated_cost_usd=0.0001, provider_name=provider, request_id=request_id,
    )


def test_health_live_and_ready(tmp_path):
    with _main_client(_settings(tmp_path)) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code in {200, 503}
        if ready.status_code == 503:
            assert ready.json()["reason"] in {"database_unavailable", "portal_frontend_not_built"}


def test_operator_system_reports_real_facts(tmp_path):
    settings = _settings(tmp_path)
    repo = _portal(settings)
    operator = repo.upsert_user(subject="sys-op", email="s@example.test", name="Sys", role="operator")
    cookies, _session = _session_cookies(repo, operator)
    with _console_client(settings) as client:
        client.cookies.update(cookies)
        response = client.get("/api/operator/system", headers=ORIGIN)
    assert response.status_code == 200
    body = response.json()
    assert body["database"]["engine"] == "sqlite"
    assert isinstance(body["database"]["tableCount"], int) and body["database"]["tableCount"] > 0
    assert isinstance(body["uptimeSeconds"], int)
    assert body["inference"]["stopped"] is False
    assert body["jobs"]["backupStatus"] == "not_configured"
    assert "secret" not in response.text.lower().replace("secret values", "")


def test_provider_health_summary_computes_percentiles(tmp_path):
    settings = _settings(tmp_path)
    repo = _portal(settings)
    user = repo.upsert_user(subject="health-user", email="h@example.test", name="Health")
    key = repo.create_user_key(user["id"], "health key", allowed_models_mode="all_approved")
    _seed_event(repo, user["id"], key["id"], request_id="req-1", status="success", latency=100)
    _seed_event(repo, user["id"], key["id"], request_id="req-2", status="success", latency=200)
    _seed_event(repo, user["id"], key["id"], request_id="req-3", status="failed", latency=900)

    summary = {item["provider"]: item for item in repo.provider_health_summary(since_iso="2000-01-01", min_samples=3)}
    acme = summary["Acme AI"]
    assert acme["sampleSize"] == 3
    assert acme["successRate"] == round(2 / 3, 4)
    assert acme["health"] == "unhealthy"
    assert acme["p50LatencyMs"] == 200 and acme["p95LatencyMs"] == 900
    assert acme["lastActivityAt"] is not None


def test_provider_health_marks_low_traffic_unknown(tmp_path):
    settings = _settings(tmp_path)
    repo = _portal(settings)
    user = repo.upsert_user(subject="low-user", email="l@example.test", name="Low")
    key = repo.create_user_key(user["id"], "low key", allowed_models_mode="all_approved")
    _seed_event(repo, user["id"], key["id"], request_id="req-1", status="success", latency=50)
    summary = repo.provider_health_summary(since_iso="2000-01-01")
    assert summary[0]["health"] == "unknown"
    assert summary[0]["sampleSize"] == 1


def test_developer_providers_endpoint_merges_catalog_and_measured_health(tmp_path):
    from tests.test_portal_gateway import _ready_offer_gateway

    settings, repo, user, issued, _public_model_id, _offer_id, _connections, _price = _ready_offer_gateway(tmp_path)
    for index in range(6):
        _seed_event(repo, user["id"], issued["id"], request_id=f"req-{index}", provider="Test Provider", latency=120)

    cookies, _session = _session_cookies(repo, user)
    with _console_client(settings) as client:
        client.cookies.update(cookies)
        response = client.get("/api/developer/providers", headers=ORIGIN)
    assert response.status_code == 200
    providers = {item["provider"]: item for item in response.json()["providers"]}
    assert providers["Test Provider"]["models"] == 1
    assert providers["Test Provider"]["health"] == "healthy"
    assert providers["Test Provider"]["sampleSize"] == 6
    assert providers["Test Provider"]["successRate"] == 1.0


def test_developer_request_detail_is_owner_scoped_and_metadata_only(tmp_path):
    settings = _settings(tmp_path)
    repo = _portal(settings)
    owner = repo.upsert_user(subject="detail-owner", email="d@example.test", name="Detail")
    other = repo.upsert_user(subject="detail-other", email="o@example.test", name="Other", role="developer")
    key = repo.create_user_key(owner["id"], "k", allowed_models_mode="all_approved")
    _seed_event(repo, owner["id"], key["id"], request_id="req-own")
    _seed_event(repo, other["id"], repo.create_user_key(other["id"], "k2", allowed_models_mode="all_approved")["id"],
                request_id="req-other")

    cookies, _session = _session_cookies(repo, owner)
    with _console_client(settings) as client:
        client.cookies.update(cookies)
        own = client.get("/api/developer/requests/req-own", headers=ORIGIN)
        missing = client.get("/api/developer/requests/req-other", headers=ORIGIN)
    assert own.status_code == 200
    assert own.json()["requestId"] == "req-own"
    assert own.json()["stream"] is False
    assert "origin" in own.json()
    assert missing.status_code == 404


def test_playground_runs_the_real_pipeline_and_records_telemetry(tmp_path):
    import respx
    import httpx
    from tests.test_portal_gateway import _ready_offer_gateway

    settings, portal, user, issued, public_model_id, _offer_id, _connections, _price = _ready_offer_gateway(
        tmp_path, upstream_models=("raw-model",), user_allowance=5
    )
    key_id = issued["id"]
    assert portal.gateway_key_by_id(key_id, owner_user_id=user["id"]) is not None
    session = portal.create_session(user["id"])

    from app.main import app
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app, base_url="https://portal.example") as client:
            client.cookies.update({"portal_session": session.raw_token, "portal_csrf": session.csrf_token})
            with respx.mock:
                respx.post("https://1.1.1.1/v1/chat/completions").mock(return_value=httpx.Response(200, json={
                    "id": "chat-1", "object": "chat.completion", "model": "raw-model",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Routed!"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
                }))
                response = client.post(
                    "/api/developer/playground",
                    json={"keyId": key_id, "payload": {"model": public_model_id, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 64}},
                    headers={**ORIGIN, "X-CSRF-Token": session.csrf_token},
                )
            assert response.status_code == 200, response.text
            assert response.json()["choices"][0]["message"]["content"] == "Routed!"
            assert response.json()["model"] == public_model_id

            events = portal.list_usage(user["id"], limit=5)
            assert events and events[0]["request_id"]
            stored = portal.get_usage_event_by_request_id(user["id"], events[0]["request_id"])
            assert stored is not None
            assert stored["provider_name_snapshot"] == "Test Provider"
    finally:
        app.dependency_overrides.clear()


def test_playground_rejects_other_users_keys_and_requires_csrf(tmp_path):
    from tests.test_portal_gateway import _ready_offer_gateway

    settings, portal, user, issued, public_model_id, _offer_id, _connections, _price = _ready_offer_gateway(tmp_path)
    outsider = portal.upsert_user(subject="outsider", email="out@example.test", name="Outsider")
    outsider_session = portal.create_session(outsider["id"])

    from app.main import app
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app, base_url="https://portal.example") as client:
            client.cookies.update({"portal_session": outsider_session.raw_token, "portal_csrf": outsider_session.csrf_token})
            stolen = client.post(
                "/api/developer/playground",
                json={"keyId": issued["id"], "payload": {"model": public_model_id, "messages": [{"role": "user", "content": "hi"}]}},
                headers={**ORIGIN, "X-CSRF-Token": outsider_session.csrf_token},
            )
            assert stolen.status_code == 403

            no_csrf = client.post(
                "/api/developer/playground",
                json={"keyId": issued["id"], "payload": {"model": public_model_id, "messages": [{"role": "user", "content": "hi"}]}},
                headers=ORIGIN,
            )
            assert no_csrf.status_code == 403
    finally:
        app.dependency_overrides.clear()
