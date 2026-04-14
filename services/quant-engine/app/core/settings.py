from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_FMP_CACHE_DIR = str(Path(__file__).resolve().parents[4] / "data" / "raw" / "fmp-cache")
DEFAULT_FMP_HOLDINGS_SNAPSHOT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "raw" / "fmp-holdings-history")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    fmp_api_key: str = Field(default="")
    fmp_base_url: str = Field(default="https://financialmodelingprep.com/stable")
    fmp_cache_enabled: bool = Field(default=True)
    fmp_cache_dir: str = Field(default=DEFAULT_FMP_CACHE_DIR)
    fmp_holdings_snapshot_dir: str = Field(default=DEFAULT_FMP_HOLDINGS_SNAPSHOT_DIR)
    fmp_quote_cache_ttl_seconds: int = Field(default=300)
    fmp_history_cache_ttl_seconds: int = Field(default=86400)
    fmp_max_requests_per_minute: int = Field(default=250)
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
