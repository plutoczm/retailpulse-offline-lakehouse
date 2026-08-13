"""Generate a deterministic serving snapshot for the AI analytics agent demo."""

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

CHANNEL_SUMMARY = [
    {"channel": "organic", "order_count": 300, "order_user_count": 285, "gmv": 78000.0, "pay_order_count": 276, "pay_user_count": 262, "pay_amount": 70000.0, "pay_conversion_rate": 0.92, "avg_order_value": 253.6232, "refund_order_count": 12, "refund_amount": 1300.0, "refund_rate": 0.018571},
    {"channel": "paid_search", "order_count": 260, "order_user_count": 247, "gmv": 67000.0, "pay_order_count": 238, "pay_user_count": 226, "pay_amount": 60000.0, "pay_conversion_rate": 0.915385, "avg_order_value": 252.1008, "refund_order_count": 16, "refund_amount": 1800.0, "refund_rate": 0.03},
    {"channel": "social", "order_count": 240, "order_user_count": 228, "gmv": 61000.0, "pay_order_count": 216, "pay_user_count": 205, "pay_amount": 54000.0, "pay_conversion_rate": 0.9, "avg_order_value": 250.0, "refund_order_count": 15, "refund_amount": 1700.0, "refund_rate": 0.031481},
    {"channel": "app_store", "order_count": 190, "order_user_count": 182, "gmv": 48000.0, "pay_order_count": 174, "pay_user_count": 166, "pay_amount": 43000.0, "pay_conversion_rate": 0.915789, "avg_order_value": 247.1264, "refund_order_count": 9, "refund_amount": 1000.0, "refund_rate": 0.023256},
    {"channel": "affiliate", "order_count": 170, "order_user_count": 161, "gmv": 40000.0, "pay_order_count": 153, "pay_user_count": 146, "pay_amount": 35500.0, "pay_conversion_rate": 0.9, "avg_order_value": 232.0261, "refund_order_count": 10, "refund_amount": 1200.0, "refund_rate": 0.033803},
    {"channel": "offline_event", "order_count": 120, "order_user_count": 115, "gmv": 28000.0, "pay_order_count": 108, "pay_user_count": 103, "pay_amount": 25000.0, "pay_conversion_rate": 0.9, "avg_order_value": 231.4815, "refund_order_count": 6, "refund_amount": 700.0, "refund_rate": 0.028},
]

PRODUCT_TOPN = [
    {"product_id": "P1001", "product_name": "高蛋白早餐组合", "sales_amount": 42800.0, "sales_quantity": 318, "buyer_count": 286},
    {"product_id": "P1002", "product_name": "智能降噪耳机", "sales_amount": 39100.0, "sales_quantity": 142, "buyer_count": 135},
    {"product_id": "P1003", "product_name": "敏感肌修护套装", "sales_amount": 33600.0, "sales_quantity": 226, "buyer_count": 205},
    {"product_id": "P1004", "product_name": "轻量通勤双肩包", "sales_amount": 28700.0, "sales_quantity": 191, "buyer_count": 184},
    {"product_id": "P1005", "product_name": "厨房收纳组合", "sales_amount": 25100.0, "sales_quantity": 248, "buyer_count": 221},
]

CATEGORY_TOPN = [
    {"category_id": "C01", "category_name": "食品饮料", "sales_amount": 105000.0, "sales_quantity": 780, "buyer_count": 692},
    {"category_id": "C02", "category_name": "家居生活", "sales_amount": 82000.0, "sales_quantity": 604, "buyer_count": 533},
    {"category_id": "C03", "category_name": "数码家电", "sales_amount": 74000.0, "sales_quantity": 238, "buyer_count": 226},
    {"category_id": "C04", "category_name": "美妆个护", "sales_amount": 61000.0, "sales_quantity": 421, "buyer_count": 389},
]

SHOP_RANK = [
    {"shop_id": "S01", "shop_name": "华东旗舰店", "shop_type": "flagship", "city": "上海", "sales_amount": 96000.0, "buyer_count": 702},
    {"shop_id": "S02", "shop_name": "华南生活馆", "shop_type": "standard", "city": "深圳", "sales_amount": 78500.0, "buyer_count": 598},
    {"shop_id": "S03", "shop_name": "华北优选店", "shop_type": "standard", "city": "北京", "sales_amount": 64700.0, "buyer_count": 511},
]

REFUND_ANALYSIS = [
    {"refund_reason": "物流破损", "refund_status": "approved", "refund_amount": 2800.0, "refund_count": 18, "refund_order_count": 17},
    {"refund_reason": "质量问题", "refund_status": "approved", "refund_amount": 2400.0, "refund_count": 15, "refund_order_count": 15},
    {"refund_reason": "描述不符", "refund_status": "approved", "refund_amount": 1500.0, "refund_count": 11, "refund_order_count": 10},
    {"refund_reason": "其他", "refund_status": "approved", "refund_amount": 1000.0, "refund_count": 8, "refund_order_count": 8},
]

RFM_SEGMENT = [
    {"user_segment": "高价值用户", "user_count": 1120, "monetary": 801000.0},
    {"user_segment": "潜力用户", "user_count": 1840, "monetary": 451000.0},
    {"user_segment": "一般用户", "user_count": 2690, "monetary": 348000.0},
    {"user_segment": "流失风险用户", "user_count": 970, "monetary": 101500.0},
]

INVENTORY_TURNOVER = [
    {"product_id": "P1001", "shop_id": "S01", "sales_amount": 42800.0, "sales_quantity": 318, "ending_quantity": 122, "inventory_turnover_rate": 2.41},
    {"product_id": "P1005", "shop_id": "S02", "sales_amount": 25100.0, "sales_quantity": 248, "ending_quantity": 177, "inventory_turnover_rate": 1.66},
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
        "channel_summary": CHANNEL_SUMMARY,
        "product_topn": PRODUCT_TOPN,
        "category_topn": CATEGORY_TOPN,
        "shop_rank": SHOP_RANK,
        "refund_analysis": REFUND_ANALYSIS,
        "rfm_segment": RFM_SEGMENT,
        "inventory_turnover": INVENTORY_TURNOVER,
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
