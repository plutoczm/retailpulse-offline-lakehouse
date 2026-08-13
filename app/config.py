from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    value = float(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    app_name: str
    metrics_path: Path
    fallback_metrics_path: Path
    allow_demo_fallback: bool
    metrics_max_age_seconds: int
    api_access_key: str | None
    rate_limit_per_minute: int
    response_cache_ttl_seconds: float
    response_cache_max_entries: int
    openai_api_key: str | None
    openai_model: str
    openai_timeout_seconds: float

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    environment = os.getenv("RETAILPULSE_ENV", "development").strip().casefold()
    if environment not in {"development", "test", "production"}:
        raise ValueError("RETAILPULSE_ENV must be development, test, or production")

    api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    access_key = os.getenv("RETAILPULSE_API_KEY", "").strip() or None
    default_allow_demo = environment != "production"
    default_max_age = 86400 if environment == "production" else 0

    return Settings(
        environment=environment,
        app_name=os.getenv("RETAILPULSE_APP_NAME", "RetailPulse AI Analyst"),
        metrics_path=_env_path(
            "RETAILPULSE_METRICS_PATH", "dashboard/data/dashboard.json"
        ),
        fallback_metrics_path=_env_path(
            "RETAILPULSE_FALLBACK_METRICS_PATH", "dashboard/data/demo.json"
        ),
        allow_demo_fallback=_env_bool(
            "RETAILPULSE_ALLOW_DEMO_FALLBACK", default_allow_demo
        ),
        metrics_max_age_seconds=_env_int(
            "RETAILPULSE_METRICS_MAX_AGE_SECONDS", default_max_age
        ),
        api_access_key=access_key,
        rate_limit_per_minute=_env_int("RETAILPULSE_RATE_LIMIT_PER_MINUTE", 30),
        response_cache_ttl_seconds=_env_float(
            "RETAILPULSE_RESPONSE_CACHE_TTL_SECONDS", 60.0
        ),
        response_cache_max_entries=_env_int(
            "RETAILPULSE_RESPONSE_CACHE_MAX_ENTRIES", 256, minimum=1
        ),
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5"),
        openai_timeout_seconds=_env_float(
            "OPENAI_TIMEOUT_SECONDS", 20.0, minimum=1.0
        ),
    )
