from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.catalog import METRIC_CATALOG


class MetricsUnavailableError(RuntimeError):
    """Raised when neither production nor demo metrics are available."""


class MetricsRepository:
    def __init__(self, primary_path: Path, fallback_path: Path) -> None:
        self.primary_path = Path(primary_path)
        self.fallback_path = Path(fallback_path)
        self._cached_path: Path | None = None
        self._cached_mtime_ns: int | None = None
        self._cached_payload: dict[str, Any] | None = None

    def _resolve_path(self) -> Path:
        if self.primary_path.exists():
            return self.primary_path
        if self.fallback_path.exists():
            return self.fallback_path
        raise MetricsUnavailableError(
            f"metrics not found: {self.primary_path} or {self.fallback_path}"
        )

    def load(self) -> dict[str, Any]:
        path = self._resolve_path()
        mtime_ns = path.stat().st_mtime_ns
        if (
            self._cached_payload is not None
            and self._cached_path == path
            and self._cached_mtime_ns == mtime_ns
        ):
            return self._cached_payload

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload.get("kpis"), dict):
            raise MetricsUnavailableError(f"invalid metrics payload: {path}")
        if not isinstance(payload.get("daily", []), list):
            raise MetricsUnavailableError(f"invalid daily series: {path}")

        payload["_source"] = str(path)
        self._cached_path = path
        self._cached_mtime_ns = mtime_ns
        self._cached_payload = payload
        return payload

    def public_snapshot(self) -> dict[str, Any]:
        payload = self.load()
        return {
            "source": payload["_source"],
            "generated_at": payload.get("generated_at"),
            "latest_dt": payload.get("latest_dt"),
            "kpis": payload["kpis"],
        }

    def build_evidence(
        self,
        metric_keys: list[str],
        payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        data = payload or self.load()
        kpis = data["kpis"]
        daily = data.get("daily", [])
        evidence: list[dict[str, Any]] = []

        for key in metric_keys:
            if key not in kpis or key not in METRIC_CATALOG:
                continue
            definition = METRIC_CATALOG[key]
            item: dict[str, Any] = {
                "metric": key,
                "label": definition.label,
                "definition": definition.definition,
                "value": kpis[key],
                "unit": definition.unit,
                "source": data["_source"],
            }
            trend = _daily_trend(key, daily)
            if trend is not None:
                item["daily_trend"] = trend
            evidence.append(item)

        return evidence


def _daily_metric_value(metric: str, row: dict[str, Any]) -> float | None:
    try:
        if metric == "gmv":
            return float(row["gmv"])
        if metric == "pay_amount":
            return float(row["pay_amount"])
        if metric == "pay_conversion_rate":
            orders = float(row["order_count"])
            return float(row["pay_order_count"]) / orders if orders else None
        if metric == "avg_order_value":
            paid_orders = float(row["pay_order_count"])
            return float(row["pay_amount"]) / paid_orders if paid_orders else None
        if metric == "refund_rate":
            paid = float(row["pay_amount"])
            return float(row["refund_amount"]) / paid if paid else None
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _daily_trend(metric: str, daily: list[dict[str, Any]]) -> dict[str, Any] | None:
    points: list[tuple[str | None, float]] = []
    for row in daily:
        value = _daily_metric_value(metric, row)
        if value is not None:
            points.append((row.get("dt"), value))

    if len(points) < 2:
        return None

    first_dt, first = points[0]
    last_dt, last = points[-1]
    change_pct = None if first == 0 else (last - first) / abs(first)
    return {
        "first_dt": first_dt,
        "first_value": round(first, 6),
        "last_dt": last_dt,
        "last_value": round(last, 6),
        "change_pct": None if change_pct is None else round(change_pct, 6),
    }
