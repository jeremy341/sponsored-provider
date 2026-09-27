"""SQLite persistence boundary for the invite-only operator/developer portals.

This repository is intentionally independent of ``app.database.Database`` so
the existing OpenAI-compatible gateway schema and ``/v1`` behavior remain
untouched during staged integration.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any

from app.catalog import DiscoveredModel, PriceSuggestion
from app.periods import period_window
from app.routing import public_model_id as format_public_model_id, resolve_offer_routes


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _digest(value: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class CreatedSession:
    raw_token: str
    csrf_token: str
    expires_at: str


@dataclass(frozen=True)
class ProviderBrand:
    id: str
    name: str
    migration_ref: str | None = None
    identity_status: str = "unknown"
    legacy_name_snapshot: str | None = None


@dataclass(frozen=True)
class ProviderConnection:
    id: str
    brand_id: str
    legacy_profile_id: str | None
    base_url: str | None = None
    secret_ref: str | None = None
    mapping_status: str = "unmapped"
    enabled: bool = False


@dataclass(frozen=True)
class CatalogOffer:
    id: str
    brand_id: str
    canonical_model_id: str
    display_name: str
    active: bool = False
    approved: bool = False
    input_rate: str | None = None
    output_rate: str | None = None
    cached_input_rate: str | None = None


@dataclass(frozen=True)
class OfferRoute:
    id: str
    offer_id: str
    connection_id: str
    upstream_model_id: str
    brand_id: str | None = None
    position: int = 0
    active: bool = False
    connection_enabled: bool = False
    mapping_status: str = "unmapped"
    identity_status: str = "unknown"
    discovery_active: bool = False
    discovery_stale: bool = True
    confirmed: bool = False
    price_matches: bool = False
    review_required: bool = False
    connection_label: str | None = None


@dataclass(frozen=True)
class ResolvedOffer:
    id: str
    public_model_id: str
    brand_id: str
    brand_slug: str
    provider_name: str
    canonical_model_id: str
    capabilities: tuple[str, ...]
    price_version_id: str
    input_rate: str
    output_rate: str
    cached_input_rate: str | None
    routes: tuple[OfferRoute, ...]


@dataclass(frozen=True)
class PriceVersion:
    id: str
    offer_id: str
    input_rate: str | None
    output_rate: str | None
    cached_input_rate: str | None
    rate_unit: str
    is_active: bool


@dataclass(frozen=True)
class SyncSummary:
    connection_id: str
    discovered_count: int
    stale_count: int
    model_ids: tuple[str, ...]


@dataclass(frozen=True)
class ProviderBudget:
    id: str
    cap_nano_usd: int | None
    period: str | None
    key_id: str | None = None


@dataclass(frozen=True)
class BudgetReservation:
    id: str
    amount_nano_usd: int
    status: str
    owner_user_id: str | None = None
    key_id: str | None = None
    connection_id: str | None = None


class BudgetModelPolicyChanged(ValueError):
    """The selected model no longer satisfies the key policy at reservation time."""


@dataclass(frozen=True)
class UsageFields:
    model_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    status: str = "success"
    stream: bool = False
    error_category: str | None = None
    latency_ms: int | None = None
    client_ip: str | None = None
    price_version_id: str | None = None
    price_snapshot: dict[str, Any] | None = None
    request_id: str | None = None


class PortalDatabase:
    """Portal-owned data access; all authorization-sensitive queries are scoped."""

    def __init__(self, path: str, *, key_pepper: str):
        if not key_pepper or len(key_pepper) < 32:
            raise ValueError("A dedicated portal key pepper of at least 32 characters is required")
        self.path = path
        self.key_pepper = key_pepper
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        if self.path != ":memory:":
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS portal_users (
                    id TEXT PRIMARY KEY,
                    oidc_subject TEXT NOT NULL UNIQUE,
                    email TEXT,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('operator','developer')),
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended')),
                    allowance_usd REAL,
                    allowance_period TEXT CHECK(allowance_period IS NULL OR allowance_period IN ('daily','weekly')),
                    rpm_limit INTEGER,
                    allowance_timezone TEXT NOT NULL DEFAULT 'UTC',
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portal_invites (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    issuer_user_id TEXT NOT NULL,
                    bound_email TEXT,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT,
                    consumed_by_user_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portal_oauth_transactions (
                    state_hash TEXT PRIMARY KEY,
                    nonce TEXT NOT NULL,
                    invite_id TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portal_sessions (
                    token_hash TEXT PRIMARY KEY,
                    csrf_hash TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS portal_auth_rate_limits (
                    bucket_hash TEXT PRIMARY KEY,
                    window_started REAL NOT NULL,
                    attempts INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portal_catalog_models (
                    provider_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL DEFAULT '[]',
                    input_price_per_million REAL,
                    output_price_per_million REAL,
                    cached_input_price_per_million REAL,
                    price_source TEXT,
                    approved INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(provider_id, model_id)
                );
                CREATE TABLE IF NOT EXISTS portal_keys (
                    id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    allowed_models_mode TEXT NOT NULL CHECK(allowed_models_mode IN ('all_approved','selected')),
                    allowed_models_json TEXT NOT NULL DEFAULT '[]',
                    spend_limit_usd REAL,
                    spend_period TEXT CHECK(spend_period IS NULL OR spend_period IN ('daily','weekly','monthly','lifetime')),
                    rpm_limit INTEGER,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    revoked_at TEXT,
                    archived_at TEXT
                );
                CREATE INDEX IF NOT EXISTS portal_keys_owner_created ON portal_keys(owner_user_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS portal_usage_events (
                    id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL,
                    owner_name_snapshot TEXT NOT NULL,
                    owner_email_snapshot TEXT,
                    key_id TEXT NOT NULL,
                    key_label_snapshot TEXT NOT NULL,
                    provider_id TEXT,
                    provider_name_snapshot TEXT,
                    model_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_category TEXT,
                    latency_ms INTEGER,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    cached_tokens INTEGER,
                    stream INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL,
                    origin TEXT NOT NULL DEFAULT 'gateway',
                    price_snapshot_json TEXT,
                    client_ip TEXT,
                    request_id TEXT
                );
                CREATE INDEX IF NOT EXISTS portal_usage_owner_time ON portal_usage_events(owner_user_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS portal_usage_key_time ON portal_usage_events(key_id, occurred_at DESC);
                CREATE TABLE IF NOT EXISTS portal_budget_reservations (
                    id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                );
                CREATE INDEX IF NOT EXISTS portal_reservations_owner_status ON portal_budget_reservations(owner_user_id,status);
                CREATE TABLE IF NOT EXISTS portal_rate_windows (
                    scope TEXT PRIMARY KEY,
                    window_id INTEGER NOT NULL,
                    request_count INTEGER NOT NULL
                );
            CREATE TRIGGER IF NOT EXISTS portal_usage_no_update
                BEFORE UPDATE ON portal_usage_events BEGIN
                    SELECT RAISE(ABORT, 'portal usage events are immutable');
                END;
                CREATE TRIGGER IF NOT EXISTS portal_usage_no_delete
                BEFORE DELETE ON portal_usage_events BEGIN
                    SELECT RAISE(ABORT, 'portal usage events are immutable');
                END;
                CREATE TABLE IF NOT EXISTS portal_audit_events (
                    id TEXT PRIMARY KEY,
                    actor_user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portal_runtime_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            try:
                conn.execute("ALTER TABLE portal_usage_events ADD COLUMN stream INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.execute("CREATE TABLE IF NOT EXISTS portal_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            applied = {row[0] for row in conn.execute("SELECT version FROM portal_schema_migrations")}
            migrations = (
                (1, self._migrate_catalog_and_credits),
                (2, self._migrate_legacy_catalog),
                (3, self._migrate_identity_and_numeric_safety),
                (4, self._migrate_local_auth_and_invite_quotas),
                (5, self._migrate_provider_discovery_and_prices),
                (6, self._migrate_ordered_offer_routes),
                (7, self._migrate_manual_mappings_and_route_review),
                (8, self._migrate_shared_credit_budgets),
            )
            for version, migration in migrations:
                if version not in applied:
                    migration(conn)
                    conn.execute("INSERT INTO portal_schema_migrations(version,applied_at) VALUES(?,?)", (version, _iso()))
            # These nullable reservation snapshot columns are an additive extension
            # to schema 8 and also repair already-initialized schema-8 databases.
            self._ensure_gateway_route_snapshot_columns(conn)

    @staticmethod
    def _ensure_gateway_route_snapshot_columns(conn: sqlite3.Connection) -> None:
        PortalDatabase._add_columns(conn, "portal_budget_reservations_v2", {
            "public_model_id": "TEXT", "route_snapshot_json": "TEXT",
        })

    @staticmethod
    def _migrate_ordered_offer_routes(conn: sqlite3.Connection) -> None:
        PortalDatabase._add_columns(conn, "offer_routes", {"sort_order": "INTEGER NOT NULL DEFAULT 0"})
        conn.execute("CREATE INDEX IF NOT EXISTS offer_routes_order ON offer_routes(offer_id,sort_order,id)")
        conn.execute("""UPDATE offer_routes SET active=1 WHERE active=0
            AND EXISTS (SELECT 1 FROM provider_connections connection
                JOIN provider_brands brand ON brand.id=connection.brand_id
                JOIN connection_models discovered ON discovered.connection_id=connection.id
                    AND discovered.upstream_model_id=offer_routes.upstream_model_id
                WHERE connection.id=offer_routes.connection_id AND connection.enabled=1
                    AND connection.mapping_status='mapped' AND brand.identity_status='mapped'
                    AND discovered.active=1 AND discovered.is_stale=0)
            AND EXISTS (SELECT 1 FROM catalog_offers offer JOIN price_versions price ON price.offer_id=offer.id
                WHERE offer.id=offer_routes.offer_id AND offer.approved=1 AND price.is_active=1)""")

    @staticmethod
    def _migrate_manual_mappings_and_route_review(conn: sqlite3.Connection) -> None:
        PortalDatabase._add_columns(conn, "connection_models", {
            "canonical_model_id": "TEXT",
            "mapping_source": "TEXT NOT NULL DEFAULT 'exact'",
        })
        PortalDatabase._add_columns(conn, "offer_routes", {"review_required": "INTEGER NOT NULL DEFAULT 0"})
        conn.execute("""UPDATE connection_models SET canonical_model_id=COALESCE(
            (SELECT offer.canonical_model_id FROM offer_routes route
                JOIN catalog_offers offer ON offer.id=route.offer_id
                WHERE route.connection_id=connection_models.connection_id
                    AND route.upstream_model_id=connection_models.upstream_model_id),
            upstream_model_id)""")
        conn.execute("""UPDATE offer_routes SET review_required=1 WHERE EXISTS (
            SELECT 1 FROM connection_models discovered
            WHERE discovered.connection_id=offer_routes.connection_id
                AND discovered.upstream_model_id=offer_routes.upstream_model_id
                AND (discovered.is_stale=1 OR discovered.active=0))""")

    def _migrate_local_auth_and_invite_quotas(self, conn: sqlite3.Connection) -> None:
        """Add local credentials while retaining every existing OIDC identity."""
        if "username_normalized" in {row[1] for row in conn.execute("PRAGMA table_info(portal_users)")}:
            return
        has_allowances = self._table_exists(conn, "user_allowances")
        if has_allowances:
            conn.execute("CREATE TABLE user_allowances_local_auth AS SELECT * FROM user_allowances")
            conn.execute("DROP TABLE user_allowances")
        conn.execute("""
            CREATE TABLE portal_users_local_auth (
                id TEXT PRIMARY KEY,
                oidc_subject TEXT UNIQUE,
                email TEXT,
                email_verified INTEGER NOT NULL DEFAULT 0,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('operator','developer')),
                status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended')),
                allowance_usd REAL,
                allowance_period TEXT CHECK(allowance_period IS NULL OR allowance_period IN ('daily','weekly')),
                rpm_limit INTEGER,
                allowance_timezone TEXT NOT NULL DEFAULT 'UTC',
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                username TEXT,
                username_normalized TEXT,
                password_hash TEXT,
                password_hash_algorithm TEXT,
                password_hash_updated_at TEXT,
                developer_invite_issued_at TEXT
            )
        """)
        columns = (
            "id,oidc_subject,email,email_verified,display_name,role,status,allowance_usd,allowance_period,"
            "rpm_limit,allowance_timezone,created_at,last_login_at"
        )
        conn.execute(f"INSERT INTO portal_users_local_auth({columns}) SELECT {columns} FROM portal_users")
        conn.execute("DROP TABLE portal_users")
        conn.execute("ALTER TABLE portal_users_local_auth RENAME TO portal_users")
        if has_allowances:
            conn.execute("""
                CREATE TABLE user_allowances (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES portal_users(id),
                    amount_nano_usd INTEGER NOT NULL, period TEXT NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'Europe/Berlin', active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("INSERT INTO user_allowances SELECT * FROM user_allowances_local_auth")
            conn.execute("DROP TABLE user_allowances_local_auth")
            conn.execute("CREATE UNIQUE INDEX user_allowances_one_active ON user_allowances(user_id) WHERE active=1")
        conn.execute("CREATE UNIQUE INDEX portal_users_username_normalized_unique ON portal_users(username_normalized) WHERE username_normalized IS NOT NULL")
        conn.execute("CREATE UNIQUE INDEX portal_users_username_nocase_unique ON portal_users(username COLLATE NOCASE) WHERE username IS NOT NULL")
        self._add_columns(conn, "portal_invites", {
            "max_uses": "INTEGER NOT NULL DEFAULT 1 CHECK(max_uses >= 1)",
            "uses_count": "INTEGER NOT NULL DEFAULT 0 CHECK(uses_count >= 0)",
            "revoked_at": "TEXT",
            "revoked_by_user_id": "TEXT",
        })
        conn.execute("UPDATE portal_invites SET uses_count=1 WHERE consumed_at IS NOT NULL AND uses_count=0")

    def _migrate_provider_discovery_and_prices(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "provider_brands"):
            self._migrate_catalog_and_credits(conn)
            self._migrate_legacy_catalog(conn)
            self._migrate_identity_and_numeric_safety(conn)
        self._add_columns(conn, "provider_brands", {"slug": "TEXT"})
        self._add_columns(conn, "provider_connections", {"label": "TEXT NOT NULL DEFAULT ''"})
        self._add_columns(conn, "connection_models", {
            "is_stale": "INTEGER NOT NULL DEFAULT 0",
            "last_seen_at": "TEXT",
        })
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS provider_brands_slug_unique ON provider_brands(slug) WHERE slug IS NOT NULL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_suggestions (
                id TEXT PRIMARY KEY,
                offer_id TEXT NOT NULL REFERENCES catalog_offers(id),
                input_rate TEXT,
                output_rate TEXT,
                cached_input_rate TEXT,
                source TEXT NOT NULL,
                source_url TEXT,
                evidence TEXT,
                confidence TEXT,
                fetched_at TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
                decided_by TEXT,
                decided_at TEXT,
                effective_version_id TEXT,
                CHECK(input_rate IS NULL OR (input_rate<>'' AND input_rate NOT GLOB '*[^0-9.]*' AND input_rate GLOB '[0-9]*' AND input_rate NOT GLOB '*.*.*' AND input_rate NOT LIKE '%.' AND input_rate NOT LIKE '.%')),
                CHECK(output_rate IS NULL OR (output_rate<>'' AND output_rate NOT GLOB '*[^0-9.]*' AND output_rate GLOB '[0-9]*' AND output_rate NOT GLOB '*.*.*' AND output_rate NOT LIKE '%.' AND output_rate NOT LIKE '.%')),
                CHECK(cached_input_rate IS NULL OR (cached_input_rate<>'' AND cached_input_rate NOT GLOB '*[^0-9.]*' AND cached_input_rate GLOB '[0-9]*' AND cached_input_rate NOT GLOB '*.*.*' AND cached_input_rate NOT LIKE '%.' AND cached_input_rate NOT LIKE '.%'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS price_suggestions_pending ON price_suggestions(offer_id,status,created_at DESC)")
        conn.executescript("""
            DROP VIEW IF EXISTS portal_eligible_legacy_models;
            CREATE VIEW portal_eligible_legacy_models AS
            SELECT DISTINCT model.provider_id,model.model_id
            FROM portal_catalog_models model
            JOIN provider_brands brand ON brand.migration_ref=model.provider_id
            JOIN provider_connections connection ON connection.brand_id=brand.id
                AND connection.legacy_profile_id=model.provider_id
            JOIN catalog_offers offer ON offer.brand_id=brand.id
                AND offer.canonical_model_id=model.model_id
            JOIN offer_routes route ON route.offer_id=offer.id
                AND route.connection_id=connection.id
                AND route.upstream_model_id=model.model_id
            JOIN connection_models discovered ON discovered.connection_id=connection.id
                AND discovered.upstream_model_id=route.upstream_model_id
            WHERE brand.identity_status='mapped'
                AND connection.mapping_status='mapped' AND connection.enabled=1
                AND discovered.active=1 AND discovered.is_stale=0
                AND route.active=1 AND offer.approved=1 AND offer.active=1
                AND EXISTS (SELECT 1 FROM price_versions price WHERE price.offer_id=offer.id AND price.is_active=1);
        """)

    @staticmethod
    def _migrate_shared_credit_budgets(conn: sqlite3.Connection) -> None:
        PortalDatabase._add_columns(conn, "provider_budgets", {
            "connection_id": "TEXT",
            "reserve_nano_usd": "INTEGER NOT NULL DEFAULT 0",
        })
        PortalDatabase._add_columns(conn, "portal_budget_reservations_v2", {
            "offer_id": "TEXT",
            "connection_id": "TEXT",
            "settlement_event_id": "TEXT",
            "price_version_id": "TEXT",
            "price_snapshot_json": "TEXT",
        })
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS provider_budgets_connection_unique ON provider_budgets(connection_id) WHERE connection_id IS NOT NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS portal_budget_v2_owner_status ON portal_budget_reservations_v2(owner_user_id,status,created_at)")
        conn.execute("UPDATE portal_users SET allowance_timezone='Europe/Berlin' WHERE allowance_usd IS NOT NULL")
        conn.execute("UPDATE user_allowances SET timezone='Europe/Berlin' WHERE active=1")

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

    @staticmethod
    def _nano_usd(value: Any, *, rounding: str) -> int | None:
        if value is None:
            return None
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid USD amount in legacy data: {value!r}") from None
        if not amount.is_finite():
            raise ValueError(f"Invalid USD amount in legacy data: {value!r}")
        return int((amount * Decimal(1_000_000_000)).to_integral_value(rounding=rounding))

    @staticmethod
    def _cap_nano_usd(value: Any) -> int | None:
        return PortalDatabase._nano_usd(value, rounding="ROUND_FLOOR")

    @staticmethod
    def _charge_nano_usd(value: Any) -> int | None:
        return PortalDatabase._nano_usd(value, rounding=ROUND_CEILING)

    @staticmethod
    def _canonical_rate(value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value) if isinstance(value, str) else format(Decimal(str(value)), "f")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", raw):
            raise ValueError(f"Rate must be a non-negative decimal value: {value!r}")
        try:
            number = Decimal(raw)
        except InvalidOperation:
            raise ValueError(f"Rate must be a non-negative decimal value: {value!r}") from None
        return format(number.normalize(), "f")

    def _migrate_catalog_and_credits(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS provider_brands (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, migration_ref TEXT UNIQUE, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS provider_connections (
                id TEXT PRIMARY KEY, brand_id TEXT NOT NULL REFERENCES provider_brands(id),
                legacy_profile_id TEXT UNIQUE, base_url TEXT,
                provider_kind TEXT, secret_ref TEXT, enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS connection_models (
                connection_id TEXT NOT NULL REFERENCES provider_connections(id), upstream_model_id TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}', active INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(connection_id,upstream_model_id)
            );
            CREATE TABLE IF NOT EXISTS catalog_offers (
                id TEXT PRIMARY KEY, brand_id TEXT NOT NULL REFERENCES provider_brands(id),
                canonical_model_id TEXT NOT NULL, display_name TEXT NOT NULL,
                capabilities_json TEXT NOT NULL DEFAULT '[]', approved INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1, price_source TEXT, updated_at TEXT NOT NULL,
                UNIQUE(brand_id,canonical_model_id)
            );
            CREATE TABLE IF NOT EXISTS offer_routes (
                id TEXT PRIMARY KEY, offer_id TEXT NOT NULL REFERENCES catalog_offers(id),
                connection_id TEXT NOT NULL REFERENCES provider_connections(id), upstream_model_id TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1, UNIQUE(offer_id,connection_id),
                UNIQUE(connection_id,upstream_model_id)
            );
            CREATE TABLE IF NOT EXISTS price_versions (
                id TEXT PRIMARY KEY, offer_id TEXT NOT NULL REFERENCES catalog_offers(id),
                input_rate TEXT, output_rate TEXT, cached_input_rate TEXT, rate_unit TEXT NOT NULL DEFAULT 'per_million_tokens',
                source TEXT, is_active INTEGER NOT NULL DEFAULT 1, effective_at TEXT NOT NULL, retired_at TEXT,
                CHECK(input_rate IS NULL OR (input_rate<>'' AND input_rate NOT GLOB '*[^0-9.]*' AND input_rate GLOB '[0-9]*' AND input_rate NOT GLOB '*.*.*' AND input_rate NOT LIKE '%.' AND input_rate NOT LIKE '.%')),
                CHECK(output_rate IS NULL OR (output_rate<>'' AND output_rate NOT GLOB '*[^0-9.]*' AND output_rate GLOB '[0-9]*' AND output_rate NOT GLOB '*.*.*' AND output_rate NOT LIKE '%.' AND output_rate NOT LIKE '.%')),
                CHECK(cached_input_rate IS NULL OR (cached_input_rate<>'' AND cached_input_rate NOT GLOB '*[^0-9.]*' AND cached_input_rate GLOB '[0-9]*' AND cached_input_rate NOT GLOB '*.*.*' AND cached_input_rate NOT LIKE '%.' AND cached_input_rate NOT LIKE '.%'))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS price_versions_one_active ON price_versions(offer_id) WHERE is_active=1;
            CREATE TABLE IF NOT EXISTS provider_budgets (
                id TEXT PRIMARY KEY, key_id TEXT UNIQUE, provider_key_id INTEGER UNIQUE,
                cap_nano_usd INTEGER, period TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_allowances (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES portal_users(id), amount_nano_usd INTEGER NOT NULL,
                period TEXT NOT NULL, timezone TEXT NOT NULL DEFAULT 'Europe/Berlin', active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS user_allowances_one_active ON user_allowances(user_id) WHERE active=1;
            CREATE TABLE IF NOT EXISTS portal_budget_reservations_v2 (
                id TEXT PRIMARY KEY, owner_user_id TEXT, key_id TEXT, provider_key_id INTEGER,
                amount_nano_usd INTEGER NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL
            );
        """)
        self._add_columns(conn, "portal_usage_events", {
            "amount_nano_usd": "INTEGER", "brand_id": "TEXT", "canonical_model_id": "TEXT",
            "offer_route_id": "TEXT", "price_version_id": "TEXT", "brand_snapshot": "TEXT",
            "model_snapshot": "TEXT", "route_snapshot_json": "TEXT", "price_snapshot_v2_json": "TEXT",
        })
        for row in conn.execute("SELECT id,owner_user_id,spend_limit_usd,spend_period,created_at FROM portal_keys WHERE spend_limit_usd IS NOT NULL"):
            conn.execute("INSERT OR IGNORE INTO provider_budgets(id,key_id,cap_nano_usd,period,created_at) VALUES(?,?,?,?,?)",
                         (f"portal-key:{row['id']}", row["id"], self._cap_nano_usd(row["spend_limit_usd"]), row["spend_period"], row["created_at"]))
        for row in conn.execute("SELECT id,allowance_usd,allowance_period,allowance_timezone,created_at FROM portal_users WHERE allowance_usd IS NOT NULL"):
            conn.execute("INSERT OR IGNORE INTO user_allowances(id,user_id,amount_nano_usd,period,timezone,created_at) VALUES(?,?,?,?,?,?)",
                         (f"portal-user:{row['id']}", row["id"], self._cap_nano_usd(row["allowance_usd"]), row["allowance_period"], "Europe/Berlin", row["created_at"]))
        if self._table_exists(conn, "portal_budget_reservations"):
            for row in conn.execute("SELECT id,owner_user_id,key_id,estimated_cost_usd,created_at,status FROM portal_budget_reservations"):
                conn.execute("INSERT OR IGNORE INTO portal_budget_reservations_v2(id,owner_user_id,key_id,amount_nano_usd,created_at,status) VALUES(?,?,?,?,?,?)",
                             (row["id"], row["owner_user_id"], row["key_id"], self._charge_nano_usd(row["estimated_cost_usd"]), row["created_at"], row["status"]))
        if self._table_exists(conn, "provider_api_keys"):
            for row in conn.execute("SELECT id,spend_limit_usd FROM provider_api_keys WHERE spend_limit_usd IS NOT NULL"):
                conn.execute("INSERT OR IGNORE INTO provider_budgets(id,provider_key_id,cap_nano_usd,created_at) VALUES(?,?,?,?)",
                             (f"legacy-key:{row['id']}", row["id"], self._cap_nano_usd(row["spend_limit_usd"]), _iso()))
        if self._table_exists(conn, "budget_reservations"):
            for row in conn.execute("SELECT id,provider_key_id,estimated_cost_usd,created_at,status FROM budget_reservations"):
                conn.execute("INSERT OR IGNORE INTO portal_budget_reservations_v2(id,provider_key_id,amount_nano_usd,created_at,status) VALUES(?,?,?,?,?)",
                             (f"legacy:{row['id']}", row["provider_key_id"], self._charge_nano_usd(row["estimated_cost_usd"]), row["created_at"], row["status"]))

        for key, budget_id in (("global_spend_cap_usd", "global-spend-cap"), ("safety_reserve_usd", "safety-reserve")):
            setting = conn.execute("SELECT value_json FROM portal_runtime_settings WHERE key=?", (key,)).fetchone()
            if setting:
                converter = self._charge_nano_usd if key == "safety_reserve_usd" else self._cap_nano_usd
                conn.execute("INSERT OR IGNORE INTO provider_budgets(id,cap_nano_usd,created_at) VALUES(?,?,?)",
                             (budget_id, converter(json.loads(setting["value_json"])), _iso()))

    def _migrate_identity_and_numeric_safety(self, conn: sqlite3.Connection) -> None:
        self._add_columns(conn, "provider_brands", {
            "identity_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "legacy_name_snapshot": "TEXT",
        })
        self._add_columns(conn, "provider_connections", {
            "mapping_status": "TEXT NOT NULL DEFAULT 'unmapped'",
            "legacy_enabled": "INTEGER NOT NULL DEFAULT 0",
        })
        conn.execute("UPDATE provider_brands SET legacy_name_snapshot=COALESCE(legacy_name_snapshot,name),name='Unknown legacy provider',identity_status='unknown' WHERE migration_ref IS NOT NULL")
        if self._table_exists(conn, "upstream_profiles"):
            conn.execute("""UPDATE provider_connections SET
                legacy_enabled=CASE WHEN legacy_enabled=0 THEN COALESCE(
                    (SELECT enabled FROM upstream_profiles WHERE upstream_profiles.id=provider_connections.legacy_profile_id),enabled
                ) ELSE legacy_enabled END,
                enabled=0,mapping_status='unmapped'""")
        else:
            conn.execute("UPDATE provider_connections SET legacy_enabled=CASE WHEN legacy_enabled=0 THEN enabled ELSE legacy_enabled END,enabled=0,mapping_status='unmapped'")
        conn.execute("UPDATE connection_models SET active=0")
        conn.execute("UPDATE catalog_offers SET approved=0,active=0")
        conn.execute("UPDATE offer_routes SET active=0")

        for operation in ("INSERT", "UPDATE"):
            trigger = f"price_versions_validate_{operation.lower()}"
            invalid = " OR ".join(
                f"NEW.{column} IS NOT NULL AND NOT ({self._sqlite_decimal_check(f'NEW.{column}')})"
                for column in ("input_rate", "output_rate", "cached_input_rate")
            )
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
            conn.execute(f"CREATE TRIGGER {trigger} BEFORE {operation} ON price_versions WHEN {invalid} BEGIN SELECT RAISE(ABORT,'rate must be a non-negative decimal value'); END")

        for row in conn.execute("SELECT id,spend_limit_usd,spend_period FROM portal_keys WHERE spend_limit_usd IS NOT NULL"):
            conn.execute("UPDATE provider_budgets SET cap_nano_usd=?,period=? WHERE key_id=?",
                         (self._cap_nano_usd(row["spend_limit_usd"]), row["spend_period"], row["id"]))
        for row in conn.execute("SELECT id,allowance_usd FROM portal_users WHERE allowance_usd IS NOT NULL"):
            conn.execute("UPDATE user_allowances SET amount_nano_usd=?,timezone='Europe/Berlin' WHERE user_id=? AND active=1",
                         (self._cap_nano_usd(row["allowance_usd"]), row["id"]))
        if self._table_exists(conn, "portal_budget_reservations"):
            for row in conn.execute("SELECT id,estimated_cost_usd FROM portal_budget_reservations"):
                conn.execute("UPDATE portal_budget_reservations_v2 SET amount_nano_usd=? WHERE id=?",
                             (self._charge_nano_usd(row["estimated_cost_usd"]), row["id"]))
        if self._table_exists(conn, "provider_api_keys"):
            for row in conn.execute("SELECT id,spend_limit_usd FROM provider_api_keys WHERE spend_limit_usd IS NOT NULL"):
                conn.execute("UPDATE provider_budgets SET cap_nano_usd=? WHERE provider_key_id=?",
                             (self._cap_nano_usd(row["spend_limit_usd"]), row["id"]))
        if self._table_exists(conn, "budget_reservations"):
            for row in conn.execute("SELECT id,estimated_cost_usd FROM budget_reservations"):
                conn.execute("UPDATE portal_budget_reservations_v2 SET amount_nano_usd=? WHERE id=?",
                             (self._charge_nano_usd(row["estimated_cost_usd"]), f"legacy:{row['id']}"))
        for setting_key, budget_id in (("global_spend_cap_usd", "global-spend-cap"), ("safety_reserve_usd", "safety-reserve")):
            setting = conn.execute("SELECT value_json FROM portal_runtime_settings WHERE key=?", (setting_key,)).fetchone()
            if setting:
                converter = self._charge_nano_usd if setting_key == "safety_reserve_usd" else self._cap_nano_usd
                conn.execute("UPDATE provider_budgets SET cap_nano_usd=? WHERE id=?",
                             (converter(json.loads(setting["value_json"])), budget_id))

        conn.execute("DROP TRIGGER IF EXISTS portal_usage_no_update")
        try:
            for row in conn.execute("SELECT id,estimated_cost_usd FROM portal_usage_events WHERE amount_nano_usd IS NULL AND estimated_cost_usd IS NOT NULL"):
                conn.execute("UPDATE portal_usage_events SET amount_nano_usd=? WHERE id=?",
                             (self._charge_nano_usd(row["estimated_cost_usd"]), row["id"]))
        finally:
            conn.execute("CREATE TRIGGER portal_usage_no_update BEFORE UPDATE ON portal_usage_events BEGIN SELECT RAISE(ABORT, 'portal usage events are immutable'); END")

    @staticmethod
    def _sqlite_decimal_check(expression: str) -> str:
        return f"({expression}<>'' AND {expression} NOT GLOB '*[^0-9.]*' AND {expression} GLOB '[0-9]*' AND {expression} NOT GLOB '*.*.*' AND {expression} NOT LIKE '%.' AND {expression} NOT LIKE '.%')"

    @staticmethod
    def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def _migrate_legacy_catalog(self, conn: sqlite3.Connection) -> None:
        profile_rows = conn.execute("SELECT * FROM upstream_profiles").fetchall() if self._table_exists(conn, "upstream_profiles") else []
        for profile in profile_rows:
            profile_id = str(profile["id"])
            brand_id = f"legacy-brand:{profile_id}"
            connection_id = f"legacy-connection:{profile_id}"
            conn.execute("INSERT OR IGNORE INTO provider_brands(id,name,migration_ref,created_at) VALUES(?,?,?,?)",
                         (brand_id, profile["name"], profile_id, profile["created_at"]))
            conn.execute("INSERT OR IGNORE INTO provider_connections(id,brand_id,legacy_profile_id,base_url,provider_kind,secret_ref,enabled,created_at) VALUES(?,?,?,?,?,?,?,?)",
                         (connection_id, brand_id, profile_id, profile["base_url"], profile["provider_kind"], profile_id, profile["enabled"], profile["created_at"]))
            try:
                model_ids = json.loads(profile["models_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                model_ids = []
            for model_id in model_ids if isinstance(model_ids, list) else []:
                conn.execute("INSERT OR IGNORE INTO connection_models(connection_id,upstream_model_id) VALUES(?,?)", (connection_id, str(model_id)))

        catalog_rows = conn.execute("SELECT * FROM portal_catalog_models").fetchall()
        for model in catalog_rows:
            provider_id = str(model["provider_id"])
            brand_id = f"legacy-brand:{provider_id}"
            connection_id = f"legacy-connection:{provider_id}"
            brand = conn.execute("SELECT id FROM provider_brands WHERE migration_ref=?", (provider_id,)).fetchone()
            if brand:
                brand_id = brand["id"]
            else:
                conn.execute("INSERT OR IGNORE INTO provider_brands(id,name,migration_ref,created_at) VALUES(?,?,?,?)",
                             (brand_id, model["provider_name"], provider_id, model["updated_at"]))
            if not conn.execute("SELECT 1 FROM provider_connections WHERE id=?", (connection_id,)).fetchone():
                conn.execute("INSERT OR IGNORE INTO provider_connections(id,brand_id,legacy_profile_id,secret_ref,created_at) VALUES(?,?,NULL,NULL,?)",
                             (connection_id, brand_id, model["updated_at"]))
            offer_id = f"legacy-offer:{provider_id}:{model['model_id']}"
            conn.execute("INSERT OR IGNORE INTO catalog_offers(id,brand_id,canonical_model_id,display_name,capabilities_json,approved,active,price_source,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                         (offer_id, brand_id, model["model_id"], model["model_id"], model["capabilities_json"], model["approved"], model["active"], model["price_source"], model["updated_at"]))
            conn.execute("INSERT OR IGNORE INTO offer_routes(id,offer_id,connection_id,upstream_model_id,active) VALUES(?,?,?,?,?)",
                         (f"legacy-route:{provider_id}:{model['model_id']}", offer_id, connection_id, model["model_id"], model["active"]))
            rate_row = conn.execute("SELECT 1 FROM price_versions WHERE offer_id=? AND is_active=1", (offer_id,)).fetchone()
            if not rate_row and (model["input_price_per_million"] is not None or model["output_price_per_million"] is not None or model["cached_input_price_per_million"] is not None):
                conn.execute("INSERT INTO price_versions(id,offer_id,input_rate,output_rate,cached_input_rate,source,is_active,effective_at) VALUES(?,?,?,?,?,?,1,?)",
                             (f"legacy-price:{provider_id}:{model['model_id']}", offer_id,
                              self._canonical_rate(model["input_price_per_million"]), self._canonical_rate(model["output_price_per_million"]),
                              self._canonical_rate(model["cached_input_price_per_million"]), model["price_source"], model["updated_at"]))
            try:
                conn.execute("ALTER TABLE portal_usage_events ADD COLUMN origin TEXT NOT NULL DEFAULT 'gateway'")
            except sqlite3.OperationalError:
                pass

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    def find_invite(self, raw_token: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id,bound_email,expires_at,consumed_at,max_uses,uses_count,revoked_at FROM portal_invites WHERE token_hash=?",
                (_digest(raw_token, self.key_pepper),),
            ).fetchone()
        invite = self._dict(row)
        if invite and (invite["revoked_at"] or invite["uses_count"] >= invite["max_uses"] or invite["expires_at"] <= _iso()):
            return None
        return invite

    def create_invite(
        self,
        *,
        issuer_user_id: str,
        expires_in_seconds: int = 7 * 24 * 60 * 60,
        bound_email: str | None = None,
        max_uses: int = 1,
    ) -> tuple[dict[str, Any], str]:
        if not 60 <= expires_in_seconds <= 30 * 24 * 60 * 60:
            raise ValueError("Invite expiry must be between 60 seconds and 30 days")
        if not isinstance(max_uses, int) or isinstance(max_uses, bool) or max_uses < 1:
            raise ValueError("Invite max_uses must be a positive integer")
        raw_token = "sp_inv_" + secrets.token_urlsafe(32)
        invite_id = uuid.uuid4().hex
        created_at = _iso()
        expires_at = _iso(_now() + timedelta(seconds=expires_in_seconds))
        with self.connect() as conn:
            issuer = conn.execute("SELECT role,status FROM portal_users WHERE id=?", (issuer_user_id,)).fetchone()
            if not issuer or issuer["role"] != "operator" or issuer["status"] != "active":
                raise PermissionError("Only an active operator can issue invites")
            conn.execute(
                "INSERT INTO portal_invites(id,token_hash,issuer_user_id,bound_email,expires_at,max_uses,created_at) VALUES(?,?,?,?,?,?,?)",
                (invite_id, _digest(raw_token, self.key_pepper), issuer_user_id, bound_email.strip().lower() if bound_email else None, expires_at, max_uses, created_at),
            )
        return {"id": invite_id, "bound_email": bound_email, "expires_at": expires_at, "max_uses": max_uses, "uses_count": 0, "revoked_at": None, "created_at": created_at}, raw_token

    def create_developer_invite(
        self, *, issuer_user_id: str, expires_in_seconds: int = 7 * 24 * 60 * 60
    ) -> tuple[dict[str, Any], str]:
        if not 60 <= expires_in_seconds <= 30 * 24 * 60 * 60:
            raise ValueError("Invite expiry must be between 60 seconds and 30 days")
        raw_token = "sp_inv_" + secrets.token_urlsafe(32)
        invite_id = uuid.uuid4().hex
        created_at = _iso()
        expires_at = _iso(_now() + timedelta(seconds=expires_in_seconds))
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            issuer = conn.execute("SELECT role,status,developer_invite_issued_at FROM portal_users WHERE id=?", (issuer_user_id,)).fetchone()
            if not issuer or issuer["role"] != "developer" or issuer["status"] != "active":
                raise PermissionError("Only an active developer can issue a developer invite")
            if issuer["developer_invite_issued_at"] is not None:
                raise PermissionError("Developer invite entitlement was already issued")
            conn.execute(
                "INSERT INTO portal_invites(id,token_hash,issuer_user_id,expires_at,max_uses,created_at) VALUES(?,?,?,?,1,?)",
                (invite_id, _digest(raw_token, self.key_pepper), issuer_user_id, expires_at, created_at),
            )
            conn.execute("UPDATE portal_users SET developer_invite_issued_at=? WHERE id=?", (created_at, issuer_user_id))
        return {"id": invite_id, "expires_at": expires_at, "max_uses": 1, "uses_count": 0, "revoked_at": None, "created_at": created_at}, raw_token

    def revoke_invite(self, invite_id: str, *, revoked_by_user_id: str) -> bool:
        now = _iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            operator = conn.execute("SELECT role,status FROM portal_users WHERE id=?", (revoked_by_user_id,)).fetchone()
            if not operator or operator["role"] != "operator" or operator["status"] != "active":
                raise PermissionError("Only an active operator can revoke invites")
            result = conn.execute(
                "UPDATE portal_invites SET revoked_at=?,revoked_by_user_id=? WHERE id=? AND revoked_at IS NULL",
                (now, revoked_by_user_id, invite_id),
            )
            return result.rowcount == 1

    def list_invites(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT id,bound_email,expires_at,consumed_at,consumed_by_user_id,max_uses,uses_count,revoked_at,revoked_by_user_id,created_at FROM portal_invites ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def developer_invite_status(self, user_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            user = conn.execute(
                "SELECT developer_invite_issued_at FROM portal_users WHERE id=? AND role='developer' AND status='active'",
                (user_id,),
            ).fetchone()
            if not user:
                raise PermissionError("Only an active developer can view invite status")
            row = conn.execute(
                "SELECT id,expires_at,max_uses,uses_count,revoked_at,created_at FROM portal_invites WHERE issuer_user_id=? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        invite = dict(row) if row else None
        if invite:
            invite["status"] = (
                "revoked" if invite["revoked_at"] else
                "exhausted" if invite["uses_count"] >= invite["max_uses"] else
                "expired" if invite["expires_at"] <= _iso() else "active"
            )
        issued_at = user["developer_invite_issued_at"]
        return {"entitled": True, "can_issue": issued_at is None, "issued_at": issued_at, "invite": invite}

    def create_local_account_with_invite(
        self, *, raw_token: str, username: str, password_hash: str, display_name: str
    ) -> dict[str, Any]:
        clean_username = username.strip() if isinstance(username, str) else ""
        if not clean_username or len(clean_username) > 64 or any(ord(char) < 32 for char in clean_username):
            raise ValueError("Invalid username: must contain 1 to 64 printable characters")
        normalized = clean_username.casefold()
        if not password_hash:
            raise ValueError("Password hash is required")
        now = _iso()
        user_id = uuid.uuid4().hex
        token_hash = _digest(raw_token, self.key_pepper)
        try:
            with self.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                invite = conn.execute("SELECT * FROM portal_invites WHERE token_hash=?", (token_hash,)).fetchone()
                if (not invite or invite["revoked_at"] or invite["uses_count"] >= invite["max_uses"]
                        or invite["expires_at"] <= now):
                    raise PermissionError("This invitation is invalid, expired, revoked, or exhausted")
                if invite["bound_email"]:
                    raise PermissionError("This invitation requires a verified email address")
                conn.execute(
                    "INSERT INTO portal_users(id,email,email_verified,display_name,role,status,created_at,last_login_at,username,username_normalized,password_hash,password_hash_algorithm,password_hash_updated_at) "
                    "VALUES(?,NULL,0,?,'developer','active',?,?,?,?,?,'argon2id',?)",
                    (user_id, display_name.strip() or clean_username, now, now, clean_username, normalized, password_hash, now),
                )
                consumed_count = invite["uses_count"] + 1
                exhausted_at = now if consumed_count >= invite["max_uses"] else None
                update = conn.execute(
                    "UPDATE portal_invites SET uses_count=?,consumed_at=COALESCE(consumed_at,?),consumed_by_user_id=COALESCE(consumed_by_user_id,?) "
                    "WHERE id=? AND uses_count=? AND uses_count<max_uses AND revoked_at IS NULL AND expires_at>?",
                    (consumed_count, exhausted_at, user_id, invite["id"], invite["uses_count"], now),
                )
                if update.rowcount != 1:
                    raise PermissionError("This invitation was already exhausted")
                return dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user_id,)).fetchone())
        except sqlite3.IntegrityError as error:
            if "username" in str(error).casefold() or "unique" in str(error).casefold():
                raise ValueError("Username is already in use") from error
            raise

    def get_local_user_by_username(self, normalized_username: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM portal_users WHERE username_normalized=?", (normalized_username,)).fetchone()
        return self._dict(row)

    def allow_local_auth_attempt(
        self, *, normalized_username: str, client_ip: str, limit: int, window_seconds: int
    ) -> bool:
        now = _now().timestamp()
        buckets = [
            _digest("username:" + normalized_username, self.key_pepper),
            _digest("ip:" + client_ip, self.key_pepper),
        ]
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = {
                row["bucket_hash"]: row
                for row in conn.execute(
                    "SELECT bucket_hash,window_started,attempts FROM portal_auth_rate_limits WHERE bucket_hash IN (?,?)",
                    buckets,
                )
            }
            if any(
                row["window_started"] + window_seconds > now and row["attempts"] >= limit
                for row in rows.values()
            ):
                return False
            for bucket in buckets:
                row = rows.get(bucket)
                if not row or row["window_started"] + window_seconds <= now:
                    conn.execute(
                        "INSERT INTO portal_auth_rate_limits(bucket_hash,window_started,attempts) VALUES(?,?,1) "
                        "ON CONFLICT(bucket_hash) DO UPDATE SET window_started=excluded.window_started,attempts=1",
                        (bucket, now),
                    )
                else:
                    conn.execute("UPDATE portal_auth_rate_limits SET attempts=attempts+1 WHERE bucket_hash=?", (bucket,))
            return True

    def create_first_local_operator(self, *, username: str, normalized_username: str, password_hash: str) -> dict[str, Any]:
        if not password_hash:
            raise ValueError("Password hash is required")
        now = _iso()
        user_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM portal_users WHERE role='operator' LIMIT 1").fetchone():
                raise PermissionError("An operator already exists")
            try:
                conn.execute(
                    "INSERT INTO portal_users(id,oidc_subject,email,email_verified,display_name,role,status,created_at,last_login_at,username,username_normalized,password_hash,password_hash_algorithm,password_hash_updated_at) "
                    "VALUES(?,NULL,NULL,0,?,'operator','active',?,?,?,?,?,'argon2id',?)",
                    (user_id, username, now, now, username, normalized_username, password_hash, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Username is already in use") from error
            return dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user_id,)).fetchone())

    def adopt_existing_operator(
        self, *, user_id: str, username: str, normalized_username: str, password_hash: str
    ) -> dict[str, Any]:
        if not password_hash:
            raise ValueError("Password hash is required")
        now = _iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute("SELECT role,username,password_hash FROM portal_users WHERE id=?", (user_id,)).fetchone()
            if not user or user["role"] != "operator" or user["username"] is not None or user["password_hash"] is not None:
                raise PermissionError("Only an operator without local credentials can be adopted")
            try:
                updated = conn.execute(
                    "UPDATE portal_users SET username=?,username_normalized=?,password_hash=?,password_hash_algorithm='argon2id',password_hash_updated_at=? "
                    "WHERE id=? AND role='operator' AND username IS NULL AND password_hash IS NULL",
                    (username, normalized_username, password_hash, now, user_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Username is already in use") from error
            if updated.rowcount != 1:
                raise PermissionError("Only an operator without local credentials can be adopted")
            return dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user_id,)).fetchone())

    def reset_local_password(self, *, user_id: str, password_hash: str) -> bool:
        if not password_hash:
            raise ValueError("Password hash is required")
        now = _iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            updated = conn.execute(
                "UPDATE portal_users SET password_hash=?,password_hash_algorithm='argon2id',password_hash_updated_at=? "
                "WHERE id=? AND username IS NOT NULL AND status='active'",
                (password_hash, now, user_id),
            )
            if updated.rowcount != 1:
                return False
            conn.execute("UPDATE portal_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE user_id=?", (now, user_id))
            return True

    def record_local_login(self, user_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE portal_users SET last_login_at=? WHERE id=? AND status='active'", (_iso(), user_id))

    def create_oauth_transaction(self, state: str, nonce: str, invite_id: str | None, ttl_seconds: int = 600) -> None:
        if not 60 <= ttl_seconds <= 900:
            raise ValueError("OAuth transaction expiry must be between 60 and 900 seconds")
        with self.connect() as conn:
            conn.execute("DELETE FROM portal_oauth_transactions WHERE expires_at <= ?", (_iso(),))
            conn.execute(
                "INSERT INTO portal_oauth_transactions(state_hash,nonce,invite_id,expires_at,created_at) VALUES(?,?,?,?,?)",
                (_digest(state, self.key_pepper), nonce, invite_id, _iso(_now() + timedelta(seconds=ttl_seconds)), _iso()),
            )

    def consume_oauth_transaction(self, state: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT nonce,invite_id,expires_at FROM portal_oauth_transactions WHERE state_hash=?", (_digest(state, self.key_pepper),)).fetchone()
            if not row or row["expires_at"] <= _iso():
                if row:
                    conn.execute("DELETE FROM portal_oauth_transactions WHERE state_hash=?", (_digest(state, self.key_pepper),))
                return None
            conn.execute("DELETE FROM portal_oauth_transactions WHERE state_hash=?", (_digest(state, self.key_pepper),))
            return dict(row)

    @staticmethod
    def _consume_invite(conn: sqlite3.Connection, invite_id: str, user_id: str, now: str) -> bool:
        result = conn.execute(
            "UPDATE portal_invites SET uses_count=uses_count+1, "
            "consumed_at=CASE WHEN uses_count+1>=max_uses THEN ? ELSE consumed_at END, "
            "consumed_by_user_id=COALESCE(consumed_by_user_id,?) "
            "WHERE id=? AND uses_count<max_uses AND revoked_at IS NULL AND expires_at>?",
            (now, user_id, invite_id, now),
        )
        return result.rowcount == 1

    def provision_identity(self, *, subject: str, email: str | None, email_verified: bool, name: str, invite_id: str | None) -> dict[str, Any]:
        now = _iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute("SELECT * FROM portal_users WHERE oidc_subject=?", (subject,)).fetchone()
            if user:
                if user["status"] != "active":
                    raise PermissionError("This account is suspended")
                if invite_id:
                    invite = conn.execute("SELECT * FROM portal_invites WHERE id=?", (invite_id,)).fetchone()
                    if not invite or invite["revoked_at"] or invite["uses_count"] >= invite["max_uses"] or invite["expires_at"] <= now:
                        raise PermissionError("This invitation is invalid, expired, revoked, or exhausted")
                    if invite["bound_email"] and (not email_verified or not email or invite["bound_email"] != email.strip().lower()):
                        raise PermissionError("This invitation is bound to a different verified email address")
                    if not self._consume_invite(conn, invite_id, user["id"], now):
                        raise PermissionError("This invitation was already exhausted")
                conn.execute("UPDATE portal_users SET email=?, email_verified=?, display_name=?, last_login_at=? WHERE id=?", (email, int(email_verified), name, now, user["id"]))
                return dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user["id"],)).fetchone())
            if not invite_id:
                raise PermissionError("An operator invitation is required to create an account")
            invite = conn.execute("SELECT * FROM portal_invites WHERE id=?", (invite_id,)).fetchone()
            if not invite or invite["revoked_at"] or invite["uses_count"] >= invite["max_uses"] or invite["expires_at"] <= now:
                raise PermissionError("This invitation is invalid, expired, revoked, or exhausted")
            if invite["bound_email"] and (not email_verified or not email or invite["bound_email"] != email.strip().lower()):
                raise PermissionError("This invitation is bound to a different verified email address")
            user_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO portal_users(id,oidc_subject,email,email_verified,display_name,role,status,created_at,last_login_at) VALUES(?,?,?,?,?,'developer','active',?,?)",
                (user_id, subject, email, int(email_verified), name or "Hack Club member", now, now),
            )
            if not self._consume_invite(conn, invite_id, user_id, now):
                raise PermissionError("This invitation was already exhausted")
            return dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user_id,)).fetchone())

    def upsert_user(self, *, subject: str, email: str | None, name: str, role: str = "developer") -> dict[str, Any]:
        """Provision/adjust identities for trusted offline bootstrap and tests only."""
        if role not in {"operator", "developer"}:
            raise ValueError("Unknown portal role")
        now = _iso()
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM portal_users WHERE oidc_subject=?", (subject,)).fetchone()
            if row:
                conn.execute("UPDATE portal_users SET email=?,display_name=?,role=?,status='active',last_login_at=? WHERE id=?", (email, name, role, now, row["id"]))
                user_id = row["id"]
            else:
                user_id = uuid.uuid4().hex
                conn.execute("INSERT INTO portal_users(id,oidc_subject,email,display_name,role,created_at,last_login_at) VALUES(?,?,?,?,?,?,?)", (user_id, subject, email, name, role, now, now))
            return dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user_id,)).fetchone())

    def bootstrap_operator(self, *, verified_subject: str, verified_email: str | None, email_verified: bool, configured_email: str | None, name: str) -> dict[str, Any]:
        """One-time bootstrap using the owner's verified Hack Club email claim."""
        configured = configured_email.strip().casefold() if configured_email else ""
        email = verified_email.strip().casefold() if verified_email else ""
        if not configured or not verified_subject or not email_verified or not email or not hmac.compare_digest(email, configured):
            raise PermissionError("Verified Hack Club email does not match the configured bootstrap email")
        now = _iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM portal_users WHERE role='operator' LIMIT 1").fetchone():
                raise PermissionError("Initial operator has already been provisioned")
            user = conn.execute("SELECT * FROM portal_users WHERE oidc_subject=?", (verified_subject,)).fetchone()
            if user:
                if user["status"] != "active":
                    raise PermissionError("Suspended identity cannot be bootstrapped")
                conn.execute("UPDATE portal_users SET role='operator',email=?,email_verified=1,display_name=?,last_login_at=? WHERE id=?", (verified_email, name, now, user["id"]))
                user_id = user["id"]
            else:
                user_id = uuid.uuid4().hex
                conn.execute("INSERT INTO portal_users(id,oidc_subject,email,email_verified,display_name,role,created_at,last_login_at) VALUES(?,?,?,1,?,'operator',?,?)", (user_id, verified_subject, verified_email, name or "Hack Club operator", now, now))
            return dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user_id,)).fetchone())

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            return self._dict(conn.execute("SELECT * FROM portal_users WHERE id=?", (user_id,)).fetchone())

    def get_user_by_subject(self, subject: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            return self._dict(conn.execute("SELECT * FROM portal_users WHERE oidc_subject=?", (subject,)).fetchone())

    def assign_user_allowance(self, user_id: str, amount_nano_usd: int | None, period: str | None, actor_id: str) -> None:
        if amount_nano_usd is not None and (isinstance(amount_nano_usd, bool) or not isinstance(amount_nano_usd, int) or amount_nano_usd < 0):
            raise ValueError("Allowance must be a non-negative integer number of nano-USD")
        if period not in (None, "daily", "weekly") or (amount_nano_usd is None) != (period is None):
            raise ValueError("Allowance amount and daily or weekly period must be set together")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute("SELECT id FROM portal_users WHERE id=?", (user_id,)).fetchone()
            if not user:
                raise LookupError("User not found")
            conn.execute("UPDATE user_allowances SET active=0 WHERE user_id=? AND active=1", (user_id,))
            if amount_nano_usd is not None:
                conn.execute("INSERT INTO user_allowances(id,user_id,amount_nano_usd,period,timezone,active,created_at) VALUES(?,?,?,?, 'Europe/Berlin',1,?)",
                             (uuid.uuid4().hex, user_id, amount_nano_usd, period, _iso()))
            usd = amount_nano_usd / 1_000_000_000 if amount_nano_usd is not None else None
            conn.execute("UPDATE portal_users SET allowance_usd=?,allowance_period=?,allowance_timezone='Europe/Berlin' WHERE id=?", (usd, period, user_id))
            conn.execute("INSERT INTO portal_audit_events(id,actor_user_id,action,target_type,target_id,details_json,occurred_at) VALUES(?,?,?,?,?,?,?)",
                         (uuid.uuid4().hex, actor_id, "person.allowance_assigned", "user", user_id, json.dumps({"amount_nano_usd": amount_nano_usd, "period": period}), _iso()))

    def set_connection_budget(self, connection_id: str, limit_nano_usd: int | None, period: str | None, reserve_nano_usd: int, actor_id: str) -> None:
        if limit_nano_usd is not None and (isinstance(limit_nano_usd, bool) or not isinstance(limit_nano_usd, int) or limit_nano_usd < 0):
            raise ValueError("Connection limit must be a non-negative integer number of nano-USD")
        if isinstance(reserve_nano_usd, bool) or not isinstance(reserve_nano_usd, int) or reserve_nano_usd < 0:
            raise ValueError("Reserve must be a non-negative integer number of nano-USD")
        if period not in (None, "daily", "weekly", "monthly", "lifetime") or (limit_nano_usd is None) != (period is None):
            raise ValueError("A connection limit requires a supported period")
        if limit_nano_usd is not None and reserve_nano_usd > limit_nano_usd:
            raise ValueError("Reserve cannot exceed the connection limit")
        if limit_nano_usd is None and reserve_nano_usd:
            raise ValueError("A reserve requires a finite connection limit")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM provider_connections WHERE id=?", (connection_id,)).fetchone():
                raise LookupError("Provider connection not found")
            existing = conn.execute("SELECT id FROM provider_budgets WHERE connection_id=?", (connection_id,)).fetchone()
            if existing:
                conn.execute("UPDATE provider_budgets SET cap_nano_usd=?,period=?,reserve_nano_usd=? WHERE id=?", (limit_nano_usd, period, reserve_nano_usd, existing["id"]))
            elif limit_nano_usd is not None or reserve_nano_usd:
                conn.execute("INSERT INTO provider_budgets(id,connection_id,cap_nano_usd,period,reserve_nano_usd,created_at) VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, connection_id, limit_nano_usd, period, reserve_nano_usd, _iso()))
            conn.execute("INSERT INTO portal_audit_events(id,actor_user_id,action,target_type,target_id,details_json,occurred_at) VALUES(?,?,?,?,?,?,?)",
                         (uuid.uuid4().hex, actor_id, "connection.budget_updated", "connection", connection_id, json.dumps({"limit_nano_usd": limit_nano_usd, "period": period, "reserve_nano_usd": reserve_nano_usd}), _iso()))

    @staticmethod
    def _sum_nano_rows(rows: list[sqlite3.Row]) -> int:
        total = 0
        for row in rows:
            amount = row["amount_nano_usd"]
            if amount is None:
                amount = PortalDatabase._charge_nano_usd(row["estimated_cost_usd"])
            total += amount or 0
        return total

    def expire_request_budget_reservations(self, now: datetime, *, older_than_seconds: int = 600) -> int:
        if now.tzinfo is None or now.utcoffset() is None or older_than_seconds < 1:
            raise ValueError("An aware time and positive expiry interval are required")
        cutoff = _iso(now - timedelta(seconds=older_than_seconds))
        with self.connect() as conn:
            expired = conn.execute("SELECT id,amount_nano_usd FROM portal_budget_reservations_v2 WHERE status='active' AND julianday(created_at)<=julianday(?) ORDER BY created_at", (cutoff,)).fetchall()
        settled = 0
        for row in expired:
            try:
                self.settle_request_budget(row["id"], row["amount_nano_usd"], None)
                settled += 1
            except ValueError:
                pass
        return settled

    def reserve_request_budget(self, owner_user_id: str, key_id: str, offer_id: str, connection_id: str, estimated_nano_usd: int, now: datetime, global_limit_nano_usd: int | None, *, public_model_id: str | None = None) -> BudgetReservation | None:
        if isinstance(estimated_nano_usd, bool) or not isinstance(estimated_nano_usd, int) or estimated_nano_usd < 0:
            raise ValueError("Estimate must be a non-negative integer number of nano-USD")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        self.expire_request_budget_reservations(now)
        reservation_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            key = conn.execute("SELECT k.owner_user_id,k.spend_limit_usd,k.spend_period,k.allowed_models_mode,k.allowed_models_json,u.status FROM portal_keys k JOIN portal_users u ON u.id=k.owner_user_id WHERE k.id=? AND k.owner_user_id=? AND k.revoked_at IS NULL AND k.archived_at IS NULL", (key_id, owner_user_id)).fetchone()
            connection = conn.execute("SELECT c.id FROM provider_connections c JOIN provider_brands b ON b.id=c.brand_id WHERE c.id=? AND c.enabled=1 AND c.mapping_status='mapped' AND b.identity_status='mapped'", (connection_id,)).fetchone()
            if not key or key["status"] != "active" or not connection:
                return None
            price = conn.execute("SELECT price.id,price.input_rate,price.output_rate,price.cached_input_rate,price.rate_unit,offer.canonical_model_id,brand.slug,brand.migration_ref FROM price_versions price JOIN catalog_offers offer ON offer.id=price.offer_id JOIN provider_brands brand ON brand.id=offer.brand_id WHERE price.offer_id=? AND price.is_active=1 AND offer.approved=1 AND offer.active=1", (offer_id,)).fetchone()
            route = conn.execute("""SELECT route.id route_id,route.upstream_model_id,offer.brand_id,
                    offer.canonical_model_id,brand.name provider_name
                FROM offer_routes route JOIN catalog_offers offer ON offer.id=route.offer_id
                JOIN provider_brands brand ON brand.id=offer.brand_id
                WHERE route.offer_id=? AND route.connection_id=? AND route.active=1""", (offer_id, connection_id)).fetchone()
            if not price or not route:
                return None
            if public_model_id is not None:
                current_ids = {
                    format_public_model_id(scope, price["canonical_model_id"])
                    for scope in (price["slug"], price["migration_ref"]) if scope
                }
                selected_ids = set(json.loads(key["allowed_models_json"] or "[]"))
                if public_model_id not in current_ids or (
                    key["allowed_models_mode"] == "selected" and not current_ids.intersection(selected_ids)
                ):
                    raise BudgetModelPolicyChanged("The selected offer no longer satisfies the key model policy")
            route_snapshot = {
                "connection_id": connection_id,
                "offer_id": offer_id,
                "offer_route_id": route["route_id"],
                "upstream_model_id": route["upstream_model_id"],
                "brand_id": route["brand_id"],
                "provider_name": route["provider_name"],
                "canonical_model_id": route["canonical_model_id"],
                "public_model_id": public_model_id,
            }
            price_snapshot = json.dumps({"input_rate": price["input_rate"], "output_rate": price["output_rate"], "cached_input_rate": price["cached_input_rate"], "rate_unit": price["rate_unit"]}, sort_keys=True)
            user_allowance = conn.execute("SELECT amount_nano_usd,period FROM user_allowances WHERE user_id=? AND active=1", (owner_user_id,)).fetchone()
            if user_allowance:
                allowance = (user_allowance["amount_nano_usd"], user_allowance["period"])
            else:
                user = conn.execute("SELECT allowance_usd,allowance_period FROM portal_users WHERE id=?", (owner_user_id,)).fetchone()
                allowance = (self._cap_nano_usd(user["allowance_usd"]), user["allowance_period"]) if user["allowance_usd"] is not None else None
            key_budget = conn.execute("SELECT cap_nano_usd,period FROM provider_budgets WHERE key_id=?", (key_id,)).fetchone()
            if not key_budget and key["spend_limit_usd"] is not None:
                key_budget = {"cap_nano_usd": self._cap_nano_usd(key["spend_limit_usd"]), "period": key["spend_period"]}
            connection_budget = conn.execute("SELECT cap_nano_usd,period,reserve_nano_usd FROM provider_budgets WHERE connection_id=?", (connection_id,)).fetchone()
            scopes: list[tuple[str, int, str | None, list[str]]] = []
            if allowance:
                scopes.append(("user", allowance[0], allowance[1], [owner_user_id]))
            if key_budget and key_budget["cap_nano_usd"] is not None:
                scopes.append(("key", key_budget["cap_nano_usd"], key_budget["period"], [owner_user_id, key_id]))
            if connection_budget and connection_budget["cap_nano_usd"] is not None:
                scopes.append(("connection", connection_budget["cap_nano_usd"] - connection_budget["reserve_nano_usd"], connection_budget["period"], [connection_id]))
            if global_limit_nano_usd is not None:
                scopes.append(("global", global_limit_nano_usd, "lifetime", []))
            for kind, cap, period, identifiers in scopes:
                if cap < 0:
                    return None
                window = period_window(period or "lifetime", now)
                start = window.start_utc.isoformat()
                where = "julianday(occurred_at)>=julianday(?)"
                event_args: list[Any] = [start]
                reserved_where = "julianday(created_at)>=julianday(?) AND status='active'"
                reserved_args: list[Any] = [start]
                if window.end_utc:
                    where += " AND julianday(occurred_at)<julianday(?)"
                    event_args.append(window.end_utc.isoformat())
                    reserved_where += " AND julianday(created_at)<julianday(?)"
                    reserved_args.append(window.end_utc.isoformat())
                if kind in ("user", "key"):
                    where += " AND owner_user_id=?"
                    event_args.append(identifiers[0])
                    reserved_where += " AND owner_user_id=?"
                    reserved_args.append(identifiers[0])
                if kind == "key":
                    where += " AND key_id=?"
                    event_args.append(identifiers[1])
                    reserved_where += " AND key_id=?"
                    reserved_args.append(identifiers[1])
                if kind == "connection":
                    aliases = conn.execute("SELECT legacy_profile_id FROM provider_connections WHERE id=?", (connection_id,)).fetchone()
                    providers = [connection_id] + ([aliases[0]] if aliases and aliases[0] else [])
                    where += " AND provider_id IN (" + ",".join("?" for _ in providers) + ")"
                    event_args.extend(providers)
                    reserved_where += " AND connection_id=?"
                    reserved_args.append(connection_id)
                events = conn.execute(f"SELECT amount_nano_usd,estimated_cost_usd,status FROM portal_usage_events WHERE {where}", event_args).fetchall()
                reserved = conn.execute(f"SELECT amount_nano_usd FROM portal_budget_reservations_v2 WHERE {reserved_where}", reserved_args).fetchall()
                known_no_delivery = {"rejected", "blocked", "connect_failed", "model_not_found"}
                if any(row["amount_nano_usd"] is None and row["estimated_cost_usd"] is None and row["status"] not in known_no_delivery for row in events):
                    return None
                used_nano = self._sum_nano_rows(events)
                reserved_nano = sum(row["amount_nano_usd"] for row in reserved)
                if used_nano + reserved_nano + estimated_nano_usd > cap:
                    return None
            conn.execute("""INSERT INTO portal_budget_reservations_v2(
                    id,owner_user_id,key_id,amount_nano_usd,created_at,status,offer_id,
                    connection_id,price_version_id,price_snapshot_json,public_model_id,route_snapshot_json
                ) VALUES(?,?,?,?,?,'active',?,?,?,?,?,?)""",
                (reservation_id, owner_user_id, key_id, estimated_nano_usd, _iso(now), offer_id,
                 connection_id, price["id"], price_snapshot, public_model_id,
                 json.dumps(route_snapshot, sort_keys=True)))
        return BudgetReservation(reservation_id, estimated_nano_usd, "active", owner_user_id, key_id, connection_id)

    def release_request_budget(self, reservation_id: str, *, delivery_known_absent: bool) -> bool:
        if delivery_known_absent is not True:
            raise ValueError("A reservation can be released only when upstream delivery is known absent")
        with self.connect() as conn:
            result = conn.execute("UPDATE portal_budget_reservations_v2 SET status='released' WHERE id=? AND status='active'", (reservation_id,))
            return result.rowcount == 1

    def settle_request_budget(
        self,
        reservation_id: str,
        charged_nano_usd: int,
        usage_fields: UsageFields | dict[str, Any] | None,
        *,
        connection_id: str | None = None,
        offer_id: str | None = None,
        upstream_model_id: str | None = None,
        price_version_id: str | None = None,
    ) -> None:
        if isinstance(charged_nano_usd, bool) or not isinstance(charged_nano_usd, int) or charged_nano_usd < 0:
            raise ValueError("Charge must be a non-negative integer number of nano-USD")
        fields = usage_fields if isinstance(usage_fields, UsageFields) else UsageFields(**usage_fields) if usage_fields else UsageFields(status="interrupted")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            reservation = conn.execute("SELECT * FROM portal_budget_reservations_v2 WHERE id=?", (reservation_id,)).fetchone()
            if not reservation or reservation["status"] != "active":
                raise ValueError("Budget reservation is not active")
            expected = (connection_id, offer_id, price_version_id)
            stored = (reservation["connection_id"], reservation["offer_id"], reservation["price_version_id"])
            if any(value is not None for value in expected) and expected != stored:
                raise ValueError("Budget reservation route snapshot does not match settlement")
            key = conn.execute("SELECT k.label,u.display_name,u.email FROM portal_keys k JOIN portal_users u ON u.id=k.owner_user_id WHERE k.id=? AND k.owner_user_id=?", (reservation["key_id"], reservation["owner_user_id"])).fetchone()
            if not key:
                raise LookupError("Reservation owner key no longer exists")
            route = conn.execute("""SELECT route.id route_id,offer.brand_id,offer.canonical_model_id,
                    brand.name provider_name,route.upstream_model_id
                FROM offer_routes route JOIN catalog_offers offer ON offer.id=route.offer_id
                JOIN provider_brands brand ON brand.id=offer.brand_id
                WHERE route.offer_id=? AND route.connection_id=?
                    AND (? IS NULL OR route.upstream_model_id=?)
                ORDER BY route.sort_order,route.id LIMIT 1""",
                (reservation["offer_id"], reservation["connection_id"], upstream_model_id, upstream_model_id)).fetchone() if reservation["offer_id"] and reservation["connection_id"] else None
            saved_route = json.loads(reservation["route_snapshot_json"]) if reservation["route_snapshot_json"] else None
            if saved_route:
                route = {
                    "route_id": saved_route["offer_route_id"], "brand_id": saved_route["brand_id"],
                    "canonical_model_id": saved_route["canonical_model_id"],
                    "provider_name": saved_route["provider_name"],
                    "upstream_model_id": saved_route["upstream_model_id"],
                }
            if upstream_model_id is not None and (not route or route["upstream_model_id"] != upstream_model_id):
                raise ValueError("Usage route does not match the reserved upstream model")
            event_id = uuid.uuid4().hex
            snapshot = json.loads(reservation["price_snapshot_json"]) if reservation["price_snapshot_json"] else None
            if snapshot and fields.input_tokens is not None and fields.output_tokens is not None and snapshot.get("input_rate") is not None and snapshot.get("output_rate") is not None:
                from app.money import rate_cost_nano_usd
                cached = fields.cached_tokens or 0
                charged_nano_usd = rate_cost_nano_usd(max(fields.input_tokens - cached, 0), cached, fields.output_tokens, Decimal(snapshot["input_rate"]), Decimal(snapshot["output_rate"]), Decimal(snapshot["cached_input_rate"]) if snapshot.get("cached_input_rate") is not None else None)
            price_version_id = reservation["price_version_id"]
            charge_usd = charged_nano_usd / 1_000_000_000
            route_snapshot = (saved_route or {"connection_id": reservation["connection_id"], "offer_id": reservation["offer_id"],
                               "offer_route_id": route["route_id"], "upstream_model_id": route["upstream_model_id"]}
                              if route else None)
            canonical_model_id = route["canonical_model_id"] if route else fields.model_id
            conn.execute("""INSERT INTO portal_usage_events(
                    id,owner_user_id,owner_name_snapshot,owner_email_snapshot,key_id,key_label_snapshot,
                    provider_id,provider_name_snapshot,model_id,occurred_at,status,error_category,latency_ms,input_tokens,
                    output_tokens,total_tokens,cached_tokens,stream,estimated_cost_usd,origin,amount_nano_usd,
                    brand_id,canonical_model_id,offer_route_id,price_version_id,brand_snapshot,model_snapshot,
                    route_snapshot_json,price_snapshot_v2_json,price_snapshot_json,client_ip,request_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, reservation["owner_user_id"], key["display_name"], key["email"], reservation["key_id"],
                 key["label"], reservation["connection_id"], route["provider_name"] if route else None,
                 canonical_model_id or "unknown", reservation["created_at"], fields.status, fields.error_category, fields.latency_ms,
                 fields.input_tokens, fields.output_tokens, fields.total_tokens, fields.cached_tokens, int(fields.stream),
                 charge_usd, "gateway", charged_nano_usd, route["brand_id"] if route else None,
                 canonical_model_id, route["route_id"] if route else None, price_version_id,
                 route["provider_name"] if route else None, canonical_model_id,
                 json.dumps(route_snapshot, sort_keys=True) if route_snapshot else None,
                 json.dumps(snapshot, sort_keys=True) if snapshot else None,
                 json.dumps(snapshot, sort_keys=True) if snapshot else None, fields.client_ip, fields.request_id))
            conn.execute("UPDATE portal_budget_reservations_v2 SET status='settled',settlement_event_id=? WHERE id=? AND status='active'", (event_id, reservation_id))

    def record_route_usage(
        self,
        reservation_id: str,
        *,
        connection_id: str,
        offer_id: str,
        upstream_model_id: str,
        price_version_id: str,
        charged_nano_usd: int,
        usage_fields: UsageFields | dict[str, Any] | None,
    ) -> int:
        self.settle_request_budget(
            reservation_id, charged_nano_usd, usage_fields,
            connection_id=connection_id, offer_id=offer_id,
            upstream_model_id=upstream_model_id, price_version_id=price_version_id,
        )
        with self.connect() as conn:
            row = conn.execute("SELECT settlement_event_id FROM portal_budget_reservations_v2 WHERE id=?", (reservation_id,)).fetchone()
        if not row or not row["settlement_event_id"]:
            raise ValueError("Route usage settlement did not produce a usage event")
        return 1

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT id,email,email_verified,display_name,role,status,allowance_usd,allowance_period,rpm_limit,allowance_timezone,created_at,last_login_at FROM portal_users ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def set_user_policy(self, user_id: str, *, allowance_usd: float | None, allowance_period: str | None, rpm_limit: int | None) -> None:
        if allowance_usd is not None and (isinstance(allowance_usd, bool) or not isinstance(allowance_usd, (int, float)) or not math.isfinite(allowance_usd) or allowance_usd < 0):
            raise ValueError("Allowance must be finite and non-negative")
        if allowance_period not in {None, "daily", "weekly"}:
            raise ValueError("Allowance period must be daily or weekly")
        if allowance_usd is not None and allowance_period is None:
            raise ValueError("A finite allowance requires a daily or weekly period")
        if rpm_limit is not None and (isinstance(rpm_limit, bool) or not isinstance(rpm_limit, int) or rpm_limit < 1):
            raise ValueError("RPM must be positive or unlimited")
        with self.connect() as conn:
            conn.execute("UPDATE portal_users SET allowance_usd=?,allowance_period=?,rpm_limit=? WHERE id=?", (allowance_usd, allowance_period, rpm_limit, user_id))

    def set_user_state(self, user_id: str, *, active: bool) -> bool:
        with self.connect() as conn:
            result = conn.execute("UPDATE portal_users SET status=? WHERE id=? AND role='developer'", ("active" if active else "suspended", user_id))
            return result.rowcount == 1

    def create_session(self, user_id: str, *, ttl_seconds: int = 8 * 60 * 60) -> CreatedSession:
        raw = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        issued = _now()
        expires = issued + timedelta(seconds=ttl_seconds)
        with self.connect() as conn:
            user = conn.execute("SELECT status FROM portal_users WHERE id=?", (user_id,)).fetchone()
            if not user or user["status"] != "active":
                raise PermissionError("Active user is required")
            conn.execute("INSERT INTO portal_sessions(token_hash,csrf_hash,user_id,issued_at,expires_at) VALUES(?,?,?,?,?)", (_digest(raw, self.key_pepper), _digest(csrf, self.key_pepper), user_id, _iso(issued), _iso(expires)))
        return CreatedSession(raw, csrf, _iso(expires))

    def get_session(self, raw_token: str) -> tuple[dict[str, Any], str] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT s.csrf_hash,s.expires_at,s.revoked_at,u.* FROM portal_sessions s JOIN portal_users u ON u.id=s.user_id WHERE s.token_hash=?",
                (_digest(raw_token, self.key_pepper),),
            ).fetchone()
        if not row or row["revoked_at"] or row["expires_at"] <= _iso() or row["status"] != "active":
            return None
        data = dict(row)
        csrf_hash = data.pop("csrf_hash")
        return data, csrf_hash

    def verify_csrf(self, expected_hash: str, csrf_token: str) -> bool:
        return hmac.compare_digest(expected_hash, _digest(csrf_token, self.key_pepper))

    def revoke_session(self, raw_token: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE portal_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE token_hash=?", (_iso(), _digest(raw_token, self.key_pepper)))

    def register_connection(
        self,
        secret_profile_id: str,
        brand_slug: str,
        brand_name: str,
        connection_label: str,
    ) -> ProviderConnection:
        if not isinstance(secret_profile_id, str) or not secret_profile_id.strip():
            raise ValueError("A legacy secret profile ID is required")
        brand_slug = brand_slug.strip().lower() if isinstance(brand_slug, str) else ""
        brand_name = brand_name.strip() if isinstance(brand_name, str) else ""
        connection_label = connection_label.strip() if isinstance(connection_label, str) else ""
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", brand_slug):
            raise ValueError("Brand slug must contain lowercase letters, digits, and single hyphens")
        if not brand_name or len(brand_name) > 120 or not connection_label or len(connection_label) > 120:
            raise ValueError("Brand name and connection label are required")
        with self.connect() as conn:
            if not self._table_exists(conn, "upstream_profiles"):
                raise LookupError("The encrypted upstream profile does not exist")
            profile = conn.execute(
                "SELECT id,name,provider_kind,base_url,enabled,created_at FROM upstream_profiles WHERE id=?",
                (secret_profile_id,),
            ).fetchone()
            if not profile:
                raise LookupError("The encrypted upstream profile does not exist")

            brand = conn.execute("SELECT id FROM provider_brands WHERE slug=?", (brand_slug,)).fetchone()
            if not brand:
                brand = conn.execute("SELECT id FROM provider_brands WHERE migration_ref=?", (secret_profile_id,)).fetchone()
            brand_id = brand["id"] if brand else f"brand:{brand_slug}"
            if brand:
                conn.execute("UPDATE provider_brands SET name=?,slug=?,identity_status='mapped' WHERE id=?", (brand_name, brand_slug, brand_id))
            else:
                conn.execute("INSERT INTO provider_brands(id,name,migration_ref,created_at,identity_status,slug) VALUES(?,?,?,?, 'mapped',?)",
                             (brand_id, brand_name, secret_profile_id, profile["created_at"], brand_slug))

            existing = conn.execute("SELECT id FROM provider_connections WHERE legacy_profile_id=?", (secret_profile_id,)).fetchone()
            connection_id = existing["id"] if existing else secret_profile_id
            conn.execute("""INSERT INTO provider_connections(
                id,brand_id,legacy_profile_id,base_url,provider_kind,secret_ref,enabled,created_at,mapping_status,legacy_enabled,label
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(legacy_profile_id) DO UPDATE SET brand_id=excluded.brand_id,
                    base_url=excluded.base_url,provider_kind=excluded.provider_kind,
                    secret_ref=excluded.secret_ref,mapping_status='mapped',enabled=excluded.enabled,label=excluded.label""",
                (connection_id, brand_id, secret_profile_id, profile["base_url"], profile["provider_kind"],
                 secret_profile_id, profile["enabled"], profile["created_at"], "mapped", profile["enabled"], connection_label))
            row = conn.execute("""SELECT id,brand_id,legacy_profile_id,base_url,secret_ref,mapping_status,enabled
                FROM provider_connections WHERE legacy_profile_id=?""", (secret_profile_id,)).fetchone()
        return ProviderConnection(row["id"], row["brand_id"], row["legacy_profile_id"], row["base_url"], row["secret_ref"], row["mapping_status"], bool(row["enabled"]))

    def get_connection(self, connection_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("""SELECT connection.*,brand.name brand_name,brand.slug brand_slug,
                brand.identity_status FROM provider_connections connection
                JOIN provider_brands brand ON brand.id=connection.brand_id WHERE connection.id=?""", (connection_id,)).fetchone()
        return dict(row) if row else None

    def apply_discovery(self, connection_id: str, discovered: list[DiscoveredModel], synced_at: datetime) -> SyncSummary:
        if not isinstance(synced_at, datetime):
            raise ValueError("Discovery timestamp must be a datetime")
        if not isinstance(discovered, list) or any(not isinstance(model, DiscoveredModel) for model in discovered):
            raise ValueError("Discovered models must be normalized DiscoveredModel records")
        ids = [model.id for model in discovered]
        if any(not model_id for model_id in ids) or len(ids) != len(set(ids)):
            raise ValueError("Discovered model IDs must be non-empty and unique")
        synced_text = _iso(synced_at)
        with self.connect() as conn:
            connection = conn.execute("""SELECT c.*,b.name brand_name,b.slug brand_slug,b.identity_status
                FROM provider_connections c JOIN provider_brands b ON b.id=c.brand_id WHERE c.id=?""", (connection_id,)).fetchone()
            if not connection:
                raise LookupError("Provider connection does not exist")
            if connection["mapping_status"] != "mapped" or connection["identity_status"] != "mapped":
                raise ValueError("Provider connection must be mapped before model discovery")
            if not self._table_exists(conn, "upstream_profiles") or not conn.execute(
                "SELECT 1 FROM upstream_profiles WHERE id=?", (connection["legacy_profile_id"],)
            ).fetchone():
                raise ValueError("Provider connection has no exact encrypted profile")

            previous_rows = conn.execute("SELECT upstream_model_id,active,is_stale FROM connection_models WHERE connection_id=?", (connection_id,)).fetchall()
            previous = {row["upstream_model_id"]: row for row in previous_rows}
            before = sum(bool(row["active"] and not row["is_stale"]) for row in previous_rows)
            missing_ids = set(previous) - set(ids)
            conn.execute("UPDATE connection_models SET active=0,is_stale=1 WHERE connection_id=?", (connection_id,))
            for upstream_model_id in missing_ids:
                conn.execute("UPDATE offer_routes SET review_required=1 WHERE connection_id=? AND upstream_model_id=?",
                             (connection_id, upstream_model_id))
            for model in discovered:
                old = previous.get(model.id)
                if old and (old["is_stale"] or not old["active"]):
                    conn.execute("UPDATE offer_routes SET review_required=1 WHERE connection_id=? AND upstream_model_id=?",
                                 (connection_id, model.id))
                conn.execute("""INSERT INTO connection_models(
                    connection_id,upstream_model_id,metadata_json,active,is_stale,last_seen_at,canonical_model_id,mapping_source)
                    VALUES(?,?,?,1,0,?,?, 'exact') ON CONFLICT(connection_id,upstream_model_id) DO UPDATE SET
                    metadata_json=excluded.metadata_json,active=1,is_stale=0,last_seen_at=excluded.last_seen_at""",
                    (connection_id, model.id, json.dumps({"name": model.name, "context_length": model.context_length,
                     "capabilities": list(model.capabilities), "metadata": dict(model.metadata)}, sort_keys=True), synced_text, model.id))

                canonical = conn.execute("SELECT canonical_model_id FROM connection_models WHERE connection_id=? AND upstream_model_id=?",
                                         (connection_id, model.id)).fetchone()["canonical_model_id"] or model.id
                offer_id = f"offer:{uuid.uuid5(uuid.NAMESPACE_URL, connection['brand_id'] + ':' + canonical).hex}"
                conn.execute("""INSERT OR IGNORE INTO catalog_offers(
                    id,brand_id,canonical_model_id,display_name,capabilities_json,approved,active,updated_at
                    ) VALUES(?,?,?,?,?,0,0,?)""",
                    (offer_id, connection["brand_id"], canonical, model.name or canonical,
                     json.dumps(sorted(set(model.capabilities))), synced_text))
                offer = conn.execute("SELECT id FROM catalog_offers WHERE brand_id=? AND canonical_model_id=?",
                                     (connection["brand_id"], canonical)).fetchone()
                route_id = f"route:{uuid.uuid5(uuid.NAMESPACE_URL, connection_id + ':' + offer['id'] + ':' + model.id).hex}"
                conn.execute("""INSERT OR IGNORE INTO offer_routes(id,offer_id,connection_id,upstream_model_id)
                    VALUES(?,?,?,?)""", (route_id, offer["id"], connection_id, model.id))

            stale_count = conn.execute("SELECT COUNT(*) FROM connection_models WHERE connection_id=? AND is_stale=1", (connection_id,)).fetchone()[0]
            if before:
                stale_count = max(stale_count, before - len(ids))
        return SyncSummary(connection_id, len(ids), stale_count, tuple(ids))

    def mark_discovery_stale(self, connection_id: str, stale_at: datetime | None = None) -> int:
        with self.connect() as conn:
            conn.execute("UPDATE connection_models SET is_stale=1,active=0 WHERE connection_id=?", (connection_id,))
            conn.execute("UPDATE offer_routes SET review_required=1 WHERE connection_id=?", (connection_id,))
            return conn.execute("SELECT COUNT(*) FROM connection_models WHERE connection_id=? AND is_stale=1", (connection_id,)).fetchone()[0]

    def list_discovered_models(self, connection_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""SELECT upstream_model_id,metadata_json,active,is_stale,last_seen_at
                FROM connection_models WHERE connection_id=? ORDER BY upstream_model_id""", (connection_id,)).fetchall()
        return [{"id": row["upstream_model_id"], "metadata": json.loads(row["metadata_json"] or "{}"),
                 "active": bool(row["active"]), "stale": bool(row["is_stale"]), "last_seen_at": row["last_seen_at"]} for row in rows]

    def get_offer_id(self, brand_slug: str, canonical_model_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("""SELECT offer.id FROM catalog_offers offer
                JOIN provider_brands brand ON brand.id=offer.brand_id
                WHERE brand.slug=? AND offer.canonical_model_id=?""", (brand_slug, canonical_model_id)).fetchone()
        return row["id"] if row else None

    def get_discovered_offer_id(self, connection_id: str, upstream_model_id: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("""SELECT route.offer_id FROM offer_routes route
                JOIN connection_models discovered ON discovered.connection_id=route.connection_id
                    AND discovered.upstream_model_id=route.upstream_model_id
                WHERE route.connection_id=? AND route.upstream_model_id=?
                    AND discovered.active=1 AND discovered.is_stale=0""",
                (connection_id, upstream_model_id)).fetchone()
        return row["offer_id"] if row else None

    def map_connection_model(self, connection_id: str, upstream_model_id: str, offer_id: str, actor_id: str) -> None:
        if not isinstance(upstream_model_id, str) or not upstream_model_id:
            raise ValueError("An exact non-empty upstream model ID is required")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            source = conn.execute("""SELECT connection.brand_id,connection.enabled,connection.mapping_status,
                    brand.identity_status
                FROM provider_connections connection JOIN provider_brands brand ON brand.id=connection.brand_id
                WHERE connection.id=?""", (connection_id,)).fetchone()
            if not source:
                raise LookupError("Provider connection does not exist")
            if not source["enabled"] or source["mapping_status"] != "mapped" or source["identity_status"] != "mapped":
                raise ValueError("Provider connection must be mapped and enabled")
            if not self._table_exists(conn, "upstream_profiles") or not conn.execute(
                "SELECT 1 FROM upstream_profiles WHERE id=(SELECT legacy_profile_id FROM provider_connections WHERE id=?)",
                (connection_id,),
            ).fetchone():
                raise ValueError("Provider connection has no exact encrypted profile")
            discovered = conn.execute("""SELECT active,is_stale FROM connection_models
                WHERE connection_id=? AND upstream_model_id=?""", (connection_id, upstream_model_id)).fetchone()
            if not discovered or not discovered["active"] or discovered["is_stale"]:
                raise ValueError("Only an exact, active, freshly discovered upstream model can be mapped")
            target = conn.execute("SELECT id,brand_id,canonical_model_id FROM catalog_offers WHERE id=?", (offer_id,)).fetchone()
            if not target:
                raise LookupError("Target catalog offer does not exist")
            if target["brand_id"] != source["brand_id"]:
                raise ValueError("Manual model mappings must stay within the same provider brand")
            current_route = conn.execute("""SELECT id FROM offer_routes
                WHERE connection_id=? AND upstream_model_id=?""", (connection_id, upstream_model_id)).fetchone()
            if not current_route:
                raise ValueError("The discovered upstream model has no exact route")
            collision = conn.execute("""SELECT 1 FROM offer_routes WHERE offer_id=? AND connection_id=? AND id<>?""",
                                     (offer_id, connection_id, current_route["id"])).fetchone()
            if collision:
                raise ValueError("This connection already has a route to the selected offer")
            next_order = conn.execute("SELECT COALESCE(MAX(sort_order),-1)+1 FROM offer_routes WHERE offer_id=?", (offer_id,)).fetchone()[0]
            conn.execute("UPDATE connection_models SET canonical_model_id=?,mapping_source='manual' WHERE connection_id=? AND upstream_model_id=?",
                         (target["canonical_model_id"], connection_id, upstream_model_id))
            conn.execute("UPDATE offer_routes SET offer_id=?,sort_order=? WHERE id=?",
                         (offer_id, next_order, current_route["id"]))
        self.audit(actor_id, "model.manual_mapping_updated", "offer", offer_id,
                   {"connection_id": connection_id, "upstream_model_id": upstream_model_id})

    def save_price_suggestion(self, offer_id: str, price: PriceSuggestion) -> PriceVersion:
        if not isinstance(price, PriceSuggestion):
            raise ValueError("A PriceSuggestion record is required")
        rates = tuple(self._canonical_rate(value) for value in (
            price.input_usd_per_million, price.output_usd_per_million, price.cached_input_usd_per_million,
        ))
        if rates[0] is None or rates[1] is None or not price.source:
            raise ValueError("Input and output rates and a provenance source are required")
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM catalog_offers WHERE id=?", (offer_id,)).fetchone():
                raise LookupError("Catalog offer does not exist")
            existing = conn.execute("""SELECT id FROM price_suggestions WHERE offer_id=? AND input_rate IS ?
                AND output_rate IS ? AND cached_input_rate IS ? AND source=? AND source_url IS ? AND evidence IS ?
                AND status='pending' ORDER BY created_at DESC,id DESC LIMIT 1""",
                (offer_id, *rates, price.source, price.source_url, price.evidence)).fetchone()
            suggestion_id = existing["id"] if existing else uuid.uuid4().hex
            if existing:
                return PriceVersion(suggestion_id, offer_id, rates[0], rates[1], rates[2], "per_million_tokens", False)
            conn.execute("""INSERT INTO price_suggestions(
                id,offer_id,input_rate,output_rate,cached_input_rate,source,source_url,evidence,confidence,fetched_at,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (suggestion_id, offer_id, *rates, price.source, price.source_url, price.evidence,
                 price.confidence, price.fetched_at, _iso()))
        return PriceVersion(suggestion_id, offer_id, rates[0], rates[1], rates[2], "per_million_tokens", False)

    def approve_price_version(self, actor_id: str, offer_id: str, version_id: str) -> None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            suggestion = conn.execute("SELECT * FROM price_suggestions WHERE id=? AND offer_id=?", (version_id, offer_id)).fetchone()
            if not suggestion or suggestion["status"] != "pending":
                raise LookupError("Pending price suggestion does not exist")
            effective_at = _iso()
            conn.execute("UPDATE price_versions SET is_active=0,retired_at=? WHERE offer_id=? AND is_active=1", (effective_at, offer_id))
            effective_id = uuid.uuid4().hex
            conn.execute("""INSERT INTO price_versions(
                id,offer_id,input_rate,output_rate,cached_input_rate,source,is_active,effective_at
                ) VALUES(?,?,?,?,?,?,1,?)""",
                (effective_id, offer_id, suggestion["input_rate"], suggestion["output_rate"],
                 suggestion["cached_input_rate"], suggestion["source"], effective_at))
            conn.execute("UPDATE catalog_offers SET approved=1,price_source=?,updated_at=? WHERE id=?",
                         (suggestion["source"], effective_at, offer_id))
            conn.execute("""UPDATE price_suggestions SET status='approved',decided_by=?,decided_at=?,effective_version_id=?
                WHERE id=?""", (actor_id, effective_at, effective_id, version_id))
        self.audit(actor_id, "offer.price_approved", "offer", offer_id,
                   {"suggestion_id": version_id, "price_version_id": effective_id, "source": suggestion["source"]})

    @staticmethod
    def _route_price_matches(route: sqlite3.Row, price: sqlite3.Row | None) -> bool:
        if not price or not route["pricing_json"]:
            return price is not None
        try:
            reported_all = json.loads(route["pricing_json"])
            reported = reported_all.get(route["upstream_model_id"])
            if not isinstance(reported, dict):
                return True
            values = (reported.get("input"), reported.get("output"), reported.get("cache"))
            if values[0] is None or values[1] is None:
                return False
            normalized = tuple(PortalDatabase._canonical_rate(value) for value in values)
            expected = (price["input_rate"], price["output_rate"], price["cached_input_rate"])
            return normalized == expected
        except (TypeError, ValueError, json.JSONDecodeError):
            return False

    @classmethod
    def _load_offer_routes(cls, conn: sqlite3.Connection, offer_id: str, *, active_override: bool | None = None) -> tuple[CatalogOffer, list[OfferRoute]] | None:
        offer_row = conn.execute("SELECT * FROM catalog_offers WHERE id=?", (offer_id,)).fetchone()
        if not offer_row:
            return None
        price = conn.execute("SELECT * FROM price_versions WHERE offer_id=? AND is_active=1", (offer_id,)).fetchone()
        offer = CatalogOffer(
            offer_row["id"], offer_row["brand_id"], offer_row["canonical_model_id"], offer_row["display_name"],
            bool(offer_row["active"]) if active_override is None else active_override, bool(offer_row["approved"]),
            price["input_rate"] if price else None, price["output_rate"] if price else None,
            price["cached_input_rate"] if price else None,
        )
        profile_join = ("LEFT JOIN upstream_profiles profile ON profile.id=connection.legacy_profile_id"
                        if cls._table_exists(conn, "upstream_profiles")
                        else "LEFT JOIN (SELECT NULL AS id,NULL AS pricing_json) profile ON 0")
        rows = conn.execute(f"""SELECT route.*,connection.brand_id connection_brand_id,
                connection.label connection_label,
                connection.enabled connection_enabled,connection.mapping_status,
                brand.identity_status,discovered.active discovery_active,discovered.is_stale discovery_stale,
                profile.id exact_profile_id,profile.pricing_json
            FROM offer_routes route
            LEFT JOIN provider_connections connection ON connection.id=route.connection_id
            LEFT JOIN provider_brands brand ON brand.id=connection.brand_id
            LEFT JOIN connection_models discovered ON discovered.connection_id=connection.id
                AND discovered.upstream_model_id=route.upstream_model_id
            {profile_join}
            WHERE route.offer_id=? ORDER BY route.sort_order,route.id""", (offer_id,)).fetchall()
        routes = []
        for row in rows:
            price_matches = cls._route_price_matches(row, price)
            confirmed = bool(
                offer.approved and price and row["exact_profile_id"]
                and row["connection_brand_id"] == offer.brand_id
                and row["mapping_status"] == "mapped" and row["identity_status"] == "mapped"
                and row["discovery_active"] and not row["discovery_stale"]
            )
            routes.append(OfferRoute(
                row["id"], row["offer_id"], row["connection_id"], row["upstream_model_id"],
                row["connection_brand_id"], row["sort_order"], bool(row["active"]),
                bool(row["connection_enabled"]), row["mapping_status"] or "unmapped",
                row["identity_status"] or "unknown", bool(row["discovery_active"]),
                bool(row["discovery_stale"]), confirmed, price_matches,
                bool(row["review_required"]), row["connection_label"],
            ))
        return offer, routes

    def list_offer_routes(self, offer_id: str) -> list[OfferRoute]:
        with self.connect() as conn:
            loaded = self._load_offer_routes(conn, offer_id)
        if not loaded:
            raise LookupError("Catalog offer does not exist")
        return resolve_offer_routes(*loaded)

    def set_offer_route_order(self, offer_id: str, connection_ids: list[str], actor_id: str) -> None:
        if not isinstance(connection_ids, list) or any(not isinstance(value, str) or not value for value in connection_ids):
            raise ValueError("connectionIds must be an ordered array of connection IDs")
        if len(connection_ids) != len(set(connection_ids)):
            raise ValueError("A connection may appear only once in the route order")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            loaded = self._load_offer_routes(conn, offer_id)
            if not loaded:
                raise LookupError("Catalog offer does not exist")
            _offer, routes = loaded
            routes_by_connection = {route.connection_id: route for route in routes}
            for connection_id in connection_ids:
                route = routes_by_connection.get(connection_id)
                if not route or not route.confirmed or not route.price_matches:
                    raise ValueError("Every ordered route must have an exact fresh discovery and matching confirmed price")
            selected = set(connection_ids)
            remaining = [route.connection_id for route in routes if route.connection_id not in selected]
            ordering = connection_ids + remaining
            for position, connection_id in enumerate(ordering):
                conn.execute("UPDATE offer_routes SET sort_order=? WHERE offer_id=? AND connection_id=?",
                             (position, offer_id, connection_id))
        self.audit(actor_id, "offer.routes_updated", "offer", offer_id, {"connection_ids": connection_ids})

    def set_route_available(self, route_id: str, enabled: bool, actor_id: str) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Route availability must be boolean")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT offer_id FROM offer_routes WHERE id=?", (route_id,)).fetchone()
            if not row:
                raise LookupError("Offer route does not exist")
            loaded = self._load_offer_routes(conn, row["offer_id"])
            _offer, routes = loaded
            route = next(item for item in routes if item.id == route_id)
            if enabled and not (route.confirmed and route.price_matches and route.connection_enabled):
                raise ValueError("Route requires an exact mapped, enabled, freshly discovered matching price")
            reconfirmed = bool(enabled and route.review_required)
            if enabled:
                conn.execute("UPDATE offer_routes SET active=1,review_required=0 WHERE id=?", (route_id,))
            else:
                conn.execute("UPDATE offer_routes SET active=0 WHERE id=?", (route_id,))
        self.audit(actor_id, "route.availability_updated", "route", route_id,
                   {"enabled": enabled, "review_confirmed": reconfirmed})

    def set_offer_available(self, offer_id: str, enabled: bool, actor_id: str) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Offer availability must be boolean")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            offer = conn.execute("SELECT * FROM catalog_offers WHERE id=?", (offer_id,)).fetchone()
            if not offer:
                raise LookupError("Catalog offer does not exist")
            loaded = self._load_offer_routes(conn, offer_id, active_override=enabled)
            eligible_routes = resolve_offer_routes(*loaded) if loaded else []
            if enabled and not eligible_routes:
                raise ValueError("Offer requires an approved price and an exact mapped, enabled, freshly discovered route")
            effective_at = _iso()
            conn.execute("UPDATE catalog_offers SET active=?,updated_at=? WHERE id=?", (int(enabled), effective_at, offer_id))
        self.audit(actor_id, "offer.availability_changed", "offer", offer_id, {"enabled": enabled})

    def list_operator_offers(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""SELECT offer.*,brand.slug brand_slug,brand.name brand_name
                FROM catalog_offers offer JOIN provider_brands brand ON brand.id=offer.brand_id
                ORDER BY brand.name,offer.canonical_model_id""").fetchall()
            results = []
            for row in rows:
                active = conn.execute("SELECT * FROM price_versions WHERE offer_id=? AND is_active=1", (row["id"],)).fetchone()
                pending = conn.execute("SELECT * FROM price_suggestions WHERE offer_id=? AND status='pending' ORDER BY created_at DESC,id DESC LIMIT 1", (row["id"],)).fetchone()
                suggestions = conn.execute("SELECT * FROM price_suggestions WHERE offer_id=? AND status='pending' ORDER BY created_at DESC,id DESC", (row["id"],)).fetchall()
                loaded = self._load_offer_routes(conn, row["id"])
                eligible = bool(loaded and resolve_offer_routes(*loaded))
                results.append({
                    "id": row["id"], "brandSlug": row["brand_slug"], "brandName": row["brand_name"],
                    "canonicalModelId": row["canonical_model_id"], "displayName": row["display_name"],
                    "capabilities": json.loads(row["capabilities_json"] or "[]"),
                    "approved": bool(row["approved"]), "available": bool(row["active"] and eligible and active),
                    "activePrice": self._api_price(active), "pendingPrice": self._api_suggestion(pending),
                    "routes": [self._operator_route(route) for route in loaded[1]] if loaded else [],
                    "priceSuggestions": [self._api_suggestion(item) for item in suggestions],
                    "modelsDevSuggestion": next((self._api_suggestion(item) for item in suggestions if item["source"] == "models.dev"), None),
                    "providerReportedPrice": next((self._api_suggestion(item) for item in suggestions if item["source"] == "provider-reported"), None),
                })
        return results

    @staticmethod
    def _operator_route(route: OfferRoute) -> dict[str, Any]:
        if not route.confirmed:
            price_status = "unconfirmed"
        elif not route.price_matches:
            price_status = "mismatch"
        else:
            price_status = "matching"
        return {
            "id": route.id,
            "connectionId": route.connection_id,
            "connectionLabel": route.connection_label,
            "upstreamModelId": route.upstream_model_id,
            "order": route.position,
            "enabled": route.active,
            "active": route.active,
            "connectionEnabled": route.connection_enabled,
            "stale": route.discovery_stale or not route.discovery_active,
            "reviewRequired": route.review_required,
            "priceStatus": price_status,
        }

    @staticmethod
    def _api_price(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {"id": row["id"], "inputUsdPerMillion": row["input_rate"],
                "outputUsdPerMillion": row["output_rate"],
                "cachedInputUsdPerMillion": row["cached_input_rate"],
                "source": row["source"]}

    @staticmethod
    def _api_suggestion(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {"id": row["id"], "inputUsdPerMillion": row["input_rate"],
                "outputUsdPerMillion": row["output_rate"],
                "cachedInputUsdPerMillion": row["cached_input_rate"],
                "source": row["source"], "sourceUrl": row["source_url"],
                "evidence": row["evidence"], "confidence": row["confidence"]}

    def add_catalog_model(
        self,
        *,
        provider_id: str,
        model_id: str,
        provider_name: str,
        capabilities: list[str],
        input_price_per_million: float | None,
        output_price_per_million: float | None,
        cached_input_price_per_million: float | None = None,
        price_source: str | None = None,
        approved: bool = False,
        active: bool = True,
    ) -> None:
        for value in (input_price_per_million, output_price_per_million, cached_input_price_per_million):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError("Model prices must be finite non-negative numbers")
        if not provider_id or not model_id or not provider_name:
            raise ValueError("Provider and model identifiers are required")
        if not isinstance(capabilities, list) or any(item not in {"text", "vision"} for item in capabilities):
            raise ValueError("Model capabilities must be text or vision")
        with self.connect() as conn:
            conn.execute("""INSERT INTO portal_catalog_models(provider_id,model_id,provider_name,capabilities_json,input_price_per_million,output_price_per_million,cached_input_price_per_million,price_source,approved,active,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(provider_id,model_id) DO UPDATE SET provider_name=excluded.provider_name,capabilities_json=excluded.capabilities_json,input_price_per_million=excluded.input_price_per_million,output_price_per_million=excluded.output_price_per_million,cached_input_price_per_million=excluded.cached_input_price_per_million,price_source=excluded.price_source,approved=excluded.approved,active=excluded.active,updated_at=excluded.updated_at""",
                (provider_id, model_id, provider_name, json.dumps(sorted(set(capabilities))), input_price_per_million, output_price_per_million, cached_input_price_per_million, price_source, int(approved), int(active), _iso()))
            brand = conn.execute("SELECT id FROM provider_brands WHERE migration_ref=?", (provider_id,)).fetchone()
            brand_id = brand["id"] if brand else f"legacy-brand:{provider_id}"
            if not brand:
                conn.execute("INSERT INTO provider_brands(id,name,migration_ref,created_at) VALUES(?,?,?,?)",
                             (brand_id, "Unknown legacy provider", provider_id, _iso()))
            has_legacy_profile = self._table_exists(conn, "upstream_profiles") and conn.execute(
                "SELECT 1 FROM upstream_profiles WHERE id=?", (provider_id,)
            ).fetchone() is not None
            connection = conn.execute("SELECT id FROM provider_connections WHERE legacy_profile_id=?", (provider_id,)).fetchone()
            connection_id = connection["id"] if connection else f"legacy-connection:{provider_id}"
            fallback = None if connection else conn.execute(
                "SELECT legacy_profile_id FROM provider_connections WHERE id=?", (connection_id,)
            ).fetchone()
            orphaned_provider = not has_legacy_profile
            if not connection:
                if fallback is None:
                    conn.execute("INSERT OR IGNORE INTO provider_connections(id,brand_id,legacy_profile_id,secret_ref,enabled,mapping_status,created_at) VALUES(?,?,?,?,0,'unmapped',?)",
                                 (connection_id, brand_id, None, None, _iso()))
            if orphaned_provider:
                conn.execute("UPDATE provider_brands SET name='Unknown legacy provider',identity_status='unknown' WHERE id=?", (brand_id,))
                conn.execute("UPDATE provider_connections SET mapping_status='unmapped',enabled=0 WHERE id=?", (connection_id,))
            elif approved:
                conn.execute("UPDATE provider_brands SET name=?,identity_status='mapped' WHERE id=?", (provider_name, brand_id))
                conn.execute("UPDATE provider_connections SET mapping_status='mapped' WHERE id=?", (connection_id,))
            offer_id = f"legacy-offer:{provider_id}:{model_id}"
            conn.execute("""INSERT INTO catalog_offers(id,brand_id,canonical_model_id,display_name,capabilities_json,approved,active,price_source,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(brand_id,canonical_model_id) DO UPDATE SET
                display_name=excluded.display_name,capabilities_json=excluded.capabilities_json,
                approved=excluded.approved,active=excluded.active,price_source=excluded.price_source,updated_at=excluded.updated_at""",
                (offer_id, brand_id, model_id, model_id, json.dumps(sorted(set(capabilities))), int(approved), int(active), price_source, _iso()))
            route_active = int(approved and active and not orphaned_provider)
            conn.execute("INSERT OR IGNORE INTO offer_routes(id,offer_id,connection_id,upstream_model_id,active) VALUES(?,?,?,?,?)",
                         (f"legacy-route:{provider_id}:{model_id}", offer_id, connection_id, model_id, route_active))
            conn.execute("UPDATE offer_routes SET active=? WHERE offer_id=? AND connection_id=?", (route_active, offer_id, connection_id))
            if input_price_per_million is not None or output_price_per_million is not None or cached_input_price_per_million is not None:
                conn.execute("UPDATE price_versions SET is_active=0,retired_at=? WHERE offer_id=? AND is_active=1", (_iso(), offer_id))
                conn.execute("INSERT INTO price_versions(id,offer_id,input_rate,output_rate,cached_input_rate,source,is_active,effective_at) VALUES(?,?,?,?,?,?,?,?)",
                             (f"catalog-price:{provider_id}:{model_id}:{uuid.uuid4().hex}", offer_id,
                              self._canonical_rate(input_price_per_million), self._canonical_rate(output_price_per_million),
                              self._canonical_rate(cached_input_price_per_million), price_source, int(approved and active), _iso()))

    def add_price_version(
        self,
        offer_id: str,
        *,
        input_rate: str | int | float | Decimal | None,
        output_rate: str | int | float | Decimal | None,
        cached_input_rate: str | int | float | Decimal | None = None,
        source: str | None = None,
        is_active: bool = True,
        effective_at: str | None = None,
    ) -> PriceVersion:
        if not isinstance(is_active, bool):
            raise ValueError("Price version active flag must be boolean")
        canonical = tuple(self._canonical_rate(value) for value in (input_rate, output_rate, cached_input_rate))
        version_id = uuid.uuid4().hex
        effective_at = effective_at or _iso()
        with self.connect() as conn:
            if not conn.execute("SELECT 1 FROM catalog_offers WHERE id=?", (offer_id,)).fetchone():
                raise LookupError("Catalog offer does not exist")
            if is_active:
                conn.execute("UPDATE price_versions SET is_active=0,retired_at=? WHERE offer_id=? AND is_active=1", (effective_at, offer_id))
            conn.execute("INSERT INTO price_versions(id,offer_id,input_rate,output_rate,cached_input_rate,source,is_active,effective_at) VALUES(?,?,?,?,?,?,?,?)",
                         (version_id, offer_id, *canonical, source, int(is_active), effective_at))
        return PriceVersion(version_id, offer_id, *canonical, "per_million_tokens", is_active)

    def list_models(self, *, approved_only: bool = True, include_inactive: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM portal_catalog_models"
        if approved_only or not include_inactive:
            query += " WHERE EXISTS (SELECT 1 FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id WHERE b.migration_ref=portal_catalog_models.provider_id AND b.identity_status='mapped' AND c.legacy_profile_id=portal_catalog_models.provider_id AND c.mapping_status='mapped' AND c.enabled=1)"
        if not include_inactive:
            query += " AND " if " WHERE " in query else " WHERE "
            query += "active=1"
        if approved_only:
            query += " AND approved=1 AND input_price_per_million IS NOT NULL AND output_price_per_million IS NOT NULL"
            query += " AND EXISTS (SELECT 1 FROM portal_eligible_legacy_models eligible WHERE eligible.provider_id=portal_catalog_models.provider_id AND eligible.model_id=portal_catalog_models.model_id)"
        query += " ORDER BY provider_name,model_id"
        with self.connect() as conn:
            rows = conn.execute(query).fetchall()
            normalized_query = """SELECT DISTINCT offer.id offer_id,COALESCE(brand.slug,brand.migration_ref,brand.id) provider_id,
                brand.migration_ref,
                brand.name provider_name,offer.canonical_model_id model_id,offer.capabilities_json,
                price.input_rate input_price_per_million,
                price.output_rate output_price_per_million,
                price.cached_input_rate cached_input_price_per_million,
                price.source price_source,offer.approved,offer.active,offer.updated_at
                FROM catalog_offers offer JOIN provider_brands brand ON brand.id=offer.brand_id
                JOIN price_versions price ON price.offer_id=offer.id AND price.is_active=1
                JOIN offer_routes route ON route.offer_id=offer.id AND route.active=1
                JOIN provider_connections connection ON connection.id=route.connection_id AND connection.brand_id=offer.brand_id
                JOIN connection_models discovered ON discovered.connection_id=connection.id
                    AND discovered.upstream_model_id=route.upstream_model_id AND discovered.active=1 AND discovered.is_stale=0
                WHERE brand.identity_status='mapped' AND connection.mapping_status='mapped' AND connection.enabled=1
                    AND EXISTS (SELECT 1 FROM upstream_profiles profile WHERE profile.id=connection.legacy_profile_id)"""
            if approved_only:
                normalized_query += " AND offer.approved=1 AND offer.active=1"
            elif not include_inactive:
                normalized_query += " AND offer.active=1"
            normalized_query += " ORDER BY provider_name,model_id"
            normalized_rows = conn.execute(normalized_query).fetchall() if self._table_exists(conn, "upstream_profiles") else []
            if approved_only:
                normalized_rows = [row for row in normalized_rows
                                   if (loaded := self._load_offer_routes(conn, row["offer_id"]))
                                   and resolve_offer_routes(*loaded)]
        legacy = [dict(row) | {"capabilities": json.loads(row["capabilities_json"]), "public_model_id": f"{row['provider_id']}::{row['model_id']}"} for row in rows]
        normalized = [dict(row) | {"capabilities": json.loads(row["capabilities_json"] or "[]"),
                                   "public_model_id": format_public_model_id(row["provider_id"], row["model_id"])} for row in normalized_rows]
        legacy_keys = {(model["provider_id"], model["model_id"]) for model in legacy}
        normalized = [model for model in normalized if (model["migration_ref"], model["model_id"]) not in legacy_keys]
        public_ids = {model["public_model_id"] for model in legacy}
        return sorted(legacy + [model for model in normalized if model["public_model_id"] not in public_ids],
                      key=lambda model: (model["provider_name"], model["model_id"]))

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        eligible = self.list_models(approved_only=True)
        exact = [item for item in eligible if item["public_model_id"] == model_id]
        if not exact and "::" not in model_id:
            exact = [item for item in eligible if item["model_id"] == model_id]
        return exact[0] if len(exact) == 1 else None

    def get_offer_for_request(self, public_model_id: str, key_id: str) -> ResolvedOffer | None:
        """Resolve an active, priced offer and its eligible routes under a key's model policy."""
        if not isinstance(public_model_id, str) or not isinstance(key_id, str):
            return None
        brand_slug, separator, canonical_model_id = public_model_id.partition("::")
        if not separator or not brand_slug or not canonical_model_id:
            return None
        model_hint = self.get_model(public_model_id)
        provider_hint = model_hint.get("provider_id") if model_hint else None
        with self.connect() as conn:
            key = conn.execute("""SELECT key.allowed_models_mode,key.allowed_models_json,user.status
                FROM portal_keys key JOIN portal_users user ON user.id=key.owner_user_id
                WHERE key.id=? AND key.revoked_at IS NULL AND key.archived_at IS NULL""", (key_id,)).fetchone()
            if not key or key["status"] != "active":
                return None
            allowed_models = json.loads(key["allowed_models_json"] or "[]")
            if key["allowed_models_mode"] == "selected" and public_model_id not in allowed_models:
                return None
            row = conn.execute("""SELECT offer.id,offer.brand_id,offer.canonical_model_id,
                    offer.capabilities_json,brand.slug brand_slug,brand.name provider_name,
                    price.id price_version_id,price.input_rate,price.output_rate,price.cached_input_rate
                FROM catalog_offers offer
                JOIN provider_brands brand ON brand.id=offer.brand_id
                JOIN price_versions price ON price.offer_id=offer.id AND price.is_active=1
                WHERE (brand.slug=? OR brand.migration_ref=? OR EXISTS (
                    SELECT 1 FROM provider_connections connection
                    WHERE connection.brand_id=brand.id AND connection.legacy_profile_id=?))
                    AND offer.canonical_model_id=? AND offer.approved=1 AND offer.active=1""",
                (brand_slug, brand_slug, provider_hint, canonical_model_id)).fetchone()
            if not row and provider_hint:
                row = conn.execute("""SELECT offer.id,offer.brand_id,offer.canonical_model_id,
                        offer.capabilities_json,brand.slug brand_slug,brand.name provider_name,
                        price.id price_version_id,price.input_rate,price.output_rate,price.cached_input_rate
                    FROM catalog_offers offer JOIN provider_brands brand ON brand.id=offer.brand_id
                    JOIN price_versions price ON price.offer_id=offer.id AND price.is_active=1
                    WHERE brand.id=(SELECT connection.brand_id FROM provider_connections connection
                        WHERE connection.legacy_profile_id=? LIMIT 1)
                        AND offer.canonical_model_id=? AND offer.approved=1 AND offer.active=1""",
                    (provider_hint, canonical_model_id)).fetchone()
            if not row and provider_hint:
                row = conn.execute("""SELECT offer.id,offer.brand_id,offer.canonical_model_id,
                        offer.capabilities_json,brand.slug brand_slug,brand.name provider_name,
                        price.id price_version_id,price.input_rate,price.output_rate,price.cached_input_rate
                    FROM catalog_offers offer JOIN provider_brands brand ON brand.id=offer.brand_id
                    JOIN price_versions price ON price.offer_id=offer.id AND price.is_active=1
                    WHERE offer.id=? AND offer.approved=1 AND offer.active=1""",
                    (f"legacy-offer:{provider_hint}:{canonical_model_id}",)).fetchone()
            if not row:
                return None
            loaded = self._load_offer_routes(conn, row["id"])
            if not loaded:
                return None
            routes = resolve_offer_routes(*loaded)
            if not routes:
                return None
            return ResolvedOffer(
                row["id"], public_model_id, row["brand_id"], row["brand_slug"],
                row["provider_name"], row["canonical_model_id"],
                tuple(json.loads(row["capabilities_json"] or "[]")), row["price_version_id"],
                row["input_rate"], row["output_rate"], row["cached_input_rate"], tuple(routes),
            )

    def set_model_active(self, model_id: str, *, active: bool, provider_id: str | None = None) -> int:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if provider_id is None:
                providers = conn.execute("SELECT DISTINCT provider_id FROM portal_catalog_models WHERE model_id=?", (model_id,)).fetchall()
                if len(providers) != 1:
                    return 0
                provider_id = providers[0]["provider_id"]
            brand = conn.execute("SELECT id FROM provider_brands WHERE migration_ref=?", (provider_id,)).fetchone()
            if not brand:
                return 0
            offer = conn.execute("SELECT id,approved FROM catalog_offers WHERE brand_id=? AND canonical_model_id=?",
                                 (brand["id"], model_id)).fetchone()
            if not offer:
                return 0
            eligible_routes = []
            if active and self._table_exists(conn, "upstream_profiles") and offer["approved"]:
                eligible_routes = conn.execute("""SELECT route.id FROM offer_routes route
                    JOIN provider_connections connection ON connection.id=route.connection_id
                        AND connection.brand_id=? AND connection.legacy_profile_id=?
                    JOIN provider_brands provider ON provider.id=connection.brand_id
                    JOIN connection_models discovered ON discovered.connection_id=connection.id
                        AND discovered.upstream_model_id=route.upstream_model_id
                    WHERE route.offer_id=? AND provider.identity_status='mapped'
                        AND connection.mapping_status='mapped' AND connection.enabled=1
                        AND discovered.active=1 AND discovered.is_stale=0
                        AND EXISTS (SELECT 1 FROM upstream_profiles profile WHERE profile.id=connection.legacy_profile_id)
                        AND EXISTS (SELECT 1 FROM price_versions price WHERE price.offer_id=route.offer_id AND price.is_active=1)""",
                    (brand["id"], provider_id, offer["id"])).fetchall()
                if not eligible_routes:
                    return 0
            cursor = conn.execute("""UPDATE portal_catalog_models SET active=?,updated_at=?
                WHERE provider_id=? AND model_id=?""", (int(active), _iso(), provider_id, model_id))
            if not cursor.rowcount:
                return 0
            conn.execute("UPDATE catalog_offers SET active=?,updated_at=? WHERE id=?", (int(active), _iso(), offer["id"]))
            if active:
                route_ids = [route["id"] for route in eligible_routes]
                placeholders = ",".join("?" for _ in route_ids)
                conn.execute(f"UPDATE offer_routes SET active=CASE WHEN id IN ({placeholders}) THEN 1 ELSE 0 END WHERE offer_id=?",
                             (*route_ids, offer["id"]))
            else:
                conn.execute("UPDATE offer_routes SET active=0 WHERE offer_id=?", (offer["id"],))
        return cursor.rowcount

    def get_runtime_setting(self, key: str, default: Any = None) -> Any:
        with self.connect() as conn:
            row = conn.execute("SELECT value_json FROM portal_runtime_settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else default

    def set_runtime_setting(self, key: str, value: Any) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO portal_runtime_settings(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at", (key, json.dumps(value), _iso()))

    def _eligible_public_offer_id(self, conn: sqlite3.Connection, selected_id: str) -> bool:
        provider_scope, separator, canonical_model_id = selected_id.partition("::")
        if not separator or not provider_scope or not canonical_model_id:
            return False
        row = conn.execute("""SELECT offer.id FROM catalog_offers offer
            JOIN provider_brands brand ON brand.id=offer.brand_id
            WHERE (brand.slug=? OR brand.migration_ref=?) AND offer.canonical_model_id=?""",
            (provider_scope, provider_scope, canonical_model_id)).fetchone()
        loaded = self._load_offer_routes(conn, row["id"]) if row else None
        return bool(loaded and resolve_offer_routes(*loaded))

    def create_user_key(
        self,
        owner_user_id: str,
        label: str,
        *,
        allowed_models_mode: str = "all_approved",
        allowed_models: list[str] | None = None,
        spend_limit_usd: float | None = None,
        spend_period: str | None = None,
        rpm_limit: int | None = None,
    ) -> dict[str, Any]:
        label = label.strip()
        if not label or len(label) > 80:
            raise ValueError("Key label must contain 1 to 80 characters")
        if allowed_models_mode not in {"all_approved", "selected"}:
            raise ValueError("Model policy must be all_approved or selected")
        models = sorted(set(allowed_models or []))
        if allowed_models_mode == "selected" and not models:
            raise ValueError("Select at least one approved model")
        if allowed_models_mode == "all_approved" and models:
            raise ValueError("All-approved model policy cannot include a pinned model list")
        if spend_limit_usd is not None and (isinstance(spend_limit_usd, bool) or not isinstance(spend_limit_usd, (int, float)) or not math.isfinite(spend_limit_usd) or spend_limit_usd <= 0):
            raise ValueError("Spend limit must be positive or omitted")
        if spend_period is not None and spend_period not in {"daily", "weekly", "monthly", "lifetime"}:
            raise ValueError("Unsupported spend period")
        if (spend_limit_usd is None) != (spend_period is None):
            raise ValueError("Spend limit and period must be set together")
        if rpm_limit is not None and (isinstance(rpm_limit, bool) or not isinstance(rpm_limit, int) or rpm_limit < 1):
            raise ValueError("RPM must be positive or omitted")

        raw = "sp_sk_" + secrets.token_urlsafe(32)
        key_id = uuid.uuid4().hex
        now = _iso()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            user = conn.execute("SELECT * FROM portal_users WHERE id=? AND status='active'", (owner_user_id,)).fetchone()
            if not user:
                raise PermissionError("Active owner is required")
            if spend_limit_usd is not None and user["allowance_usd"] is not None:
                if spend_period != user["allowance_period"] or spend_limit_usd > user["allowance_usd"]:
                    raise ValueError("A key spend cap cannot exceed or outlive the user allowance")
            if rpm_limit is not None and user["rpm_limit"] is not None and rpm_limit > user["rpm_limit"]:
                raise ValueError("A key RPM cannot exceed the user-wide RPM")
            if models:
                normalized_models: set[str] = set()
                for selected_id in models:
                    if self._eligible_public_offer_id(conn, selected_id):
                        normalized_models.add(selected_id)
                        continue
                    provider_id, separator, upstream_id = selected_id.partition("::")
                    if separator:
                        row = conn.execute("SELECT 1 FROM portal_catalog_models WHERE provider_id=? AND model_id=? AND active=1 AND approved=1 AND input_price_per_million IS NOT NULL AND output_price_per_million IS NOT NULL AND EXISTS (SELECT 1 FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id WHERE b.migration_ref=portal_catalog_models.provider_id AND b.identity_status='mapped' AND c.legacy_profile_id=portal_catalog_models.provider_id AND c.mapping_status='mapped' AND c.enabled=1) AND EXISTS (SELECT 1 FROM portal_eligible_legacy_models eligible WHERE eligible.provider_id=portal_catalog_models.provider_id AND eligible.model_id=portal_catalog_models.model_id)", (provider_id, upstream_id)).fetchone()
                        if row:
                            normalized_models.add(selected_id)
                    else:
                        rows = conn.execute("SELECT provider_id FROM portal_catalog_models WHERE model_id=? AND active=1 AND approved=1 AND input_price_per_million IS NOT NULL AND output_price_per_million IS NOT NULL AND EXISTS (SELECT 1 FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id WHERE b.migration_ref=portal_catalog_models.provider_id AND b.identity_status='mapped' AND c.legacy_profile_id=portal_catalog_models.provider_id AND c.mapping_status='mapped' AND c.enabled=1) AND EXISTS (SELECT 1 FROM portal_eligible_legacy_models eligible WHERE eligible.provider_id=portal_catalog_models.provider_id AND eligible.model_id=portal_catalog_models.model_id)", (selected_id,)).fetchall()
                        if len(rows) == 1:
                            normalized_models.add(f"{rows[0]['provider_id']}::{selected_id}")
                if len(normalized_models) != len(models):
                    raise ValueError("One or more selected models are not approved and priced")
                models = sorted(normalized_models)
            conn.execute("INSERT INTO portal_keys(id,owner_user_id,label,key_prefix,key_hash,allowed_models_mode,allowed_models_json,spend_limit_usd,spend_period,rpm_limit,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (key_id, owner_user_id, label, raw[:14], _digest(raw, self.key_pepper), allowed_models_mode, json.dumps(models), spend_limit_usd, spend_period, rpm_limit, now))
        return {"id": key_id, "owner_id": owner_user_id, "label": label, "key_prefix": raw[:14], "api_key": raw, "allowed_models_mode": allowed_models_mode, "allowed_models": models, "spend_limit_usd": spend_limit_usd, "spend_period": spend_period, "rpm_limit": rpm_limit, "created_at": now, "enabled": True}

    def list_user_keys(self, owner_user_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT id,owner_user_id,label,key_prefix,allowed_models_mode,allowed_models_json,spend_limit_usd,spend_period,rpm_limit,created_at,last_used_at,revoked_at,archived_at FROM portal_keys WHERE owner_user_id=? ORDER BY created_at DESC", (owner_user_id,)).fetchall()
        return [dict(row) | {"allowed_models": json.loads(row["allowed_models_json"]), "enabled": row["revoked_at"] is None and row["archived_at"] is None, "spend_used_usd": self.key_period_spend(owner_user_id, row["id"], row["spend_period"]), "spend_reset_at": self.period_reset_at(row["spend_period"])} for row in rows]

    def find_gateway_key(self, raw_token: str) -> dict[str, Any] | None:
        """Resolve a bearer token for the existing ``/v1`` gateway adapter.

        Return ``None`` for unknown/disabled records. The result never contains
        the raw credential; ``key_id``, owner, effective models, user allowance,
        and both user/key RPM and spend policies are ready for main.py to enforce.
        """
        if not isinstance(raw_token, str) or not raw_token or len(raw_token) > 512:
            return None
        with self.connect() as conn:
            row = conn.execute("""SELECT k.*,u.status AS owner_status,u.display_name AS owner_name,
                    u.email AS owner_email,u.allowance_usd AS user_allowance_usd,
                    u.allowance_period AS user_allowance_period,u.rpm_limit AS user_rpm_limit
                FROM portal_keys k JOIN portal_users u ON u.id=k.owner_user_id
                WHERE k.key_hash=?""", (_digest(raw_token, self.key_pepper),)).fetchone()
            if not row:
                return None
            record = dict(row)
            if record["owner_status"] != "active" or record["revoked_at"] or record["archived_at"]:
                return None
            models = json.loads(record["allowed_models_json"])
            allowed_mode = record["allowed_models_mode"]
        eligible = self.list_models(approved_only=True)
        effective_models = [
            item["public_model_id"] for item in eligible
            if allowed_mode == "all_approved" or item["public_model_id"] in models
        ]
        return {
            "key_id": record["id"], "provider_key_id": record["id"], "owner_id": record["owner_user_id"],
            "owner_status": record["owner_status"], "owner_name": record["owner_name"], "owner_email": record["owner_email"],
            "label": record["label"], "key_prefix": record["key_prefix"], "enabled": True,
            "allowed_models_mode": record["allowed_models_mode"], "allowed_models": models,
            "effective_model_ids": effective_models,
            "spend_limit_usd": record["spend_limit_usd"], "spend_period": record["spend_period"],
            "rpm_limit": record["rpm_limit"], "user_allowance_usd": record["user_allowance_usd"],
            "user_allowance_period": record["user_allowance_period"], "user_rpm_limit": record["user_rpm_limit"],
            "created_at": record["created_at"], "last_used_at": record["last_used_at"],
        }

    def touch_gateway_key(self, key_id: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE portal_keys SET last_used_at=? WHERE id=? AND revoked_at IS NULL AND archived_at IS NULL", (_iso(), key_id))

    def get_user_key(self, owner_user_id: str, key_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT id,owner_user_id,label,key_prefix,allowed_models_mode,allowed_models_json,spend_limit_usd,spend_period,rpm_limit,created_at,last_used_at,revoked_at,archived_at FROM portal_keys WHERE owner_user_id=? AND id=?", (owner_user_id, key_id)).fetchone()
        return dict(row) | {"allowed_models": json.loads(row["allowed_models_json"]), "enabled": row["revoked_at"] is None and row["archived_at"] is None, "spend_used_usd": self.key_period_spend(owner_user_id, row["id"], row["spend_period"]), "spend_reset_at": self.period_reset_at(row["spend_period"])} if row else None

    def key_period_spend(self, owner_user_id: str, key_id: str, period: str | None) -> float:
        start = self._period_start(period, _now())
        usage_query = "SELECT COALESCE(SUM(estimated_cost_usd),0) FROM portal_usage_events WHERE owner_user_id=? AND key_id=?"
        reservation_query = "SELECT COALESCE(SUM(estimated_cost_usd),0) FROM portal_budget_reservations WHERE owner_user_id=? AND key_id=? AND status='active'"
        usage_args: list[Any] = [owner_user_id, key_id]
        reservation_args: list[Any] = [owner_user_id, key_id]
        if start:
            usage_query += " AND julianday(occurred_at)>=julianday(?)"
            reservation_query += " AND julianday(created_at)>=julianday(?)"
            usage_args.append(start)
            reservation_args.append(start)
        with self.connect() as conn:
            used = conn.execute(usage_query, usage_args).fetchone()[0]
            reserved = conn.execute(reservation_query, reservation_args).fetchone()[0]
        return float(used or 0) + float(reserved or 0)

    def update_user_key_policy(
        self,
        owner_user_id: str,
        key_id: str,
        *,
        allowed_models_mode: str,
        allowed_models: list[str],
        spend_limit_usd: float | None,
        spend_period: str | None,
        rpm_limit: int | None,
    ) -> bool:
        models = sorted(set(allowed_models))
        if allowed_models_mode not in {"all_approved", "selected"}:
            raise ValueError("Model access must be all approved or selected")
        if allowed_models_mode == "all_approved" and models:
            raise ValueError("All-approved model access cannot include a fixed list")
        if allowed_models_mode == "selected" and not models:
            raise ValueError("Select at least one approved model")
        if spend_limit_usd is not None and (isinstance(spend_limit_usd, bool) or not isinstance(spend_limit_usd, (int, float)) or not math.isfinite(spend_limit_usd) or spend_limit_usd <= 0):
            raise ValueError("Spend cap must be positive or unlimited")
        if (spend_limit_usd is None) != (spend_period is None):
            raise ValueError("Spend cap and reset period must be set together")
        if spend_period is not None and spend_period not in {"daily", "weekly", "monthly", "lifetime"}:
            raise ValueError("Unsupported spend period")
        if rpm_limit is not None and (isinstance(rpm_limit, bool) or not isinstance(rpm_limit, int) or rpm_limit < 1):
            raise ValueError("RPM must be positive or unlimited")

        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""SELECT k.id,u.allowance_usd,u.allowance_period,u.rpm_limit
                FROM portal_keys k JOIN portal_users u ON u.id=k.owner_user_id
                WHERE k.id=? AND k.owner_user_id=? AND k.archived_at IS NULL""", (key_id, owner_user_id)).fetchone()
            if not row:
                return False
            if spend_limit_usd is not None and row["allowance_usd"] is not None:
                if spend_period != row["allowance_period"] or spend_limit_usd > row["allowance_usd"]:
                    raise ValueError("A key cap cannot exceed or outlive the user allowance")
            if rpm_limit is not None and row["rpm_limit"] is not None and rpm_limit > row["rpm_limit"]:
                raise ValueError("A key RPM cannot exceed the user-wide RPM")
            if models:
                normalized_models: set[str] = set()
                for selected_id in models:
                    if self._eligible_public_offer_id(conn, selected_id):
                        normalized_models.add(selected_id)
                        continue
                    provider_id, separator, upstream_id = selected_id.partition("::")
                    if separator:
                        row = conn.execute("SELECT 1 FROM portal_catalog_models WHERE provider_id=? AND model_id=? AND active=1 AND approved=1 AND input_price_per_million IS NOT NULL AND output_price_per_million IS NOT NULL AND EXISTS (SELECT 1 FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id WHERE b.migration_ref=portal_catalog_models.provider_id AND b.identity_status='mapped' AND c.legacy_profile_id=portal_catalog_models.provider_id AND c.mapping_status='mapped' AND c.enabled=1) AND EXISTS (SELECT 1 FROM portal_eligible_legacy_models eligible WHERE eligible.provider_id=portal_catalog_models.provider_id AND eligible.model_id=portal_catalog_models.model_id)", (provider_id, upstream_id)).fetchone()
                        if row:
                            normalized_models.add(selected_id)
                    else:
                        rows = conn.execute("SELECT provider_id FROM portal_catalog_models WHERE model_id=? AND active=1 AND approved=1 AND input_price_per_million IS NOT NULL AND output_price_per_million IS NOT NULL AND EXISTS (SELECT 1 FROM provider_brands b JOIN provider_connections c ON c.brand_id=b.id WHERE b.migration_ref=portal_catalog_models.provider_id AND b.identity_status='mapped' AND c.legacy_profile_id=portal_catalog_models.provider_id AND c.mapping_status='mapped' AND c.enabled=1) AND EXISTS (SELECT 1 FROM portal_eligible_legacy_models eligible WHERE eligible.provider_id=portal_catalog_models.provider_id AND eligible.model_id=portal_catalog_models.model_id)", (selected_id,)).fetchall()
                        if len(rows) == 1:
                            normalized_models.add(f"{rows[0]['provider_id']}::{selected_id}")
                if len(normalized_models) != len(models):
                    raise ValueError("Selected models must be approved and priced")
                models = sorted(normalized_models)
            conn.execute("UPDATE portal_keys SET allowed_models_mode=?,allowed_models_json=?,spend_limit_usd=?,spend_period=?,rpm_limit=? WHERE id=? AND owner_user_id=?", (allowed_models_mode, json.dumps(models), spend_limit_usd, spend_period, rpm_limit, key_id, owner_user_id))
        return True

    def revoke_user_key(self, owner_user_id: str, key_id: str) -> bool:
        with self.connect() as conn:
            result = conn.execute("UPDATE portal_keys SET revoked_at=COALESCE(revoked_at,?) WHERE owner_user_id=? AND id=? AND archived_at IS NULL", (_iso(), owner_user_id, key_id))
            return result.rowcount == 1

    def archive_user_key(self, owner_user_id: str, key_id: str) -> bool:
        with self.connect() as conn:
            result = conn.execute("UPDATE portal_keys SET archived_at=COALESCE(archived_at,?),revoked_at=COALESCE(revoked_at,?) WHERE owner_user_id=? AND id=?", (_iso(), _iso(), owner_user_id, key_id))
            return result.rowcount == 1

    def record_usage(
        self,
        owner_user_id: str,
        key_id: str,
        *,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        latency_ms: int | None,
        status: str,
        estimated_cost_usd: float | None,
        stream: bool = False,
        provider_id: str | None = None,
        provider_name: str | None = None,
        cached_tokens: int | None = None,
        error_category: str | None = None,
        price_snapshot: dict[str, Any] | None = None,
        client_ip: str | None = None,
        request_id: str | None = None,
        occurred_at: str | None = None,
        reservation_id: str | None = None,
        amount_nano_usd: int | None = None,
        brand_id: str | None = None,
        canonical_model_id: str | None = None,
        offer_route_id: str | None = None,
        price_version_id: str | None = None,
        route_snapshot: dict[str, Any] | None = None,
    ) -> str:
        if amount_nano_usd is not None and (isinstance(amount_nano_usd, bool) or not isinstance(amount_nano_usd, int) or amount_nano_usd < 0):
            raise ValueError("Usage charge must be a non-negative integer number of nano-USD")
        minimum_charge = self._charge_nano_usd(estimated_cost_usd)
        if amount_nano_usd is not None and minimum_charge is not None and amount_nano_usd < minimum_charge:
            raise ValueError("Nano-USD usage charge cannot understate the estimated USD charge")
        if amount_nano_usd is None:
            amount_nano_usd = minimum_charge
        event_id = uuid.uuid4().hex
        with self.connect() as conn:
            key = conn.execute("SELECT k.label,u.display_name,u.email FROM portal_keys k JOIN portal_users u ON u.id=k.owner_user_id WHERE k.id=? AND k.owner_user_id=?", (key_id, owner_user_id)).fetchone()
            if not key:
                raise LookupError("Key does not belong to this user")
            conn.execute("""INSERT INTO portal_usage_events(
                id,owner_user_id,owner_name_snapshot,owner_email_snapshot,key_id,key_label_snapshot,provider_id,
                provider_name_snapshot,model_id,occurred_at,status,error_category,latency_ms,input_tokens,output_tokens,
                total_tokens,cached_tokens,stream,estimated_cost_usd,price_snapshot_json,client_ip,request_id,
                amount_nano_usd,brand_id,canonical_model_id,offer_route_id,price_version_id,brand_snapshot,
                model_snapshot,route_snapshot_json,price_snapshot_v2_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (event_id, owner_user_id, key["display_name"], key["email"], key_id, key["label"], provider_id,
                          provider_name, model, occurred_at or _iso(), status, error_category, latency_ms, input_tokens,
                          output_tokens, total_tokens, cached_tokens, int(stream), estimated_cost_usd,
                          json.dumps(price_snapshot) if price_snapshot is not None else None, client_ip, request_id,
                          amount_nano_usd, brand_id, canonical_model_id or model, offer_route_id, price_version_id,
                          provider_name, canonical_model_id or model,
                          json.dumps(route_snapshot if route_snapshot is not None else ({"provider_id": provider_id, "model_id": model} if provider_id else None)) if route_snapshot is not None or provider_id else None,
                          json.dumps(price_snapshot) if price_snapshot is not None else None))
            if reservation_id:
                conn.execute("UPDATE portal_budget_reservations SET status='settled' WHERE id=? AND owner_user_id=? AND key_id=? AND status='active'", (reservation_id, owner_user_id, key_id))
        return event_id

    def record_gateway_usage(self, resolved_key: dict[str, Any], **usage: Any) -> str:
        """Append the terminal /v1 outcome using identity captured by the resolver."""
        key_id = resolved_key.get("key_id") or resolved_key.get("provider_key_id")
        owner_id = resolved_key.get("owner_id")
        if not key_id or not owner_id:
            raise ValueError("A key returned by find_gateway_key is required")
        return self.record_usage(owner_id, key_id, **usage)

    def import_legacy_usage(self, owner_user_id: str, records: list[dict[str, Any]]) -> int:
        owner = self.get_user(owner_user_id)
        if not owner or owner["role"] != "operator":
            raise PermissionError("Only the provisioned operator can own imported legacy usage")
        imported = 0
        with self.connect() as conn:
            for record in records:
                legacy_id = record.get("id")
                if legacy_id is None:
                    continue
                key_id = f"legacy-key-{record.get('provider_key_id') or 'unknown'}"
                cur = conn.execute("""INSERT OR IGNORE INTO portal_usage_events
                (id,owner_user_id,owner_name_snapshot,owner_email_snapshot,key_id,key_label_snapshot,provider_id,provider_name_snapshot,model_id,occurred_at,status,error_category,latency_ms,input_tokens,output_tokens,total_tokens,cached_tokens,stream,estimated_cost_usd,origin,price_snapshot_json,client_ip,request_id,amount_nano_usd)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (f"legacy-{legacy_id}", owner_user_id, owner["display_name"], owner["email"], key_id,
                     record.get("key_label") or "Legacy key", record.get("upstream_profile_id"), record.get("provider_name") or "Legacy provider",
                     record.get("model") or "unknown", record.get("timestamp") or _iso(), record.get("status") or "unknown",
                     record.get("error_category"), record.get("latency_ms"), record.get("input_tokens"), record.get("output_tokens"),
                     record.get("total_tokens"), None, int(bool(record.get("stream"))), record.get("estimated_cost_usd"), "legacy", None,
                     record.get("client_ip"), f"legacy-request-{legacy_id}", self._charge_nano_usd(record.get("estimated_cost_usd"))))
                imported += cur.rowcount
        return imported

    def import_legacy_key_snapshots(self, owner_user_id: str, keys: list[dict[str, Any]]) -> int:
        owner = self.get_user(owner_user_id)
        if not owner or owner["role"] != "operator":
            raise PermissionError("Only the provisioned operator can own legacy key snapshots")
        imported = 0
        with self.connect() as conn:
            for key in keys:
                legacy_id = key.get("id")
                if legacy_id is None:
                    continue
                key_id = f"legacy-key-{legacy_id}"
                allowed_models = [item.strip() for item in (key.get("allowed_models") or "").split(",") if item.strip()]
                mode = "selected" if allowed_models else "all_approved"
                marker_hash = _digest(f"legacy-snapshot:{legacy_id}", self.key_pepper)
                now = _iso()
                cursor = conn.execute("""INSERT OR IGNORE INTO portal_keys
                    (id,owner_user_id,label,key_prefix,key_hash,allowed_models_mode,allowed_models_json,spend_limit_usd,spend_period,rpm_limit,created_at,last_used_at,revoked_at,archived_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (key_id, owner_user_id, key.get("label") or "Legacy key", key.get("key_prefix") or "legacy", marker_hash,
                     mode, json.dumps(allowed_models), key.get("spend_limit_usd"), "lifetime" if key.get("spend_limit_usd") is not None else None,
                     key.get("requests_per_minute") if key.get("requests_per_minute") and key.get("requests_per_minute") > 0 else None,
                     key.get("created_at") or now, key.get("last_used_at"), key.get("revoked_at"), key.get("deleted_at") or now))
                imported += cursor.rowcount
        return imported

    def record_legacy_usage(self, legacy_key_id: int, legacy_event_id: int, *, key_label: str, provider_name: str | None, model: str, input_tokens: int | None, output_tokens: int | None, total_tokens: int | None, estimated_cost_usd: float | None, latency_ms: int | None, status: str, stream: bool, client_ip: str | None, upstream_profile_id: str | None, error_category: str | None = None) -> int:
        key_id = f"legacy-key-{legacy_key_id}"
        with self.connect() as conn:
            row = conn.execute("SELECT owner_user_id FROM portal_keys WHERE id=?", (key_id,)).fetchone()
        if not row:
            return 0
        return self.import_legacy_usage(row["owner_user_id"], [{
            "id": legacy_event_id,
            "provider_key_id": legacy_key_id,
            "key_label": key_label,
            "upstream_profile_id": upstream_profile_id,
            "provider_name": provider_name,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "latency_ms": latency_ms,
            "status": status,
            "stream": stream,
            "error_category": error_category,
            "client_ip": client_ip,
        }])

    def reserve_gateway_budget(self, owner_user_id: str, key_id: str, estimated_cost_usd: float, *, global_limit_usd: float, reservation_ttl_seconds: int = 600) -> str | None:
        reservation_id = uuid.uuid4().hex
        now = _now()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            expired_before = _iso(now - timedelta(seconds=max(1, reservation_ttl_seconds)))
            conn.execute("UPDATE portal_budget_reservations SET status='released' WHERE status='active' AND created_at<=?", (expired_before,))
            key = conn.execute("SELECT k.spend_limit_usd,k.spend_period,u.allowance_usd,u.allowance_period,u.status FROM portal_keys k JOIN portal_users u ON u.id=k.owner_user_id WHERE k.id=? AND k.owner_user_id=? AND k.revoked_at IS NULL AND k.archived_at IS NULL", (key_id, owner_user_id)).fetchone()
            if not key or key["status"] != "active":
                return None
            global_used = conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM portal_usage_events WHERE origin='gateway'").fetchone()[0]
            global_reserved = conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM portal_budget_reservations WHERE status='active'").fetchone()[0]
            try:
                global_used += conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM usage_records").fetchone()[0]
                global_reserved += conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM budget_reservations WHERE status='active'").fetchone()[0]
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc).lower():
                    raise
            if global_limit_usd > 0 and global_used + global_reserved + estimated_cost_usd >= global_limit_usd:
                return None
            policies = (
                (owner_user_id, None, key["allowance_usd"], key["allowance_period"]),
                (owner_user_id, key_id, key["spend_limit_usd"], key["spend_period"]),
            )
            for scope_owner_id, scoped_key_id, cap, period in policies:
                if cap is None or cap <= 0:
                    continue
                start = self._period_start(period, now)
                usage_where = "owner_user_id=?"
                usage_args: list[Any] = [scope_owner_id]
                reserve_where = "owner_user_id=? AND status='active'"
                reserve_args: list[Any] = [scope_owner_id]
                if scoped_key_id:
                    usage_where += " AND key_id=?"
                    usage_args.append(scoped_key_id)
                    reserve_where += " AND key_id=?"
                    reserve_args.append(scoped_key_id)
                if start:
                    usage_where += " AND julianday(occurred_at)>=julianday(?)"
                    usage_args.append(start)
                    reserve_where += " AND julianday(created_at)>=julianday(?)"
                    reserve_args.append(start)
                used = conn.execute(f"SELECT COALESCE(SUM(estimated_cost_usd),0) FROM portal_usage_events WHERE {usage_where}", usage_args).fetchone()[0]
                reserved = conn.execute(f"SELECT COALESCE(SUM(estimated_cost_usd),0) FROM portal_budget_reservations WHERE {reserve_where}", reserve_args).fetchone()[0]
                if used + reserved + estimated_cost_usd >= cap:
                    return None
            conn.execute("INSERT INTO portal_budget_reservations(id,owner_user_id,key_id,estimated_cost_usd,created_at) VALUES(?,?,?,?,?)", (reservation_id, owner_user_id, key_id, estimated_cost_usd, _iso(now)))
        return reservation_id

    @staticmethod
    def _period_start(period: str | None, now: datetime) -> str | None:
        if period in {"daily", "day"}:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period in {"weekly", "week"}:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
        elif period in {"monthly", "month"}:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "lifetime":
            start = datetime.min.replace(tzinfo=timezone.utc)
        else:
            return None
        return period_window({"day": "daily", "week": "weekly", "month": "monthly"}.get(period, period), now).start_utc.isoformat()

    @staticmethod
    def period_reset_at(period: str | None, now: datetime | None = None) -> str | None:
        if not period or period in {"lifetime", "life"}:
            return None
        aliases = {"day": "daily", "week": "weekly", "month": "monthly"}
        try:
            reset = period_window(aliases.get(period, period), now or _now()).reset_at_utc
        except ValueError:
            return None
        return reset.isoformat() if reset else None

    def key_usage_summary(self, owner_user_id: str, key_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) request_count,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(total_tokens) total_tokens,SUM(estimated_cost_usd) estimated_cost_usd FROM portal_usage_events WHERE owner_user_id=? AND key_id=?", (owner_user_id, key_id)).fetchone()
        return dict(row)

    def allow_portal_request(self, owner_user_id: str, key_id: str, *, user_limit: int | None, key_limit: int | None, window: int) -> bool:
        scopes = ((f"user:{owner_user_id}", user_limit), (f"key:{key_id}", key_limit))
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            counts = {}
            for scope, limit in scopes:
                row = conn.execute("SELECT window_id,request_count FROM portal_rate_windows WHERE scope=?", (scope,)).fetchone()
                count = row["request_count"] if row and row["window_id"] == window else 0
                counts[scope] = count
                if limit is not None and limit > 0 and count >= limit:
                    return False
            for scope, _limit in scopes:
                conn.execute("""INSERT INTO portal_rate_windows(scope,window_id,request_count) VALUES(?,?,1)
                    ON CONFLICT(scope) DO UPDATE SET window_id=excluded.window_id,
                    request_count=CASE WHEN portal_rate_windows.window_id=excluded.window_id THEN portal_rate_windows.request_count+1 ELSE 1 END""", (scope, window))
            conn.execute("DELETE FROM portal_rate_windows WHERE window_id < ?", (window - 2,))
        return True

    def release_gateway_reservation(self, reservation_id: str | None) -> None:
        if not reservation_id:
            return
        with self.connect() as conn:
            conn.execute("UPDATE portal_budget_reservations SET status='released' WHERE id=? AND status='active'", (reservation_id,))

    def list_usage(self, owner_user_id: str, *, limit: int = 100, before: str | None = None, key_id: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        query = "SELECT id,key_id,key_label_snapshot,provider_id,provider_name_snapshot,model_id,occurred_at,status,error_category,latency_ms,input_tokens,output_tokens,total_tokens,cached_tokens,estimated_cost_usd,amount_nano_usd,price_version_id,client_ip,request_id FROM portal_usage_events WHERE owner_user_id=?"
        args: list[Any] = [owner_user_id]
        if key_id:
            query += " AND key_id=?"
            args.append(key_id)
        if before:
            query += " AND occurred_at<?"
            args.append(before)
        query += " ORDER BY occurred_at DESC,id DESC LIMIT ?"
        args.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [dict(row) | {"model": row["model_id"]} for row in rows]

    def list_all_usage(self, *, limit: int = 100, before: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        query = "SELECT id,owner_user_id,owner_name_snapshot,owner_email_snapshot,key_id,key_label_snapshot,provider_id,provider_name_snapshot,model_id,occurred_at,status,error_category,latency_ms,input_tokens,output_tokens,total_tokens,cached_tokens,estimated_cost_usd,client_ip,request_id FROM portal_usage_events"
        args: list[Any] = []
        if before:
            query += " WHERE occurred_at<?"
            args.append(before)
        query += " ORDER BY occurred_at DESC,id DESC LIMIT ?"
        args.append(limit)
        with self.connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return [dict(row) | {"model": row["model_id"]} for row in rows]

    def user_usage_summary(self, owner_user_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) request_count,SUM(CASE WHEN status IN ('ok','success') THEN 1 ELSE 0 END) successful_requests,SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) rejected_requests,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(total_tokens) total_tokens,SUM(estimated_cost_usd) estimated_cost_usd,AVG(latency_ms) avg_latency_ms FROM portal_usage_events WHERE owner_user_id=?", (owner_user_id,)).fetchone()
        return dict(row)

    def user_period_spend(self, owner_user_id: str, period: str | None) -> float:
        window = period_window(period if period in {"daily", "weekly", "monthly", "lifetime"} else "lifetime", _now())
        start = window.start_utc.isoformat()
        with self.connect() as conn:
            events = conn.execute("SELECT amount_nano_usd,estimated_cost_usd FROM portal_usage_events WHERE owner_user_id=? AND julianday(occurred_at)>=julianday(?)", (owner_user_id, start)).fetchall()
            reserved = conn.execute("SELECT amount_nano_usd FROM portal_budget_reservations_v2 WHERE owner_user_id=? AND status='active' AND julianday(created_at)>=julianday(?)", (owner_user_id, start)).fetchall()
        used_nano = self._sum_nano_rows(events) + sum(row["amount_nano_usd"] for row in reserved)
        return used_nano / 1_000_000_000

    def operator_usage_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) request_count,SUM(CASE WHEN status IN ('ok','success') THEN 1 ELSE 0 END) successful_requests,SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) rejected_requests,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(total_tokens) total_tokens,SUM(estimated_cost_usd) estimated_cost_usd,AVG(latency_ms) avg_latency_ms FROM portal_usage_events").fetchone()
        return dict(row)

    def latency_percentile(self, owner_user_id: str | None = None) -> dict[str, int | None]:
        where = "latency_ms IS NOT NULL"
        args: list[Any] = []
        if owner_user_id:
            where += " AND owner_user_id=?"
            args.append(owner_user_id)
        with self.connect() as conn:
            sample_count = conn.execute(f"SELECT COUNT(*) FROM portal_usage_events WHERE {where}", args).fetchone()[0]
            if sample_count < 20:
                return {"p95": None, "sample_count": sample_count}
            offset = max(0, math.ceil(0.95 * sample_count) - 1)
            value = conn.execute(f"SELECT latency_ms FROM portal_usage_events WHERE {where} ORDER BY latency_ms LIMIT 1 OFFSET ?", [*args, offset]).fetchone()[0]
        return {"p95": value, "sample_count": sample_count}

    def gateway_usage_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) request_count,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(total_tokens) total_tokens,SUM(estimated_cost_usd) estimated_cost_usd,AVG(latency_ms) avg_latency_ms FROM portal_usage_events WHERE origin='gateway'").fetchone()
        return dict(row)

    def usage_timeseries(self, owner_user_id: str | None = None, *, days: int = 14) -> list[dict[str, Any]]:
        days = max(1, min(int(days), 90))
        start = _iso(_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1))
        where = "occurred_at>=?"
        args: list[Any] = [start]
        if owner_user_id:
            where += " AND owner_user_id=?"
            args.append(owner_user_id)
        with self.connect() as conn:
            rows = conn.execute(f"""SELECT substr(occurred_at,1,10) day,COUNT(*) requests,
                SUM(total_tokens) total_tokens,SUM(estimated_cost_usd) estimated_spend_usd
                FROM portal_usage_events WHERE {where} GROUP BY substr(occurred_at,1,10) ORDER BY day""", args).fetchall()
        return [dict(row) for row in rows]

    def usage_by_model(self, owner_user_id: str | None = None, *, limit: int = 8) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 50))
        where = ""
        args: list[Any] = []
        if owner_user_id:
            where = " WHERE owner_user_id=?"
            args.append(owner_user_id)
        with self.connect() as conn:
            rows = conn.execute(f"""SELECT model_id,MAX(provider_name_snapshot) provider_name,
                COUNT(*) requests,SUM(total_tokens) total_tokens,SUM(estimated_cost_usd) estimated_spend_usd
                FROM portal_usage_events{where} GROUP BY model_id ORDER BY requests DESC,estimated_spend_usd DESC LIMIT ?""", [*args, limit]).fetchall()
        return [dict(row) for row in rows]

    def list_people(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""SELECT u.id,u.display_name,u.email,u.status,u.allowance_usd,u.allowance_period,u.rpm_limit,
                COALESCE(k.key_count,0) key_count,COALESCE(e.request_count,0) request_count,
                e.used_usd,e.last_active_at
                FROM portal_users u
                LEFT JOIN (SELECT owner_user_id,COUNT(*) key_count FROM portal_keys WHERE archived_at IS NULL GROUP BY owner_user_id) k ON k.owner_user_id=u.id
                LEFT JOIN (SELECT owner_user_id,COUNT(*) request_count,SUM(estimated_cost_usd) used_usd,MAX(occurred_at) last_active_at FROM portal_usage_events GROUP BY owner_user_id) e ON e.owner_user_id=u.id
                ORDER BY u.created_at DESC""").fetchall()
        people = []
        for row in rows:
            current_used = self.user_period_spend(row["id"], row["allowance_period"]) if row["allowance_period"] else row["used_usd"]
            people.append({
                "id": row["id"], "displayName": row["display_name"], "email": row["email"],
                "status": "disabled" if row["status"] != "active" else "active",
                "allowanceUsd": row["allowance_usd"], "allowancePeriod": {"daily": "day", "weekly": "week"}.get(row["allowance_period"]),
                "allowanceNanoUsd": self.user_allowance_nano_usd(row["id"]),
                "allowanceResetAt": self.period_reset_at(row["allowance_period"]),
                "rpmLimit": row["rpm_limit"], "usedUsd": current_used, "keyCount": row["key_count"] or 0,
                "requestCount": row["request_count"] or 0, "lastActiveAt": row["last_active_at"],
            })
        return people

    def user_allowance_nano_usd(self, owner_user_id: str) -> int | None:
        with self.connect() as conn:
            row = conn.execute("SELECT amount_nano_usd FROM user_allowances WHERE user_id=? AND active=1", (owner_user_id,)).fetchone()
            if row:
                return row["amount_nano_usd"]
            legacy = conn.execute("SELECT allowance_usd FROM portal_users WHERE id=?", (owner_user_id,)).fetchone()
        return self._cap_nano_usd(legacy["allowance_usd"]) if legacy and legacy["allowance_usd"] is not None else None

    def user_period_spend_nano_usd(self, owner_user_id: str, period: str | None) -> int:
        window = period_window(period if period in {"daily", "weekly", "monthly", "lifetime"} else "lifetime", _now())
        with self.connect() as conn:
            events = conn.execute("SELECT amount_nano_usd,estimated_cost_usd FROM portal_usage_events WHERE owner_user_id=? AND julianday(occurred_at)>=julianday(?)", (owner_user_id, window.start_utc.isoformat())).fetchall()
            reserved = conn.execute("SELECT amount_nano_usd FROM portal_budget_reservations_v2 WHERE owner_user_id=? AND status='active' AND julianday(created_at)>=julianday(?)", (owner_user_id, window.start_utc.isoformat())).fetchall()
        return self._sum_nano_rows(events) + sum(row["amount_nano_usd"] for row in reserved)

    def list_providers(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("""SELECT provider_id,provider_name,COUNT(*) discovered_models,
                SUM(CASE WHEN approved=1 AND input_price_per_million IS NOT NULL AND output_price_per_million IS NOT NULL THEN 1 ELSE 0 END) approved_models,
                MAX(updated_at) last_sync_at FROM portal_catalog_models WHERE active=1 GROUP BY provider_id,provider_name ORDER BY provider_name""").fetchall()
        return [{"id": row["provider_id"], "name": row["provider_name"], "baseUrlDisplay": "", "enabled": True,
                 "health": "unknown", "lastSyncAt": row["last_sync_at"], "discoveredModels": row["discovered_models"],
                 "approvedModels": row["approved_models"]} for row in rows]

    def audit(self, actor_user_id: str, action: str, target_type: str, target_id: str | None, details: dict[str, Any] | None = None) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO portal_audit_events(id,actor_user_id,action,target_type,target_id,details_json,occurred_at) VALUES(?,?,?,?,?,?,?)", (uuid.uuid4().hex, actor_user_id, action, target_type, target_id, json.dumps(details or {}, sort_keys=True), _iso()))

    def list_audit_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self.connect() as conn:
            rows = conn.execute("""SELECT a.id,u.display_name actor,a.action,
                COALESCE(a.target_id,a.target_type) target,a.occurred_at
                FROM portal_audit_events a LEFT JOIN portal_users u ON u.id=a.actor_user_id
                ORDER BY a.occurred_at DESC LIMIT ?""", (limit,)).fetchall()
        return [{"id": row["id"], "actor": row["actor"] or "Unknown operator", "action": row["action"], "target": row["target"], "occurredAt": row["occurred_at"]} for row in rows]
