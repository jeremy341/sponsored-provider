import asyncio

import httpx
import pytest

from app.errors import ProviderError


def test_openai_compatible_client_lists_models_and_completes_for_non_alibaba_provider():
    try:
        from app.openai_compatible import OpenAICompatibleClient
    except ImportError as exc:
        pytest.fail(f"provider-neutral client is not implemented: {exc}")

    observed = []

    async def handler(request):
        observed.append((request.url.path, request.headers.get("Authorization")))
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "generic-model"}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = OpenAICompatibleClient(
        "https://93.184.216.34/v1", "generic-secret", transport=httpx.MockTransport(handler),
    )

    async def exercise():
        models = await client.list_models()
        completion, latency_ms = await client.chat_completion({"model": "generic-model", "messages": []})
        return models, completion, latency_ms

    models, completion, latency_ms = asyncio.run(exercise())

    assert models == {"data": [{"id": "generic-model"}]}
    assert completion["choices"][0]["message"]["content"] == "ok"
    assert latency_ms >= 0
    assert observed == [
        ("/v1/models", "Bearer generic-secret"),
        ("/v1/chat/completions", "Bearer generic-secret"),
    ]


def test_legacy_alibaba_client_import_remains_compatible():
    try:
        from app.openai_compatible import OpenAICompatibleClient
    except ImportError as exc:
        pytest.fail(f"provider-neutral client is not implemented: {exc}")
    from app.alibaba import AlibabaClient

    assert AlibabaClient is OpenAICompatibleClient


def test_openai_compatible_client_rejects_redirects_without_following_them():
    try:
        from app.openai_compatible import OpenAICompatibleClient
    except ImportError as exc:
        pytest.fail(f"provider-neutral client is not implemented: {exc}")

    requested = []

    async def handler(request):
        requested.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    client = OpenAICompatibleClient(
        "https://93.184.216.34/v1", "generic-secret", transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderError):
        asyncio.run(client.list_models())
    assert requested == ["https://93.184.216.34/v1/models"]
