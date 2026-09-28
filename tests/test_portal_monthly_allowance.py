import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.portal_api import PortalService, create_portal_router
from app.portal_db import PortalDatabase


def test_monthly_user_allowance_is_shared_across_keys_and_keeps_history(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    user = repository.upsert_user(subject="monthly-user", email="monthly@example.test", name="Monthly")

    repository.assign_user_allowance(user["id"], 7_000_000_000, "monthly", "operator")
    repository.assign_user_allowance(user["id"], 6_000_000_000, "monthly", "operator")

    with repository.connect() as connection:
        records = connection.execute(
            "SELECT amount_nano_usd,period,active FROM user_allowances WHERE user_id=? ORDER BY rowid",
            (user["id"],),
        ).fetchall()

    assert [tuple(record) for record in records] == [
        (7_000_000_000, "monthly", 0), (6_000_000_000, "monthly", 1),
    ]


def test_invalid_invite_does_not_create_an_account_or_allowance(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)

    with pytest.raises(PermissionError):
        repository.create_local_account_with_invite(
            raw_token="invalid", username="no-account", password_hash="hash", display_name="No account",
            default_allowance_nano_usd=7_000_000_000,
        )

    with repository.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM portal_users WHERE username='no-account'").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM user_allowances").fetchone()[0] == 0


def test_failed_invite_consumption_rolls_back_account_and_default_allowance(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    operator = repository.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    invite, token = repository.create_invite(issuer_user_id=operator["id"])
    with repository.connect() as connection:
        connection.execute(
            "CREATE TRIGGER reject_invite_use BEFORE UPDATE ON portal_invites BEGIN SELECT RAISE(ABORT,'invite write rejected'); END"
        )

    with pytest.raises(sqlite3.IntegrityError, match="invite write rejected"):
        repository.create_local_account_with_invite(
            raw_token=token, username="rolled-back", password_hash="hash", display_name="Rolled back",
            default_allowance_nano_usd=7_000_000_000,
        )

    with repository.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM portal_users WHERE username='rolled-back'").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM user_allowances").fetchone()[0] == 0
        assert connection.execute("SELECT uses_count FROM portal_invites WHERE id=?", (invite["id"],)).fetchone()[0] == 0


def test_monthly_migration_preserves_allowance_history_invites_keys_usage_and_reservations(tmp_path):
    path = tmp_path / "legacy-portal.db"
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute(
            """CREATE TABLE portal_users (
                id TEXT PRIMARY KEY, oidc_subject TEXT UNIQUE, email TEXT,
                email_verified INTEGER NOT NULL DEFAULT 0, display_name TEXT NOT NULL,
                role TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', allowance_usd REAL,
                allowance_period TEXT CHECK(allowance_period IS NULL OR allowance_period IN ('daily','weekly')),
                rpm_limit INTEGER, allowance_timezone TEXT NOT NULL DEFAULT 'UTC',
                created_at TEXT NOT NULL, last_login_at TEXT NOT NULL, username TEXT,
                username_normalized TEXT, password_hash TEXT, password_hash_algorithm TEXT,
                password_hash_updated_at TEXT, developer_invite_issued_at TEXT
            )"""
        )
        connection.execute("CREATE UNIQUE INDEX portal_users_oidc_subject ON portal_users(oidc_subject)")
        connection.execute("INSERT INTO portal_users(id,display_name,role,created_at,last_login_at) VALUES('legacy','Legacy','developer','2026-01-01','2026-01-02')")
        connection.execute("CREATE TABLE user_allowances(id TEXT PRIMARY KEY,user_id TEXT REFERENCES portal_users(id),amount_nano_usd INTEGER,period TEXT,timezone TEXT,active INTEGER,created_at TEXT)")
        connection.execute("INSERT INTO user_allowances VALUES('allowance','legacy',3000000000,'weekly','Europe/Berlin',1,'2026-01-03')")
        connection.execute("CREATE TABLE portal_invites(id TEXT PRIMARY KEY,uses_count INTEGER,max_uses INTEGER)")
        connection.execute("INSERT INTO portal_invites VALUES('invite',1,5)")
        connection.execute("CREATE TABLE portal_keys(id TEXT PRIMARY KEY,owner_user_id TEXT)")
        connection.execute("INSERT INTO portal_keys VALUES('key','legacy')")
        connection.execute("CREATE TABLE portal_usage_events(id TEXT PRIMARY KEY,owner_user_id TEXT)")
        connection.execute("INSERT INTO portal_usage_events VALUES('event','legacy')")
        connection.execute("CREATE TABLE portal_budget_reservations_v2(id TEXT PRIMARY KEY,owner_user_id TEXT,status TEXT,amount_nano_usd INTEGER)")
        connection.execute("INSERT INTO portal_budget_reservations_v2 VALUES('reservation','legacy','active',25)")
        PortalDatabase._migrate_monthly_allowance_period(connection)
        PortalDatabase._migrate_monthly_allowance_period(connection)

        assert connection.execute("SELECT allowance_period FROM portal_users WHERE id='legacy'").fetchone()[0] is None
        assert tuple(connection.execute("SELECT amount_nano_usd,period,active FROM user_allowances WHERE id='allowance'").fetchone()) == (3000000000, "weekly", 1)
        assert tuple(connection.execute("SELECT uses_count,max_uses FROM portal_invites WHERE id='invite'").fetchone()) == (1, 5)
        assert connection.execute("SELECT id FROM portal_keys WHERE owner_user_id='legacy'").fetchone()[0] == "key"
        assert connection.execute("SELECT id FROM portal_usage_events WHERE owner_user_id='legacy'").fetchone()[0] == "event"
        assert tuple(connection.execute("SELECT status,amount_nano_usd FROM portal_budget_reservations_v2 WHERE id='reservation'").fetchone()) == ("active", 25)
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='portal_users_oidc_subject'"
        ).fetchone()
        connection.execute("INSERT INTO portal_users(id,display_name,role,allowance_period,created_at,last_login_at) VALUES('monthly','Monthly','developer','monthly','2026-01-01','2026-01-02')")


@pytest.mark.parametrize(("stored_table_name", "expected_prefix"), [
    ("IF NOT EXISTS portal_users", "CREATE TABLE IF NOT EXISTS portal_users"),
    ('"portal_users"', 'CREATE TABLE "portal_users"'),
])
def test_full_init_upgrades_legacy_table_with_live_foreign_keys(tmp_path, stored_table_name, expected_prefix):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS portal_users (
                id TEXT PRIMARY KEY, oidc_subject TEXT UNIQUE, email TEXT,
                email_verified INTEGER NOT NULL DEFAULT 0, display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('operator','developer')),
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended')),
                allowance_usd REAL,
                allowance_period TEXT CHECK(allowance_period IS NULL OR allowance_period IN ('daily','weekly')),
                rpm_limit INTEGER, allowance_timezone TEXT NOT NULL DEFAULT 'UTC',
                created_at TEXT NOT NULL, last_login_at TEXT NOT NULL, username TEXT,
                username_normalized TEXT, password_hash TEXT, password_hash_algorithm TEXT,
                password_hash_updated_at TEXT, developer_invite_issued_at TEXT
            );
            CREATE UNIQUE INDEX portal_users_oidc_subject ON portal_users(oidc_subject);
            CREATE TABLE user_allowances (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES portal_users(id),
                amount_nano_usd INTEGER NOT NULL, period TEXT NOT NULL,
                timezone TEXT NOT NULL, active INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            INSERT INTO portal_users(id,display_name,role,created_at,last_login_at)
                VALUES('legacy','Legacy','developer','2026-01-01','2026-01-02');
            INSERT INTO user_allowances VALUES
                ('allowance','legacy',3000000000,'weekly','Europe/Berlin',0,'2026-01-03'),
                ('allowance-active','legacy',4000000000,'daily','Europe/Berlin',1,'2026-01-04');
            CREATE UNIQUE INDEX user_allowances_one_active ON user_allowances(user_id) WHERE active=1;
            CREATE TABLE portal_invites(id TEXT PRIMARY KEY, uses_count INTEGER, max_uses INTEGER);
            INSERT INTO portal_invites VALUES('invite',2,5);
            CREATE TABLE portal_keys(
                id TEXT PRIMARY KEY, owner_user_id TEXT, label TEXT, key_prefix TEXT,
                key_hash TEXT, allowed_models_mode TEXT, allowed_models_json TEXT,
                spend_limit_usd REAL, spend_period TEXT, rpm_limit INTEGER,
                created_at TEXT, last_used_at TEXT, revoked_at TEXT, archived_at TEXT
            );
            INSERT INTO portal_keys(id,owner_user_id,created_at) VALUES('key','legacy','2026-01-05');
            CREATE TABLE portal_usage_events(
                id TEXT PRIMARY KEY, owner_user_id TEXT, owner_name_snapshot TEXT,
                owner_email_snapshot TEXT, key_id TEXT, key_label_snapshot TEXT,
                provider_id TEXT, provider_name_snapshot TEXT, model_id TEXT,
                occurred_at TEXT, status TEXT, error_category TEXT, latency_ms INTEGER,
                input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
                cached_tokens INTEGER, stream INTEGER, estimated_cost_usd REAL,
                origin TEXT, price_snapshot_json TEXT, client_ip TEXT, request_id TEXT
            );
            INSERT INTO portal_usage_events(id,owner_user_id,key_id,occurred_at) VALUES('event','legacy','key','2026-01-06');
            CREATE TABLE portal_schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO portal_schema_migrations VALUES
                (1,'old'),(2,'old'),(3,'old'),(4,'old'),(5,'old'),(6,'old'),(7,'old'),(8,'old');
            CREATE TABLE portal_budget_reservations_v2 (
                id TEXT PRIMARY KEY, owner_user_id TEXT, key_id TEXT, offer_id TEXT,
                connection_id TEXT, amount_nano_usd INTEGER, created_at TEXT,
                status TEXT, request_id TEXT, public_model_id TEXT, route_snapshot_json TEXT
            );
            INSERT INTO portal_budget_reservations_v2(id,owner_user_id,created_at,status,amount_nano_usd)
                VALUES('reservation','legacy','2026-01-07','active',25);
        """)
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql=replace(sql,'CREATE TABLE portal_users',?) "
            "WHERE type='table' AND name='portal_users'",
            (f"CREATE TABLE {stored_table_name}",),
        )
        connection.execute("PRAGMA writable_schema=OFF")
        connection.execute("PRAGMA schema_version=1234")
        saved_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='portal_users'"
        ).fetchone()[0]
        assert saved_sql.startswith(expected_prefix)

    repository = PortalDatabase(str(path), key_pepper="p" * 40)

    with repository.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert [tuple(row) for row in connection.execute(
            "SELECT id,amount_nano_usd,period,active FROM user_allowances ORDER BY id"
        )] == [
            ("allowance", 3_000_000_000, "weekly", 0),
            ("allowance-active", 4_000_000_000, "daily", 1),
        ]
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='portal_users_oidc_subject'"
        ).fetchone()
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='user_allowances_one_active'"
        ).fetchone()
        assert tuple(connection.execute("SELECT uses_count,max_uses FROM portal_invites WHERE id='invite'").fetchone()) == (2, 5)
        assert connection.execute("SELECT owner_user_id FROM portal_keys WHERE id='key'").fetchone()[0] == "legacy"
        assert connection.execute("SELECT owner_user_id FROM portal_usage_events WHERE id='event'").fetchone()[0] == "legacy"
        assert tuple(connection.execute(
            "SELECT owner_user_id,status,amount_nano_usd FROM portal_budget_reservations_v2 WHERE id='reservation'"
        ).fetchone()) == ("legacy", "active", 25)
        connection.execute(
            "INSERT INTO portal_users(id,display_name,role,allowance_period,created_at,last_login_at) "
            "VALUES('monthly','Monthly','developer','monthly','2026-01-01','2026-01-02')"
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_monthly_migration_rejects_unrecognized_table_declaration_after_check_rewrite(tmp_path):
    path = tmp_path / "unsupported-ddl.db"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("""CREATE TABLE portal_users (
        id TEXT PRIMARY KEY, allowance_period TEXT CHECK(allowance_period IS NULL OR allowance_period IN ('daily','weekly'))
    )""")
    connection.execute("PRAGMA writable_schema=ON")
    connection.execute(
        "UPDATE sqlite_master SET sql=replace(sql,'CREATE TABLE portal_users',"
        "'CREATE TABLE /* unsupported declaration */ portal_users') "
        "WHERE type='table' AND name='portal_users'"
    )
    connection.execute("PRAGMA writable_schema=OFF")
    connection.execute("PRAGMA schema_version=2345")

    with pytest.raises(RuntimeError, match="portal_users table declaration"):
        PortalDatabase._migrate_monthly_allowance_period(connection)
    connection.close()


def test_monthly_migration_rolls_back_failed_copy_with_if_not_exists_schema(tmp_path):
    path = tmp_path / "rollback-legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS portal_users (
                id TEXT PRIMARY KEY, oidc_subject TEXT UNIQUE, email TEXT,
                email_verified INTEGER NOT NULL DEFAULT 0, display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('operator','developer')),
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended')),
                allowance_usd REAL,
                allowance_period TEXT CHECK(allowance_period IS NULL OR allowance_period IN ('daily','weekly')),
                rpm_limit INTEGER, allowance_timezone TEXT NOT NULL DEFAULT 'UTC',
                created_at TEXT NOT NULL, last_login_at TEXT NOT NULL, username TEXT,
                username_normalized TEXT, password_hash TEXT, password_hash_algorithm TEXT,
                password_hash_updated_at TEXT, developer_invite_issued_at TEXT
            );
            CREATE TABLE user_allowances (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES portal_users(id),
                amount_nano_usd INTEGER NOT NULL, period TEXT NOT NULL,
                timezone TEXT NOT NULL, active INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE portal_schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO portal_schema_migrations VALUES
                (1,'old'),(2,'old'),(3,'old'),(4,'old'),(5,'old'),(6,'old'),(7,'old'),(8,'old');
            CREATE TABLE portal_budget_reservations_v2 (
                id TEXT PRIMARY KEY, owner_user_id TEXT, key_id TEXT, offer_id TEXT,
                connection_id TEXT, amount_nano_usd INTEGER, created_at TEXT,
                status TEXT, request_id TEXT, public_model_id TEXT, route_snapshot_json TEXT
            );
            PRAGMA ignore_check_constraints=ON;
            INSERT INTO portal_users(id,display_name,role,created_at,last_login_at)
                VALUES('invalid','Invalid','not-a-role','2026-01-01','2026-01-02');
            PRAGMA ignore_check_constraints=OFF;
        """)
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql=replace(sql,'CREATE TABLE portal_users',"
            "'CREATE TABLE IF NOT EXISTS portal_users') WHERE type='table' AND name='portal_users'"
        )
        connection.execute("PRAGMA writable_schema=OFF")
        connection.execute("PRAGMA schema_version=1234")

    with pytest.raises(sqlite3.IntegrityError):
        PortalDatabase(str(path), key_pepper="p" * 40)

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='portal_users'"
        ).fetchone()[0].startswith("CREATE TABLE IF NOT EXISTS portal_users")
        assert tuple(connection.execute(
            "SELECT id,role FROM portal_users WHERE id='invalid'"
        ).fetchone()) == ("invalid", "not-a-role")
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='portal_users_monthly'"
        ).fetchone() is None


def test_default_invite_allowance_is_written_with_the_account_transaction(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    operator = repository.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    _invite, token = repository.create_invite(issuer_user_id=operator["id"])

    user = repository.create_local_account_with_invite(
        raw_token=token, username="invited", password_hash="hash", display_name="Invited",
        default_allowance_nano_usd=7_000_000_000,
    )

    with repository.connect() as connection:
        allowance = tuple(connection.execute(
            "SELECT amount_nano_usd,period,timezone,active FROM user_allowances WHERE user_id=?",
            (user["id"],),
        ).fetchone())
        policy = tuple(connection.execute(
            "SELECT allowance_usd,allowance_period FROM portal_users WHERE id=?", (user["id"],)
        ).fetchone())
        invite = connection.execute("SELECT uses_count FROM portal_invites WHERE consumed_by_user_id=?", (user["id"],)).fetchone()

    assert allowance == (7_000_000_000, "monthly", "Europe/Berlin", 1)
    assert policy == (7.0, "monthly")
    assert invite["uses_count"] == 1


def test_default_developer_allowance_is_a_validated_decimal_setting(tmp_path):
    from app.config import Settings

    settings = Settings(
        database_path=str(tmp_path / "settings.db"), provider_key_pepper="p" * 40,
        default_developer_allowance_usd="7", _env_file=None,
    )

    assert settings.default_developer_allowance_usd == "7"
    assert settings.default_developer_allowance_nano_usd == 7_000_000_000

    with pytest.raises(ValueError):
        Settings(
            database_path=str(tmp_path / "invalid.db"), provider_key_pepper="p" * 40,
            default_developer_allowance_usd="not-a-number", _env_file=None,
        )


def test_operator_can_override_and_remove_monthly_allowance_without_erasing_history(tmp_path):
    repository = PortalDatabase(str(tmp_path / "portal.db"), key_pepper="p" * 40)
    operator = repository.upsert_user(subject="operator", email="operator@example.test", name="Operator", role="operator")
    user = repository.upsert_user(subject="developer", email="developer@example.test", name="Developer")
    session = repository.create_session(operator["id"])
    app = FastAPI()
    app.include_router(create_portal_router(PortalService(repository, identity=None, cookie_secure=False)))

    with TestClient(app) as client:
        client.cookies.set("portal_session", session.raw_token)
        client.cookies.set("portal_csrf", session.csrf_token)
        headers = {"X-CSRF-Token": session.csrf_token}
        changed = client.patch(
            f"/api/operator/people/{user['id']}/policy", headers=headers,
            json={"allowanceUsd": "2.000000001", "allowancePeriod": "monthly", "rpmLimit": None},
        )
        assert changed.status_code == 200, changed.text
        person = next(item for item in client.get("/api/operator/people").json() if item["id"] == user["id"])
        assert person["allowanceUsd"] == "2.000000001"
        assert person["allowancePeriod"] == "monthly"
        assert person["allowanceResetAt"]

        alias = client.patch(
            f"/api/operator/people/{user['id']}/policy", headers=headers,
            json={"allowanceUsd": "2.000000002", "allowancePeriod": "month", "rpmLimit": None},
        )
        assert alias.status_code == 200, alias.text

        removed = client.patch(
            f"/api/operator/people/{user['id']}/policy", headers=headers,
            json={"allowanceUsd": None, "allowancePeriod": None, "rpmLimit": None},
        )
        assert removed.status_code == 200, removed.text

    with repository.connect() as connection:
        history = connection.execute(
            "SELECT amount_nano_usd,period,active FROM user_allowances WHERE user_id=? ORDER BY rowid",
            (user["id"],),
        ).fetchall()
    assert [tuple(item) for item in history] == [
        (2_000_000_001, "monthly", 0), (2_000_000_002, "monthly", 0),
    ]
