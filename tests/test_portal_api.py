from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.database import Database
from app.portal_api import PortalService, create_portal_router
from app.portal_db import PortalDatabase


class FixedIdentity:
    def __init__(self, subject="member-a", role="developer"):
        self.subject = subject
        self.role = role

    async def begin_login(self, *_args, **_kwargs):
        raise AssertionError("not used")


def _app(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    app = FastAPI()
    app.include_router(create_portal_router(PortalService(repository, identity=FixedIdentity(), cookie_secure=False)))
    return TestClient(app), repository


def _login(client, repository, subject, role="developer"):
    user = repository.upsert_user(subject=subject, email=f"{subject}@example.test", name=subject, role=role)
    session = repository.create_session(user["id"], ttl_seconds=3600)
    client.cookies.set("portal_session", session.raw_token)
    client.cookies.set("portal_csrf", session.csrf_token)
    return user, session


def test_api_key_is_returned_once_and_owner_is_derived_from_session(tmp_path):
    client, repository = _app(tmp_path)
    user, _ = _login(client, repository, "member-a")
    response = client.post("/api/developer/keys", json={"label": "OpenCode", "owner_id": "attacker", "modelAccess": {"mode": "all_approved"}, "spendCapUsd": None, "spendPeriod": None, "rpmLimit": None}, headers={"X-CSRF-Token": client.cookies.get("portal_csrf")})
    assert response.status_code == 201
    created = response.json()
    assert created["key"]["id"] == repository.list_user_keys(user["id"])[0]["id"]
    assert created["secret"].startswith("sp_sk_")
    assert "secret" not in client.get("/api/developer/keys").json()[0]
    assert repository.list_user_keys(user["id"])[0]["key_prefix"] != created["secret"]


def test_usage_and_keys_are_scoped_to_authenticated_user(tmp_path):
    client, repository = _app(tmp_path)
    user_a, _ = _login(client, repository, "member-a")
    key_a = repository.create_user_key(user_a["id"], "A key", allowed_models_mode="all_approved")
    repository.record_usage(user_a["id"], key_a["id"], model="model-a", input_tokens=10, output_tokens=4, total_tokens=14, latency_ms=120, status="ok", estimated_cost_usd=0.01)

    client.cookies.clear()
    user_b, _ = _login(client, repository, "member-b")
    key_b = repository.create_user_key(user_b["id"], "B key", allowed_models_mode="all_approved")
    repository.record_usage(user_b["id"], key_b["id"], model="model-b", input_tokens=3, output_tokens=2, total_tokens=5, latency_ms=80, status="ok", estimated_cost_usd=0.02)

    rows = client.get("/api/activity").json()["items"]
    assert len(rows) == 1
    assert rows[0]["modelId"] == "model-b"
    assert client.get(f"/api/keys/{key_a['id']}").status_code == 404
    assert [item["label"] for item in client.get("/api/keys").json()] == ["B key"]


def test_mutations_require_csrf_and_admin_routes_require_operator_role(tmp_path):
    client, repository = _app(tmp_path)
    user, _ = _login(client, repository, "member-a")
    assert client.post("/api/keys", json={"label": "No CSRF"}).status_code == 403
    assert client.post("/api/operator/invites", json={}, headers={"X-CSRF-Token": client.cookies.get("portal_csrf")}).status_code == 403

    client.cookies.clear()
    _login(client, repository, "operator-1", role="operator")
    response = client.post("/api/operator/invites", json={"expires_in_seconds": 3600}, headers={"X-CSRF-Token": client.cookies.get("portal_csrf")})
    assert response.status_code == 201
    assert response.json()["invite_token"]
    assert "invite_token" not in client.get("/api/operator/invites").text


def test_operator_guardrail_changes_persist_and_provider_secrets_stay_write_only(tmp_path):
    path = str(tmp_path / "operator.db")
    settings = Settings(database_path=path, provider_key_pepper="z" * 40, provider_secret_key=Fernet.generate_key().decode(), admin_token="operator-token", provider_hard_stop_usd=35, provider_estimate_reserve_usd=0.1)
    legacy = Database(path, settings.provider_key_pepper, settings.provider_secret_key)
    repository = PortalDatabase(path, key_pepper="p" * 40)
    app = FastAPI()
    app.include_router(create_portal_router(PortalService(repository, identity=FixedIdentity(), cookie_secure=False, legacy_database=legacy, settings=settings)))
    client = TestClient(app)
    operator, _session = _login(client, repository, "operator", role="operator")
    headers = {"X-CSRF-Token": client.cookies.get("portal_csrf")}

    update = client.patch("/api/operator/guardrails", headers=headers, json={"globalSpendCapUsd": 20, "safetyReserveUsd": 1, "globalStopped": True})
    assert update.status_code == 200
    snapshot = client.get("/api/operator/guardrails").json()
    assert snapshot["globalSpendCapUsd"] == 20
    assert snapshot["safetyReserveUsd"] == 1
    assert snapshot["globalStopped"] is True

    legacy.create_upstream("Provider One", "openai_compatible", "https://api.example.test/v1", "upstream-secret-value")
    providers = client.get("/api/operator/providers")
    assert providers.status_code == 200
    assert providers.json()[0]["baseUrlDisplay"] == "https://api.example.test/v1"
    assert "upstream-secret-value" not in providers.text
    rejected = client.post("/api/operator/providers", headers=headers, json={"name": "Local", "baseUrl": "https://127.0.0.1/v1", "apiKey": "secret"})
    assert rejected.status_code == 422


def test_archived_key_keeps_usage_history(tmp_path):
    client, repository = _app(tmp_path)
    user, _ = _login(client, repository, "member-a")
    key = repository.create_user_key(user["id"], "Keep history", allowed_models_mode="all_approved")
    repository.record_usage(user["id"], key["id"], model="old-model", input_tokens=2, output_tokens=1, total_tokens=3, latency_ms=30, status="ok", estimated_cost_usd=0.03)
    assert repository.archive_user_key(user["id"], key["id"]) is True
    assert repository.list_usage(user["id"])[0]["model_id"] == "old-model"


def test_key_policy_can_be_edited_only_by_its_owner(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    owner = repository.upsert_user(subject="owner", email="owner@example.test", name="Owner")
    other = repository.upsert_user(subject="other", email="other@example.test", name="Other")
    repository.add_catalog_model(provider_id="p", model_id="model-a", provider_name="P", capabilities=["text"], input_price_per_million=1, output_price_per_million=1, price_source="verified", approved=True)
    key = repository.create_user_key(owner["id"], "Editable", allowed_models_mode="all_approved")
    assert repository.update_user_key_policy(owner["id"], key["id"], allowed_models_mode="selected", allowed_models=["model-a"], spend_limit_usd=5, spend_period="weekly", rpm_limit=30) is True
    updated = repository.get_user_key(owner["id"], key["id"])
    assert updated["allowed_models_mode"] == "selected"
    assert updated["allowed_models"] == ["p::model-a"]
    assert updated["spend_limit_usd"] == 5
    assert repository.update_user_key_policy(other["id"], key["id"], allowed_models_mode="all_approved", allowed_models=[], spend_limit_usd=None, spend_period=None, rpm_limit=None) is False


def test_key_policy_edit_endpoint_is_csrf_protected_and_owner_scoped(tmp_path):
    client, repository = _app(tmp_path)
    owner, _session = _login(client, repository, "owner")
    other = repository.upsert_user(subject="other", email="other@example.test", name="Other")
    key = repository.create_user_key(owner["id"], "Policy key", allowed_models_mode="all_approved")
    payload = {"modelAccess": {"mode": "all_approved"}, "spendCapUsd": 3, "spendPeriod": "week", "rpmLimit": 40}
    assert client.patch(f"/api/developer/keys/{key['id']}", json=payload).status_code == 403
    response = client.patch(f"/api/developer/keys/{key['id']}", json=payload, headers={"X-CSRF-Token": client.cookies.get("portal_csrf")})
    assert response.status_code == 200
    assert response.json()["spendCapUsd"] == 3

    client.cookies.clear()
    _login(client, repository, "other")
    assert client.patch(f"/api/developer/keys/{key['id']}", json=payload, headers={"X-CSRF-Token": client.cookies.get("portal_csrf")}).status_code == 404


def test_session_and_dashboard_endpoints_match_portal_contract(tmp_path):
    client, repository = _app(tmp_path)
    user, _ = _login(client, repository, "member-a")
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["user"]["displayName"] == "member-a"
    assert session.json()["role"] == "developer"
    assert session.json()["csrfToken"] == client.cookies.get("portal_csrf")
    assert client.get("/api/developer/dashboard").status_code == 200
    assert set(client.get("/api/developer/dashboard").json()) == {"usage", "series", "topModels", "keys", "recentActivity", "allowance"}
    assert client.get("/api/operator/dashboard").status_code == 403

    client.cookies.clear()
    _login(client, repository, "operator-1", role="operator")
    assert client.get("/api/operator/dashboard").status_code == 200
    assert client.get("/api/developer/dashboard").status_code == 403


def test_catalog_exposes_only_approved_priced_models(tmp_path):
    client, repository = _app(tmp_path)
    _login(client, repository, "member-a")
    repository.add_catalog_model(provider_id="p1", model_id="priced-approved", provider_name="Provider", capabilities=["text"], input_price_per_million=1, output_price_per_million=2, price_source="verified", approved=True)
    repository.add_catalog_model(provider_id="p1", model_id="unapproved", provider_name="Provider", capabilities=["text"], input_price_per_million=1, output_price_per_million=2, price_source="verified", approved=False)
    repository.add_catalog_model(provider_id="p1", model_id="missing-price", provider_name="Provider", capabilities=["text"], input_price_per_million=None, output_price_per_million=None, approved=True)
    assert [model["id"] for model in client.get("/api/models").json()] == ["p1::priced-approved"]
    repository.set_model_active("priced-approved", active=False)
    assert client.get("/api/models").json() == []
    client.cookies.clear()
    _login(client, repository, "operator-1", role="operator")
    operator_models = client.get("/api/operator/models").json()
    assert len(operator_models) == 3
    assert next(model for model in operator_models if model["id"] == "priced-approved")["available"] is False


def test_historic_usage_api_keeps_float_compatible_cost_after_schema_migration(tmp_path):
    client, repository = _app(tmp_path)
    user, _ = _login(client, repository, "member-a")
    key = repository.create_user_key(user["id"], "Historic", allowed_models_mode="all_approved")
    repository.record_usage(
        user["id"], key["id"], model="removed-model", input_tokens=5, output_tokens=2, total_tokens=7,
        latency_ms=12, status="success", estimated_cost_usd=0.000000123456,
        provider_id="old-provider", provider_name="Old provider", price_snapshot={"legacy_rate": 0.123456},
        occurred_at="2025-01-02T03:04:05+00:00",
    )
    with repository.connect() as connection:
        connection.execute("DELETE FROM portal_schema_migrations")
    repository.init_schema()

    item = client.get("/api/activity").json()["items"][0]
    assert item["modelId"] == "removed-model"
    assert item["providerName"] == "Old provider"
    assert item["estimatedCostUsd"] == 0.000000123456
    assert item["occurredAt"] == "2025-01-02T03:04:05+00:00"


def test_unmapped_legacy_catalog_is_not_listed_or_routable(tmp_path):
    client, repository = _app(tmp_path)
    user, _ = _login(client, repository, "member-a")
    key = repository.create_user_key(user["id"], "Unmapped", allowed_models_mode="all_approved")
    repository.add_catalog_model(
        provider_id="legacy-provider", model_id="legacy-model", provider_name="Ambiguous label",
        capabilities=["text"], input_price_per_million=1, output_price_per_million=2,
        price_source="legacy", approved=True, active=True,
    )
    with repository.connect() as connection:
        connection.execute("DELETE FROM portal_schema_migrations")
    repository.init_schema()

    assert client.get("/api/models").json() == []
    assert repository.get_model("legacy-provider::legacy-model") is None
    resolved = repository.find_gateway_key(key["api_key"])
    assert resolved["effective_model_ids"] == []


def test_portal_key_resolves_for_gateway_and_usage_is_immutable_with_owner_snapshot(tmp_path):
    client, repository = _app(tmp_path)
    user, _ = _login(client, repository, "member-a")
    repository.set_user_policy(user["id"], allowance_usd=12, allowance_period="weekly", rpm_limit=80)
    repository.add_catalog_model(provider_id="provider-1", model_id="model-1", provider_name="Provider One", capabilities=["text"], input_price_per_million=1, output_price_per_million=2, price_source="verified", approved=True)
    created = repository.create_user_key(user["id"], "Gateway key", allowed_models_mode="all_approved")

    resolved = repository.find_gateway_key(created["api_key"])
    assert resolved is not None
    assert resolved["owner_id"] == user["id"]
    assert resolved["owner_status"] == "active"
    assert resolved["user_rpm_limit"] == 80
    assert resolved["effective_model_ids"] == [f"provider-1::model-1"]
    assert resolved["key_id"] == created["id"]
    assert "api_key" not in resolved

    event_id = repository.record_gateway_usage(resolved, model="model-1", input_tokens=7, output_tokens=2, total_tokens=9, latency_ms=40, status="success", estimated_cost_usd=0.000011, client_ip="192.0.2.4")
    usage = repository.list_all_usage(limit=10)[0]
    assert usage["id"] == event_id
    assert usage["owner_user_id"] == user["id"]
    assert usage["owner_name_snapshot"] == "member-a"
    assert usage["key_label_snapshot"] == "Gateway key"
    assert repository.find_gateway_key("sp_sk_not-a-real-key") is None

    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        with repository.connect() as connection:
            connection.execute("DELETE FROM portal_usage_events WHERE id=?", (event_id,))


def test_user_allowance_reservations_are_shared_across_all_keys(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="member", email="member@example.test", name="Member")
    repository.set_user_policy(user["id"], allowance_usd=0.01, allowance_period="weekly", rpm_limit=80)
    first = repository.create_user_key(user["id"], "First", allowed_models_mode="all_approved")
    second = repository.create_user_key(user["id"], "Second", allowed_models_mode="all_approved")

    reservation = repository.reserve_gateway_budget(user["id"], first["id"], 0.006, global_limit_usd=1)
    assert reservation is not None
    assert repository.reserve_gateway_budget(user["id"], second["id"], 0.005, global_limit_usd=1) is None
    repository.record_gateway_usage(
        repository.find_gateway_key(first["api_key"]),
        model="model-a",
        input_tokens=4,
        output_tokens=2,
        total_tokens=6,
        latency_ms=50,
        status="success",
        estimated_cost_usd=0.006,
        reservation_id=reservation,
    )
    assert repository.reserve_gateway_budget(user["id"], second["id"], 0.005, global_limit_usd=1) is None


def test_stale_gateway_reservation_expires_instead_of_locking_usage_forever(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="member", email="member@example.test", name="Member")
    repository.set_user_policy(user["id"], allowance_usd=0.01, allowance_period="weekly", rpm_limit=80)
    key = repository.create_user_key(user["id"], "First", allowed_models_mode="all_approved")
    repository.reserve_gateway_budget(user["id"], key["id"], 0.006, global_limit_usd=1)
    with repository.connect() as connection:
        connection.execute("UPDATE portal_budget_reservations SET created_at='2000-01-01T00:00:00+00:00' WHERE status='active'")

    assert repository.reserve_gateway_budget(user["id"], key["id"], 0.006, global_limit_usd=1, reservation_ttl_seconds=10) is not None


def test_people_usage_does_not_multiply_when_user_has_multiple_keys(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="member", email="member@example.test", name="Member")
    first = repository.create_user_key(user["id"], "First", allowed_models_mode="all_approved")
    repository.create_user_key(user["id"], "Second", allowed_models_mode="all_approved")
    repository.record_usage(user["id"], first["id"], model="model-a", input_tokens=10, output_tokens=4, total_tokens=14, latency_ms=120, status="ok", estimated_cost_usd=0.01)

    person = repository.list_people()[0]
    assert person["keyCount"] == 2
    assert person["requestCount"] == 1
    assert person["usedUsd"] == 0.01


def test_person_usage_matches_daily_allowance_period_not_lifetime_total(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="member", email="member@example.test", name="Member")
    repository.set_user_policy(user["id"], allowance_usd=1, allowance_period="daily", rpm_limit=60)
    key = repository.create_user_key(user["id"], "Daily key", allowed_models_mode="all_approved")
    repository.record_usage(user["id"], key["id"], model="old", input_tokens=2, output_tokens=1, total_tokens=3, latency_ms=20, status="ok", estimated_cost_usd=0.4, occurred_at="2026-09-24T12:00:00+00:00")
    repository.record_usage(user["id"], key["id"], model="today", input_tokens=2, output_tokens=1, total_tokens=3, latency_ms=20, status="ok", estimated_cost_usd=0.1)

    person = repository.list_people()[0]
    assert person["usedUsd"] == 0.1


def test_latency_percentile_requires_twenty_samples_and_uses_full_history(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="member", email="member@example.test", name="Member")
    key = repository.create_user_key(user["id"], "Latency", allowed_models_mode="all_approved")
    for sample in range(1, 20):
        repository.record_usage(user["id"], key["id"], model="model", input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=sample, status="ok", estimated_cost_usd=0.0001)
    assert repository.latency_percentile(user["id"])["p95"] is None
    repository.record_usage(user["id"], key["id"], model="model", input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=20, status="ok", estimated_cost_usd=0.0001)
    assert repository.latency_percentile(user["id"]) == {"p95": 19, "sample_count": 20}


def test_operator_runtime_guardrails_persist_between_repository_instances(tmp_path):
    path = str(tmp_path / "portal.db")
    repository = PortalDatabase(path, key_pepper="p" * 40)
    repository.set_runtime_setting("global_spend_cap_usd", 20)
    repository.set_runtime_setting("global_stopped", True)

    restarted = PortalDatabase(path, key_pepper="p" * 40)
    assert restarted.get_runtime_setting("global_spend_cap_usd") == 20
    assert restarted.get_runtime_setting("global_stopped") is True


def test_portal_rpm_windows_are_shared_per_user_and_isolated_between_users(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user_a = repository.upsert_user(subject="a", email="a@example.test", name="A")
    user_b = repository.upsert_user(subject="b", email="b@example.test", name="B")
    key_a1 = repository.create_user_key(user_a["id"], "A1", allowed_models_mode="all_approved")
    key_a2 = repository.create_user_key(user_a["id"], "A2", allowed_models_mode="all_approved")
    key_b = repository.create_user_key(user_b["id"], "B1", allowed_models_mode="all_approved")

    assert repository.allow_portal_request(user_a["id"], key_a1["id"], user_limit=2, key_limit=None, window=100)
    assert repository.allow_portal_request(user_a["id"], key_a2["id"], user_limit=2, key_limit=None, window=100)
    assert not repository.allow_portal_request(user_a["id"], key_a1["id"], user_limit=2, key_limit=None, window=100)
    assert repository.allow_portal_request(user_b["id"], key_b["id"], user_limit=2, key_limit=None, window=100)


def test_legacy_usage_import_is_idempotent_and_keeps_old_model_cost_and_tokens(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    operator = repository.upsert_user(subject="owner", email="owner@example.test", name="Owner", role="operator")
    imported = repository.import_legacy_usage(operator["id"], [{
        "id": 47,
        "provider_key_id": 3,
        "key_label": "Old key",
        "upstream_profile_id": "provider-7",
        "provider_name": "Old upstream",
        "timestamp": "2026-09-26T10:00:00+00:00",
        "model": "removed-model",
        "input_tokens": 100,
        "output_tokens": 25,
        "total_tokens": 125,
        "estimated_cost_usd": 0.0042,
        "latency_ms": 500,
        "status": "success",
        "stream": 0,
        "error_category": None,
        "client_ip": "192.0.2.4",
    }])
    assert imported == 1
    assert repository.import_legacy_usage(operator["id"], [{"id": 47}]) == 0
    record = repository.list_usage(operator["id"])[0]
    assert record["model_id"] == "removed-model"
    assert record["total_tokens"] == 125
    assert record["estimated_cost_usd"] == 0.0042
    assert record["key_label_snapshot"] == "Old key"
    assert repository.operator_usage_summary()["estimated_cost_usd"] == 0.0042
    assert repository.gateway_usage_summary()["estimated_cost_usd"] is None
