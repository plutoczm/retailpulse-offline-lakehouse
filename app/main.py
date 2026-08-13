from __future__ import annotations

import json
import logging
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.analytics import MetricsRepository, MetricsUnavailableError
from app.config import load_settings
from app.llm import DeterministicProvider, OpenAIProvider
from app.models import AskRequest, AskResponse, MetricsResponse
from app.service import AnalystService


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("retailpulse.api")
settings = load_settings()

repository = MetricsRepository(
    primary_path=settings.metrics_path,
    fallback_path=settings.fallback_metrics_path,
)

if settings.llm_enabled:
    provider = OpenAIProvider(
        api_key=settings.openai_api_key or "",
        model=settings.openai_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )
else:
    provider = DeterministicProvider()

service = AnalystService(repository=repository, provider=provider)

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Grounded retail analytics copilot backed by trusted lakehouse metrics.",
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.state.request_id = request_id
    started = perf_counter()
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

    latency_ms = round((perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        json.dumps(
            {
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
            ensure_ascii=False,
        )
    )
    return response


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> JSONResponse | dict[str, str]:
    try:
        repository.load()
    except MetricsUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": str(exc)},
        )
    return {
        "status": "ready",
        "provider": provider.name,
        "model": provider.model,
    }


@app.get("/api/v1/metrics", response_model=MetricsResponse)
def metrics() -> dict:
    return repository.public_snapshot()


@app.post("/api/v1/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request) -> dict:
    result = service.ask(body.question, top_k=body.top_k)
    result["request_id"] = request.state.request_id
    return result


dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
if dashboard_dir.exists():
    app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
