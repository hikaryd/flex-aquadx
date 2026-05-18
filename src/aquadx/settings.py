from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

CacheBackend = Literal["memory", "redis", "noop"]
AssetsMode = Literal["redirect", "proxy"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "aquadx-python"
    # Defaults match the public AquaNet instance — see AquaNet/.env in upstream.
    aquadx_base_url: str = "https://aquadx.net/aqua"
    aquadx_data_host: str = "https://aquadx.net"
    aquadx_data_host_fallback: str | None = None

    assets_mode: AssetsMode = "redirect"

    cache_backend: CacheBackend = "memory"
    redis_url: str | None = None
    cache_ttl_player_seconds: int = 60
    cache_ttl_ranking_seconds: int = 300
    cache_ttl_meta_seconds: int = 86_400

    http_timeout_s: float = 10.0
    http_rps: float = 5.0

    api_key: str | None = None
    log_level: str = "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    global _settings
    _settings = None
