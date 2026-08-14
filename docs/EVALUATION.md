# Analytics Planner Evaluation

RetailPulse intentionally uses a bounded deterministic planner for its stable retail analytics domain. The evaluation therefore measures the planner as a **routing policy**, not as an open-ended language model.

## Why recall-only was insufficient

The previous tool-routing gate only counted expected decisions that appeared in the plan. A planner could call unnecessary tools or dimensions and still receive a perfect recall score. That is especially dangerous in analytics systems because extra calls increase latency/cost and can silently substitute an unsupported dimension with a different one.

The current evaluator scores four independent surfaces:

- tool selection;
- KPI metric selection;
- supported dimension selection;
- explicit coverage-gap detection.

For each surface it reports TP / FP / FN, precision, recall and F1. It also reports micro-averaged routing precision/recall/F1 and whole-case exact-match rate.

## Evaluation set

`evals/tool_routing_cases.json` contains 50 curated cases spanning:

- KPI lookup;
- trend comparison;
- ranking / Top-N;
- diagnosis;
- anomaly detection;
- unsupported `campaign` / `region` coverage gaps;
- multi-dimension requests;
- mixed intents;
- Chinese and English phrasing.

The set intentionally includes hard cases that expose **over-planning**, not just missed tools. Examples include:

1. `退款率最高的退款原因 Top5` — `退款原因` is a dimension name, not automatically a causal-diagnosis request. Calling `compare_periods` solely because the substring `原因` appears is a false positive.
2. `GMV为什么变化？按活动分析` — `campaign` is unsupported. The system should report the coverage gap rather than silently substituting `category` as if it answered the requested dimension.

These cases make known limitations visible in the report instead of hiding them behind a recall-only score.

## Running

```bash
python scripts/run_tool_evals.py
```

Optional report artifact:

```bash
python scripts/run_tool_evals.py \
  --threshold 0.95 \
  --exact-threshold 0.90 \
  --report reports/tool_routing_eval.json
```

`--threshold` applies to micro F1. `--exact-threshold` applies to the fraction of cases where tools, metrics, dimensions and coverage gaps all match exactly.

## How to use the metrics

Do not put a routing number on a resume unless it comes from a saved report generated from the committed case set and planner version. The useful engineering workflow is:

1. add/modify a planner rule;
2. add the motivating case before or with the code change;
3. run the regression suite;
4. inspect false positives and false negatives by category;
5. promote the planner change only if the intended case improves without unacceptable regressions elsewhere.

If the domain grows beyond a maintainable deterministic policy, a structured LLM planner can be introduced behind the **same tool allowlist and argument validators**, first in shadow/offline evaluation. The current project deliberately does not call a keyword router “LLM reasoning.”
