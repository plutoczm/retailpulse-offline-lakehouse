from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.catalog import METRIC_CATALOG


class MetricsUnavailableError(RuntimeError):
    """Raised when trusted metrics cannot be loaded or validated."""


class MetricsRepository:
    def __init__(
        self,
        primary_path: Path,
        fallback_path: Path,
        allow_fallback: bool = True,
    ) -> None:
        self.primary_path = Path(primary_path)
        self.fallback_path = Path(fallback_path)
        self.allow_fallback = allow_fallback
        self._cached_path: Path | None = None
        self._cached_mtime_ns: int | None = None
        self._cached_payload: dict[str, Any] | None = None

    def _resolve_path(self) -> tuple[Path, str]:
        if self.primary_path.exists():
            return self.primary_path, "lakehouse"
        if self.allow_fallback and self.fallback_path.exists():
            return self.fallback_path, "demo"
        raise MetricsUnavailableError("trusted metrics are unavailable")

    def load(self) -> dict[str, Any]:
        path, source_kind = self._resolve_path()
        mtime_ns = path.stat().st_mtime_ns
        if (
            self._cached_payload is not None
            and self._cached_path == path
            and self._cached_mtime_ns == mtime_ns
        ):
            return self._cached_payload

        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload.get("kpis"), dict):
            raise MetricsUnavailableError("metrics payload failed schema validation")
        if not isinstance(payload.get("daily", []), list):
            raise MetricsUnavailableError("metrics daily series failed schema validation")

        payload["_source"] = str(path)
        payload["_source_kind"] = source_kind
        payload["_data_version"] = hashlib.sha256(raw).hexdigest()[:16]
        self._cached_path = path
        self._cached_mtime_ns = mtime_ns
        self._cached_payload = payload
        return payload

    def metadata(self) -> dict[str, Any]:
        payload = self.load()
        return {
            "source": payload["_source"],
            "source_kind": payload["_source_kind"],
            "data_version": payload["_data_version"],
            "generated_at": payload.get("generated_at"),
            "latest_dt": payload.get("latest_dt"),
            "age_seconds": _age_seconds(payload.get("generated_at")),
        }

    def public_snapshot(self) -> dict[str, Any]:
        payload = self.load()
        return {**self.metadata(), "kpis": payload["kpis"]}

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


def _age_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
        return round(max(age.total_seconds(), 0.0), 2)
    except ValueError:
        return None


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
