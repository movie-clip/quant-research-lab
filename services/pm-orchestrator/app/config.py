import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    app_name: str = "PM Orchestrator"
    db_path: Path = BASE_DIR / "pm_orchestrator.db"
    worker_poll_interval_seconds: float = 0.5
    max_memory_summary_chars: int = 2000
    llm_provider: str = os.getenv("PM_ORCHESTRATOR_LLM_PROVIDER", "fake")
    llm_model: str = os.getenv("PM_ORCHESTRATOR_LLM_MODEL", "gpt-4.1")
    llm_api_base: str = os.getenv("PM_ORCHESTRATOR_LLM_API_BASE", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("PM_ORCHESTRATOR_LLM_API_KEY", "")
    llm_timeout_seconds: float = float(os.getenv("PM_ORCHESTRATOR_LLM_TIMEOUT_SECONDS", "60"))


settings = Settings()
