from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DATA_ROOT = Path(os.getenv("PORTFOLIO_RUNTIME_DATA_DIR", REPO_ROOT / ".runtime-data"))

DEFAULT_FMP_CACHE_DIR = str(REPO_ROOT / "data" / "raw" / "fmp-cache")
DEFAULT_FMP_HOLDINGS_SNAPSHOT_DIR = str(REPO_ROOT / "data" / "raw" / "fmp-holdings-history")
DEFAULT_FMP_ALPHA_PIT_SNAPSHOT_DIR = str(REPO_ROOT / "data" / "raw" / "fmp-alpha-pit")
DEFAULT_OPTIMIZER_HANDOFF_DIR = str(RUNTIME_DATA_ROOT / "artifacts" / "optimizer-handoffs")
DEFAULT_CONSTRUCTION_ARTIFACT_DIR = str(RUNTIME_DATA_ROOT / "artifacts" / "construction-artifacts")
DEFAULT_MONITOR_DEFINITION_ARTIFACT_DIR = str(RUNTIME_DATA_ROOT / "artifacts" / "monitor-definitions")
DEFAULT_REVIEW_SNAPSHOT_ARTIFACT_DIR = str(RUNTIME_DATA_ROOT / "artifacts" / "review-snapshots")
DEFAULT_ETF_RANKING_ARTIFACT_DIR = str(RUNTIME_DATA_ROOT / "artifacts" / "etf-ranking-artifacts")
DEFAULT_REPLACEMENT_RANKING_ARTIFACT_DIR = str(RUNTIME_DATA_ROOT / "artifacts" / "etf-replacement-ranking-artifacts")
DEFAULT_CROSS_SECTIONAL_RESEARCH_ARTIFACT_DIR = str(
    RUNTIME_DATA_ROOT / "artifacts" / "cross-sectional-research-artifacts"
)
DEFAULT_GENERIC_RANKING_ARTIFACTS_DIR = str(
    Path(__file__).resolve().parents[4] / "data" / "artifacts" / "generic-ranking-artifacts"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    fmp_api_key: str = Field(default="")
    fmp_base_url: str = Field(default="https://financialmodelingprep.com/stable")
    # Legacy FMP v3 surface. Kept separate from `fmp_base_url` (which points at
    # /stable) because some endpoints — currently `etf-holder`, used for ETF
    # look-through — exist ONLY on v3 and would 404 under /stable (US-24.6).
    # Configurable so every outbound call can be redirected to a proxy/mock.
    fmp_legacy_base_url: str = Field(default="https://financialmodelingprep.com/api/v3")
    fmp_cache_enabled: bool = Field(default=True)
    fmp_cache_dir: str = Field(default=DEFAULT_FMP_CACHE_DIR)
    fmp_holdings_snapshot_dir: str = Field(default=DEFAULT_FMP_HOLDINGS_SNAPSHOT_DIR)
    fmp_alpha_pit_snapshot_dir: str = Field(default=DEFAULT_FMP_ALPHA_PIT_SNAPSHOT_DIR)
    optimizer_handoff_dir: str = Field(default=DEFAULT_OPTIMIZER_HANDOFF_DIR)
    construction_artifact_dir: str = Field(default=DEFAULT_CONSTRUCTION_ARTIFACT_DIR)
    monitor_definition_artifact_dir: str = Field(default=DEFAULT_MONITOR_DEFINITION_ARTIFACT_DIR)
    review_snapshot_artifact_dir: str = Field(default=DEFAULT_REVIEW_SNAPSHOT_ARTIFACT_DIR)
    etf_ranking_artifact_dir: str = Field(default=DEFAULT_ETF_RANKING_ARTIFACT_DIR)
    replacement_ranking_artifact_dir: str = Field(default=DEFAULT_REPLACEMENT_RANKING_ARTIFACT_DIR)
    cross_sectional_research_artifact_dir: str = Field(default=DEFAULT_CROSS_SECTIONAL_RESEARCH_ARTIFACT_DIR)
    generic_ranking_artifacts_dir: str = Field(default=DEFAULT_GENERIC_RANKING_ARTIFACTS_DIR)
    fmp_quote_cache_ttl_seconds: int = Field(default=300)
    fmp_history_cache_ttl_seconds: int = Field(default=86400)
    # Epic 37 / US-37.1 decision #4: company-profile data (sector, ISIN) is
    # far less time-sensitive than a quote — widened off the 5-minute quote
    # tier to 30 days so equity sector resolution doesn't re-fetch every run.
    fmp_profile_cache_ttl_seconds: int = Field(default=2592000)
    fmp_max_requests_per_minute: int = Field(default=250)
    # HTTP transport timeout for every FMP request (US-24.6 — was a literal
    # 30.0 in the client, the one transport knob that was not configurable).
    fmp_request_timeout_seconds: float = Field(default=30.0)
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
