import sqlite3
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet

from app.database import Database
from app.portal_db import PortalDatabase


def _legacy_database(path):
    legacy = Database(str(path), pepper="legacy-pepper", secret_key=Fernet.generate_key().decode())
    with legacy.connect() as connection:
        connection.execute(
            "INSERT INTO upstream_profiles(id,name,provider_kind,base_url,encrypted_api_key,models_json,created_at,pricing_json) VALUES(?,?,?,?,?,?,?,?)",
            ("provider-old", "Old provider", "openai_compatible", "https://provider.example/v1", "encrypted-secret", '["alpha"]', "2026-01-01T00:00:00+00:00", '{"alpha":{"input":1.25,"output":2.5}}'),
        )
        connection.execute(
            "INSERT INTO provider_api_keys(key_prefix,key_hash,label,created_at,spend_limit_usd) VALUES(?,?,?,?,?)",
            ("sp_sk_legacy", "legacy-hash", "Legacy key", "2026-01-01T00:00:00+00:00", 3.125),
        )
        key_id = connection.execute("SELECT id FROM provider_api_keys WHERE key_hash='legacy-hash'").fetchone()[0]
        connection.execute(
            "INSERT INTO usage_records(provider_key_id,timestamp,model,input_tokens,output_tokens,total_tokens,estimated_cost_usd,latency_ms,status,stream,error_category,upstream_profile_id,client_ip) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key_id, "2026-02-03T04:05:06+00:00", "removed-model", 101, 17, 118, 0.000000123456, 321, "success", 1, "none", "provider-old", "192.0.2.1"),
        )
    return legacy, key_id


def _catalog(repository):
    repository.add_catalog_model(
        provider_id="provider-old",
        model_id="alpha",
        provider_name="Old provider",
        capabilities=["text", "vision"],
        input_price_per_million=1.25,
        output_price_per_million=2.5,
        cached_input_price_per_million=0.125,
        price_source="legacy-import",
        approved=True,
        active=False,
    )


def _rerun_migrations(repository):
    with repository.connect() as connection:
        connection.execute("DELETE FROM portal_schema_migrations")
    repository.init_schema()


def test_migration_preserves_legacy_catalog_and_all_usage_snapshots(tmp_path):
    path = tmp_path / "portal.db"
    legacy, key_id = _legacy_database(path)
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    _catalog(repository)
    user = repository.upsert_user(subject="legacy-owner", email="legacy@example.test", name="Legacy owner", role="operator")
    repository.import_legacy_usage(user["id"], [{
        "id": 9001, "provider_key_id": key_id, "key_label": "Old label", "upstream_profile_id": "provider-old",
        "provider_name": "Snapshot provider", "timestamp": "2025-03-04T05:06:07+00:00", "model": "gone-v1",
        "input_tokens": 19, "output_tokens": 8, "total_tokens": 27, "estimated_cost_usd": 0.000000987654,
        "latency_ms": 90, "status": "success", "stream": True, "error_category": "old-error", "client_ip": "198.51.100.4",
    }])
    with repository.connect() as connection:
        original = connection.execute("SELECT * FROM portal_usage_events").fetchone()
        original_usage = {name: original[name] for name in original.keys()}
    _rerun_migrations(repository)

    migrated = PortalDatabase(str(path), key_pepper="p" * 40)
    with migrated.connect() as connection:
        catalog = connection.execute("SELECT * FROM portal_catalog_models WHERE provider_id='provider-old' AND model_id='alpha'").fetchone()
        events = connection.execute("SELECT * FROM portal_usage_events ORDER BY id").fetchall()
    with legacy.connect() as connection:
        old_usage = connection.execute("SELECT * FROM usage_records").fetchone()

    assert dict(catalog) == {
        "provider_id": "provider-old", "model_id": "alpha", "provider_name": "Old provider",
        "capabilities_json": '["text", "vision"]', "input_price_per_million": 1.25,
        "output_price_per_million": 2.5, "cached_input_price_per_million": 0.125,
        "price_source": "legacy-import", "approved": 1, "active": 0, "updated_at": catalog["updated_at"],
    }
    assert len(events) == 1
    assert {name: events[0][name] for name in original_usage} == original_usage
    assert old_usage["model"] == "removed-model"
    assert old_usage["estimated_cost_usd"] == 0.000000123456
    with migrated.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM offer_routes").fetchone()[0] == 1
        route = connection.execute("SELECT * FROM offer_routes").fetchone()
        assert route["upstream_model_id"] == "alpha"
        assert route["offer_id"]


def test_migration_maps_each_legacy_profile_to_brand_connection(tmp_path):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    with legacy.connect() as connection:
        connection.execute(
            "INSERT INTO upstream_profiles(id,name,provider_kind,base_url,encrypted_api_key,models_json,created_at) VALUES(?,?,?,?,?,?,?)",
            ("provider-second", "Old provider", "openai_compatible", "https://second.example/v1", "encrypted-second", '["beta"]', "2026-01-02T00:00:00+00:00"),
        )
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    _catalog(repository)
    _rerun_migrations(repository)

    with repository.connect() as connection:
        profiles = connection.execute("""SELECT b.migration_ref,b.name,b.identity_status,b.legacy_name_snapshot,
            c.legacy_profile_id,c.base_url,c.secret_ref,c.mapping_status,c.enabled,c.legacy_enabled
            FROM provider_connections c JOIN provider_brands b ON b.id=c.brand_id ORDER BY c.legacy_profile_id""").fetchall()

    assert [tuple(row) for row in profiles] == [
        ("provider-old", "Unknown legacy provider", "unknown", "Old provider", "provider-old", "https://provider.example/v1", "provider-old", "unmapped", 0, 1),
        ("provider-second", "Unknown legacy provider", "unknown", "Old provider", "provider-second", "https://second.example/v1", "provider-second", "unmapped", 0, 1),
    ]
    with repository.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM connection_models").fetchone()[0] == 2
        assert "encrypted_api_key" not in {row[1] for row in connection.execute("PRAGMA table_info(provider_connections)")}
        offer = connection.execute("SELECT approved,active FROM catalog_offers WHERE canonical_model_id='alpha'").fetchone()
        route = connection.execute("SELECT active FROM offer_routes WHERE upstream_model_id='alpha'").fetchone()
        assert tuple(offer) == (0, 0)
        assert route["active"] == 0


def test_model_approval_does_not_reenable_legacy_disabled_connection(tmp_path):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    with legacy.connect() as connection:
        connection.execute("UPDATE upstream_profiles SET enabled=0 WHERE id='provider-old'")
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    user = repository.upsert_user(subject="disabled-provider", email="disabled@example.test", name="Disabled")
    key = repository.create_user_key(user["id"], "Disabled provider", allowed_models_mode="all_approved")

    repository.add_catalog_model(
        provider_id="provider-old", model_id="alpha", provider_name="Old provider", capabilities=["text"],
        input_price_per_million=1.25, output_price_per_million=2.5, price_source="review", approved=False,
    )
    repository.add_catalog_model(
        provider_id="provider-old", model_id="alpha", provider_name="Old provider", capabilities=["text"],
        input_price_per_million=1.25, output_price_per_million=2.5, price_source="review", approved=True,
    )
    repository.add_catalog_model(
        provider_id="provider-old", model_id="alpha", provider_name="Old provider", capabilities=["text"],
        input_price_per_million=1.5, output_price_per_million=3, price_source="review-update", approved=True,
    )

    with repository.connect() as connection:
        state = connection.execute("""SELECT b.identity_status,c.mapping_status,c.enabled,c.legacy_enabled
            FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id
            WHERE c.legacy_profile_id='provider-old'""").fetchone()

    assert tuple(state) == ("mapped", "mapped", 0, 0)
    assert repository.list_models() == []
    assert repository.get_model("provider-old::alpha") is None
    assert repository.find_gateway_key(key["api_key"])["effective_model_ids"] == []


def test_migrations_are_idempotent(tmp_path):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    _catalog(repository)
    _rerun_migrations(repository)
    repository = PortalDatabase(str(path), key_pepper="p" * 40)

    def snapshot():
        with repository.connect() as connection:
            return {
                table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
                for table in ("portal_schema_migrations", "provider_brands", "provider_connections", "connection_models", "catalog_offers", "offer_routes", "price_versions")
            }

    first = snapshot()
    PortalDatabase(str(path), key_pepper="p" * 40)
    assert snapshot() == first
    with legacy.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM upstream_profiles").fetchone()[0] == 1


def test_migration_converts_caps_without_changing_usd_values(tmp_path):
    path = tmp_path / "portal.db"
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    user = repository.upsert_user(subject="member", email="member@example.test", name="Member")
    repository.set_user_policy(user["id"], allowance_usd=0.123456789, allowance_period="weekly", rpm_limit=40)
    key = repository.create_user_key(user["id"], "Nano cap", allowed_models_mode="all_approved")
    repository.update_user_key_policy(user["id"], key["id"], allowed_models_mode="all_approved", allowed_models=[], spend_limit_usd=0.000000001, spend_period="weekly", rpm_limit=40)
    _rerun_migrations(repository)

    with repository.connect() as connection:
        user_before = connection.execute("SELECT allowance_usd,allowance_timezone FROM portal_users WHERE id=?", (user["id"],)).fetchone()
        key_before = connection.execute("SELECT spend_limit_usd FROM portal_keys WHERE id=?", (key["id"],)).fetchone()
    migrated = PortalDatabase(str(path), key_pepper="p" * 40)
    with migrated.connect() as connection:
        allowance = connection.execute("SELECT amount_nano_usd,period,timezone FROM user_allowances WHERE user_id=? AND active=1", (user["id"],)).fetchone()
        cap = connection.execute("SELECT cap_nano_usd FROM provider_budgets WHERE key_id=?", (key["id"],)).fetchone()

    assert user_before["allowance_usd"] == 0.123456789
    assert user_before["allowance_timezone"] == "UTC"
    assert key_before["spend_limit_usd"] == 0.000000001
    assert tuple(allowance) == (123456789, "weekly", "Europe/Berlin")
    assert cap["cap_nano_usd"] == 1


def test_new_offer_routes_and_prices_enforce_unique_identity(tmp_path):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    _catalog(repository)
    _rerun_migrations(repository)

    with repository.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='price_versions'").fetchone()[0] == 1
        offer = connection.execute("SELECT id FROM catalog_offers").fetchone()[0]
        route = connection.execute("SELECT connection_id FROM offer_routes").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO offer_routes(id,offer_id,connection_id,upstream_model_id) VALUES('duplicate','legacy-offer:provider-old:alpha',?,'other')", (route,))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO price_versions(id,offer_id,input_rate,is_active,effective_at) VALUES('duplicate-price',?,'3',1,'2026-09-26')", (offer,))
    with legacy.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM upstream_profiles").fetchone()[0] == 1


def test_new_usage_events_store_nano_charge_and_immutable_catalog_snapshots(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="member", email="member@example.test", name="Member")
    key = repository.create_user_key(user["id"], "Snapshot key", allowed_models_mode="all_approved")

    event_id = repository.record_usage(
        user["id"], key["id"], model="canonical-v2", input_tokens=3, output_tokens=2, total_tokens=5,
        latency_ms=11, status="success", estimated_cost_usd=0.000000007,
        amount_nano_usd=7, brand_id="brand-1", canonical_model_id="canonical-v2",
        offer_route_id="route-1", price_version_id="price-1",
        route_snapshot={"connection_id": "connection-1", "upstream_model_id": "upstream-v1"},
        price_snapshot={"input_rate": "1.25", "output_rate": "2.5"},
    )

    with repository.connect() as connection:
        event = connection.execute("SELECT * FROM portal_usage_events WHERE id=?", (event_id,)).fetchone()
    assert event["estimated_cost_usd"] == 0.000000007
    assert event["amount_nano_usd"] == 7
    assert event["brand_id"] == "brand-1"
    assert event["canonical_model_id"] == "canonical-v2"
    assert event["offer_route_id"] == "route-1"
    assert event["price_version_id"] == "price-1"
    assert event["route_snapshot_json"] == '{"connection_id": "connection-1", "upstream_model_id": "upstream-v1"}'
    assert event["price_snapshot_v2_json"] == '{"input_rate": "1.25", "output_rate": "2.5"}'


@pytest.mark.parametrize("field,bad_rate", [
    ("input_rate", "1.2.3"),
    ("output_rate", "1..2"),
    ("cached_input_rate", "1.2.3"),
    ("cached_input_rate", "-0.1"),
])
def test_price_write_boundary_rejects_malformed_decimal_rates(tmp_path, field, bad_rate):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    _catalog(repository)
    _rerun_migrations(repository)
    with repository.connect() as connection:
        offer_id = connection.execute("SELECT id FROM catalog_offers WHERE canonical_model_id='alpha'").fetchone()[0]
    values = {"input_rate": "1.25", "output_rate": "2.5", "cached_input_rate": "0.125"}
    values[field] = bad_rate

    with pytest.raises(ValueError, match="decimal"):
        repository.add_price_version(offer_id, **values)


@pytest.mark.parametrize("field", ["input_rate", "output_rate", "cached_input_rate"])
def test_price_table_rejects_malformed_decimal_rates(tmp_path, field):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    _catalog(repository)
    _rerun_migrations(repository)
    with repository.connect() as connection:
        offer_id = connection.execute("SELECT id FROM catalog_offers WHERE canonical_model_id='alpha'").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"INSERT INTO price_versions(id,offer_id,{field},is_active,effective_at) VALUES('malformed',?,'1.2.3',0,'2026-09-26')",
                (offer_id,),
            )


def test_subnano_migration_preserves_display_values_and_rounds_enforcement_up(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="nano", email="nano@example.test", name="Nano")
    repository.set_user_policy(user["id"], allowance_usd=0.0000000001, allowance_period="weekly", rpm_limit=30)
    key = repository.create_user_key(user["id"], "Subnano", allowed_models_mode="all_approved", spend_limit_usd=0.0000000001, spend_period="weekly")
    event_id = repository.record_usage(
        user["id"], key["id"], model="old", input_tokens=1, output_tokens=0, total_tokens=1,
        latency_ms=1, status="success", estimated_cost_usd=0.0000000001,
    )
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO portal_budget_reservations(id,owner_user_id,key_id,estimated_cost_usd,created_at,status) VALUES('subnano-reservation',?,?,?,?,'active')",
            (user["id"], key["id"], 0.0000000001, "2026-09-26T00:00:00+00:00"),
        )
    _rerun_migrations(repository)
    with repository.connect() as connection:
        connection.execute("UPDATE provider_budgets SET cap_nano_usd=0 WHERE key_id=?", (key["id"],))
        connection.execute("UPDATE user_allowances SET amount_nano_usd=0 WHERE user_id=?", (user["id"],))
        connection.execute("UPDATE portal_budget_reservations_v2 SET amount_nano_usd=0 WHERE id='subnano-reservation'")
        connection.execute("DROP TRIGGER portal_usage_no_update")
        connection.execute("UPDATE portal_usage_events SET amount_nano_usd=NULL WHERE id=?", (event_id,))
        connection.execute("CREATE TRIGGER portal_usage_no_update BEFORE UPDATE ON portal_usage_events BEGIN SELECT RAISE(ABORT, 'portal usage events are immutable'); END")
    with repository.connect() as connection:
        connection.execute("DELETE FROM portal_schema_migrations")
    repository.init_schema()

    with repository.connect() as connection:
        allowance = connection.execute("SELECT allowance_usd FROM portal_users WHERE id=?", (user["id"],)).fetchone()[0]
        original_cap = connection.execute("SELECT spend_limit_usd FROM portal_keys WHERE id=?", (key["id"],)).fetchone()[0]
        original_charge = connection.execute("SELECT estimated_cost_usd,amount_nano_usd FROM portal_usage_events WHERE id=?", (event_id,)).fetchone()
        migrated_cap = connection.execute("SELECT cap_nano_usd FROM provider_budgets WHERE key_id=?", (key["id"],)).fetchone()[0]
        migrated_allowance = connection.execute("SELECT amount_nano_usd FROM user_allowances WHERE user_id=?", (user["id"],)).fetchone()[0]
        migrated_reservation = connection.execute("SELECT amount_nano_usd FROM portal_budget_reservations_v2 WHERE id='subnano-reservation'").fetchone()[0]

    assert allowance == original_cap == original_charge["estimated_cost_usd"] == 0.0000000001
    assert migrated_cap == migrated_allowance == 0
    assert migrated_reservation == original_charge["amount_nano_usd"] == 1
    assert Decimal(str(original_charge["estimated_cost_usd"])) <= Decimal(original_charge["amount_nano_usd"]) / Decimal(1_000_000_000)


def test_supplied_nano_charge_cannot_understate_legacy_usd_charge(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="nano", email="nano@example.test", name="Nano")
    key = repository.create_user_key(user["id"], "Subnano", allowed_models_mode="all_approved")

    with pytest.raises(ValueError, match="understate"):
        repository.record_usage(
            user["id"], key["id"], model="m", input_tokens=0, output_tokens=0, total_tokens=0,
            latency_ms=1, status="success", estimated_cost_usd=0.0000000001, amount_nano_usd=0,
        )
