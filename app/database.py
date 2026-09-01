import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str, pepper: str = ""):
        self.path = path
        self.pepper = pepper
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
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
              estimated_cost_usd REAL NOT NULL DEFAULT 0
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
              FOREIGN KEY(provider_key_id) REFERENCES provider_api_keys(id)
            );
            """)

    def digest(self, raw_key: str) -> str:
        return hashlib.sha256((self.pepper + raw_key).encode()).hexdigest()

    def create_key(self, label: str) -> tuple[str, dict]:
        raw = "sp_sk_" + secrets.token_urlsafe(32)
        created = now_iso()
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO provider_api_keys(key_prefix,key_hash,label,created_at) VALUES(?,?,?,?)",
                (raw[:14], self.digest(raw), label, created),
            )
            key_id = cur.lastrowid
        return raw, {"id": key_id, "key_prefix": raw[:14], "label": label, "created_at": created, "enabled": True}

    def find_key(self, raw_key: str):
        with self.connect() as conn:
            return conn.execute("SELECT * FROM provider_api_keys WHERE key_hash=?", (self.digest(raw_key),)).fetchone()

    def list_keys(self):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM provider_api_keys ORDER BY created_at DESC")]

    def set_key_state(self, key_id: int, enabled: bool, revoke: bool = False):
        with self.connect() as conn:
            conn.execute(
                "UPDATE provider_api_keys SET enabled=?, revoked_at=CASE WHEN ? THEN COALESCE(revoked_at, ?) ELSE revoked_at END WHERE id=?",
                (int(enabled and not revoke), int(revoke), now_iso(), key_id),
            )

    def record_usage(self, key_id, *, model, input_tokens, output_tokens, total_tokens, estimated_cost_usd, latency_ms, status, stream, error_category=None):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO usage_records(provider_key_id,timestamp,model,input_tokens,output_tokens,total_tokens,estimated_cost_usd,latency_ms,status,stream,error_category) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (key_id, now_iso(), model, input_tokens, output_tokens, total_tokens, estimated_cost_usd, latency_ms, status, int(stream), error_category),
            )
            conn.execute(
                "UPDATE provider_api_keys SET request_count=request_count+1, estimated_cost_usd=estimated_cost_usd+?, last_used_at=? WHERE id=?",
                (estimated_cost_usd, now_iso(), key_id),
            )

    def usage_summary(self):
        with self.connect() as conn:
            totals = conn.execute("SELECT COUNT(*) requests, COALESCE(SUM(input_tokens),0) input_tokens, COALESCE(SUM(output_tokens),0) output_tokens, COALESCE(SUM(total_tokens),0) total_tokens, COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd FROM usage_records").fetchone()
            recent = [dict(r) for r in conn.execute("SELECT timestamp, model, total_tokens, estimated_cost_usd, latency_ms, status, stream FROM usage_records ORDER BY id DESC LIMIT 20")]
            by_model = [dict(r) for r in conn.execute("SELECT model, COUNT(*) requests, COALESCE(SUM(total_tokens),0) total_tokens, COALESCE(SUM(estimated_cost_usd),0) estimated_cost_usd FROM usage_records GROUP BY model ORDER BY estimated_cost_usd DESC")]
        return {"totals": dict(totals), "recent": recent, "by_model": by_model, "keys": self.list_keys()}

