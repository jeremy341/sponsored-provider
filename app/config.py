from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    alibaba_api_key: str = ""
    alibaba_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    allowed_models: str = ""
    database_path: str = "./provider.db"
    provider_key_pepper: str = ""
    provider_secret_key: str = ""
    admin_token: str = ""
    max_request_bytes: int = 1_048_576
    max_input_chars: int = 50_000
    max_output_tokens: int = 1_024
    rate_limit_requests_per_minute: int = 10
    provider_hard_stop_usd: float = 35.0
    provider_warning_usd: float = 25.0
    provider_estimate_reserve_usd: float = 5.0
    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    emergency_stop: bool = False
    upstream_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def model_allowlist(self) -> set[str]:
        return {item.strip() for item in self.allowed_models.split(",") if item.strip()}

    @property
    def normalized_base_url(self) -> str:
        return self.alibaba_base_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
