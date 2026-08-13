from __future__ import annotations

import json
import logging
import secrets
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.analytics import MetricsRepository, MetricsUnavailableError
from app.cache import ResponseCache
from app.config import load_settings
from app.llm import DeterministicProvider, OpenAIProvider
from app.models import AnalysisContent, AskRequest, AskResponse, MetricsResponse
from app.observability import HTTP_LATENCY, HTTP_REQUESTS
from app.rate_limit import SlidingWindowRateLimiter
from app.service import AnalystService

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("retailpulse.api")
settings = load_settings()

repository = MetricsRepository(
    primary_path=settings.metrics_path,
    fallback_path=settings.fallback_metrics_path,
    allow_fallback=settings.allow_demo_fallback,
)

if settings.llm_enabled:
    provider = OpenAIProvider(
        api_key=settings.openai_api_key or "",
        model=settings.openai_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )
else:
    provider = DeterministicProvider()

cache = ResponseCache[AnalysisContent](
    ttl_seconds=settings.response_cache_ttl_seconds,
    max_entries=settings.response_cache_max_entries,
)
service = AnalystService(repository=repository, provider=provider, cache=cache)
limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)

app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description="Grounded retail analytics copilot backed by trusted lakehouse metrics.",
)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "request_id": getattr(request.state, "request_id", "unknown"),
            "error": {"code": code, "message": message},
        },
        headers=headers,
    )


@app.middleware("http")
async def request_guardrails(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.state.request_id = request_id
    started = perf_counter()

    if request.url.path == "/api/v1/ask":
        if settings.api_access_key:
            supplied = request.headers.get("x-api-key", "")
            if not secrets.compare_digest(supplied, settings.api_access_key):
                return _error_response(
                    request,
                    401,
                    "unauthorized",
                    "A valid X-API-Key is required.",
                )

        client_key = request.client.host if request.client else "unknown"
        decision = limiter.check(client_key)
        if not decision.allowed:
            return _error_response(
                request,
                429,
                "rate_limited",
                "Too many AI requests.",
                {"Retry-After": str(decision.retry_after_seconds)},
            )

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            json.dumps(
                {
                    "event": "request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
                ensure_ascii=False,
            )
        )
        raise

    latency_seconds = perf_counter() - started
    route = getattr(request.scope.get("route"), "path", request.url.path)
    HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    HTTP_LATENCY.labels(request.method, route).observe(latency_seconds)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status_code": response.status_code,
                "latency_ms": round(latency_seconds * 1000, 2),
            },
            ensure_ascii=False,
        )
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return _error_response(
        request,
        422,
        "validation_error",
        "Request payload failed validation.",
    )


@app.exception_handler(MetricsUnavailableError)
async def metrics_error(request: Request, exc: MetricsUnavailableError):
    return _error_response(
        request,
        503,
        "metrics_unavailable",
        "Trusted metrics are unavailable.",
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        metadata = repository.metadata()
    except MetricsUnavailableError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "metrics_unavailable"},
        )

    age_seconds = metadata.get("age_seconds")
    if (
        settings.metrics_max_age_seconds
        and age_seconds is not None
        and age_seconds > settings.metrics_max_age_seconds
    ):
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "metrics_stale",
                "data_version": metadata["data_version"],
            },
        )

    return {
        "status": "ready",
        "environment": settings.environment,
        "provider": provider.name,
        "model": provider.model,
        "source_kind": metadata["source_kind"],
        "data_version": metadata["data_version"],
        "age_seconds": age_seconds,
    }


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/metrics", response_model=MetricsResponse)
def metrics() -> dict:
    return repository.public_snapshot()


@app.post(
    "/api/v1/ask",
    response_model=AskResponse,
    responses={
        401: {"description": "Invalid API key"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Trusted metrics unavailable"},
    },
)
def ask(body: AskRequest, request: Request) -> dict:
    result = service.ask(body.question, top_k=body.top_k)
    result["request_id"] = request.state.request_id
    return result


dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
if dashboard_dir.exists():
    app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
