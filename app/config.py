from functools import lru_cache
import json
import secrets
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar

from cryptography.fernet import Fernet

from pydantic import PrivateAttr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DEFAULT_DEVELOPER_ALLOWANCE_NANO_USD: ClassVar[int] = 7_000_000_000
    _bootstrap_generated: bool = PrivateAttr(default=False)
    alibaba_api_key: str = ""
    alibaba_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    allowed_models: str = ""
    database_path: str = "./provider.db"
    provider_key_pepper: str = ""
    provider_secret_key: str = ""
    hackclub_client_id: str = ""
    hackclub_client_secret: str = ""
    portal_redirect_uri: str = ""
    portal_bootstrap_operator_email: str = ""
    portal_public_origin: str = ""
    portal_allow_framing: bool = False
    portal_bootstrap_operator_username: str = ""
    portal_bootstrap_operator_password: str = ""
    portal_bootstrap_developer_username: str = ""
    portal_bootstrap_developer_password: str = ""
    portal_cookie_secure: bool = True
    portal_auth_rate_limit_attempts: int = 5
    portal_auth_rate_limit_window_seconds: int = 900
    default_developer_allowance_usd: str = "7"
    rate_limit_requests_per_minute: int = 0
    provider_hard_stop_usd: float = 34.70
    provider_warning_usd: float = 25.0
    provider_estimate_reserve_usd: float = 0.10
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    emergency_stop: bool = False
    upstream_timeout_seconds: float = 300.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("default_developer_allowance_usd")
    @classmethod
    def validate_default_developer_allowance(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except (InvalidOperation, TypeError):
            raise ValueError("Default developer allowance must be a decimal USD amount") from None
        if not amount.is_finite() or amount < 0 or amount * 1_000_000_000 != (amount * 1_000_000_000).to_integral_value():
            raise ValueError("Default developer allowance must be non-negative and precise to nano-USD")
        return value

    @property
    def default_developer_allowance_nano_usd(self) -> int:
        return int(Decimal(self.default_developer_allowance_usd) * 1_000_000_000)

    def model_post_init(self, __context):
        secret_path = Path(self.database_path).with_name("runtime-secrets.json")
        stored = {}
        if secret_path.exists():
            try:
                stored = json.loads(secret_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                stored = {}
        changed = False
        if not self.provider_secret_key:
            self.provider_secret_key = stored.get("provider_secret_key") or Fernet.generate_key().decode()
            changed = True
        if not self.provider_key_pepper:
            self.provider_key_pepper = stored.get("provider_key_pepper") or secrets.token_urlsafe(32)
            changed = True
        if changed:
            self._bootstrap_generated = True
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            secret_path.write_text(json.dumps({"provider_secret_key": self.provider_secret_key, "provider_key_pepper": self.provider_key_pepper}, indent=2), encoding="utf-8")
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
