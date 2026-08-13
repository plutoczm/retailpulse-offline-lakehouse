from app.observability import AI_PROVIDER_FALLBACKS
from app.provider_policy import breaker_from_env
from app.service_core import AnalystService as CoreAnalystService
from app.service_core import _validate_grounding


class AnalystService(CoreAnalystService):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.provider_breaker = breaker_from_env()

    def _generate_analysis(self, question, context):
        if not self.provider_breaker.allow():
            provider = self.fallback_provider
            analysis = provider.generate(question, context)
            _validate_grounding(analysis, context)
            AI_PROVIDER_FALLBACKS.labels(self.provider.name).inc()
            return analysis, provider, ["Primary AI circuit open; fallback used."]

        analysis, provider, warnings = super()._generate_analysis(question, context)
        if provider is self.provider:
            self.provider_breaker.success()
        else:
            self.provider_breaker.failure()
        return analysis, provider, warnings
