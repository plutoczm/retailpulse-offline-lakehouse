import json
from pathlib import Path

import pytest

from app.analytics import MetricsRepository, MetricsUnavailableError
from app.cache import ResponseCache
from app.llm import DeterministicProvider
from app.models import AnalysisContent
from app.rate_limit import SlidingWindowRateLimiter
from app.service import AnalystService


def _write_metrics(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-13T00:00:00Z",
                "latest_dt": "2025-01-02",
                "kpis": {
                    "gmv": 300.0,
                    "pay_amount": 250.0,
                    "pay_conversion_rate": 0.8,
                    "avg_order_value": 25.0,
                    "repeat_purchase_rate": 0.2,
                    "refund_rate": 0.03,
                },
                "daily": [
                    {
                        "dt": "2025-01-01",
                        "order_count": 10,
                        "pay_order_count": 8,
                        "gmv": 100.0,
                        "pay_amount": 80.0,
                        "refund_amount": 2.0,
                    },
                    {
                        "dt": "2025-01-02",
                        "order_count": 20,
                        "pay_order_count": 16,
                        "gmv": 200.0,
                        "pay_amount": 170.0,
                        "refund_amount": 5.5,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_structured_grounding_and_versioned_cache(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.json"
    _write_metrics(metrics)
    repository = MetricsRepository(metrics, tmp_path / "fallback.json")
    cache = ResponseCache[AnalysisContent](ttl_seconds=60, max_entries=10)
    service = AnalystService(repository, DeterministicProvider(), cache=cache)

    first = service.ask("GMV 最近表现如何？", top_k=2)
    second = service.ask("GMV 最近表现如何？", top_k=2)

    observation = first["analysis"]["observations"][0]
    assert observation["evidence_keys"] == ["gmv"]
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert first["data_version"] == second["data_version"]


def test_rate_limiter_uses_sliding_window() -> None:
    limiter = SlidingWindowRateLimiter(2)

    assert limiter.check("user", now=0).allowed
    assert limiter.check("user", now=1).allowed
    blocked = limiter.check("user", now=2)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds > 0
    assert limiter.check("user", now=61).allowed


def test_demo_fallback_can_be_disabled_for_production(tmp_path: Path) -> None:
    fallback = tmp_path / "demo.json"
    _write_metrics(fallback)
    repository = MetricsRepository(
        tmp_path / "missing.json",
        fallback,
        allow_fallback=False,
    )

    with pytest.raises(MetricsUnavailableError):
        repository.load()
