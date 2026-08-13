from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from app.analytics import MetricsRepository
from app.catalog import select_metric_keys
from app.llm import DeterministicProvider, LLMProvider

logger = logging.getLogger("retailpulse.ai")


class AnalystService:
    def __init__(
        self,
        repository: MetricsRepository,
        provider: LLMProvider,
        fallback_provider: LLMProvider | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.fallback_provider = fallback_provider or DeterministicProvider()

    def ask(self, question: str, top_k: int = 4) -> dict[str, Any]:
        started = perf_counter()
        payload = self.repository.load()
        metric_keys = select_metric_keys(
            question,
            set(payload["kpis"]),
            max_items=max(1, min(top_k, 6)),
        )
        evidence = self.repository.build_evidence(metric_keys, payload)

        provider = self.provider
        warnings: list[str] = []
        try:
            answer = provider.generate(question, evidence)
        except Exception as exc:  # external provider failures should degrade gracefully
            logger.warning("llm_provider_failed provider=%s error=%s", provider.name, type(exc).__name__)
            provider = self.fallback_provider
            answer = provider.generate(question, evidence)
            warnings.append("LLM provider unavailable; deterministic fallback used.")

        return {
            "answer": answer,
            "evidence": evidence,
            "provider": provider.name,
            "model": provider.model,
            "warnings": warnings,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }
