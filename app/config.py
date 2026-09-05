from functools import lru_cache
import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _bootstrap_generated: bool = PrivateAttr(default=False)
    alibaba_api_key: str = ""
    alibaba_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    allowed_models: str = ""
    database_path: str = "./provider.db"
    provider_key_pepper: str = ""
    provider_secret_key: str = ""
    admin_token: str = ""
    rate_limit_requests_per_minute: int = 0
    provider_hard_stop_usd: float = 35.0
    provider_warning_usd: float = 25.0
    provider_estimate_reserve_usd: float = 5.0
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    emergency_stop: bool = False
    upstream_timeout_seconds: float = 300.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def model_post_init(self, __context):
        secret_path = Path(self.database_path).with_name("runtime-secrets.json")
        stored = {}
        if secret_path.exists():
            try:
                stored = json.loads(secret_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                stored = {}
        changed = False
        if not self.admin_token:
            self.admin_token = stored.get("admin_token") or secrets.token_urlsafe(32)
            changed = True
        if not self.provider_secret_key:
            self.provider_secret_key = stored.get("provider_secret_key") or Fernet.generate_key().decode()
            changed = True
        if not self.provider_key_pepper:
            self.provider_key_pepper = stored.get("provider_key_pepper") or secrets.token_urlsafe(32)
            changed = True
        if changed:
            self._bootstrap_generated = True
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            secret_path.write_text(json.dumps({"admin_token": self.admin_token, "provider_secret_key": self.provider_secret_key, "provider_key_pepper": self.provider_key_pepper}, indent=2), encoding="utf-8")
            try:
                secret_path.chmod(0o600)
            except OSError:
                pass

    @property
    def model_allowlist(self) -> set[str]:
        return {item.strip() for item in self.allowed_models.split(",") if item.strip()}

    @property
    def normalized_base_url(self) -> str:
        return self.alibaba_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
