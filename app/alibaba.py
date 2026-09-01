import time

import httpx

from .errors import ProviderError


class AlibabaClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0, transport=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport

    def _client(self):
        return httpx.AsyncClient(timeout=self.timeout, transport=self.transport, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})

    async def list_models(self):
        async with self._client() as client:
            try:
                response = await client.get(f"{self.base_url}/models")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                raise ProviderError("Upstream model discovery failed.", "upstream_error", exc.response.status_code) from exc
            except httpx.HTTPError as exc:
                raise ProviderError("Upstream model discovery timed out or failed.", "upstream_unavailable", 503) from exc

    async def chat_completion(self, payload: dict):
        started = time.perf_counter()
        async with self._client() as client:
            try:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload)
                response.raise_for_status()
                return response.json(), int((time.perf_counter() - started) * 1000)
            except httpx.HTTPStatusError as exc:
                raise ProviderError("The upstream model request failed.", "upstream_error", exc.response.status_code) from exc
            except httpx.HTTPError as exc:
                raise ProviderError("The upstream model is unavailable.", "upstream_unavailable", 503) from exc

    async def stream_chat_completion(self, payload: dict):
        client = self._client()
        request = client.stream("POST", f"{self.base_url}/chat/completions", json=payload)
        response = await request.__aenter__()
        try:
            if response.status_code >= 400:
                raise ProviderError("The upstream model request failed.", "upstream_error", response.status_code)
            async for line in response.aiter_lines():
                yield line + "\n"
        except httpx.HTTPError as exc:
            raise ProviderError("The upstream model is unavailable.", "upstream_unavailable", 503) from exc
        finally:
            await request.__aexit__(None, None, None)
            await client.aclose()
