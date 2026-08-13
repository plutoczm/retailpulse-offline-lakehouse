# RetailPulse AI Analyst Operations Runbook

This document describes how the online AI service is expected to behave outside a notebook or local demo.

## Runtime contract

The online path is intentionally small:

`metrics snapshot -> deterministic metric retrieval -> grounded structured analysis -> FastAPI`

The Spark lakehouse remains an offline data plane. The API image does not install Java or PySpark.

## Environments

- `development`: demo fallback is allowed by default and metrics freshness is not enforced.
- `test`: deterministic provider and fixture/demo metrics are expected.
- `production`: demo fallback is disabled by default and metrics older than 24 hours make `/readyz` fail unless the threshold is explicitly changed.

Use `RETAILPULSE_API_KEY` to protect `/api/v1/ask` in non-public deployments. Clients send it as `X-API-Key`.

## Health and readiness

- `/healthz` means the process is alive.
- `/readyz` validates that trusted metrics are loadable and, when configured, fresh enough to answer business questions.
- `/metrics` exposes Prometheus counters and latency histograms.

Readiness returns the data version and source kind so operators can tell whether the service is answering from the lakehouse export or demo data.

## Grounding contract

LLM output is parsed into a strict structure: summary, observations, actions, and caveats. Every observation must reference metric keys that were actually included in the trusted evidence. If an external provider returns invalid JSON, references unknown evidence, or fails, the request degrades to the deterministic provider and records a fallback metric.

## Cost and abuse controls

The service includes a short TTL/LRU response cache. Cache keys include the metrics content hash, so a new metrics export automatically invalidates old answers.

A per-process sliding-window limiter protects the expensive AI endpoint. This is deliberately dependency-free for a single-instance portfolio deployment. For multiple replicas, replace the in-process limiter/cache with a shared Redis-backed implementation rather than pretending local state is globally consistent.

## Prometheus metrics

Important series include:

- `retailpulse_http_requests_total`
- `retailpulse_http_request_duration_seconds`
- `retailpulse_ai_requests_total`
- `retailpulse_ai_cache_hits_total`
- `retailpulse_ai_provider_fallbacks_total`

A practical first SLO for a small deployment is 99.5% successful non-4xx requests and p95 API latency under 2 seconds in deterministic mode. External-model latency should be tracked separately from the API process latency before setting a production LLM SLO.

## Container deployment

The Docker image runs as a non-root user and has an image-level health check. CI builds the exact image and sends a real HTTP request to `/api/v1/ask`, so dependency or packaging mistakes fail before merge.

For production, mount or generate `dashboard/data/dashboard.json`, set `RETAILPULSE_ENV=production`, configure `RETAILPULSE_API_KEY`, and provide `OPENAI_API_KEY` only when external model inference is desired.

## Failure modes

- Metrics missing: readiness and business endpoints fail closed instead of silently using invented values.
- Metrics stale: production readiness can fail based on `RETAILPULSE_METRICS_MAX_AGE_SECONDS`.
- LLM timeout/provider error: deterministic grounded fallback is used.
- Invalid/ungrounded model output: grounding validation rejects it and uses fallback.
- Repeated question on unchanged data: versioned cache can serve it without another model call.
- Request burst: the AI endpoint returns HTTP 429 with `Retry-After`.
