from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_FMP_CACHE_DIR = str(Path(__file__).resolve().parents[4] / "data" / "raw" / "fmp-cache")
DEFAULT_FMP_HOLDINGS_SNAPSHOT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "raw" / "fmp-holdings-history")
DEFAULT_FMP_ALPHA_PIT_SNAPSHOT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "raw" / "fmp-alpha-pit")
DEFAULT_OPTIMIZER_HANDOFF_DIR = str(Path(__file__).resolve().parents[4] / "data" / "artifacts" / "optimizer-handoffs")
DEFAULT_CONSTRUCTION_ARTIFACT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "artifacts" / "construction-artifacts")
DEFAULT_MONITOR_DEFINITION_ARTIFACT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "artifacts" / "monitor-definitions")
DEFAULT_REVIEW_SNAPSHOT_ARTIFACT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "artifacts" / "review-snapshots")
DEFAULT_ETF_RANKING_ARTIFACT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "artifacts" / "etf-ranking-artifacts")
DEFAULT_REPLACEMENT_RANKING_ARTIFACT_DIR = str(Path(__file__).resolve().parents[4] / "data" / "artifacts" / "etf-replacement-ranking-artifacts")
DEFAULT_CROSS_SECTIONAL_RESEARCH_ARTIFACT_DIR = str(
    Path(__file__).resolve().parents[4] / "data" / "artifacts" / "cross-sectional-research-artifacts"
)
DEFAULT_GENERIC_RANKING_ARTIFACTS_DIR = str(
    Path(__file__).resolve().parents[4] / "data" / "artifacts" / "generic-ranking-artifacts"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    fmp_api_key: str = Field(default="")
    fmp_base_url: str = Field(default="https://financialmodelingprep.com/stable")
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
    fmp_max_requests_per_minute: int = Field(default=250)
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
