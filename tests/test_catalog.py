import httpx
import pytest

from app.catalog import MODELS_DEV_URL, ModelsDevCatalog, normalize_openai_models


MODELS_DEV_FIXTURE = {
    "metadata": {
        "source_url": "https://models.dev/api.json?type=all",
        "fetched_at": "2026-09-26T00:00:00Z",
        "attribution": "Models.dev public API; provider records keyed by provider slug; models keyed by exact upstream ID.",
    },
    "payload": {
        "acme": {
            "models": {
                "acme-chat-v2": {
                    "id": "acme-chat-v2",
                    "name": "Acme Chat V2",
                    "cost": {"input": 2.5, "output": 10, "cache_read": 0.25, "cache_write": 99},
                },
                "acme-chat": {
                    "id": "acme-chat",
                    "name": "Acme Chat",
                    "aliases": ["acme-chat-v2-preview"],
                    "cost": {"input": 1, "output": 4},
                },
    },
}
    },
}


def test_model_list_keeps_exact_ids_and_deduplicates_identical_rows():
    rows = [
        {"id": "vendor/model:latest", "name": "Model", "context_length": 8192},
        {"id": "vendor/model:latest", "name": "Model", "context_length": 8192},
    ]

    models = normalize_openai_models({"data": rows})

    assert len(models) == 1
    assert models[0].id == "vendor/model:latest"
    assert models[0].name == "Model"
    assert models[0].context_length == 8192


def test_malformed_model_list_is_rejected_without_emptying_catalog():
    with pytest.raises(ValueError):
        normalize_openai_models({"data": [{"name": "missing id"}]})


def test_conflicting_duplicate_model_id_is_rejected():
    with pytest.raises(ValueError, match="conflicting duplicate model id"):
        normalize_openai_models({"data": [
            {"id": "model-v1", "context_length": 4096},
            {"id": "model-v1", "context_length": 8192},
        ]})


def test_models_dev_exact_vendor_model_match_returns_usd_suggestion():
    catalog = ModelsDevCatalog.from_payload(MODELS_DEV_FIXTURE["payload"], source_url=MODELS_DEV_FIXTURE["metadata"]["source_url"], fetched_at=MODELS_DEV_FIXTURE["metadata"]["fetched_at"])

    match = catalog.lookup("acme", "acme-chat-v2")

    assert match.status == "exact"
    assert match.input_usd_per_million == 2.5
    assert match.output_usd_per_million == 10
    assert match.cached_input_usd_per_million == 0.25
    assert match.source_url == MODELS_DEV_FIXTURE["metadata"]["source_url"]
    assert match.fetched_at == MODELS_DEV_FIXTURE["metadata"]["fetched_at"]
    assert match.evidence == "exact provider slug and exact model ID"
    assert match.confidence == "high"


def test_ambiguous_alias_does_not_return_auto_match():
    catalog = ModelsDevCatalog.from_payload(MODELS_DEV_FIXTURE["payload"])

    match = catalog.lookup("acme", "acme-chat-v2-preview")

    assert match.status == "ambiguous"
    assert match.input_usd_per_million is None
    assert match.output_usd_per_million is None


def test_unknown_model_requires_manual_price():
    catalog = ModelsDevCatalog.from_payload(MODELS_DEV_FIXTURE["payload"])

    match = catalog.lookup("acme", "missing-model")

    assert match.status == "not_found"
    assert match.input_usd_per_million is None
    assert match.output_usd_per_million is None


class _FakeResponse:
    def __init__(self, *, status_code=200, url=MODELS_DEV_URL, payload=MODELS_DEV_FIXTURE["payload"], json_error=None):
        self.status_code = status_code
        self.url = httpx.URL(url)
        self.payload = payload
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("unexpected status", request=None, response=None)

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requested_url = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url):
        self.requested_url = url
        if self.error:
            raise self.error
        return self.response


def _patch_catalog_client(monkeypatch, fake_client):
    config = {}

    def client_factory(**kwargs):
        config.update(kwargs)
        return fake_client

    monkeypatch.setattr("app.catalog.httpx.Client", client_factory)
    return config


def _assert_not_found_without_prices(catalog):
    match = catalog.lookup("acme", "acme-chat-v2")
    assert match.status == "not_found"
    assert match.input_usd_per_million is None
    assert match.output_usd_per_million is None
    assert match.cached_input_usd_per_million is None


def test_models_dev_fetch_uses_fixed_endpoint_bounded_timeout_and_no_redirects(monkeypatch):
    fake_client = _FakeClient(response=_FakeResponse())
    config = _patch_catalog_client(monkeypatch, fake_client)

    catalog = ModelsDevCatalog.fetch(timeout=7)

    assert fake_client.requested_url == "https://models.dev/api.json?type=all"
    assert fake_client.requested_url == MODELS_DEV_URL
    assert config["follow_redirects"] is False
    assert config["trust_env"] is False
    assert isinstance(config["timeout"], httpx.Timeout)
    assert config["timeout"].connect <= 3
    assert config["timeout"].read <= 7
    assert config["timeout"].write <= 7
    assert config["timeout"].pool <= 7
    assert catalog.lookup("acme", "acme-chat-v2").status == "exact"


@pytest.mark.parametrize("status_code", [302, 503])
def test_models_dev_non_200_response_returns_not_found(monkeypatch, status_code):
    fake_client = _FakeClient(response=_FakeResponse(status_code=status_code))
    _patch_catalog_client(monkeypatch, fake_client)

    _assert_not_found_without_prices(ModelsDevCatalog.fetch())


def test_models_dev_timeout_returns_not_found(monkeypatch):
    fake_client = _FakeClient(error=httpx.ReadTimeout("fixture timeout"))
    _patch_catalog_client(monkeypatch, fake_client)

    _assert_not_found_without_prices(ModelsDevCatalog.fetch())


def test_models_dev_malformed_json_returns_not_found(monkeypatch):
    fake_client = _FakeClient(response=_FakeResponse(json_error=ValueError("malformed fixture JSON")))
    _patch_catalog_client(monkeypatch, fake_client)

    _assert_not_found_without_prices(ModelsDevCatalog.fetch())


def test_models_dev_wrong_host_returns_not_found(monkeypatch):
    fake_client = _FakeClient(response=_FakeResponse(url="https://attacker.example/api.json"))
    _patch_catalog_client(monkeypatch, fake_client)

    _assert_not_found_without_prices(ModelsDevCatalog.fetch())
