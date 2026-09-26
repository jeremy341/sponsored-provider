import hashlib
import hmac
import secrets
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str, pepper: str = "", secret_key: str = ""):
        self.path = path
        self.pepper = pepper
        self.secret_box = Fernet(secret_key.encode()) if secret_key else None
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self):
        conn = sqlite3.connect(self.path, check_same_thread=False, timeout=10.0)
        # Keep usage history referentially protected: key removal must use archive/revoke,
        # otherwise SQLite refuses to delete a key that still has usage records.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS provider_api_keys (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              key_prefix TEXT NOT NULL,
              key_hash TEXT NOT NULL UNIQUE,
              label TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              revoked_at TEXT,
              created_at TEXT NOT NULL,
              last_used_at TEXT,
              request_count INTEGER NOT NULL DEFAULT 0,
              estimated_cost_usd REAL NOT NULL DEFAULT 0,
              spend_limit_usd REAL,
              requests_per_minute INTEGER,
              token_limit INTEGER,
              allowed_models TEXT NOT NULL DEFAULT '',
              allowed_upstreams TEXT NOT NULL DEFAULT '',
              risk_profile TEXT NOT NULL DEFAULT 'standard',
              risk_approved INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS usage_records (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              provider_key_id INTEGER,
              timestamp TEXT NOT NULL,
              model TEXT NOT NULL,
              input_tokens INTEGER,
              output_tokens INTEGER,
              total_tokens INTEGER,
              estimated_cost_usd REAL NOT NULL DEFAULT 0,
              latency_ms INTEGER,
              status TEXT NOT NULL,
              stream INTEGER NOT NULL DEFAULT 0,
              error_category TEXT,
              upstream_profile_id TEXT,
              FOREIGN KEY(provider_key_id) REFERENCES provider_api_keys(id)
            );
            CREATE TABLE IF NOT EXISTS blocked_ips (
              ip TEXT PRIMARY KEY,
              reason TEXT NOT NULL,
              created_at TEXT NOT NULL,
              expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS upstream_profiles (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              provider_kind TEXT NOT NULL,
              base_url TEXT NOT NULL,
              encrypted_api_key TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              models_json TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              last_checked_at TEXT,
              health_status TEXT NOT NULL DEFAULT 'unknown',
              pricing_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS budget_reservations (
              id TEXT PRIMARY KEY,
              provider_key_id INTEGER NOT NULL,
              upstream_profile_id TEXT,
              model TEXT NOT NULL,
              estimated_cost_usd REAL NOT NULL,
              estimated_tokens REAL NOT NULL,
              created_at TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active'
            );
            """)
            for statement in (
                "ALTER TABLE usage_records ADD COLUMN client_ip TEXT",
                "ALTER TABLE usage_records ADD COLUMN upstream_profile_id TEXT",
                "ALTER TABLE provider_api_keys ADD COLUMN spend_limit_usd REAL",
                "ALTER TABLE provider_api_keys ADD COLUMN requests_per_minute INTEGER",
                "ALTER TABLE provider_api_keys ADD COLUMN token_limit INTEGER",
                "ALTER TABLE provider_api_keys ADD COLUMN allowed_models TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE provider_api_keys ADD COLUMN allowed_upstreams TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE provider_api_keys ADD COLUMN risk_profile TEXT NOT NULL DEFAULT 'standard'",
                "ALTER TABLE provider_api_keys ADD COLUMN risk_approved INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE provider_api_keys ADD COLUMN deleted_at TEXT",
                "ALTER TABLE upstream_profiles ADD COLUMN pricing_json TEXT NOT NULL DEFAULT '{}'",
            ):
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError:
                    pass

    def digest(self, raw_key: str) -> str:
        return hashlib.sha256((self.pepper + raw_key).encode()).hexdigest()

    def create_key(self, label: str, policy: dict | None = None) -> tuple[str, dict]:
        raw = "sp_sk_" + secrets.token_urlsafe(32)
        created = now_iso()
        policy = policy or {}
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO provider_api_keys(key_prefix,key_hash,label,created_at,spend_limit_usd,requests_per_minute,token_limit,allowed_models,allowed_upstreams,risk_profile,risk_approved) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (raw[:14], self.digest(raw), label, created, policy.get("spend_limit_usd"), policy.get("requests_per_minute"), policy.get("token_limit"), policy.get("allowed_models", ""), policy.get("allowed_upstreams", ""), policy.get("risk_profile", "standard"), int(policy.get("risk_approved", True))),
            )
            key_id = cur.lastrowid
        return raw, {"id": key_id, "key_prefix": raw[:14], "label": label, "created_at": created, "enabled": True, "risk_profile": policy.get("risk_profile", "standard"), "risk_approved": bool(policy.get("risk_approved", True))}

    def find_key(self, raw_key: str):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM provider_api_keys WHERE key_hash=?", (self.digest(raw_key),)).fetchone()

    def list_keys(self):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT id,key_prefix,label,created_at,enabled,revoked_at,deleted_at,spend_limit_usd,requests_per_minute,token_limit,allowed_models,allowed_upstreams,risk_profile,risk_approved,request_count,estimated_cost_usd,last_used_at FROM provider_api_keys ORDER BY created_at DESC")]

    def set_key_state(self, key_id: int, enabled: bool, revoke: bool = False):
        with self.connect() as conn:
            conn.execute(
                "UPDATE provider_api_keys SET enabled=?, revoked_at=CASE WHEN ? THEN COALESCE(revoked_at, ?) ELSE revoked_at END WHERE id=?",
                (int(enabled and not revoke), int(revoke), now_iso(), key_id),
            )

    def archive_key(self, key_id: int):
        with self.connect() as conn:
            conn.execute("UPDATE provider_api_keys SET enabled=0, revoked_at=COALESCE(revoked_at, ?), deleted_at=COALESCE(deleted_at, ?) WHERE id=?", (now_iso(), now_iso(), key_id))

    def update_key_policy(self, key_id: int, *, spend_limit_usd=None, requests_per_minute=None, token_limit=None, allowed_models=None, allowed_upstreams=None, risk_profile=None, risk_approved=None, clear_fields=None):
        fields, values = [], []
        for name in clear_fields or []:
            if name in {"spend_limit_usd", "requests_per_minute", "token_limit", "allowed_models", "allowed_upstreams", "risk_profile", "risk_approved"}:
                fields.append(f"{name}=NULL")
        for name, value in (("spend_limit_usd", spend_limit_usd), ("requests_per_minute", requests_per_minute), ("token_limit", token_limit), ("allowed_models", allowed_models), ("allowed_upstreams", allowed_upstreams), ("risk_profile", risk_profile), ("risk_approved", risk_approved)):
            if value is not None and name not in (clear_fields or []):
                fields.append(f"{name}=?")
                values.append(value)
        if fields:
            values.append(key_id)
            with self.connect() as conn:
                conn.execute(f"UPDATE provider_api_keys SET {', '.join(fields)} WHERE id=?", values)

    def remove_model_from_keys(self, model: str):
        with self.connect() as conn:
            rows = conn.execute("SELECT id, allowed_models FROM provider_api_keys WHERE allowed_models IS NOT NULL AND allowed_models != ''").fetchall()
            changed = 0
            for row in rows:
                current = [item.strip() for item in row["allowed_models"].split(",") if item.strip()]
                filtered = [item for item in current if item != model]
                if filtered != current:
                    conn.execute("UPDATE provider_api_keys SET allowed_models=? WHERE id=?", (", ".join(filtered), row["id"]))
                    changed += 1
            return changed

    def record_usage(self, key_id, *, model, input_tokens, output_tokens, total_tokens, estimated_cost_usd, latency_ms, status, stream, client_ip=None, upstream_profile_id=None, reservation_id=None, error_category=None):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO usage_records(provider_key_id,timestamp,model,input_tokens,output_tokens,total_tokens,estimated_cost_usd,latency_ms,status,stream,error_category,client_ip,upstream_profile_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key_id, now_iso(), model, input_tokens, output_tokens, total_tokens, estimated_cost_usd, latency_ms, status, int(stream), error_category, client_ip, upstream_profile_id),
            )
            conn.execute(
                "UPDATE provider_api_keys SET request_count=request_count+1, estimated_cost_usd=estimated_cost_usd+?, last_used_at=? WHERE id=?",
                (estimated_cost_usd, now_iso(), key_id),
            )
            if reservation_id:
                conn.execute("UPDATE budget_reservations SET status='released' WHERE id=? AND status='active'", (reservation_id,))

    def usage_summary(self):
        with self.connect() as conn:
            totals = conn.execute("SELECT COUNT(*) requests, COALESCE(SUM(input_tokens),0) input_tokens, COALESCE(SUM(output_tokens),0) output_tokens, COALESCE(SUM(total_tokens),0) total_tokens, COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd FROM usage_records").fetchone()
            recent = [dict(r) for r in conn.execute("SELECT timestamp, model, total_tokens, estimated_cost_usd, latency_ms, status, stream, client_ip, provider_key_id, upstream_profile_id FROM usage_records ORDER BY id DESC LIMIT 50")]
            by_model = [dict(r) for r in conn.execute("SELECT model, COUNT(*) requests, COALESCE(SUM(total_tokens),0) total_tokens, COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd FROM usage_records GROUP BY model ORDER BY estimated_cost_usd DESC")]
            by_ip = [dict(r) for r in conn.execute("SELECT COALESCE(client_ip,'unknown') client_ip, COUNT(*) requests, COALESCE(SUM(total_tokens),0) total_tokens, COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd FROM usage_records GROUP BY client_ip ORDER BY requests DESC")]
            daily = [dict(r) for r in conn.execute("SELECT substr(timestamp,1,10) day, COUNT(*) requests, COALESCE(SUM(total_tokens),0) total_tokens, COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd FROM usage_records GROUP BY substr(timestamp,1,10) ORDER BY day DESC LIMIT 14")]
        return {"totals": dict(totals), "recent": recent, "by_model": by_model, "by_ip": by_ip, "daily": list(reversed(daily)), "keys": self.list_keys(), "blocked_ips": self.list_blocked_ips()}

    def key_usage(self, key_id: int):
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) requests, COALESCE(SUM(total_tokens),0) total_tokens, COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd FROM usage_records WHERE provider_key_id=?", (key_id,)).fetchone()
        return dict(row)

    def create_upstream(self, name: str, provider_kind: str, base_url: str, api_key: str):
        if not self.secret_box:
            raise ValueError("PROVIDER_SECRET_KEY is not configured")
        profile_id = uuid.uuid4().hex
        created = now_iso()
        encrypted = self.secret_box.encrypt(api_key.encode()).decode()
        with self.connect() as conn:
            conn.execute("INSERT INTO upstream_profiles(id,name,provider_kind,base_url,encrypted_api_key,created_at) VALUES(?,?,?,?,?,?)", (profile_id, name, provider_kind, base_url.rstrip("/"), encrypted, created))
        return {"id": profile_id, "name": name, "provider_kind": provider_kind, "base_url": base_url.rstrip("/"), "secret_configured": True, "enabled": True, "models": [], "created_at": created, "health_status": "unknown"}

    def list_upstreams(self):
        with self.connect() as conn:
            return [dict(row) | {"secret_configured": True, "models": json.loads(row["models_json"] or "[]"), "pricing": json.loads(row["pricing_json"] or "{}")} for row in conn.execute("SELECT id,name,provider_kind,base_url,enabled,models_json,created_at,last_checked_at,health_status,pricing_json FROM upstream_profiles ORDER BY created_at")]

    def get_upstream(self, profile_id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM upstream_profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["models"] = json.loads(data.pop("models_json") or "[]")
        data["pricing"] = json.loads(data.pop("pricing_json") or "{}")
        if self.secret_box:
            data["api_key"] = self.secret_box.decrypt(data.pop("encrypted_api_key").encode()).decode()
        return data

    def update_upstream_models(self, profile_id: str, models: list[str] | None, health_status: str):
        with self.connect() as conn:
            if models is None or (health_status == "error" and not models):
                conn.execute("UPDATE upstream_profiles SET last_checked_at=?,health_status=? WHERE id=?", (now_iso(), health_status, profile_id))
            else:
                conn.execute("UPDATE upstream_profiles SET models_json=?, last_checked_at=?, health_status=? WHERE id=?", (json.dumps(sorted(set(models))), now_iso(), health_status, profile_id))

    def update_upstream_pricing(self, profile_id: str, pricing: dict):
        with self.connect() as conn:
            row = conn.execute("SELECT pricing_json FROM upstream_profiles WHERE id=?", (profile_id,)).fetchone()
            existing = json.loads(row[0] or "{}") if row else {}
            existing.update(pricing)
            conn.execute("UPDATE upstream_profiles SET pricing_json=? WHERE id=?", (json.dumps(existing), profile_id))

    def model_pricing(self, profile_id: str | None, model: str, fallback_input: float, fallback_output: float):
        if not profile_id or profile_id == "configured":
            return fallback_input, fallback_output
        profile = self.get_upstream(profile_id)
        price = (profile or {}).get("pricing", {}).get(model, {})
        return float(price.get("input", 0)), float(price.get("output", 0))

    def reserve_budget(self, key_id: int, upstream_profile_id: str | None, model: str, estimated_cost_usd: float, estimated_tokens: float, global_limit: float, key_limit: float | None):
        reservation_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            totals = conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM usage_records").fetchone()[0]
            active = conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM budget_reservations WHERE status='active'").fetchone()[0]
            key_used = conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM usage_records WHERE provider_key_id=?", (key_id,)).fetchone()[0]
            key_active = conn.execute("SELECT COALESCE(SUM(estimated_cost_usd),0) FROM budget_reservations WHERE provider_key_id=? AND status='active'", (key_id,)).fetchone()[0]
            if global_limit > 0 and totals + active + estimated_cost_usd >= global_limit:
                return None
            if key_limit is not None and key_limit > 0 and key_used + key_active + estimated_cost_usd >= key_limit:
                return None
            conn.execute("INSERT INTO budget_reservations(id,provider_key_id,upstream_profile_id,model,estimated_cost_usd,estimated_tokens,created_at) VALUES(?,?,?,?,?,?,?)", (reservation_id, key_id, upstream_profile_id, model, estimated_cost_usd, estimated_tokens, now_iso()))
        return reservation_id

    def finish_reservation(self, reservation_id: str | None):
        if not reservation_id:
            return
        with self.connect() as conn:
            conn.execute("UPDATE budget_reservations SET status='released' WHERE id=? AND status='active'", (reservation_id,))

    def set_upstream_state(self, profile_id: str, enabled: bool):
        with self.connect() as conn:
            conn.execute("UPDATE upstream_profiles SET enabled=? WHERE id=?", (int(enabled), profile_id))

    def is_ip_blocked(self, ip: str | None) -> bool:
        if not ip:
            return False
        with self.connect() as conn:
            row = conn.execute("SELECT expires_at FROM blocked_ips WHERE ip=?", (ip,)).fetchone()
            if not row:
                return False
            if row["expires_at"] and row["expires_at"] <= now_iso():
                conn.execute("DELETE FROM blocked_ips WHERE ip=?", (ip,))
                return False
            return True

    def list_blocked_ips(self):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT ip, reason, created_at, expires_at FROM blocked_ips ORDER BY created_at DESC")]

    def block_ip(self, ip: str, reason: str, expires_at: str | None = None):
        with self.connect() as conn:
            conn.execute("INSERT INTO blocked_ips(ip,reason,created_at,expires_at) VALUES(?,?,?,?) ON CONFLICT(ip) DO UPDATE SET reason=excluded.reason, expires_at=excluded.expires_at", (ip, reason, now_iso(), expires_at))

    def unblock_ip(self, ip: str):
        with self.connect() as conn:
            conn.execute("DELETE FROM blocked_ips WHERE ip=?", (ip,))
