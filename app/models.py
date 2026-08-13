from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AskRequest(StrictModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=6)


class EvidenceItem(StrictModel):
    metric: str
    label: str
    definition: str
    value: Any
    unit: str
    source: str
    daily_trend: dict[str, Any] | None = None


ToolName = Literal[
    "get_kpi",
    "compare_periods",
    "breakdown_by_dimension",
    "get_topn",
    "detect_anomaly",
]


class ToolCall(StrictModel):
    call_id: str
    tool: ToolName
    arguments: dict[str, Any]
    reason: str


class QueryPlan(StrictModel):
    planner_version: str
    intent: Literal[
        "kpi_lookup",
        "trend_analysis",
        "diagnostic",
        "ranking",
        "anomaly_detection",
        "mixed",
    ]
    calls: list[ToolCall]
    coverage_gaps: list[str]


class ToolResult(StrictModel):
    call_id: str
    evidence_key: str
    tool: ToolName
    title: str
    status: Literal["ok", "insufficient_data"]
    data: Any
    source: str
    notes: list[str] = Field(default_factory=list)


class AnalysisObservation(StrictModel):
    title: str
    detail: str
    evidence_keys: list[str]


class AnalysisContent(StrictModel):
    summary: str
    observations: list[AnalysisObservation]
    actions: list[str]
    caveats: list[str]


class AskResponse(StrictModel):
    request_id: str
    answer: str
    analysis: AnalysisContent
    evidence: list[EvidenceItem]
    plan: QueryPlan
    tool_results: list[ToolResult]
    provider: str
    model: str
    warnings: list[str]
    latency_ms: float
    cache_hit: bool
    data_version: str


class MetricsResponse(StrictModel):
    source: str
    source_kind: str
    data_version: str
    generated_at: str | None = None
    latest_dt: str | None = None
    age_seconds: float | None = None
    kpis: dict[str, Any]


class CapabilitiesResponse(StrictModel):
    planner_version: str
    tools: list[str]
    supported_dimensions: list[str]
    known_coverage_gaps: list[str]


class ErrorDetail(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    request_id: str
    error: ErrorDetail
