import hashlib
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import respx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.catalog import DiscoveredModel
from app.database import Database
from app.main import app, get_portal_db
from app.portal_db import PortalDatabase


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
