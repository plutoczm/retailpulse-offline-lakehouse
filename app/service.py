from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from app.agent import PLANNER_VERSION, QueryPlanner, RetailToolbox
from app.analytics import MetricsRepository
from app.cache import ResponseCache
from app.llm import DeterministicProvider, LLMProvider
from app.models import AnalysisContent
from app.observability import (
    AGENT_PLANS,
    AGENT_TOOL_CALLS,
    AI_CACHE_HITS,
    AI_PROVIDER_FALLBACKS,
    AI_REQUESTS,
)

logger = logging.getLogger("retailpulse.ai")


class GroundingValidationError(RuntimeError):
    """Raised when a model references evidence outside executed tool results."""


class AnalystService:
    def __init__(
        self,
        repository: MetricsRepository,
        provider: LLMProvider,
        fallback_provider: LLMProvider | None = None,
        cache: ResponseCache[AnalysisContent] | None = None,
        planner: QueryPlanner | None = None,
        toolbox: RetailToolbox | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.fallback_provider = fallback_provider or DeterministicProvider()
        self.cache = cache or ResponseCache(ttl_seconds=0)
        self.planner = planner or QueryPlanner()
        self.toolbox = toolbox or RetailToolbox()

    def ask(
        self,
        question: str,
        top_k: int = 4,
    ) -> dict[str, Any]:
        started = perf_counter()
        payload = self.repository.load()
        data_version = payload["_data_version"]

        plan = self.planner.plan(
            question,
            payload,
            top_k=top_k,
        )
        AGENT_PLANS.labels(plan.intent).inc()

        tool_results = self.toolbox.execute(plan, payload)
        for result in tool_results:
            AGENT_TOOL_CALLS.labels(result.tool, result.status).inc()

        metric_keys = _planned_metric_keys(plan.model_dump())
        evidence = self.repository.build_evidence(metric_keys, payload)
        trusted_context = [
            result.model_dump()
            for result in tool_results
            if result.status == "ok"
        ]

        cache_key = (
            data_version,
            PLANNER_VERSION,
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
            analysis, provider, provider_warnings = self._generate_analysis(
                question,
                trusted_context,
            )
            warnings.extend(provider_warnings)
            if provider is self.provider:
                self.cache.set(cache_key, analysis)

        if plan.coverage_gaps:
            gap_text = ", ".join(plan.coverage_gaps)
            analysis = _with_caveat(
                analysis,
                f"Requested dimensions are not available in the serving mart: {gap_text}.",
            )
            warnings.append(f"Unsupported serving dimensions: {gap_text}.")

        insufficient = [
            result
            for result in tool_results
            if result.status != "ok"
        ]
        if insufficient:
            warnings.append(
                f"{len(insufficient)} planned tool call(s) had insufficient serving data."
            )

        return {
            "answer": analysis.summary,
            "analysis": analysis.model_dump(),
            "evidence": evidence,
            "plan": plan.model_dump(),
            "tool_results": [result.model_dump() for result in tool_results],
            "provider": provider.name,
            "model": provider.model,
            "warnings": warnings,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "cache_hit": cache_hit,
            "data_version": data_version,
        }

    def _generate_analysis(
        self,
        question: str,
        trusted_context: list[dict[str, Any]],
    ) -> tuple[AnalysisContent, LLMProvider, list[str]]:
        provider = self.provider
        try:
            analysis = provider.generate(question, trusted_context)
            _validate_grounding(analysis, trusted_context)
            AI_REQUESTS.labels(provider.name, "success").inc()
            return analysis, provider, []
        except Exception as exc:
            logger.warning(
                "llm_provider_failed provider=%s error=%s",
                provider.name,
                type(exc).__name__,
            )
            AI_REQUESTS.labels(provider.name, "failure").inc()
            AI_PROVIDER_FALLBACKS.labels(provider.name).inc()

        provider = self.fallback_provider
        analysis = provider.generate(question, trusted_context)
        _validate_grounding(analysis, trusted_context)
        return (
            analysis,
            provider,
            [
                "Primary AI provider unavailable or violated grounding contract; "
                "deterministic fallback used."
            ],
        )


def _planned_metric_keys(plan: dict[str, Any]) -> list[str]:
    metrics: list[str] = []
    for call in plan["calls"]:
        if call["tool"] != "get_kpi":
            continue
        metric = str(call["arguments"].get("metric", ""))
        if metric and metric not in metrics:
            metrics.append(metric)
    return metrics


def _validate_grounding(
    analysis: AnalysisContent,
    context: list[dict[str, Any]],
) -> None:
    allowed = {item["evidence_key"] for item in context}
    if context and not analysis.observations:
        raise GroundingValidationError("analysis has no observations")

    for observation in analysis.observations:
        references = set(observation.evidence_keys)
        if not references or not references.issubset(allowed):
            raise GroundingValidationError(
                "observation references evidence outside trusted tool results"
            )


def _with_caveat(
    analysis: AnalysisContent,
    caveat: str,
) -> AnalysisContent:
    if caveat in analysis.caveats:
        return analysis
    return analysis.model_copy(
        update={"caveats": [*analysis.caveats, caveat]}
    )
