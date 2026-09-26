from app.catalog import ModelsDevCatalog, normalize_openai_models


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
    import pytest

    with pytest.raises(ValueError):
        normalize_openai_models({"data": [{"name": "missing id"}]})


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
