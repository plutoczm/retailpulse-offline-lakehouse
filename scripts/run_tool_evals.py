"""Offline routing evals for the controlled analytics-agent planner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent import QueryPlanner  # noqa: E402
from app.catalog import METRIC_CATALOG  # noqa: E402


def evaluate(cases: list[dict]) -> dict:
    planner = QueryPlanner()
    payload = {"kpis": {key: 1.0 for key in METRIC_CATALOG}}
    expected_count = 0
    hit_count = 0
    details = []

    for case in cases:
        plan = planner.plan(case["question"], payload, top_k=5)
        predicted_tools = {call.tool for call in plan.calls}
        predicted_dimensions = {
            str(call.arguments["dimension"])
            for call in plan.calls
            if "dimension" in call.arguments
        }
        predicted_gaps = set(plan.coverage_gaps)

        expected_tools = set(case.get("expected_tools", []))
        expected_dimensions = set(case.get("expected_dimensions", []))
        expected_gaps = set(case.get("expected_coverage_gaps", []))

        expected_count += (
            len(expected_tools)
            + len(expected_dimensions)
            + len(expected_gaps)
        )
        hit_count += (
            len(expected_tools & predicted_tools)
            + len(expected_dimensions & predicted_dimensions)
            + len(expected_gaps & predicted_gaps)
        )
        details.append(
            {
                "question": case["question"],
                "tools": sorted(predicted_tools),
                "dimensions": sorted(predicted_dimensions),
                "coverage_gaps": sorted(predicted_gaps),
            }
        )

    recall = hit_count / expected_count if expected_count else 1.0
    return {
        "cases": len(cases),
        "routing_recall": round(recall, 4),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="evals/tool_routing_cases.json")
    parser.add_argument("--threshold", type=float, default=0.95)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    result = evaluate(cases)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["routing_recall"] < args.threshold:
        raise SystemExit(
            f"tool routing recall {result['routing_recall']:.4f} "
            f"< threshold {args.threshold:.4f}"
        )


if __name__ == "__main__":
    main()
