from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=6)


class EvidenceItem(BaseModel):
    metric: str
    label: str
    definition: str
    value: Any
    unit: str
    source: str
    daily_trend: dict[str, Any] | None = None


class AskResponse(BaseModel):
    request_id: str
    answer: str
    evidence: list[EvidenceItem]
    provider: str
    model: str
    warnings: list[str]
    latency_ms: float


class MetricsResponse(BaseModel):
    source: str
    generated_at: str | None = None
    latest_dt: str | None = None
    kpis: dict[str, Any]
