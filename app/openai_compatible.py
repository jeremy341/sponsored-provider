"""Provider-neutral OpenAI-compatible HTTP client."""

from __future__ import annotations

import ipaddress
import math
import socket
import time
from urllib.parse import urlsplit

import httpx

from .errors import ProviderError


def validate_public_https_base_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderError("A public HTTPS upstream URL is required.", "invalid_upstream", 400)
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProviderError("The upstream URL contains an invalid port.", "invalid_upstream", 400) from exc
    host = parsed.hostname
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError("Use a public HTTPS base URL without credentials, query, or fragment.", "invalid_upstream", 400)
    if port not in (None, 443) or host.endswith(".") or host.lower() in {"localhost", "localhost.localdomain"}:
        raise ProviderError("Local, ambiguous, and custom-port upstream URLs are not allowed.", "invalid_upstream", 400)
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
        except (OSError, ValueError) as exc:
            raise ProviderError("The upstream hostname could not be resolved safely.", "invalid_upstream", 400) from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ProviderError("Upstream host must resolve only to public IP addresses.", "invalid_upstream", 400)
    return value


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0, transport: httpx.AsyncBaseTransport | None = None):
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("An upstream API key is required")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Upstream timeout must be finite and positive")
        self.base_url = validate_public_https_base_url(base_url)
        self.api_key = api_key
        self.timeout = float(timeout)
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10.0)),
            transport=self.transport,
            follow_redirects=False,
            trust_env=False,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )

    async def _get_json(self, path: str, *, error_message: str) -> dict:
        self.base_url = validate_public_https_base_url(self.base_url)
        async with self._client() as client:
            try:
                response = await client.get(f"{self.base_url}{path}")
                response.raise_for_status()
                value = response.json()
                if not isinstance(value, dict):
                    raise ValueError("upstream response must be a JSON object")
                return value
            except httpx.HTTPStatusError as exc:
                raise ProviderError(error_message, "upstream_error", exc.response.status_code) from exc
            except (httpx.HTTPError, ValueError) as exc:
                raise ProviderError("The upstream model service is unavailable.", "upstream_unavailable", 503) from exc

    async def list_models(self) -> dict:
        return await self._get_json("/models", error_message="Upstream model discovery failed.")

    async def chat_completion(self, payload: dict) -> tuple[dict, int]:
        self.base_url = validate_public_https_base_url(self.base_url)
        started = time.perf_counter()
        async with self._client() as client:
            try:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload)
                response.raise_for_status()
                value = response.json()
                if not isinstance(value, dict):
                    raise ValueError("upstream response must be a JSON object")
                return value, int((time.perf_counter() - started) * 1000)
            except httpx.HTTPStatusError as exc:
                raise ProviderError("The upstream model request failed.", "upstream_error", exc.response.status_code) from exc
            except (httpx.HTTPError, ValueError) as exc:
                raise ProviderError("The upstream model is unavailable.", "upstream_unavailable", 503) from exc

    async def stream_chat_completion(self, payload: dict):
        self.base_url = validate_public_https_base_url(self.base_url)
        client = self._client()
        request = client.stream("POST", f"{self.base_url}/chat/completions", json=payload)
        response = None
        try:
            response = await request.__aenter__()
            if response.status_code >= 400:
                raise ProviderError("The upstream model request failed.", "upstream_error", response.status_code)
            async for line in response.aiter_lines():
                yield line + "\n"
        except httpx.HTTPError as exc:
            raise ProviderError("The upstream model is unavailable.", "upstream_unavailable", 503) from exc
        finally:
            if response is not None:
                await request.__aexit__(None, None, None)
            await client.aclose()
