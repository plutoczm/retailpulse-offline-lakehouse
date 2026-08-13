from __future__ import annotations

from typing import Any

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


class ErrorDetail(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    request_id: str
    error: ErrorDetail
