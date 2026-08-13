from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from app.catalog import METRIC_CATALOG, select_metric_keys
from app.models import QueryPlan, ToolCall, ToolResult

PLANNER_VERSION = "rules-v1"
SUPPORTED_TOOLS = (
    "get_kpi",
    "compare_periods",
    "breakdown_by_dimension",
    "get_topn",
    "detect_anomaly",
)
SUPPORTED_DIMENSIONS = (
    "product",
    "category",
    "shop",
    "refund_reason",
    "user_segment",
)
KNOWN_COVERAGE_GAPS = ("channel", "campaign", "region")

_DIMENSION_KEYWORDS = {
    "product": ("商品", "产品", "sku", "product"),
    "category": ("品类", "类目", "category"),
    "shop": ("店铺", "门店", "shop", "store"),
    "refund_reason": ("退款原因", "退货原因", "refund reason"),
    "user_segment": ("用户分层", "用户群", "rfm", "segment"),
}
_GAP_KEYWORDS = {
    "channel": ("渠道", "channel"),
    "campaign": ("活动", "campaign", "promotion"),
    "region": ("地区", "区域", "地域", "region", "province"),
}


def capabilities() -> dict[str, Any]:
    return {
        "planner_version": PLANNER_VERSION,
        "tools": list(SUPPORTED_TOOLS),
        "supported_dimensions": list(SUPPORTED_DIMENSIONS),
        "known_coverage_gaps": list(KNOWN_COVERAGE_GAPS),
    }


class QueryPlanner:
    """Create a bounded analytics plan from a user question.

    Planning is deterministic on purpose. The model never chooses arbitrary SQL,
    table names, file paths, or executable code.
    """

    def plan(
        self,
        question: str,
        payload: dict[str, Any],
        top_k: int = 4,
    ) -> QueryPlan:
        normalized = question.casefold()
        available = set(payload.get("kpis", {}))
        metrics = select_metric_keys(
            question,
            available,
            max_items=min(max(top_k, 1), 3),
        )
        dimensions = [
            dimension
            for dimension, keywords in _DIMENSION_KEYWORDS.items()
            if any(keyword.casefold() in normalized for keyword in keywords)
        ]
        coverage_gaps = [
            dimension
            for dimension, keywords in _GAP_KEYWORDS.items()
            if any(keyword.casefold() in normalized for keyword in keywords)
        ]

        trend = _contains(
            normalized,
            (
                "趋势",
                "最近",
                "变化",
                "增长",
                "下降",
                "环比",
                "同比",
                "trend",
                "change",
                "compare",
            ),
        )
        diagnostic = _contains(
            normalized,
            ("为什么", "原因", "诊断", "归因", "why", "reason", "diagnose"),
        )
        ranking = _contains(
            normalized,
            ("top", "排名", "排行", "最高", "最多", "前几", "rank"),
        )
        anomaly = _contains(
            normalized,
            ("异常", "波动", "突增", "突降", "anomaly", "outlier", "spike"),
        )

        calls: list[ToolCall] = []
        for metric in metrics[:2]:
            calls.append(
                self._call(
                    "get_kpi",
                    {"metric": metric},
                    f"读取 {metric} 的可信快照",
                )
            )

        if trend or diagnostic:
            for metric in metrics[:2]:
                calls.append(
                    self._call(
                        "compare_periods",
                        {"metric": metric, "window_days": 3},
                        f"比较 {metric} 最近窗口与前一窗口",
                    )
                )

        if anomaly:
            for metric in metrics[:2]:
                calls.append(
                    self._call(
                        "detect_anomaly",
                        {"metric": metric, "z_threshold": 2.0},
                        f"检查 {metric} 日序列异常点",
                    )
                )

        if dimensions:
            for dimension in dimensions[:2]:
                calls.append(
                    self._dimension_call(
                        dimension=dimension,
                        ranking=ranking,
                        top_k=top_k,
                    )
                )
        elif diagnostic:
            diagnostic_call = self._diagnostic_dimension_call(metrics)
            if diagnostic_call is not None:
                calls.append(diagnostic_call)

        calls = _deduplicate_calls(calls)[:6]
        return QueryPlan(
            planner_version=PLANNER_VERSION,
            intent=_intent(trend, diagnostic, ranking, anomaly, len(calls)),
            calls=calls,
            coverage_gaps=coverage_gaps,
        )

    def _dimension_call(
        self,
        dimension: str,
        ranking: bool,
        top_k: int,
    ) -> ToolCall:
        tool = "get_topn" if ranking else "breakdown_by_dimension"
        verb = "返回受控 Top-N" if ranking else "下钻经营表现"
        return self._call(
            tool,
            _dimension_arguments(
                dimension,
                limit=min(max(top_k, 1), 10),
            ),
            f"按 {dimension} {verb}",
        )

    def _diagnostic_dimension_call(
        self,
        metrics: list[str],
    ) -> ToolCall | None:
        if "refund_rate" in metrics:
            return self._call(
                "breakdown_by_dimension",
                _dimension_arguments("refund_reason", limit=5),
                "退款指标诊断优先下钻退款原因",
            )
        if any(metric in metrics for metric in ("gmv", "pay_amount", "avg_order_value")):
            return self._call(
                "breakdown_by_dimension",
                _dimension_arguments("category", limit=5),
                "收入类指标诊断优先下钻品类",
            )
        return None

    @staticmethod
    def _call(
        tool: str,
        arguments: dict[str, Any],
        reason: str,
    ) -> ToolCall:
        fingerprint = ":".join(str(value) for value in arguments.values())
        return ToolCall(
            call_id=f"{tool}:{fingerprint}"[:120],
            tool=tool,
            arguments=arguments,
            reason=reason,
        )


class RetailToolbox:
    """Execute only allow-listed analytics tools against the serving snapshot."""

    def execute(
        self,
        plan: QueryPlan,
        payload: dict[str, Any],
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for call in plan.calls:
            try:
                results.append(self.execute_call(call, payload))
            except (KeyError, TypeError, ValueError) as exc:
                results.append(
                    _insufficient(
                        call,
                        payload,
                        f"tool execution rejected invalid serving data: {type(exc).__name__}",
                    )
                )
        return results

    def execute_call(
        self,
        call: ToolCall,
        payload: dict[str, Any],
    ) -> ToolResult:
        handler = getattr(self, f"_{call.tool}")
        return handler(call, payload)

    def _get_kpi(
        self,
        call: ToolCall,
        payload: dict[str, Any],
    ) -> ToolResult:
        metric = str(call.arguments["metric"])
        value = payload.get("kpis", {}).get(metric)
        definition = METRIC_CATALOG.get(metric)
        if value is None or definition is None:
            return _insufficient(call, payload, f"KPI {metric} 不存在")
        return _ok(
            call,
            payload,
            evidence_key=f"kpi:{metric}",
            title=definition.label,
            data={
                "metric": metric,
                "value": value,
                "unit": definition.unit,
                "latest_dt": payload.get("latest_dt"),
            },
        )

    def _compare_periods(
        self,
        call: ToolCall,
        payload: dict[str, Any],
    ) -> ToolResult:
        metric = str(call.arguments["metric"])
        daily = sorted(
            payload.get("daily", []),
            key=lambda row: str(row.get("dt", "")),
        )
        requested = int(call.arguments.get("window_days", 3))
        window = min(requested, len(daily) // 2)
        if window < 1:
            return _insufficient(call, payload, "日序列不足以形成两个对比窗口")

        previous_rows = daily[-2 * window : -window]
        current_rows = daily[-window:]
        previous = _aggregate_metric(metric, previous_rows)
        current = _aggregate_metric(metric, current_rows)
        if previous is None or current is None:
            return _insufficient(call, payload, f"{metric} 缺少可聚合字段")

        change_pct = None if previous == 0 else (current - previous) / abs(previous)
        return _ok(
            call,
            payload,
            evidence_key=f"compare:{metric}:{window}d",
            title=f"{METRIC_CATALOG[metric].label} 分期对比",
            data={
                "metric": metric,
                "window_days": window,
                "previous": round(previous, 6),
                "current": round(current, 6),
                "change_pct": None if change_pct is None else round(change_pct, 6),
                "previous_range": [
                    previous_rows[0].get("dt"),
                    previous_rows[-1].get("dt"),
                ],
                "current_range": [
                    current_rows[0].get("dt"),
                    current_rows[-1].get("dt"),
                ],
            },
        )

    def _breakdown_by_dimension(
        self,
        call: ToolCall,
        payload: dict[str, Any],
    ) -> ToolResult:
        result = self._ranked_dimension(call, payload)
        if result.status == "ok":
            result.notes.append(
                "Serving mart 仅暴露受控聚合结果，不提供任意 SQL 或原始明细访问。"
            )
        return result

    def _get_topn(
        self,
        call: ToolCall,
        payload: dict[str, Any],
    ) -> ToolResult:
        return self._ranked_dimension(call, payload)

    def _ranked_dimension(
        self,
        call: ToolCall,
        payload: dict[str, Any],
    ) -> ToolResult:
        dimension = str(call.arguments["dimension"])
        limit = min(max(int(call.arguments.get("limit", 5)), 1), 10)
        spec = _dimension_spec(dimension)
        rows = list(payload.get(spec["table"], []))
        if not rows:
            return _insufficient(call, payload, f"{dimension} serving mart 暂无数据")

        metric = str(call.arguments.get("metric") or spec["metric"])
        rows = sorted(
            rows,
            key=lambda row: _numeric(row.get(metric)),
            reverse=True,
        )[:limit]
        projected = [
            {
                key: row.get(key)
                for key in spec["fields"]
                if key in row
            }
            | {metric: row.get(metric)}
            for row in rows
        ]
        notes = [spec["note"]] if spec.get("note") else []
        return _ok(
            call,
            payload,
            evidence_key=f"{call.tool}:{dimension}:{metric}",
            title=f"{dimension} · {metric}",
            data={
                "dimension": dimension,
                "metric": metric,
                "rows": projected,
            },
            notes=notes,
        )

    def _detect_anomaly(
        self,
        call: ToolCall,
        payload: dict[str, Any],
    ) -> ToolResult:
        metric = str(call.arguments["metric"])
        threshold = float(call.arguments.get("z_threshold", 2.0))
        points = []
        for row in sorted(
            payload.get("daily", []),
            key=lambda item: str(item.get("dt", "")),
        ):
            value = _row_metric(metric, row)
            if value is not None:
                points.append((row.get("dt"), value))

        if len(points) < 5:
            return _insufficient(call, payload, "异常检测至少需要 5 个日级观测")

        values = [value for _, value in points]
        sigma = pstdev(values)
        if sigma == 0:
            anomalies: list[dict[str, Any]] = []
            latest_z = 0.0
        else:
            center = mean(values)
            scored = [
                (dt, value, (value - center) / sigma)
                for dt, value in points
            ]
            anomalies = [
                {
                    "dt": dt,
                    "value": round(value, 6),
                    "z_score": round(z_score, 4),
                }
                for dt, value, z_score in scored
                if abs(z_score) >= threshold
            ]
            latest_z = scored[-1][2]

        return _ok(
            call,
            payload,
            evidence_key=f"anomaly:{metric}",
            title=f"{METRIC_CATALOG[metric].label} 异常检测",
            data={
                "metric": metric,
                "method": "population_zscore",
                "threshold": threshold,
                "latest_z_score": round(latest_z, 4),
                "anomalies": anomalies,
                "sample_size": len(points),
            },
            notes=["该检测用于运营提示，不替代统计显著性或因果分析。"],
        )


def _contains(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.casefold() in text for keyword in keywords)


def _dimension_arguments(
    dimension: str,
    limit: int,
) -> dict[str, Any]:
    spec = _dimension_spec(dimension)
    return {
        "dimension": dimension,
        "metric": spec["metric"],
        "limit": limit,
    }


def _dimension_spec(dimension: str) -> dict[str, Any]:
    specs: dict[str, dict[str, Any]] = {
        "product": {
            "table": "product_topn",
            "metric": "sales_amount",
            "fields": (
                "product_id",
                "product_name",
                "sales_quantity",
                "buyer_count",
            ),
            "note": "商品数据来自 ADS Top-N serving mart，并非全量商品明细。",
        },
        "category": {
            "table": "category_topn",
            "metric": "sales_amount",
            "fields": (
                "category_id",
                "category_name",
                "sales_quantity",
                "buyer_count",
            ),
            "note": "品类数据来自 ADS Top-N serving mart。",
        },
        "shop": {
            "table": "shop_rank",
            "metric": "sales_amount",
            "fields": (
                "shop_id",
                "shop_name",
                "shop_type",
                "city",
                "buyer_count",
            ),
            "note": "店铺数据来自 ADS 排名 serving mart。",
        },
        "refund_reason": {
            "table": "refund_analysis",
            "metric": "refund_amount",
            "fields": (
                "refund_reason",
                "refund_status",
                "refund_count",
                "refund_order_count",
            ),
        },
        "user_segment": {
            "table": "rfm_segment",
            "metric": "monetary",
            "fields": ("user_segment", "user_count"),
        },
    }
    if dimension not in specs:
        raise ValueError(f"unsupported dimension: {dimension}")
    return specs[dimension]


def _aggregate_metric(
    metric: str,
    rows: list[dict[str, Any]],
) -> float | None:
    if not rows:
        return None
    if metric == "gmv":
        return sum(_numeric(row.get("gmv")) for row in rows)
    if metric == "pay_amount":
        return sum(_numeric(row.get("pay_amount")) for row in rows)
    if metric == "pay_conversion_rate":
        orders = sum(_numeric(row.get("order_count")) for row in rows)
        paid = sum(_numeric(row.get("pay_order_count")) for row in rows)
        return paid / orders if orders else None
    if metric == "avg_order_value":
        paid_orders = sum(_numeric(row.get("pay_order_count")) for row in rows)
        paid_amount = sum(_numeric(row.get("pay_amount")) for row in rows)
        return paid_amount / paid_orders if paid_orders else None
    if metric == "refund_rate":
        paid_amount = sum(_numeric(row.get("pay_amount")) for row in rows)
        refund_amount = sum(_numeric(row.get("refund_amount")) for row in rows)
        return refund_amount / paid_amount if paid_amount else None
    if metric == "repeat_purchase_rate":
        values = [_numeric_or_none(row.get(metric)) for row in rows]
        valid = [value for value in values if value is not None]
        return mean(valid) if valid else None
    return None


def _row_metric(
    metric: str,
    row: dict[str, Any],
) -> float | None:
    if metric in ("gmv", "pay_amount"):
        return _numeric_or_none(row.get(metric))
    return _aggregate_metric(metric, [row])


def _numeric(value: Any) -> float:
    parsed = _numeric_or_none(value)
    return parsed if parsed is not None else -math.inf


def _numeric_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _ok(
    call: ToolCall,
    payload: dict[str, Any],
    evidence_key: str,
    title: str,
    data: Any,
    notes: list[str] | None = None,
) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        evidence_key=evidence_key,
        tool=call.tool,
        title=title,
        status="ok",
        data=data,
        source=str(payload.get("_source", "metrics_snapshot")),
        notes=notes or [],
    )


def _insufficient(
    call: ToolCall,
    payload: dict[str, Any],
    note: str,
) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        evidence_key=f"insufficient:{call.call_id}",
        tool=call.tool,
        title=call.tool,
        status="insufficient_data",
        data={},
        source=str(payload.get("_source", "metrics_snapshot")),
        notes=[note],
    )


def _deduplicate_calls(calls: list[ToolCall]) -> list[ToolCall]:
    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    result: list[ToolCall] = []
    for call in calls:
        signature = (
            call.tool,
            tuple(
                sorted(
                    (key, str(value))
                    for key, value in call.arguments.items()
                )
            ),
        )
        if signature in seen:
            continue
        seen.add(signature)
        result.append(call)
    return result


def _intent(
    trend: bool,
    diagnostic: bool,
    ranking: bool,
    anomaly: bool,
    call_count: int,
) -> str:
    active = sum((trend, diagnostic, ranking, anomaly))
    if active > 1 or call_count > 4:
        return "mixed"
    if diagnostic:
        return "diagnostic"
    if ranking:
        return "ranking"
    if anomaly:
        return "anomaly_detection"
    if trend:
        return "trend_analysis"
    return "kpi_lookup"
