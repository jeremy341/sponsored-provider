import httpx
import respx
from app.config import Settings
from app.database import Database
from app.main import estimate_cost, upstream_client
from pathlib import Path
from shutil import rmtree
from uuid import uuid4


def test_health_never_needs_upstream(client):
    test_client, _, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_provider_key_can_be_created_and_disabled(client):
    test_client, _, db = client
    raw_key, metadata = db.create_key("local-client")
    assert raw_key.startswith("sp_sk_")
    assert db.find_key(raw_key) is not None
    db.set_key_state(metadata["id"], False)
    assert test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"}).status_code == 401


def test_key_creation_accepts_policy_atomically(client):
    test_client, _, db = client
    raw_key, _ = db.create_key("atomic", {"allowed_upstreams": "provider-1", "allowed_models": "model-a, model-b", "spend_limit_usd": 35, "requests_per_minute": 0, "token_limit": 0, "risk_approved": True})
    visible = test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert [item["id"] for item in visible.json()["data"]] == ["model-a", "model-b"]


def test_provider_key_revoke_is_permanent(client):
    test_client, _, db = client
    raw_key, metadata = db.create_key("revoke-me")
    db.set_key_state(metadata["id"], False, revoke=True)
    assert db.find_key(raw_key)["revoked_at"] is not None
    assert test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"}).status_code == 401


def test_models_requires_key_and_returns_allowlist(client):
    test_client, _, db = client
    raw_key, _ = db.create_key("test")
    assert test_client.get("/v1/models").status_code == 401
    response = test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["qwen-test"]


def test_guardrail_settings_and_emergency_stop_gate_health(client):
    test_client, settings, _ = client
    settings.allowed_models = "qwen-a, qwen-b"
    settings.provider_hard_stop_usd = 35
    settings.rate_limit_requests_per_minute = 4
    assert settings.model_allowlist == {"qwen-a", "qwen-b"}
    assert settings.rate_limit_requests_per_minute == 4
    settings.emergency_stop = True
    assert test_client.get("/health").json()["ok"] is False


@respx.mock
async def test_configured_upstream_lists_models_without_profile(client):
    _, settings, db = client
    settings.alibaba_base_url = "https://1.1.1.1/v1"
    route = respx.get(f"{settings.normalized_base_url}/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "qwen-a"}, {"id": "qwen-a"}, {"id": "qwen-b"}]}))
    api_client, resolved = upstream_client(None, db, settings)
    assert resolved == "configured"
    payload = await api_client.list_models()
    items = payload.get("data", payload if isinstance(payload, list) else [])
    assert sorted({item.get("id") for item in items if isinstance(item, dict) and item.get("id")}) == ["qwen-a", "qwen-b"]
    assert route.called


@respx.mock
async def test_upstream_profile_secret_stays_encrypted_and_models_sync(client):
    _, settings, _ = client
    db = Database(settings.database_path, "test-pepper", settings.provider_secret_key)
    profile = db.create_upstream("OpenAI test", "openai", "https://93.184.216.34/v1", "upstream-secret")
    profile_id = profile["id"]
    stored = db.list_upstreams()
    assert stored[0]["secret_configured"] is True
    assert "upstream-secret" not in str(stored)
    respx.get("https://93.184.216.34/v1/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "gpt-test"}]}))
    api_client, resolved = upstream_client(profile_id, db, settings)
    assert resolved == profile_id
    payload = await api_client.list_models()
    items = payload.get("data", payload if isinstance(payload, list) else [])
    model_ids = sorted({item.get("id") for item in items if isinstance(item, dict) and item.get("id")})
    db.update_upstream_models(profile_id, model_ids, "healthy" if model_ids else "empty_catalog")
    refreshed = next(item for item in db.list_upstreams() if item["id"] == profile_id)
    assert refreshed["models"] == ["gpt-test"]


def test_failed_provider_sync_preserves_last_successful_model_ids(client):
    _test_client, _settings, db = client
    profile_id = "cached-model-profile"
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO upstream_profiles(id,name,provider_kind,base_url,encrypted_api_key,models_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (profile_id, "Cached models", "openai_compatible", "https://93.184.216.34/v1", "encrypted-secret", "[]", "2026-01-01T00:00:00+00:00"),
        )
    db.update_upstream_models(profile_id, ["model-a", "model-b"], "healthy")

    db.update_upstream_models(profile_id, [], "error")
    refreshed = next(item for item in db.list_upstreams() if item["id"] == profile_id)

    assert refreshed["models"] == ["model-a", "model-b"]
    assert refreshed["health_status"] == "error"


def test_upstream_pricing_is_stored(client):
    _, settings, _ = client
    db = Database(settings.database_path, "test-pepper", settings.provider_secret_key)
    profile = db.create_upstream("Priced", "openai", "https://provider.example/v1", "secret")
    db.update_upstream_pricing(profile["id"], {"model-a": {"input": 0.1, "output": 0.2}})
    stored = db.list_upstreams()
    priced = next(item for item in stored if item["id"] == profile["id"])
    assert priced["pricing"] == {"model-a": {"input": 0.1, "output": 0.2}}


def test_pricing_updates_merge_without_removing_existing_entries(client):
    _, settings, _ = client
    db = Database(settings.database_path, "test-pepper", settings.provider_secret_key)
    profile = db.create_upstream("Priced merge", "openai", "https://provider.example/v1", "secret")
    profile_id = profile["id"]
    db.update_upstream_pricing(profile_id, {"model-a": {"input": 0.1, "output": 0.2}})
    db.update_upstream_pricing(profile_id, {"model-b": {"input": 0.3, "output": 0.4}})
    stored = db.list_upstreams()
    profile_row = next(item for item in stored if item["id"] == profile_id)
    assert set(profile_row["pricing"]) == {"model-a", "model-b"}


def test_budget_reservation_counts_active_requests(client):
    _, _, db = client
    reservation = db.reserve_budget(1, "provider", "model", 0.006, 100, 0.01, None)
    assert reservation
    blocked = db.reserve_budget(1, "provider", "model", 0.006, 100, 0.01, None)
    assert blocked is None
    db.finish_reservation(reservation)
    assert db.reserve_budget(1, "provider", "model", 0.006, 100, 0.01, None)


def test_ip_block_applies_before_key_validation(client):
    test_client, _, db = client
    raw_key, _ = db.create_key("blocked-client")
    db.block_ip("203.0.113.10", "abuse")
    db.block_ip("testclient", "test abuse")
    blocked = test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "ip_blocked"


@respx.mock
def test_rate_limit_blocks_before_upstream(client):
    test_client, settings, db = client
    settings.alibaba_base_url = "https://1.1.1.1/v1"
    settings.rate_limit_requests_per_minute = 1
    raw_key, _ = db.create_key("test")
    respx.post(f"{settings.normalized_base_url}/chat/completions").mock(return_value=httpx.Response(503, json={"error": "busy"}))
    first = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "qwen-test", "messages": [{"role": "user", "content": "hello"}]})
    second = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "qwen-test", "messages": [{"role": "user", "content": "hello"}]})
    assert first.status_code in (502, 503)
    assert second.status_code == 429


@respx.mock
def test_chat_proxy_forwards_allowlisted_model_and_records_usage(client):
    test_client, settings, db = client
    settings.alibaba_base_url = "https://1.1.1.1/v1"
    raw_key, _ = db.create_key("test")
    route = respx.post(f"{settings.normalized_base_url}/chat/completions").mock(return_value=httpx.Response(200, json={"id": "chat-1", "choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}}))
    response = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "qwen-test", "messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code == 200
    assert route.called
    assert db.usage_summary()["totals"]["requests"] == 1
    assert db.usage_summary()["totals"]["total_tokens"] == 1500
    assert db.usage_summary()["recent"][0]["client_ip"] == "testclient"
    assert db.usage_summary()["by_ip"][0]["requests"] == 1


def test_key_policy_can_require_approval_and_limit_models(client):
    test_client, _, db = client
    raw_key, metadata = db.create_key("restricted")
    db.update_key_policy(metadata["id"], risk_profile="strict", risk_approved=False, allowed_models="qwen-other", requests_per_minute=2, token_limit=1000, spend_limit_usd=1)
    assert test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"}).status_code == 403
    db.update_key_policy(metadata["id"], risk_approved=True)
    response = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "qwen-test", "messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code == 404


@respx.mock
def test_zero_key_rpm_means_unlimited_not_inherit_global_limit(client):
    test_client, settings, db = client
    settings.alibaba_base_url = "https://1.1.1.1/v1"
    settings.rate_limit_requests_per_minute = 1
    raw_key, metadata = db.create_key("unlimited-rpm")
    db.update_key_policy(metadata["id"], requests_per_minute=0)
    respx.post(f"{settings.normalized_base_url}/chat/completions").mock(return_value=httpx.Response(200, json={"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}))
    payload = {"model": "qwen-test", "messages": [{"role": "user", "content": "hello"}]}
    assert test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json=payload).status_code == 200
    assert test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json=payload).status_code == 200


@respx.mock
def test_key_spend_cap_blocks_before_upstream_request(client):
    test_client, settings, db = client
    raw_key, metadata = db.create_key("small-budget")
    db.update_key_policy(metadata["id"], spend_limit_usd=0.001)
    route = respx.post(f"{settings.normalized_base_url}/chat/completions").mock(return_value=httpx.Response(200, json={"choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}}))
    response = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "qwen-test", "messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "key_budget_exhausted"
    assert route.called is False


def test_cost_estimate_retains_sub_microdollar_precision(client):
    _test_client, settings, _db = client
    assert estimate_cost(1, 0, settings, input_price=0.1, output_price=0.1) == 0.0000001


def test_settings_bootstrap_generates_persistent_secrets(tmp_path):
    test_dir = tmp_path / f".bootstrap-test-{uuid4().hex}"
    test_dir.mkdir()
    settings = Settings(database_path=str(test_dir / "provider.db"))
    assert settings.provider_secret_key
    assert settings.provider_key_pepper
    assert (test_dir / "runtime-secrets.json").exists()
    second = Settings(database_path=str(test_dir / "provider.db"))
    assert second.provider_secret_key == settings.provider_secret_key
    rmtree(test_dir, ignore_errors=True)


def test_chat_rejects_non_allowlisted_model_without_upstream(client):
    test_client, _, db = client
    raw_key, _ = db.create_key("test")
    response = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "not-allowed", "messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
