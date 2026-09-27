"""Provider-scoped public identities and exact eligible route selection."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from app.portal_db import CatalogOffer, OfferRoute


def public_model_id(brand_slug: str, canonical_model_id: str) -> str:
    if not isinstance(brand_slug, str) or not brand_slug:
        raise ValueError("A provider brand slug is required")
    if not isinstance(canonical_model_id, str) or not canonical_model_id:
        raise ValueError("A canonical model ID is required")
    return f"{brand_slug}::{canonical_model_id}"


def _rates_match(offer: CatalogOffer, route: OfferRoute) -> bool:
    explicit = getattr(route, "price_matches", None)
    if explicit is not None:
        return explicit is True
    fields = ("input_rate", "output_rate", "cached_input_rate")
    try:
        for field in fields:
            offer_rate = getattr(offer, field, None)
            route_rate = getattr(route, field, None)
            if offer_rate is None or route_rate is None:
                if offer_rate is not route_rate:
                    return False
            elif Decimal(str(offer_rate)) != Decimal(str(route_rate)):
                return False
    except (InvalidOperation, TypeError, ValueError):
        return False
    return True


def _eligible(offer: CatalogOffer, route: OfferRoute) -> bool:
    return (
        getattr(offer, "active", False) is True
        and getattr(offer, "approved", False) is True
        and route.offer_id == offer.id
        and getattr(route, "brand_id", None) == offer.brand_id
        and getattr(route, "active", False) is True
        and getattr(route, "connection_enabled", False) is True
        and getattr(route, "mapping_status", None) == "mapped"
        and getattr(route, "identity_status", None) == "mapped"
        and getattr(route, "discovery_active", False) is True
        and getattr(route, "discovery_stale", True) is False
        and getattr(route, "review_required", False) is False
        and getattr(route, "confirmed", False) is True
        and _rates_match(offer, route)
    )


def resolve_offer_routes(offer: CatalogOffer, routes: Sequence[OfferRoute]) -> list[OfferRoute]:
    """Return active same-brand routes in configured primary/fallback order."""
    return sorted(
        (route for route in routes if _eligible(offer, route)),
        key=lambda route: (getattr(route, "position", 0), route.id),
    )
