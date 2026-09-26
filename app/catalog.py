"""Read-only model discovery normalization and Models.dev price suggestions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

import httpx


MODELS_DEV_URL = "https://models.dev/api.json?type=all"
MODELS_DEV_HOST = "models.dev"
_MODEL_METADATA_FIELDS = ("name", "context_length", "capabilities", "owned_by", "created", "object")


@dataclass(frozen=True)
class DiscoveredModel:
    id: str
    name: str | None = None
    context_length: int | None = None
    capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PriceMatch:
    status: str = "not_found"
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None
    cached_input_usd_per_million: float | None = None
    source_url: str = MODELS_DEV_URL
    fetched_at: str | None = None
    evidence: str = "no exact catalog match"
    confidence: str = "none"


@dataclass(frozen=True)
class PriceSuggestion:
    input_usd_per_million: float | None
    output_usd_per_million: float | None
    cached_input_usd_per_million: float | None = None
    source: str = "manual"
    source_url: str | None = None
    evidence: str | None = None
    confidence: str | None = None
    fetched_at: str | None = None


def normalize_openai_models(payload: Mapping[str, Any]) -> list[DiscoveredModel]:
    """Validate an OpenAI-style model list and retain explicitly advertised fields."""
    if not isinstance(payload, Mapping):
        raise ValueError("model list response must be an object")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise ValueError("model list response must contain a data array")

    results: list[DiscoveredModel] = []
    seen: dict[str, DiscoveredModel] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("each model list entry must be an object")
        model_id = row.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("each model list entry must have a non-empty string id")

        metadata = {key: row[key] for key in _MODEL_METADATA_FIELDS if key in row}
        context_length = row.get("context_length")
        if context_length is not None and (isinstance(context_length, bool) or not isinstance(context_length, int) or context_length < 0):
            raise ValueError("context_length must be a non-negative integer")
        capabilities = row.get("capabilities", ())
        if capabilities is None:
            capabilities = ()
        if not isinstance(capabilities, (list, tuple)) or any(not isinstance(item, str) for item in capabilities):
            raise ValueError("capabilities must be an array of strings")
        name = row.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError("name must be a string")
        model = DiscoveredModel(
            id=model_id,
            name=name,
            context_length=context_length,
            capabilities=tuple(capabilities),
            metadata=metadata,
        )
        previous = seen.get(model_id)
        if previous is not None:
            if previous != model:
                raise ValueError(f"conflicting duplicate model id: {model_id}")
            continue
        seen[model_id] = model
        results.append(model)
    return results


class ModelsDevCatalog:
    """Read-only Models.dev catalog. Failed fetches safely behave as not found."""

    def __init__(self, payload: Mapping[str, Any] | None = None, *, source_url: str = MODELS_DEV_URL, fetched_at: str | None = None):
        self.source_url = source_url
        self.fetched_at = fetched_at
        self.providers: Mapping[str, Any] = {}
        if payload is not None:
            self.providers = self._validate_payload(payload)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], *, source_url: str = MODELS_DEV_URL, fetched_at: str | None = None) -> "ModelsDevCatalog":
        return cls(payload, source_url=source_url, fetched_at=fetched_at)

    @classmethod
    def fetch(cls, *, timeout: float = 5.0) -> "ModelsDevCatalog":
        """Fetch only the documented HTTPS endpoint; do not follow redirects."""
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 30:
            raise ValueError("timeout must be between 0 and 30 seconds")
        try:
            with httpx.Client(
                timeout=httpx.Timeout(timeout, connect=min(timeout, 3.0)),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.get(MODELS_DEV_URL)
                if response.status_code != 200:
                    return cls()
                response.raise_for_status()
                if response.url.scheme != "https" or response.url.host != MODELS_DEV_HOST:
                    return cls()
                payload = response.json()
            fetched_at = datetime.now(timezone.utc).isoformat()
            return cls.from_payload(payload, source_url=MODELS_DEV_URL, fetched_at=fetched_at)
        except (httpx.HTTPError, ValueError, TypeError):
            return cls()

    @staticmethod
    def _validate_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(payload, Mapping):
            raise ValueError("Models.dev response must be an object keyed by provider slug")
        for slug, provider in payload.items():
            if not isinstance(slug, str) or not isinstance(provider, Mapping):
                raise ValueError("Models.dev provider records are malformed")
            models = provider.get("models")
            if not isinstance(models, Mapping):
                raise ValueError(f"Models.dev provider {slug} has no models map")
            if any(not isinstance(model_id, str) or not isinstance(model, Mapping) for model_id, model in models.items()):
                raise ValueError(f"Models.dev models for provider {slug} are malformed")
        return payload

    def lookup(self, provider_slug: str, upstream_model_id: str) -> PriceMatch:
        provider = self.providers.get(provider_slug) if isinstance(provider_slug, str) else None
        models = provider.get("models", {}) if isinstance(provider, Mapping) else {}
        if not isinstance(upstream_model_id, str) or not isinstance(models, Mapping):
            return self._not_found()

        model = models.get(upstream_model_id)
        if isinstance(model, Mapping):
            if model.get("id", upstream_model_id) != upstream_model_id:
                return self._not_found()
            cost = model.get("cost", {})
            if not isinstance(cost, Mapping):
                cost = {}
            return PriceMatch(
                status="exact",
                input_usd_per_million=self._price(cost.get("input")),
                output_usd_per_million=self._price(cost.get("output")),
                cached_input_usd_per_million=self._price(cost.get("cache_read")),
                source_url=self.source_url,
                fetched_at=self.fetched_at,
                evidence="exact provider slug and exact model ID",
                confidence="high",
            )

        for record in models.values():
            aliases = record.get("aliases", ()) if isinstance(record, Mapping) else ()
            if isinstance(aliases, (list, tuple)) and upstream_model_id in aliases:
                return PriceMatch(
                    status="ambiguous",
                    source_url=self.source_url,
                    fetched_at=self.fetched_at,
                    evidence="query matches provider metadata alias only; exact model ID required",
                    confidence="none",
                )
        return self._not_found()

    @staticmethod
    def _price(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            return None
        return float(value)

    def _not_found(self) -> PriceMatch:
        return PriceMatch(source_url=self.source_url, fetched_at=self.fetched_at)
