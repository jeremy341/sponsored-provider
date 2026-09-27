from datetime import datetime, timezone
from types import SimpleNamespace

from cryptography.fernet import Fernet

from app.catalog import DiscoveredModel
from app.database import Database
from app.portal_db import PortalDatabase
from app.routing import public_model_id, resolve_offer_routes


def _discovered_repository(tmp_path):
    path = str(tmp_path / "portal.db")
    legacy = Database(path, "routing-test-pepper", Fernet.generate_key().decode())
    repository = PortalDatabase(path, key_pepper="p" * 40)
    return legacy, repository


def _add_connection(legacy, repository, *, profile_id, brand_slug, model_ids):
    profile = legacy.create_upstream(profile_id, "openai_compatible", f"https://{profile_id}.example/v1", "encrypted-key")
    connection = repository.register_connection(profile["id"], brand_slug, brand_slug.title(), profile_id)
    repository.apply_discovery(connection.id, [DiscoveredModel(item) for item in model_ids], datetime.now(timezone.utc))
    return connection


def test_same_brand_duplicate_upstream_model_merges_to_one_offer(tmp_path):
    legacy, repository = _discovered_repository(tmp_path)
    first = _add_connection(legacy, repository, profile_id="primary", brand_slug="acme", model_ids=["acme-chat-v2"])
    second = _add_connection(legacy, repository, profile_id="backup", brand_slug="acme", model_ids=["acme-chat-v2"])

    with repository.connect() as connection:
        offers = connection.execute("SELECT id FROM catalog_offers WHERE brand_id=? AND canonical_model_id=?", (first.brand_id, "acme-chat-v2")).fetchall()
        routes = connection.execute("SELECT connection_id,upstream_model_id FROM offer_routes WHERE offer_id=? ORDER BY connection_id", (offers[0]["id"],)).fetchall()

    assert len(offers) == 1
    assert [(row["connection_id"], row["upstream_model_id"]) for row in routes] == sorted([
        (first.id, "acme-chat-v2"), (second.id, "acme-chat-v2"),
    ])


def test_same_model_from_different_brands_stays_distinct(tmp_path):
    legacy, repository = _discovered_repository(tmp_path)
    _add_connection(legacy, repository, profile_id="first", brand_slug="acme", model_ids=["shared-model"])
    _add_connection(legacy, repository, profile_id="second", brand_slug="other", model_ids=["shared-model"])

    with repository.connect() as connection:
        offers = connection.execute("SELECT brand_id,canonical_model_id FROM catalog_offers WHERE canonical_model_id='shared-model'").fetchall()

    assert len(offers) == 2
    assert len({row["brand_id"] for row in offers}) == 2


def test_public_model_id_is_stable_and_provider_scoped():
    assert public_model_id("acme", "chat-v2") == "acme::chat-v2"
    assert public_model_id("acme", "chat-v2") != public_model_id("other", "chat-v2")


def _offer_and_routes():
    offer = SimpleNamespace(
        id="offer-1", brand_id="brand-1", active=True, approved=True,
        input_rate="1", output_rate="2", cached_input_rate=None,
    )

    def route(route_id, position, *, enabled=True, mapping="mapped", stale=False, active=True, confirmed=True, brand="brand-1", rates=("1", "2", None)):
        return SimpleNamespace(
            id=route_id, offer_id=offer.id, brand_id=brand, position=position, active=active,
            connection_enabled=enabled, mapping_status=mapping,
            identity_status="mapped",
            discovery_active=not stale, discovery_stale=stale, confirmed=confirmed,
            input_rate=rates[0], output_rate=rates[1], cached_input_rate=rates[2],
        )

    return offer, route


def test_route_order_skips_disabled_or_stale_connections():
    offer, route = _offer_and_routes()
    routes = [route("disabled", 0, enabled=False), route("stale", 1, stale=True), route("ready", 2)]

    assert [item.id for item in resolve_offer_routes(offer, routes)] == ["ready"]


def test_offer_with_missing_or_unmapped_connection_never_resolves():
    offer, route = _offer_and_routes()
    routes = [
        route("unmapped", 0, mapping="unmapped"),
        route("missing", 1, brand=None, enabled=False),
        route("unconfirmed", 2, confirmed=False),
    ]

    assert resolve_offer_routes(offer, routes) == []


def test_price_mismatch_route_is_ineligible_for_fallback():
    offer, route = _offer_and_routes()
    routes = [route("wrong-price", 0, rates=("1.01", "2", None)), route("matching", 1)]

    assert [item.id for item in resolve_offer_routes(offer, routes)] == ["matching"]
