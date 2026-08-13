from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "retailpulse_http_requests_total",
    "HTTP requests served by RetailPulse.",
    ("method", "route", "status"),
)
HTTP_LATENCY = Histogram(
    "retailpulse_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ("method", "route"),
)
AI_REQUESTS = Counter(
    "retailpulse_ai_requests_total",
    "AI analysis requests by provider and outcome.",
    ("provider", "outcome"),
)
AI_CACHE_HITS = Counter(
    "retailpulse_ai_cache_hits_total",
    "AI response cache hits.",
)
AI_PROVIDER_FALLBACKS = Counter(
    "retailpulse_ai_provider_fallbacks_total",
    "External provider fallbacks.",
    ("provider",),
)
