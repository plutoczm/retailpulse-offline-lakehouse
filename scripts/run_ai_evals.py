"""Offline retrieval evals for the AI analyst grounding layer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalog import METRIC_CATALOG, select_metric_keys  # noqa: E402


def evaluate(cases: list[dict], top_k: int) -> dict:
    total_expected = 0
    total_hit = 0
    details = []

    for case in cases:
        expected = set(case["expected_metrics"])
        predicted = set(
            select_metric_keys(
                case["question"],
                set(METRIC_CATALOG),
                max_items=top_k,
            )
        )
        hits = expected & predicted
        total_expected += len(expected)
        total_hit += len(hits)
        details.append(
            {
                "question": case["question"],
                "expected": sorted(expected),
                "predicted": sorted(predicted),
                "hits": sorted(hits),
            }
        )

    recall = total_hit / total_expected if total_expected else 1.0
    return {
        "cases": len(cases),
        "recall": round(recall, 4),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="evals/retrieval_cases.json")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.95)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    result = evaluate(cases, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["recall"] < args.threshold:
        raise SystemExit(
            f"retrieval recall {result['recall']:.4f} < threshold {args.threshold:.4f}"
        )


if __name__ == "__main__":
    main()
