import json
from pathlib import Path

from app.analytics import MetricsRepository
from app.llm import DeterministicProvider
from app.service import AnalystService


def test_service_returns_grounded_evidence(tmp_path: Path) -> None:
    metrics = tmp_path / "metrics.json"
    metrics.write_text(
        json.dumps(
            {
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
    repository = MetricsRepository(metrics, tmp_path / "fallback.json")
    service = AnalystService(repository, DeterministicProvider())

    result = service.ask("GMV 最近表现如何？", top_k=2)

    assert result["provider"] == "deterministic"
    assert result["evidence"][0]["metric"] == "gmv"
    assert result["evidence"][0]["daily_trend"]["change_pct"] == 1.0
