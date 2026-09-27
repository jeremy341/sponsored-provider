import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.catalog import DiscoveredModel, PriceSuggestion
from app.database import Database
from app.main import app, get_portal_db
from app.portal_db import PortalDatabase


def _ready_offer_gateway(tmp_path, *, upstream_models=("raw-model",), priced=True, user_allowance=None):
    database_path = str(tmp_path / f"routed-gateway-{uuid4().hex}.db")
    settings = Settings(
        database_path=database_path,
        provider_key_pepper=f"routed-gateway-{uuid4().hex}",
        provider_secret_key=Fernet.generate_key().decode(),
        admin_token="admin-test-token",
        alibaba_api_key="configured-upstream-secret",
        alibaba_base_url="https://1.1.1.1/v1",
        allowed_models="",
        provider_hard_stop_usd=100,
        input_price_per_million=1,
        output_price_per_million=1,
    )
    portal_pepper = hashlib.sha256(("sponsored-provider:portal:v1:" + settings.provider_key_pepper).encode()).hexdigest()
    legacy = Database(database_path, settings.provider_key_pepper, settings.provider_secret_key)
    portal = PortalDatabase(database_path, key_pepper=portal_pepper)
    user = portal.upsert_user(subject="routed-member", email="routed@example.test", name="Routed member")

    connections = []
    for index, upstream_model_id in enumerate(upstream_models):
        base_url = f"https://{['1.1.1.1', '8.8.8.8'][index]}/v1"
        profile = legacy.create_upstream(
            f"Provider {index}", "openai_compatible", base_url, f"upstream-secret-{index}"
        )
        connection = portal.register_connection(
            profile["id"], "test-provider", "Test Provider", f"private-label-{index}"
        )
        portal.apply_discovery(connection.id, [DiscoveredModel(upstream_model_id)], datetime.now(timezone.utc))
        connections.append((connection, profile, upstream_model_id))

    offer_id = portal.get_discovered_offer_id(connections[0][0].id, connections[0][2])
    for connection, _profile, upstream_model_id in connections[1:]:
        portal.map_connection_model(connection.id, upstream_model_id, offer_id, "operator")

    if priced:
        suggestion = portal.save_price_suggestion(
            offer_id, PriceSuggestion(1, 2, None, "task7-test")
        )
        portal.approve_price_version("operator", offer_id, suggestion.id)
        portal.set_offer_route_order(offer_id, [item[0].id for item in connections], "operator")
        for route in portal.list_offer_routes(offer_id):
            portal.set_route_available(route.id, True, "operator")
        portal.set_offer_available(offer_id, True, "operator")

    issued = portal.create_user_key(user["id"], "Gateway regression key", allowed_models_mode="all_approved")
    key_snapshot = portal.find_gateway_key(issued["api_key"])
    public_model_id = next(
        (value for value in key_snapshot["effective_model_ids"] if value.endswith("::" + connections[0][2])),
        "test-provider::" + connections[0][2],
    )
    if user_allowance is not None:
        portal.set_user_policy(
            user["id"], allowance_usd=user_allowance, allowance_period="daily", rpm_limit=None
        )
    app.dependency_overrides[get_settings] = lambda: settings
    active_price = next(
        (item["activePrice"] for item in portal.list_operator_offers() if item["id"] == offer_id), None
    )
    return settings, portal, user, issued, public_model_id, offer_id, connections, active_price


def test_models_endpoint_returns_provider_scoped_offer_ids(tmp_path):
    """Portal model IDs are stable and scoped to their provider offer."""
    settings, _portal, _user, issued, public_model_id, _offer, _connections, _price = _ready_offer_gateway(
        tmp_path, upstream_models=("raw-model",)
    )
    assert public_model_id == "test-provider::raw-model"
    try:
        with TestClient(app) as client:
            response = client.get("/v1/models", headers={"Authorization": f"Bearer {issued['api_key']}"})
        assert response.status_code == 200
        assert [model["id"] for model in response.json()["data"]] == [public_model_id]
    finally:
        app.dependency_overrides.clear()


def test_models_endpoint_never_leaks_connection_credentials_or_labels(tmp_path):
    """Developer-facing models contain no connection details."""
    database_path = str(tmp_path / f"portal-models-private-{uuid4().hex}.db")
    settings = Settings(database_path=database_path, provider_key_pepper="private-models-test", provider_secret_key=Fernet.generate_key().decode(), admin_token="admin", alibaba_api_key="gateway-secret", allowed_models="")
    portal_pepper = hashlib.sha256(("sponsored-provider:portal:v1:" + settings.provider_key_pepper).encode()).hexdigest()
    legacy = Database(database_path, settings.provider_key_pepper, settings.provider_secret_key)
    profile = legacy.create_upstream("Provider A", "openai_compatible", "https://1.1.1.1/v1", "upstream-secret")
    portal = PortalDatabase(database_path, key_pepper=portal_pepper)
    user = portal.upsert_user(subject="private", email="private@example.test", name="Private")
    portal.add_catalog_model(provider_id=profile["id"], model_id="raw-model", provider_name="Provider A", capabilities=["text"], input_price_per_million=1, output_price_per_million=1, price_source="test", approved=True)
    connection = portal.register_connection(profile["id"], "upstream-secret", "Provider A", "private connection label")
    portal.apply_discovery(connection.id, [DiscoveredModel("raw-model")], datetime.now(timezone.utc))
    issued = portal.create_user_key(user["id"], "key", allowed_models_mode="all_approved")
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.get("/v1/models", headers={"Authorization": f"Bearer {issued['api_key']}"})
        assert response.status_code == 200
        for secret in ("upstream-secret", "gateway-secret", "private connection label", "https://1.1.1.1"):
            assert secret not in response.text
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_completion_maps_public_model_to_exact_upstream_id(tmp_path):
    _settings, _portal, _user, issued, public_model_id, _offer, _connections, _price = _ready_offer_gateway(
        tmp_path, upstream_models=("vendor/private-model-v3",)
    )
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(return_value=httpx.Response(
        200, json={"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}}
    ))
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8,
            })
        assert response.status_code == 200, response.text
        assert upstream.called
        assert json.loads(upstream.calls[0].request.content)["model"] == "vendor/private-model-v3"
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_disabled_or_unpriced_offer_is_rejected_before_upstream(tmp_path):
    for state in ("disabled", "unpriced"):
        state_path = tmp_path / state
        state_path.mkdir()
        _settings, portal, _user, issued, public_model_id, offer_id, _connections, _price = _ready_offer_gateway(state_path, priced=state != "unpriced")
        if state == "disabled":
            portal.set_offer_available(offer_id, False, "operator")
        upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(return_value=httpx.Response(200, json={"choices": []}))
        try:
            with TestClient(app) as client:
                response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                    "model": public_model_id, "messages": [{"role": "user", "content": "must not be sent"}], "max_tokens": 8,
                })
            assert response.status_code in (404, 503)
            assert not upstream.called
        finally:
            app.dependency_overrides.clear()


@respx.mock
def test_out_of_budget_rejection_is_logged_without_upstream_dispatch(tmp_path):
    _settings, portal, user, issued, public_model_id, _offer, _connections, _price = _ready_offer_gateway(
        tmp_path, user_allowance=0
    )
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(return_value=httpx.Response(200, json={"choices": []}))
    prompt = "PRIVATE_PROMPT_MUST_NOT_ENTER_USAGE_LEDGER"
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": 8,
            })
        assert response.status_code == 429
        assert not upstream.called
        events = portal.list_usage(user["id"])
        assert events and events[0]["status"] == "rejected"
        assert events[0]["error_category"] in {"budget_exhausted", "key_budget_exhausted"}
        assert events[0]["input_tokens"] is None and events[0]["total_tokens"] is None
        assert prompt not in json.dumps(events)
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_monthly_allowance_rejects_before_upstream_dispatch(tmp_path):
    _settings, portal, user, issued, public_model_id, _offer, _connections, _price = _ready_offer_gateway(tmp_path)
    portal.assign_user_allowance(user["id"], 0, "monthly", "operator")
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})
    )

    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "monthly cap"}], "max_tokens": 8,
            })
        assert response.status_code == 429
        assert not upstream.called
    finally:
        app.dependency_overrides.clear()


def test_monthly_allowance_reservations_are_shared_across_user_keys(tmp_path):
    _settings, portal, user, issued, _model, offer_id, connections, _price = _ready_offer_gateway(tmp_path)
    second_key = portal.create_user_key(user["id"], "Second monthly key", allowed_models_mode="all_approved")
    portal.assign_user_allowance(user["id"], 7_000_000_000, "monthly", "operator")
    now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
    connection_id = connections[0][0].id

    keys = [issued["id"], second_key["id"]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(
            lambda key_id: portal.reserve_request_budget(
                user["id"], key_id, offer_id, connection_id, 4_000_000_000, now, None
            ),
            keys,
        ))
    assert sum(reservation is not None for reservation in concurrent) == 1

    second = portal.reserve_request_budget(user["id"], second_key["id"], offer_id, connection_id, 2_999_999_999, now, None)
    blocked = portal.reserve_request_budget(user["id"], issued["id"], offer_id, connection_id, 1, now, None)

    assert second is not None
    assert blocked is None


@respx.mock
def test_connection_budget_rejects_before_upstream_dispatch(tmp_path):
    _settings, portal, _user, issued, public_model_id, _offer, connections, _price = _ready_offer_gateway(tmp_path)
    portal.set_connection_budget(connections[0][0].id, 1, "lifetime", 0, "operator")
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})
    )
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8,
            })
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "budget_exhausted"
        assert not upstream.called
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_same_brand_fallback_is_used_only_when_first_route_is_known_undelivered(tmp_path):
    _settings, portal, user, issued, public_model_id, _offer, connections, _price = _ready_offer_gateway(
        tmp_path, upstream_models=("raw-primary", "raw-fallback")
    )
    first = respx.post("https://1.1.1.1/v1/chat/completions").mock(side_effect=httpx.ConnectError("connect refused"))
    fallback = respx.post("https://8.8.8.8/v1/chat/completions").mock(return_value=httpx.Response(
        200, json={"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3}}
    ))
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8,
            })
        assert response.status_code == 200, response.text
        assert first.called and fallback.called
        assert json.loads(fallback.calls[0].request.content)["model"] == "raw-fallback"
        events = portal.list_usage(user["id"])
        assert len(events) == 1
        assert events[0]["provider_id"] == connections[1][0].id
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_ambiguous_timeout_is_not_retried(tmp_path):
    _settings, _portal, _user, issued, public_model_id, _offer, _connections, _price = _ready_offer_gateway(
        tmp_path, upstream_models=("raw-primary", "raw-fallback")
    )
    first = respx.post("https://1.1.1.1/v1/chat/completions").mock(side_effect=httpx.ReadTimeout("response timed out"))
    fallback = respx.post("https://8.8.8.8/v1/chat/completions").mock(return_value=httpx.Response(200, json={"choices": []}))
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8,
            })
        assert first.called
        assert not fallback.called
        assert response.status_code in (502, 503, 504)
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_stream_started_is_never_retried(tmp_path):
    _settings, _portal, _user, issued, public_model_id, _offer, _connections, _price = _ready_offer_gateway(
        tmp_path, upstream_models=("raw-primary", "raw-fallback")
    )
    first = respx.post("https://1.1.1.1/v1/chat/completions").mock(return_value=httpx.Response(
        200, text='data: {"choices":[{"delta":{"content":"started"}}]}\n\ndata: [DONE]\n\n',
        headers={"content-type": "text/event-stream"},
    ))
    fallback = respx.post("https://8.8.8.8/v1/chat/completions").mock(return_value=httpx.Response(200, json={"choices": []}))
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8, "stream": True,
            })
        assert response.status_code == 200
        assert "started" in response.text
        assert first.called
        assert not fallback.called
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_usage_snapshots_keep_provider_connection_and_price_version_after_disable(tmp_path):
    _settings, portal, user, issued, public_model_id, offer_id, connections, price = _ready_offer_gateway(tmp_path)
    connection = connections[0][0]
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(return_value=httpx.Response(
        200, json={"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}}
    ))
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8,
            })
        assert response.status_code == 200, response.text
        assert upstream.called
        portal.set_offer_available(offer_id, False, "operator")
        event = portal.list_usage(user["id"])[0]
        assert event["provider_id"] == connection.id
        assert event["price_version_id"] == price["id"]
        assert event["total_tokens"] == 5
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_tool_schemas_are_included_in_the_preflight_input_estimate(tmp_path):
    _settings, _portal, _user, issued, public_model_id, _offer, _connections, _price = _ready_offer_gateway(
        tmp_path, user_allowance=0.0001
    )
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})
    )
    tools = [{"type": "function", "function": {
        "name": "large_schema", "description": "x" * 12000,
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
    }}]
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hi"}],
                "tools": tools, "max_tokens": 8,
            })
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "budget_exhausted"
        assert not upstream.called
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_reservation_rechecks_route_review_state_before_dispatch(tmp_path, monkeypatch):
    _settings, _portal, _user, issued, public_model_id, _offer, connections, _price = _ready_offer_gateway(tmp_path)
    connection_id, upstream_model_id = connections[0][0].id, connections[0][2]
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})
    )
    reserve = PortalDatabase.reserve_request_budget
    invalidated = False

    def invalidate_after_route_resolution(repository, *args, **kwargs):
        nonlocal invalidated
        if not invalidated:
            invalidated = True
            repository.mark_discovery_stale(connection_id)
            repository.apply_discovery(
                connection_id, [DiscoveredModel(upstream_model_id)], datetime.now(timezone.utc)
            )
        return reserve(repository, *args, **kwargs)

    monkeypatch.setattr(PortalDatabase, "reserve_request_budget", invalidate_after_route_resolution)
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": public_model_id, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 8,
            })
        assert invalidated
        assert response.status_code != 200
        assert not upstream.called
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_portal_key_calls_existing_openai_compatible_gateway_and_saves_owned_usage(tmp_path):
    database_path = str(tmp_path / f"portal-gateway-{uuid4().hex}.db")
    settings = Settings(
        database_path=database_path,
        provider_key_pepper="portal-gateway-test-pepper",
        provider_secret_key=Fernet.generate_key().decode(),
        admin_token="admin-test-token",
        alibaba_api_key="test-upstream",
        alibaba_base_url="https://1.1.1.1/v1",
        allowed_models="",
        input_price_per_million=1,
        output_price_per_million=1,
        provider_hard_stop_usd=10,
    )
    portal_pepper = hashlib.sha256(("sponsored-provider:portal:v1:" + settings.provider_key_pepper).encode()).hexdigest()
    legacy = Database(database_path, settings.provider_key_pepper, settings.provider_secret_key)
    profile = legacy.create_upstream("Test upstream", "openai_compatible", settings.normalized_base_url, "test-upstream")
    legacy.update_upstream_models(profile["id"], ["model-a"], "healthy")
    portal = PortalDatabase(database_path, key_pepper=portal_pepper)
    user = portal.upsert_user(subject="member", email="member@example.test", name="Member")
    portal.add_catalog_model(provider_id=profile["id"], model_id="model-a", provider_name="Test upstream", capabilities=["text"], input_price_per_million=1, output_price_per_million=1, price_source="test", approved=True)
    connection = portal.register_connection(profile["id"], "test-upstream", "Test upstream", "Primary")
    portal.apply_discovery(connection.id, [DiscoveredModel("model-a")], datetime.now(timezone.utc))
    offer_id = portal.get_offer_id("test-upstream", "model-a")
    operator_offer = next(item for item in portal.list_operator_offers() if item["id"] == offer_id)
    for offer_route in operator_offer["routes"]:
        portal.set_route_available(offer_route["id"], True, "operator")
    issued = portal.create_user_key(user["id"], "Coding agent", allowed_models_mode="all_approved")
    assert portal.find_gateway_key(issued["api_key"])["effective_model_ids"] == [f"{profile['id']}::model-a"]
    route = respx.post(f"{settings.normalized_base_url}/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
    }))
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={
                "model": "model-a", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 10,
            })
        assert response.status_code == 200, response.text
        assert route.called
        events = portal.list_usage(user["id"])
        assert len(events) == 1
        assert events[0]["model_id"] == "model-a"
        assert events[0]["key_label_snapshot"] == "Coding agent"
        assert events[0]["total_tokens"] == 110
    finally:
        app.dependency_overrides.clear()
        try:
            Path(database_path).unlink(missing_ok=True)
        except PermissionError:
            pass


@respx.mock
def test_authenticated_model_rejection_is_logged_without_sending_upstream(tmp_path):
    database_path = str(tmp_path / "rejected.db")
    settings = Settings(database_path=database_path, provider_key_pepper="reject-test-pepper", provider_secret_key=Fernet.generate_key().decode(), admin_token="admin", alibaba_api_key="test-upstream", provider_hard_stop_usd=10)
    portal_pepper = hashlib.sha256(("sponsored-provider:portal:v1:" + settings.provider_key_pepper).encode()).hexdigest()
    portal = PortalDatabase(database_path, key_pepper=portal_pepper)
    user = portal.upsert_user(subject="member", email="member@example.test", name="Member")
    portal.add_catalog_model(provider_id="configured", model_id="model-a", provider_name="Test upstream", capabilities=["text"], input_price_per_million=1, output_price_per_million=1, price_source="test", approved=True)
    issued = portal.create_user_key(user["id"], "Coding agent", allowed_models_mode="all_approved")
    route = respx.post(f"{settings.normalized_base_url}/chat/completions").mock(return_value=httpx.Response(200, json={"choices": []}))
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {issued['api_key']}"}, json={"model": "unapproved-model", "messages": [{"role": "user", "content": "hello"}]})
        assert response.status_code == 404
        assert not route.called
        event = portal.list_usage(user["id"])[0]
        assert event["status"] == "rejected"
        assert event["error_category"] == "model_not_found"
        assert event["total_tokens"] is None
    finally:
        app.dependency_overrides.clear()


@respx.mock
def test_spend_capped_legacy_key_requires_output_bound_and_reports_reason(tmp_path):
    database_path = str(tmp_path / f"legacy-unbounded-{uuid4().hex}.db")
    settings = Settings(
        database_path=database_path,
        provider_key_pepper="legacy-bound-test",
        provider_secret_key=Fernet.generate_key().decode(),
        admin_token="admin",
        alibaba_api_key="legacy-upstream-secret",
        alibaba_base_url="https://1.1.1.1/v1",
        allowed_models="legacy-model",
        input_price_per_million=1,
        output_price_per_million=2,
        provider_hard_stop_usd=10,
    )
    legacy = Database(database_path, settings.provider_key_pepper, settings.provider_secret_key)
    key, _metadata = legacy.create_key("Spend-capped legacy", {"spend_limit_usd": 1})
    upstream = respx.post("https://1.1.1.1/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": []})
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={
                "model": "legacy-model", "messages": [{"role": "user", "content": "unbounded output"}],
            })
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "key_budget_exhausted"
        assert not upstream.called
    finally:
        app.dependency_overrides.clear()


def test_legacy_key_usage_is_mirrored_once_into_operator_history(tmp_path):
    database_path = str(tmp_path / "legacy.db")
    pepper = "legacy-import-test-pepper"
    settings = Settings(database_path=database_path, provider_key_pepper=pepper, provider_secret_key=Fernet.generate_key().decode(), admin_token="admin")
    legacy = Database(database_path, settings.provider_key_pepper, settings.provider_secret_key)
    portal = PortalDatabase(database_path, key_pepper=hashlib.sha256(("sponsored-provider:portal:v1:" + pepper).encode()).hexdigest())
    owner = portal.upsert_user(subject="owner", email="owner@example.test", name="Owner", role="operator")
    _raw_key, key_info = legacy.create_key("Existing legacy key")
    portal.import_legacy_key_snapshots(owner["id"], legacy.list_keys())

    usage_id = legacy.record_usage(key_info["id"], model="old-model", input_tokens=8, output_tokens=3, total_tokens=11, estimated_cost_usd=0.000012, latency_ms=60, status="success", stream=False, client_ip="192.0.2.4")
    mirrored = portal.record_legacy_usage(key_info["id"], usage_id, key_label="Existing legacy key", provider_name=None, model="old-model", input_tokens=8, output_tokens=3, total_tokens=11, estimated_cost_usd=0.000012, latency_ms=60, status="success", stream=False, client_ip="192.0.2.4", upstream_profile_id=None)
    imported = portal.import_legacy_usage(owner["id"], legacy.export_usage_history())

    assert mirrored == 1
    assert imported == 0
    assert portal.operator_usage_summary()["request_count"] == 1
    assert portal.gateway_usage_summary()["request_count"] == 0
    assert portal.list_all_usage()[0]["key_label_snapshot"] == "Existing legacy key"
