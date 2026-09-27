import json
import sqlite3
from decimal import Decimal
from datetime import datetime, timezone

import pytest
from cryptography.fernet import Fernet

from app.database import Database
from app.portal_db import PortalDatabase


def _budget_setup(tmp_path):
    database_path = str(tmp_path / "budget.db")
    legacy = Database(database_path, "legacy-budget-fixture-pepper", Fernet.generate_key().decode())
    repository = PortalDatabase(database_path, key_pepper="p" * 40)
    owner = repository.upsert_user(subject="budget-member", email="budget@example.test", name="Budget member", role="operator")
    key_a = repository.create_user_key(owner["id"], "A", allowed_models_mode="all_approved")
    key_b = repository.create_user_key(owner["id"], "B", allowed_models_mode="all_approved")
    with repository.connect() as connection:
        connection.execute("INSERT INTO provider_brands(id,name,migration_ref,created_at,identity_status,slug) VALUES('brand-a','A',NULL,'2026-01-01T00:00:00+00:00','mapped','brand-a')")
        connection.execute("INSERT INTO provider_brands(id,name,migration_ref,created_at,identity_status,slug) VALUES('brand-b','B',NULL,'2026-01-01T00:00:00+00:00','mapped','brand-b')")
        connection.execute("INSERT INTO provider_connections(id,brand_id,legacy_profile_id,base_url,provider_kind,secret_ref,enabled,created_at,mapping_status,label) VALUES('conn-a','brand-a','conn-a','https://a.example','openai_compatible','secret',1,'2026-01-01T00:00:00+00:00','mapped','A')")
        connection.execute("INSERT INTO provider_connections(id,brand_id,legacy_profile_id,base_url,provider_kind,secret_ref,enabled,created_at,mapping_status,label) VALUES('conn-b','brand-b','conn-b','https://b.example','openai_compatible','secret',1,'2026-01-01T00:00:00+00:00','mapped','B')")
        connection.execute("INSERT INTO catalog_offers(id,brand_id,canonical_model_id,display_name,approved,active,updated_at) VALUES('offer-a','brand-a','model-a','Model A',1,1,'2026-01-01T00:00:00+00:00')")
        connection.execute("INSERT INTO catalog_offers(id,brand_id,canonical_model_id,display_name,approved,active,updated_at) VALUES('offer-b','brand-b','model-b','Model B',1,1,'2026-01-01T00:00:00+00:00')")
        connection.execute("INSERT INTO offer_routes(id,offer_id,connection_id,upstream_model_id,active) VALUES('route-a','offer-a','conn-a','model-a',1)")
        connection.execute("INSERT INTO offer_routes(id,offer_id,connection_id,upstream_model_id,active) VALUES('route-b','offer-b','conn-b','model-b',1)")
        connection.execute("INSERT INTO connection_models(connection_id,upstream_model_id,metadata_json,active,is_stale,last_seen_at) VALUES('conn-a','model-a','{}',1,0,'2026-01-01T00:00:00+00:00')")
        connection.execute("INSERT INTO connection_models(connection_id,upstream_model_id,metadata_json,active,is_stale,last_seen_at) VALUES('conn-b','model-b','{}',1,0,'2026-01-01T00:00:00+00:00')")
        connection.execute("INSERT INTO price_versions(id,offer_id,input_rate,output_rate,source,is_active,effective_at) VALUES('price-approved','offer-a','0.001','0.002','operator',1,'2026-01-01T00:00:00+00:00')")
        connection.execute("INSERT INTO price_versions(id,offer_id,input_rate,output_rate,source,is_active,effective_at) VALUES('price-b','offer-b','0.001','0.002','operator',1,'2026-01-01T00:00:00+00:00')")
    with legacy.connect() as upstream:
        for connection_id, name, model_id in (("conn-a", "A", "model-a"), ("conn-b", "B", "model-b")):
            upstream.execute("INSERT INTO upstream_profiles(id,name,provider_kind,base_url,encrypted_api_key,models_json,created_at) VALUES(?,?,?,?,?,?,?)",
                             (connection_id, name, "openai_compatible", f"https://{name.lower()}.example/v1", "encrypted-test-secret", json.dumps([model_id]), "2026-01-01T00:00:00+00:00"))
    return repository, owner, key_a, key_b


def test_user_allowance_is_shared_across_keys_and_connections(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    now = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
    repository.assign_user_allowance(owner["id"], 100, "weekly", "operator")
    reservation = repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 60, now, None)
    assert reservation is not None
    assert repository.reserve_request_budget(owner["id"], second["id"], "offer-b", "conn-b", 41, now, None) is None


def test_allowance_resets_at_berlin_boundary_and_expires_old_credit(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    before = datetime(2026, 9, 27, 21, 59, tzinfo=timezone.utc)
    after = datetime(2026, 9, 27, 22, 1, tzinfo=timezone.utc)
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 100, before, None)
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 100, after, None)


def test_usage_with_offset_timestamp_is_compared_by_instant_at_berlin_reset(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    repository.record_usage(owner["id"], first["id"], model="prior-day", input_tokens=1, output_tokens=1,
                            total_tokens=2, latency_ms=1, status="ok", estimated_cost_usd=0.00000006,
                            amount_nano_usd=60, occurred_at="2026-09-27T23:30:00+02:00")
    reservation = repository.reserve_request_budget(owner["id"], second["id"], "offer-b", "conn-b", 100,
                                                    datetime(2026, 9, 27, 22, 1, tzinfo=timezone.utc), None)
    assert reservation is not None


def test_current_period_includes_legacy_usage_after_key_archive(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    repository.import_legacy_key_snapshots(owner["id"], [{"id": 99, "label": "Old archived key"}])
    repository.import_legacy_usage(owner["id"], [{"id": 101, "provider_key_id": 99, "timestamp": "2026-09-27T09:00:00+00:00", "model": "legacy", "estimated_cost_usd": 0.00000006, "upstream_profile_id": "conn-a"}])
    repository.archive_user_key(owner["id"], "legacy-key-99")
    assert repository.reserve_request_budget(owner["id"], second["id"], "offer-a", "conn-a", 41, datetime(2026, 9, 27, 10, tzinfo=timezone.utc), None) is None


def test_unpriced_prior_delivery_fails_closed_under_user_allowance(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    repository.record_usage(owner["id"], first["id"], model="unknown-cost", input_tokens=None, output_tokens=None,
                            total_tokens=None, latency_ms=None, status="error", estimated_cost_usd=None,
                            occurred_at=datetime.now(timezone.utc).isoformat())
    assert repository.reserve_request_budget(owner["id"], second["id"], "offer-b", "conn-b", 1,
                                             datetime.now(timezone.utc), None) is None


def test_provider_cap_includes_connection_usage_from_current_period(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    repository.set_connection_budget("conn-a", 100, "daily", 0, "operator")
    repository.record_usage(owner["id"], first["id"], model="model-a", input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=1, status="ok", estimated_cost_usd=0, amount_nano_usd=60, provider_id="conn-a")
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 41, datetime.now(timezone.utc), None) is None


def test_provider_cap_is_scoped_to_selected_connection_and_period(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    repository.set_connection_budget("conn-a", 100, "daily", 0, "operator")
    repository.record_usage(owner["id"], first["id"], model="model-a", input_tokens=1, output_tokens=1, total_tokens=2, latency_ms=1, status="ok", estimated_cost_usd=0, amount_nano_usd=100, provider_id="conn-a", occurred_at="2026-09-26T10:00:00+00:00")
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-b", "conn-b", 100, datetime(2026, 9, 27, 10, tzinfo=timezone.utc), None)


def test_operator_connection_catalog_reports_connection_budget_and_usage(tmp_path):
    repository, owner, key, _ = _budget_setup(tmp_path)
    repository.set_connection_budget("conn-a", 100, "daily", 20, "operator")
    repository.record_usage(owner["id"], key["id"], model="model-a", input_tokens=1, output_tokens=1,
        total_tokens=2, latency_ms=1, status="ok", estimated_cost_usd=0.00000003,
        amount_nano_usd=30, provider_id="conn-a")

    record = next(item for item in repository.list_operator_connections() if item["id"] == "conn-a")

    assert record["brandSlug"] == "brand-a"
    assert record["brandName"] == "A"
    assert record["connectionLabel"] == "A"
    assert record["providerKind"] == "openai_compatible"
    assert record["budget"] == {
        "limitUsd": "0.0000001", "period": "daily", "reserveUsd": "0.00000002",
        "usedUsd": "0.00000003", "reservedUsd": "0", "remainingUsd": "0.00000005",
        "resetAt": record["budget"]["resetAt"],
    }
    assert record["budget"]["resetAt"]


def test_all_usage_filters_run_before_limit_and_do_not_expose_prompt_fields(tmp_path):
    repository, owner, key, _ = _budget_setup(tmp_path)
    for model, provider_id, status, occurred_at in (
        ("alpha", "conn-a", "ok", "2026-09-26T22:30:00+00:00"),
        ("beta", "conn-b", "error", "2026-09-27T10:00:00+00:00"),
        ("alpha", "conn-a", "rejected", "2026-09-27T11:00:00+00:00"),
    ):
        repository.record_usage(owner["id"], key["id"], model=model, input_tokens=1, output_tokens=1,
            total_tokens=2, latency_ms=1, status=status, estimated_cost_usd=0.00000001,
            provider_id=provider_id, occurred_at=occurred_at)

    rows = repository.list_all_usage(limit=1, brand_slug="brand-a", connection_id="conn-a",
        model="alpha", from_date="2026-09-27", to_date="2026-09-27", outcome="success")

    assert len(rows) == 1
    assert rows[0]["model_id"] == "alpha"
    assert rows[0]["status"] == "ok"
    assert "prompt" not in rows[0] and "completion" not in rows[0]


def test_disabled_connection_cannot_receive_a_new_budget_reservation(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    with repository.connect() as connection:
        connection.execute("UPDATE provider_connections SET enabled=0 WHERE id='conn-a'")
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 10,
                                             datetime.now(timezone.utc), None) is None


def test_reserve_is_subtracted_from_provider_available_headroom(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.set_connection_budget("conn-a", 100, "daily", 0, "operator")
    now = datetime.now(timezone.utc)
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 60, now, None)
    assert repository.reserve_request_budget(owner["id"], second["id"], "offer-a", "conn-a", 41, now, None) is None


def test_key_cap_only_tightens_user_allowance(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.set_user_policy(owner["id"], allowance_usd=0.0000001, allowance_period="daily", rpm_limit=None)
    with repository.connect() as connection:
        connection.execute("INSERT INTO provider_budgets(id,key_id,cap_nano_usd,period,created_at) VALUES('key-cap',?,40,'daily','2026-01-01')", (first["id"],))
    now = datetime.now(timezone.utc)
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 41, now, None) is None
    assert repository.reserve_request_budget(owner["id"], second["id"], "offer-b", "conn-b", 101, now, None) is None
    assert repository.reserve_request_budget(owner["id"], second["id"], "offer-a", "conn-a", 100, now, None)


def test_all_budget_scopes_reserve_atomically(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    repository.set_connection_budget("conn-a", 100, "daily", 0, "operator")
    with repository.connect() as connection:
        connection.execute("INSERT INTO provider_budgets(id,key_id,cap_nano_usd,period,created_at) VALUES('key-cap',?,100,'daily','2026-01-01')", (first["id"],))
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 60, datetime.now(timezone.utc), 50) is None
    with repository.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM portal_budget_reservations_v2 WHERE status='active'").fetchone()[0] == 0


def test_concurrent_last_credit_requests_allow_only_one(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    now = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda key: repository.reserve_request_budget(owner["id"], key["id"], "offer-a", "conn-a", 60, now, None), (first, second)))
    assert sum(result is not None for result in results) == 1


def test_released_reservation_does_not_count_as_spent(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    now = datetime.now(timezone.utc)
    reservation = repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 100, now, None)
    with pytest.raises(ValueError, match="known absent"):
        repository.release_request_budget(reservation.id, delivery_known_absent=False)
    assert repository.release_request_budget(reservation.id, delivery_known_absent=True)
    assert repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 100, now, None)


def test_settlement_uses_actual_reported_tokens_and_approved_price_snapshot(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    reservation = repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 100, datetime.now(timezone.utc), None)
    repository.settle_request_budget(reservation.id, 100, {"input_tokens": 3, "output_tokens": 2})
    event = repository.list_usage(owner["id"])[0]
    assert (event["input_tokens"], event["output_tokens"], event["amount_nano_usd"], event["price_version_id"]) == (3, 2, 7, "price-approved")


def test_missing_usage_settles_estimate_without_claiming_zero(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    reservation = repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 100, datetime.now(timezone.utc), None)
    repository.settle_request_budget(reservation.id, 100, None)
    event = repository.list_usage(owner["id"])[0]
    assert event["amount_nano_usd"] == 100
    assert event["input_tokens"] is None and event["output_tokens"] is None and event["total_tokens"] is None


@pytest.mark.parametrize("outcome,delivered", [
    ("connect_failure", False),
    ("upstream_error", True),
    ("provider_timeout", True),
    ("client_disconnect", True),
    ("partial_stream", True),
])
def test_request_exit_settles_conservatively_unless_delivery_is_known_absent(tmp_path, outcome, delivered):
    repository, owner, first, _ = _budget_setup(tmp_path)
    reservation = repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 60, datetime.now(timezone.utc), None)
    if delivered:
        repository.settle_request_budget(reservation.id, reservation.amount_nano_usd, {"status": outcome})
        assert repository.list_usage(owner["id"])[0]["amount_nano_usd"] == 60
    else:
        assert repository.release_request_budget(reservation.id, delivery_known_absent=True)
        assert repository.list_usage(owner["id"]) == []


def test_budget_reservation_can_only_be_settled_once(tmp_path):
    repository, owner, first, _ = _budget_setup(tmp_path)
    reservation = repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 60, datetime.now(timezone.utc), None)
    repository.settle_request_budget(reservation.id, 60, None)
    with pytest.raises(ValueError, match="not active"):
        repository.settle_request_budget(reservation.id, 60, None)
    assert len(repository.list_usage(owner["id"])) == 1


def test_expired_reservation_is_conservatively_settled(tmp_path):
    repository, owner, first, second = _budget_setup(tmp_path)
    repository.assign_user_allowance(owner["id"], 100, "daily", "operator")
    reserved_at = datetime(2026, 9, 27, 10, tzinfo=timezone.utc)
    reservation = repository.reserve_request_budget(owner["id"], first["id"], "offer-a", "conn-a", 60, reserved_at, None)
    assert reservation is not None
    now = datetime(2026, 9, 27, 10, 11, tzinfo=timezone.utc)
    assert repository.reserve_request_budget(owner["id"], second["id"], "offer-b", "conn-b", 41, now, None) is None
    event = repository.list_usage(owner["id"])[0]
    assert event["amount_nano_usd"] == 60
    assert event["total_tokens"] is None


def test_local_auth_migration_preserves_hca_identity_invite_history_and_is_idempotent(tmp_path):
    path = tmp_path / "portal.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE portal_users (
                id TEXT PRIMARY KEY, oidc_subject TEXT NOT NULL UNIQUE, email TEXT,
                email_verified INTEGER NOT NULL DEFAULT 0, display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('operator','developer')),
                status TEXT NOT NULL DEFAULT 'active', allowance_usd REAL,
                allowance_period TEXT, rpm_limit INTEGER,
                allowance_timezone TEXT NOT NULL DEFAULT 'UTC', created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL
            );
            CREATE TABLE portal_invites (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, issuer_user_id TEXT NOT NULL,
                bound_email TEXT, expires_at TEXT NOT NULL, consumed_at TEXT,
                consumed_by_user_id TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE portal_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO portal_schema_migrations VALUES(1,'2026-01-01T00:00:00+00:00');
            INSERT INTO portal_schema_migrations VALUES(2,'2026-01-02T00:00:00+00:00');
            INSERT INTO portal_schema_migrations VALUES(3,'2026-01-03T00:00:00+00:00');
            INSERT INTO portal_users(id,oidc_subject,email,email_verified,display_name,role,created_at,last_login_at)
            VALUES('legacy-user','ident!hca-subject','legacy@example.test',1,'Legacy HCA','developer','2026-01-04','2026-02-05');
            INSERT INTO portal_invites(id,token_hash,issuer_user_id,bound_email,expires_at,consumed_at,consumed_by_user_id,created_at)
            VALUES('legacy-invite','hashed-token','legacy-operator','legacy@example.test','2027-01-01','2026-01-05','legacy-user','2026-01-04');
        """)

    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    with repository.connect() as connection:
        user_before = tuple(connection.execute(
            "SELECT id,oidc_subject,email,email_verified,display_name,role,created_at,last_login_at FROM portal_users WHERE id='legacy-user'"
        ).fetchone())
        invite_before = tuple(connection.execute(
            "SELECT id,token_hash,issuer_user_id,bound_email,expires_at,consumed_at,consumed_by_user_id,created_at FROM portal_invites WHERE id='legacy-invite'"
        ).fetchone())
        columns = {row[1] for row in connection.execute("PRAGMA table_info(portal_users)")}
        invite_columns = {row[1] for row in connection.execute("PRAGMA table_info(portal_invites)")}
        migrations = [tuple(row) for row in connection.execute("SELECT version,applied_at FROM portal_schema_migrations ORDER BY version")]
        first_applied_at = migrations[-1][1]

    assert "username_normalized" in columns
    assert "password_hash" in columns
    assert "max_uses" in invite_columns
    assert "uses_count" in invite_columns
    assert "revoked_at" in invite_columns
    assert migrations[-1][0] == 8
    assert user_before == ("legacy-user", "ident!hca-subject", "legacy@example.test", 1, "Legacy HCA", "developer", "2026-01-04", "2026-02-05")
    assert invite_before == ("legacy-invite", "hashed-token", "legacy-operator", "legacy@example.test", "2027-01-01", "2026-01-05", "legacy-user", "2026-01-04")

    repository.init_schema()
    with repository.connect() as connection:
        rerun = [tuple(row) for row in connection.execute("SELECT version,applied_at FROM portal_schema_migrations ORDER BY version")]
    assert rerun == migrations
    assert rerun[-1][1] == first_applied_at


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


def test_legacy_offer_requires_exact_active_discovery_before_routing(tmp_path):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    with legacy.connect() as connection:
        connection.execute("UPDATE upstream_profiles SET models_json='[\"different-model\"]' WHERE id='provider-old'")
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    user = repository.upsert_user(subject="undiscovered", email="undiscovered@example.test", name="Undiscovered")
    key = repository.create_user_key(user["id"], "Undiscovered model", allowed_models_mode="all_approved")
    repository.add_catalog_model(
        provider_id="provider-old", model_id="alpha", provider_name="Old provider", capabilities=["text"],
        input_price_per_million=1.25, output_price_per_million=2.5,
        price_source="reviewed", approved=True, active=True,
    )
    with repository.connect() as connection:
        connection.execute("UPDATE provider_connections SET enabled=1 WHERE legacy_profile_id='provider-old'")

    assert repository.list_models() == []
    assert repository.get_model("provider-old::alpha") is None
    assert repository.find_gateway_key(key["api_key"])["effective_model_ids"] == []


def test_model_availability_changes_only_the_exact_brand_offer(tmp_path):
    from datetime import datetime, timezone

    from app.catalog import DiscoveredModel

    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    with legacy.connect() as connection:
        connection.execute("UPDATE upstream_profiles SET models_json=?,enabled=1 WHERE id='provider-old'", ('["shared-model"]',))
        connection.execute(
            "INSERT INTO upstream_profiles(id,name,provider_kind,base_url,encrypted_api_key,models_json,created_at,enabled) VALUES(?,?,?,?,?,?,?,1)",
            ("provider-second", "Second provider", "openai_compatible", "https://second.example/v1", "encrypted-second", '["shared-model"]', "2026-01-02T00:00:00+00:00"),
        )
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    first = repository.register_connection("provider-old", "vendor-one", "Vendor One", "Primary")
    second = repository.register_connection("provider-second", "vendor-two", "Vendor Two", "Primary")
    for provider_id, name in (("provider-old", "Vendor One"), ("provider-second", "Vendor Two")):
        repository.add_catalog_model(
            provider_id=provider_id, model_id="shared-model", provider_name=name, capabilities=["text"],
            input_price_per_million=1, output_price_per_million=2, price_source="reviewed", approved=True, active=True,
        )
    repository.apply_discovery(first.id, [DiscoveredModel("shared-model")], datetime.now(timezone.utc))
    repository.apply_discovery(second.id, [DiscoveredModel("shared-model")], datetime.now(timezone.utc))

    changed = repository.set_model_active("shared-model", active=False)
    assert changed == 0
    with repository.connect() as connection:
        before_scoped_change = [tuple(row) for row in connection.execute("""SELECT brand.slug,offer.active
            FROM catalog_offers offer JOIN provider_brands brand ON brand.id=offer.brand_id
            WHERE offer.canonical_model_id='shared-model' ORDER BY brand.slug""")]
    assert before_scoped_change == [("vendor-one", 1), ("vendor-two", 1)]

    changed = repository.set_model_active("shared-model", active=False, provider_id="provider-old")
    assert changed == 1
    with repository.connect() as connection:
        after_scoped_change = [tuple(row) for row in connection.execute("""SELECT brand.slug,offer.active
            FROM catalog_offers offer JOIN provider_brands brand ON brand.id=offer.brand_id
            WHERE offer.canonical_model_id='shared-model' ORDER BY brand.slug""")]
    assert after_scoped_change == [("vendor-one", 0), ("vendor-two", 1)]


def test_legacy_model_uses_its_exact_connection_within_multi_connection_brand(tmp_path):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    with legacy.connect() as connection:
        connection.execute(
            "INSERT INTO upstream_profiles(id,name,provider_kind,base_url,encrypted_api_key,created_at,enabled) VALUES(?,?,?,?,?,?,?)",
            ("provider-other", "Other connection", "openai_compatible", "https://other.example/v1", "other-encrypted", "2026-01-02T00:00:00+00:00", 1),
        )
        connection.execute("UPDATE upstream_profiles SET enabled=0 WHERE id='provider-old'")
    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    user = repository.upsert_user(subject="multi-connection", email="multi@example.test", name="Multi")
    key = repository.create_user_key(user["id"], "Exact route", allowed_models_mode="all_approved")
    repository.add_catalog_model(
        provider_id="provider-old", model_id="legacy-model", provider_name="Shared display name",
        capabilities=["text"], input_price_per_million=1, output_price_per_million=2,
        price_source="legacy", approved=True, active=True,
    )

    with repository.connect() as connection:
        brand_id = connection.execute("SELECT id FROM provider_brands WHERE migration_ref='provider-old'").fetchone()[0]
        connection.execute("UPDATE provider_connections SET brand_id=?,mapping_status='mapped',enabled=1 WHERE legacy_profile_id='provider-other'", (brand_id,))
        exact_connection = connection.execute("SELECT enabled FROM provider_connections WHERE legacy_profile_id='provider-old'").fetchone()[0]
        other_connection = connection.execute("SELECT enabled FROM provider_connections WHERE legacy_profile_id='provider-other'").fetchone()[0]

    assert (exact_connection, other_connection) == (0, 1)
    assert repository.list_models() == []
    assert repository.get_model("provider-old::legacy-model") is None
    assert repository.find_gateway_key(key["api_key"])["effective_model_ids"] == []


def test_approved_orphan_legacy_catalog_stays_unknown_and_unroutable(tmp_path):
    path = tmp_path / "portal.db"
    legacy, _ = _legacy_database(path)
    with legacy.connect() as connection:
        connection.execute("DELETE FROM upstream_profiles")

    repository = PortalDatabase(str(path), key_pepper="p" * 40)
    with repository.connect() as connection:
        connection.execute(
            "INSERT INTO portal_catalog_models(provider_id,model_id,provider_name,capabilities_json,input_price_per_million,output_price_per_million,price_source,approved,active,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("orphan-provider", "orphan-model", "Unverified label", '["text"]', 1, 2, "legacy", 0, 1, "2026-01-03T00:00:00+00:00"),
        )
        connection.execute("DELETE FROM portal_schema_migrations")
    repository.init_schema()

    user = repository.upsert_user(subject="orphan", email="orphan@example.test", name="Orphan")
    key = repository.create_user_key(user["id"], "Orphan key", allowed_models_mode="all_approved")
    repository.add_catalog_model(
        provider_id="orphan-provider", model_id="orphan-model", provider_name="Unverified label",
        capabilities=["text"], input_price_per_million=1, output_price_per_million=2,
        price_source="legacy", approved=True, active=True,
    )

    with repository.connect() as connection:
        identity = connection.execute("""SELECT b.name,b.identity_status,c.mapping_status,c.legacy_profile_id,c.enabled
            FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id
            WHERE b.migration_ref='orphan-provider'""").fetchone()
        legacy_catalog = connection.execute("""SELECT provider_name,capabilities_json,input_price_per_million,
            output_price_per_million,price_source,approved,active FROM portal_catalog_models
            WHERE provider_id='orphan-provider' AND model_id='orphan-model'""").fetchone()
        historical_price = connection.execute("""SELECT input_rate,output_rate,cached_input_rate,source
            FROM price_versions WHERE id='legacy-price:orphan-provider:orphan-model'""").fetchone()
        route = connection.execute("SELECT active FROM offer_routes WHERE id='legacy-route:orphan-provider:orphan-model'").fetchone()

    assert tuple(identity) == ("Unknown legacy provider", "unknown", "unmapped", None, 0)
    assert tuple(legacy_catalog) == ("Unverified label", '["text"]', 1, 2, "legacy", 1, 1)
    assert tuple(historical_price) == ("1", "2", None, "legacy")
    assert route["active"] == 0
    assert repository.list_models() == []
    assert repository.get_model("orphan-provider::orphan-model") is None
    assert repository.find_gateway_key(key["api_key"])["effective_model_ids"] == []


def test_approved_catalog_without_legacy_profile_or_connection_stays_unmapped(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="unconfigured", email="unconfigured@example.test", name="Unconfigured")
    key = repository.create_user_key(user["id"], "Unconfigured key", allowed_models_mode="all_approved")

    repository.add_catalog_model(
        provider_id="not-configured", model_id="orphan-model", provider_name="Unverified label",
        capabilities=["text"], input_price_per_million=1, output_price_per_million=2,
        price_source="catalog-import", approved=True, active=True,
    )

    with repository.connect() as connection:
        identity = connection.execute("""SELECT b.name,b.identity_status,c.legacy_profile_id,c.mapping_status,c.enabled
            FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id
            WHERE b.migration_ref='not-configured'""").fetchone()
        route = connection.execute("""SELECT active FROM offer_routes
            WHERE id='legacy-route:not-configured:orphan-model'""").fetchone()
        legacy_catalog = connection.execute("""SELECT provider_name,capabilities_json,input_price_per_million,
            output_price_per_million,price_source,approved,active FROM portal_catalog_models
            WHERE provider_id='not-configured' AND model_id='orphan-model'""").fetchone()
        price = connection.execute("""SELECT input_rate,output_rate,source FROM price_versions
            WHERE offer_id='legacy-offer:not-configured:orphan-model' AND is_active=1""").fetchone()

    assert tuple(identity) == ("Unknown legacy provider", "unknown", None, "unmapped", 0)
    assert route["active"] == 0
    assert tuple(legacy_catalog) == ("Unverified label", '["text"]', 1, 2, "catalog-import", 1, 1)
    assert tuple(price) == ("1", "2", "catalog-import")
    assert repository.list_models() == []
    assert repository.get_model("not-configured::orphan-model") is None
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
    assert user_before["allowance_timezone"] == "Europe/Berlin"
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
