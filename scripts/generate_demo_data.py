"""Generate a small deterministic metrics payload for the AI application demo."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DAILY = [
    {"dt": "2025-01-01", "order_count": 1000, "pay_order_count": 860, "gmv": 245000.0, "pay_amount": 207000.0, "refund_amount": 6200.0},
    {"dt": "2025-01-02", "order_count": 1040, "pay_order_count": 900, "gmv": 252000.0, "pay_amount": 216500.0, "refund_amount": 6100.0},
    {"dt": "2025-01-03", "order_count": 1090, "pay_order_count": 960, "gmv": 268000.0, "pay_amount": 232000.0, "refund_amount": 6500.0},
    {"dt": "2025-01-04", "order_count": 1120, "pay_order_count": 985, "gmv": 276500.0, "pay_amount": 238500.0, "refund_amount": 6900.0},
    {"dt": "2025-01-05", "order_count": 1180, "pay_order_count": 1050, "gmv": 291000.0, "pay_amount": 254000.0, "refund_amount": 7100.0},
    {"dt": "2025-01-06", "order_count": 1210, "pay_order_count": 1088, "gmv": 303000.0, "pay_amount": 266000.0, "refund_amount": 7400.0},
    {"dt": "2025-01-07", "order_count": 1280, "pay_order_count": 1165, "gmv": 322000.0, "pay_amount": 287500.0, "refund_amount": 7700.0},
]


def build_payload() -> dict:
    order_count = sum(row["order_count"] for row in DAILY)
    pay_order_count = sum(row["pay_order_count"] for row in DAILY)
    gmv = sum(row["gmv"] for row in DAILY)
    pay_amount = sum(row["pay_amount"] for row in DAILY)
    refund_amount = sum(row["refund_amount"] for row in DAILY)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "latest_dt": DAILY[-1]["dt"],
        "kpis": {
            "gmv": round(gmv, 2),
            "pay_amount": round(pay_amount, 2),
            "pay_conversion_rate": round(pay_order_count / order_count, 4),
            "avg_order_value": round(pay_amount / pay_order_count, 2),
            "repeat_purchase_rate": 0.184,
            "refund_rate": round(refund_amount / pay_amount, 4),
        },
        "daily": DAILY,
    }


def main() -> None:
    output = Path("dashboard/data/demo.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"generated {output}")


if __name__ == "__main__":
    main()
