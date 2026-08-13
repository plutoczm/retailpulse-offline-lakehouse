from typing import Any

from app.observability import AI_PROVIDER_FALLBACKS
from app.provider_circuit import CircuitBreaker
from app.service_core import AnalystService as CoreAnalystService
from app.service_core import _validate_grounding


class AnalystService(CoreAnalystService):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.provider_breaker = CircuitBreaker()

    def _generate_analysis(self, question: str, context: list[dict[str, Any]]):
        if not self.provider_breaker.allow():
            provider = self.fallback_provider
            analysis = provider.generate(question, context)
            _validate_grounding(analysis, context)
            AI_PROVIDER_FALLBACKS.labels(self.provider.name).inc()
            warning = "Primary AI circuit open; deterministic fallback used."
            return analysis, provider, [warning]

        analysis, provider, warnings = super()._generate_analysis(question, context)
        if provider is self.provider:
            self.provider_breaker.success()
        else:
            self.provider_breaker.failure()
        return analysis, provider, warnings
