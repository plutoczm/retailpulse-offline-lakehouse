from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    metrics_path: Path
    fallback_metrics_path: Path
    openai_api_key: str | None
    openai_model: str
    openai_timeout_seconds: float

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
    return Settings(
        app_name=os.getenv("RETAILPULSE_APP_NAME", "RetailPulse AI Analyst"),
        metrics_path=_env_path(
            "RETAILPULSE_METRICS_PATH", "dashboard/data/dashboard.json"
        ),
        fallback_metrics_path=_env_path(
            "RETAILPULSE_FALLBACK_METRICS_PATH", "dashboard/data/demo.json"
        ),
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5"),
        openai_timeout_seconds=max(timeout, 1.0),
    )
