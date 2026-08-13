from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from app.analytics import MetricsRepository
from app.cache import ResponseCache
from app.catalog import select_metric_keys
from app.llm import DeterministicProvider, LLMProvider
from app.models import AnalysisContent
from app.observability import AI_CACHE_HITS, AI_PROVIDER_FALLBACKS, AI_REQUESTS

logger = logging.getLogger("retailpulse.ai")


class GroundingValidationError(RuntimeError):
    """Raised when a model response references evidence it was not given."""


class AnalystService:
    def __init__(
        self,
        repository: MetricsRepository,
        provider: LLMProvider,
        fallback_provider: LLMProvider | None = None,
        cache: ResponseCache[AnalysisContent] | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.fallback_provider = fallback_provider or DeterministicProvider()
        self.cache = cache or ResponseCache(ttl_seconds=0)

    def ask(self, question: str, top_k: int = 4) -> dict[str, Any]:
        started = perf_counter()
        payload = self.repository.load()
        data_version = payload["_data_version"]
        metric_keys = select_metric_keys(
            question,
            set(payload["kpis"]),
            max_items=max(1, min(top_k, 6)),
        )
        evidence = self.repository.build_evidence(metric_keys, payload)
        cache_key = (
            data_version,
            question.strip().casefold(),
            top_k,
            self.provider.name,
            self.provider.model,
        )

        analysis = self.cache.get(cache_key)
        warnings: list[str] = []
        provider = self.provider
        cache_hit = analysis is not None

        if analysis is not None:
            AI_CACHE_HITS.inc()
            AI_REQUESTS.labels(provider.name, "cache_hit").inc()
        else:
            try:
                analysis = provider.generate(question, evidence)
                _validate_grounding(analysis, evidence)
                self.cache.set(cache_key, analysis)
                AI_REQUESTS.labels(provider.name, "success").inc()
            except Exception as exc:
                logger.warning(
                    "llm_provider_failed provider=%s error=%s",
                    provider.name,
                    type(exc).__name__,
                )
                AI_REQUESTS.labels(provider.name, "failure").inc()
                AI_PROVIDER_FALLBACKS.labels(provider.name).inc()
                provider = self.fallback_provider
                analysis = provider.generate(question, evidence)
                _validate_grounding(analysis, evidence)
                warnings.append(
                    "Primary AI provider unavailable or violated grounding contract; "
                    "deterministic fallback used."
                )

        return {
            "answer": analysis.summary,
            "analysis": analysis.model_dump(),
            "evidence": evidence,
            "provider": provider.name,
            "model": provider.model,
            "warnings": warnings,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "cache_hit": cache_hit,
            "data_version": data_version,
        }


def _validate_grounding(
    analysis: AnalysisContent,
    evidence: list[dict[str, Any]],
) -> None:
    allowed = {item["metric"] for item in evidence}
    if evidence and not analysis.observations:
        raise GroundingValidationError("analysis has no observations")

    for observation in analysis.observations:
        references = set(observation.evidence_keys)
        if not references or not references.issubset(allowed):
            raise GroundingValidationError(
                "observation references evidence outside the trusted context"
            )
