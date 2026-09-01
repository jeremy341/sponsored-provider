import httpx
import respx


def test_health_never_needs_upstream(client):
    test_client, _, _ = client
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_dashboard_starts_empty(client):
    test_client, _, _ = client
    response = test_client.get("/api/dashboard", headers={"X-Admin-Token": "admin"})
    assert response.status_code == 200
    assert response.json()["budget"]["used_usd"] == 0
    assert response.json()["totals"]["requests"] == 0


def test_admin_can_create_and_disable_provider_key(client):
    test_client, _, db = client
    created = test_client.post("/api/admin/keys", headers={"X-Admin-Token": "admin"}, json={"label": "local-client"})
    assert created.status_code == 200
    raw_key = created.json()["key"]
    key_id = created.json()["id"]
    assert raw_key.startswith("sp_sk_")
    assert db.find_key(raw_key) is not None
    assert test_client.post(f"/api/admin/keys/{key_id}/disable", headers={"X-Admin-Token": "admin"}).json()["enabled"] is False
    assert test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"}).status_code == 401


def test_models_requires_key_and_returns_allowlist(client):
    test_client, _, db = client
    raw_key, _ = db.create_key("test")
    assert test_client.get("/v1/models").status_code == 401
    response = test_client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["qwen-test"]


def test_dashboard_requires_admin_token(client):
    test_client, _, _ = client
    assert test_client.get("/api/dashboard").status_code == 401


def test_dashboard_page_and_static_assets_are_served(client):
    test_client, _, _ = client
    assert test_client.get("/dashboard").status_code == 200
    assert test_client.get("/static/style.css").status_code == 200


@respx.mock
def test_rate_limit_blocks_before_upstream(client):
    test_client, settings, db = client
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
    raw_key, _ = db.create_key("test")
    route = respx.post(f"{settings.normalized_base_url}/chat/completions").mock(return_value=httpx.Response(200, json={"id": "chat-1", "choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}}))
    response = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "qwen-test", "messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code == 200
    assert route.called
    assert db.usage_summary()["totals"]["requests"] == 1
    assert db.usage_summary()["totals"]["total_tokens"] == 1500


def test_chat_rejects_non_allowlisted_model_without_upstream(client):
    test_client, _, db = client
    raw_key, _ = db.create_key("test")
    response = test_client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": "not-allowed", "messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
