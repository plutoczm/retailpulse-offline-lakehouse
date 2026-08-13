from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Sample:
    latency_ms: float
    ok: bool
    status_code: int
    error: str | None = None


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def request_once(url: str, question: str, api_key: str | None, timeout: float) -> Sample:
    payload = json.dumps({"question": question, "top_k": 4}, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json", "X-Request-ID": "benchmark"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
            ok = (
                response.status == 200
                and bool(body.get("data_version"))
                and isinstance(body.get("plan", {}).get("calls"), list)
                and isinstance(body.get("tool_results"), list)
                and bool(body.get("analysis", {}).get("summary"))
            )
            return Sample(
                latency_ms=(time.perf_counter() - started) * 1000,
                ok=ok,
                status_code=response.status,
                error=None if ok else "response contract failed",
            )
    except urllib.error.HTTPError as exc:
        return Sample(
            latency_ms=(time.perf_counter() - started) * 1000,
            ok=False,
            status_code=exc.code,
            error=f"HTTPError:{exc.code}",
        )
    except Exception as exc:
        return Sample(
            latency_ms=(time.perf_counter() - started) * 1000,
            ok=False,
            status_code=0,
            error=type(exc).__name__,
        )


def run_benchmark(
    *,
    url: str,
    question: str,
    requests: int,
    concurrency: int,
    warmup: int,
    timeout: float,
    api_key: str | None,
) -> dict[str, Any]:
    for _ in range(warmup):
        request_once(url, question, api_key, timeout)

    started = time.perf_counter()
    samples: list[Sample] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(request_once, url, question, api_key, timeout)
            for _ in range(requests)
        ]
        for future in as_completed(futures):
            samples.append(future.result())
    wall_seconds = time.perf_counter() - started

    latencies = [sample.latency_ms for sample in samples]
    successes = sum(sample.ok for sample in samples)
    errors = len(samples) - successes
    return {
        "url": url,
        "question": question,
        "requests": len(samples),
        "concurrency": concurrency,
        "warmup": warmup,
        "successes": successes,
        "errors": errors,
        "error_rate": errors / len(samples) if samples else 1.0,
        "wall_seconds": round(wall_seconds, 6),
        "throughput_rps": round(len(samples) / wall_seconds, 4) if wall_seconds else None,
        "latency_ms": {
            "min": round(min(latencies), 3) if latencies else None,
            "mean": round(statistics.fmean(latencies), 3) if latencies else None,
            "p50": round(percentile(latencies, 0.50), 3) if latencies else None,
            "p95": round(percentile(latencies, 0.95), 3) if latencies else None,
            "p99": round(percentile(latencies, 0.99), 3) if latencies else None,
            "max": round(max(latencies), 3) if latencies else None,
        },
        "failure_samples": [asdict(sample) for sample in samples if not sample.ok][:10],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the bounded RetailPulse ask API")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/v1/ask")
    parser.add_argument("--question", default="GMV 最近表现如何？")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--api-key")
    parser.add_argument("--p95-budget-ms", type=float, default=1500.0)
    parser.add_argument("--error-rate-budget", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=Path("reports/performance.json"))
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1 or args.warmup < 0:
        parser.error("requests/concurrency must be positive and warmup must be non-negative")

    report = run_benchmark(
        url=args.url,
        question=args.question,
        requests=args.requests,
        concurrency=min(args.concurrency, args.requests),
        warmup=args.warmup,
        timeout=args.timeout,
        api_key=args.api_key,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    p95 = report["latency_ms"]["p95"]
    if report["error_rate"] > args.error_rate_budget:
        print("performance gate failed: error-rate budget exceeded")
        return 2
    if p95 is None or p95 > args.p95_budget_ms:
        print("performance gate failed: p95 latency budget exceeded")
        return 3
    print("performance gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
