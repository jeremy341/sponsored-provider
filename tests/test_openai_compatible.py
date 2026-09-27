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


def test_dns_rebinding_cannot_change_the_pinned_socket_destination(monkeypatch):
    import socket
    import app.openai_compatible as provider_module

    answers = [
        ["1.1.1.1", "2606:4700:4700::1111"],
        ["1.0.0.1", "2606:4700:4700::1001"],
        ["127.0.0.1"],
    ]
    lookups = []

    def changing_dns(host, port, *, type):
        answer = answers[min(len(lookups), len(answers) - 1)]
        lookups.append((host, port))
        return [
            (socket.AF_INET6 if ":" in address else socket.AF_INET, type, 6, "", (address, port))
            for address in answer
        ]

    monkeypatch.setattr(provider_module.socket, "getaddrinfo", changing_dns)
    observed = []

    async def handler(request):
        destination = request.url.host
        if not _is_ip_literal(destination):
            destination = changing_dns(destination, 443, type=socket.SOCK_STREAM)[0][4][0]
        observed.append((destination, request.headers.get("Host"), request.extensions.get("sni_hostname")))
        return httpx.Response(200, json={"data": [{"id": "safe-model"}]})

    try:
        from app.openai_compatible import OpenAICompatibleClient
    except ImportError as exc:
        pytest.fail(f"provider-neutral client is not implemented: {exc}")
    client = OpenAICompatibleClient(
        "https://provider.example/v1", "secret", transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.list_models())

    assert result["data"][0]["id"] == "safe-model"
    assert observed == [("1.0.0.1", "provider.example", "provider.example")]
    assert len(lookups) == 2

    def mixed_public_private_dns(host, port, *, type):
        return [
            (socket.AF_INET, type, 6, "", ("1.1.1.1", port)),
            (socket.AF_INET6, type, 6, "", ("fd00::1", port, 0, 0)),
        ]

    monkeypatch.setattr(provider_module.socket, "getaddrinfo", mixed_public_private_dns)
    with pytest.raises(ProviderError, match="public IP addresses"):
        OpenAICompatibleClient("https://mixed.example/v1", "secret")


def _is_ip_literal(value):
    import ipaddress
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False
