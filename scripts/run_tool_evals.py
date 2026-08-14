"""Offline quality evals for the bounded analytics planner.

Unlike the original recall-only gate, this evaluator penalizes over-planning as well as
missed calls. A planner that always calls every tool can therefore no longer score well.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent import QueryPlanner  # noqa: E402
from app.catalog import METRIC_CATALOG  # noqa: E402


SURFACES = ("tools", "metrics", "dimensions", "coverage_gaps")
METRIC_TOOLS = {"get_kpi", "compare_periods", "detect_anomaly"}


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _predicted_sets(plan) -> dict[str, set[str]]:
    tools = {call.tool for call in plan.calls}
    metrics = {
        str(call.arguments["metric"])
        for call in plan.calls
        if call.tool in METRIC_TOOLS and "metric" in call.arguments
    }
    dimensions = {
        str(call.arguments["dimension"])
        for call in plan.calls
        if "dimension" in call.arguments
    }
    return {
        "tools": tools,
        "metrics": metrics,
        "dimensions": dimensions,
        "coverage_gaps": set(plan.coverage_gaps),
    }


def _expected_sets(case: dict[str, Any]) -> dict[str, set[str]]:
    return {
        "tools": set(case.get("expected_tools", [])),
        "metrics": set(case.get("expected_metrics", [])),
        "dimensions": set(case.get("expected_dimensions", [])),
        "coverage_gaps": set(case.get("expected_coverage_gaps", [])),
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    planner = QueryPlanner()
    payload = {"kpis": {key: 1.0 for key in METRIC_CATALOG}}
    surface_counts = {name: {"tp": 0, "fp": 0, "fn": 0} for name in SURFACES}
    category_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "exact": 0})
    exact_count = 0
    details = []

    for case in cases:
        plan = planner.plan(case["question"], payload, top_k=5)
        predicted = _predicted_sets(plan)
        expected = _expected_sets(case)
        exact = all(predicted[name] == expected[name] for name in SURFACES)
        exact_count += int(exact)
        category = str(case.get("category") or "uncategorized")
        category_counts[category]["total"] += 1
        category_counts[category]["exact"] += int(exact)

        case_surfaces = {}
        for name in SURFACES:
            tp = len(predicted[name] & expected[name])
            fp = len(predicted[name] - expected[name])
            fn = len(expected[name] - predicted[name])
            surface_counts[name]["tp"] += tp
            surface_counts[name]["fp"] += fp
            surface_counts[name]["fn"] += fn
            case_surfaces[name] = {
                "expected": sorted(expected[name]),
                "predicted": sorted(predicted[name]),
                **_prf(tp, fp, fn),
            }

        details.append(
            {
                "id": case.get("id"),
                "category": category,
                "question": case["question"],
                "exact_match": exact,
                "planner_intent": plan.intent,
                "surfaces": case_surfaces,
                "notes": case.get("notes"),
            }
        )

    per_surface = {
        name: _prf(counts["tp"], counts["fp"], counts["fn"])
        for name, counts in surface_counts.items()
    }
    total_tp = sum(item["tp"] for item in surface_counts.values())
    total_fp = sum(item["fp"] for item in surface_counts.values())
    total_fn = sum(item["fn"] for item in surface_counts.values())
    micro = _prf(total_tp, total_fp, total_fn)
    exact_match_rate = exact_count / len(cases) if cases else 1.0

    categories = {
        name: {
            **counts,
            "exact_match_rate": round(counts["exact"] / counts["total"], 4)
            if counts["total"]
            else 1.0,
        }
        for name, counts in sorted(category_counts.items())
    }
    return {
        "cases": len(cases),
        # Backward-compatible field used by older reports.
        "routing_recall": micro["recall"],
        "routing_precision": micro["precision"],
        "routing_f1": micro["f1"],
        "exact_match_rate": round(exact_match_rate, 4),
        "micro": micro,
        "surfaces": per_surface,
        "categories": categories,
        "failures": [item for item in details if not item["exact_match"]],
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="evals/tool_routing_cases.json")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.95,
        help="Minimum micro F1 across tool/metric/dimension/coverage-gap decisions.",
    )
    parser.add_argument(
        "--exact-threshold",
        type=float,
        default=0.90,
        help="Minimum fraction of cases with an exact routing match.",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("tool-routing cases must be a JSON array")
    result = evaluate(cases)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")

    failures = []
    if result["routing_f1"] < args.threshold:
        failures.append(
            f"routing F1 {result['routing_f1']:.4f} < threshold {args.threshold:.4f}"
        )
    if result["exact_match_rate"] < args.exact_threshold:
        failures.append(
            f"exact match {result['exact_match_rate']:.4f} "
            f"< threshold {args.exact_threshold:.4f}"
        )
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()
