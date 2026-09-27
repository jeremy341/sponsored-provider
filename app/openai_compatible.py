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
    _resolve_public_addresses(host, port or 443)
    return value


def _resolve_public_addresses(host: str, port: int) -> list[str]:
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ProviderError("The upstream hostname is invalid.", "invalid_upstream", 400) from exc
    try:
        records = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            records = [ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
        except (OSError, ValueError) as exc:
            raise ProviderError("The upstream hostname could not be resolved safely.", "invalid_upstream", 400) from exc
    if not records or any(not address.is_global for address in records):
        raise ProviderError("Upstream host must resolve only to public IP addresses.", "invalid_upstream", 400)
    return list(dict.fromkeys(str(address) for address in records))


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

    def _pinned_target(self, path: str) -> tuple[str, dict[str, str], dict[str, str]]:
        parsed = urlsplit(self.base_url)
        host = parsed.hostname
        if host is None:
            raise ProviderError("The upstream URL has no hostname.", "invalid_upstream", 400)
        port = parsed.port or 443
        address = _resolve_public_addresses(host, port)[0]
        # Use a checked literal as the actual URL host so the transport cannot
        # resolve the provider hostname a second time after validation.
        base = httpx.URL(self.base_url).copy_with(host=address)
        target = f"{str(base).rstrip('/')}{path}"
        sni_hostname = host.encode("idna").decode("ascii")
        host_header = f"[{sni_hostname}]" if ":" in sni_hostname else sni_hostname
        if parsed.port is not None:
            host_header = f"{host_header}:{parsed.port}"
        return target, {"Host": host_header}, {"sni_hostname": sni_hostname}

    async def _get_json(self, path: str, *, error_message: str) -> dict:
        target, headers, extensions = self._pinned_target(path)
        async with self._client() as client:
            try:
                request = client.build_request("GET", target, headers=headers, extensions=extensions)
                response = await client.send(request)
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
        target, headers, extensions = self._pinned_target("/chat/completions")
        started = time.perf_counter()
        async with self._client() as client:
            try:
                request = client.build_request("POST", target, json=payload, headers=headers, extensions=extensions)
                response = await client.send(request)
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
        target, headers, extensions = self._pinned_target("/chat/completions")
        client = self._client()
        response = None
        try:
            request = client.build_request("POST", target, json=payload, headers=headers, extensions=extensions)
            response = await client.send(request, stream=True)
            if response.status_code >= 400:
                raise ProviderError("The upstream model request failed.", "upstream_error", response.status_code)
            async for line in response.aiter_lines():
                yield line + "\n"
        except httpx.HTTPError as exc:
            raise ProviderError("The upstream model is unavailable.", "upstream_unavailable", 503) from exc
        finally:
            if response is not None:
                await response.aclose()
            await client.aclose()
