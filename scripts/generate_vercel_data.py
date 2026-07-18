"""Generate dashboard.json for Vercel deployment of RetailPulse.
This script creates sample e-commerce analytics data matching the dashboard's expected format.
"""
import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

random.seed(2025)


def daily_rows(start: str, days: int) -> list[dict]:
    """Generate daily transaction metrics."""
    rows = []
    d = date.fromisoformat(start)
    for i in range(days):
        dt = d.isoformat()
        order_count = random.randint(1800, 3200) + i * random.randint(5, 30)
        pay_count = int(order_count * random.uniform(0.82, 0.94))
        gmv = order_count * random.uniform(180, 450)
        pay_amount = pay_count * random.uniform(150, 380)
        rows.append({
            "dt": dt,
            "order_count": order_count,
            "pay_order_count": pay_count,
            "order_amount": round(gmv, 2),
            "pay_amount": round(pay_amount, 2),
            "gmv": round(gmv, 2),
            "order_user_count": int(pay_count * random.uniform(0.6, 0.75)),
            "pay_user_count": int(pay_count * random.uniform(0.55, 0.7)),
            "refund_order_count": int(pay_count * random.uniform(0.03, 0.08)),
            "refund_amount": round(pay_amount * random.uniform(0.02, 0.06), 2),
        })
        d += timedelta(days=1)
    return rows


def synerise_daily(start: str, days: int) -> list[dict]:
    """Generate daily user behavior metrics (Synerise-style)."""
    rows = []
    d = date.fromisoformat(start)
    base_events = 500_000
    for i in range(days):
        dt = d.isoformat()
        event_count = int(base_events + random.randint(-20000, 80000) + i * random.randint(8000, 25000))
        view = int(event_count * random.uniform(0.38, 0.48))
        search = int(event_count * random.uniform(0.08, 0.15))
        cart = int(event_count * random.uniform(0.055, 0.10))
        pay = int(event_count * random.uniform(0.03, 0.06))
        active = int(event_count * random.uniform(0.18, 0.30))
        view_to_pay = pay / max(view, 1)
        cart_to_pay = pay / max(cart, 1)
        rows.append({
            "dt": dt,
            "event_count": event_count,
            "active_user_count": active,
            "view_event_count": view,
            "search_event_count": search,
            "cart_event_count": cart,
            "pay_event_count": pay,
            "view_to_pay_rate": round(view_to_pay, 6),
            "cart_to_pay_rate": round(cart_to_pay, 6),
        })
        d += timedelta(days=1)
    return rows


def synerise_event_types(dates: list[str]) -> list[dict]:
    """Generate event-type heatmap data."""
    event_types = ["view", "search", "cart", "remove_cart", "pay"]
    rows = []
    for dt in dates:
        for etype in event_types:
            count = random.randint(800, 600000)
            rows.append({"dt": dt, "event_type": etype, "event_count": count})
    return rows


def product_topn(dates: list[str], topn: int = 12) -> list[dict]:
    """Generate product ranking data."""
    rows = []
    skus = [f"sku-{1000 + i}" for i in range(40)]
    for dt in dates:
        random.shuffle(skus)
        for sku in skus[:topn]:
            rows.append({
                "dt": dt,
                "sku": sku,
                "pay_event_count": random.randint(120, 4800),
                "active_user_count": random.randint(60, 2200),
            })
    return rows


def asset_table() -> list[dict]:
    return [
        {"table": "ods_synerise_behavior", "rows": 225_224_262, "size_mb": 1824.5},
        {"table": "dwd_synerise_user_behavior_detail", "rows": 225_224_262, "size_mb": 2106.8},
        {"table": "dws_synerise_daily_behavior", "rows": 7_280_000, "size_mb": 98.3},
        {"table": "ads_synerise_category_topn", "rows": 1_820_000, "size_mb": 42.7},
        {"table": "dwd_orders", "rows": 600_000, "size_mb": 32.6},
        {"table": "dwd_payments", "rows": 260_000, "size_mb": 18.4},
        {"table": "dws_shop_daily", "rows": 185_000, "size_mb": 28.1},
        {"table": "ads_gmv_report", "rows": 90, "size_mb": 2.4},
    ]


def kpis(synerise_rows: list[dict], retail_rows: list[dict]) -> dict:
    total_pay = sum(r["pay_amount"] for r in retail_rows)
    total_gmv = sum(r["gmv"] for r in retail_rows)
    total_orders = sum(r["order_count"] for r in retail_rows)
    total_pay_orders = sum(r["pay_order_count"] for r in retail_rows)
    total_users = sum(r["pay_user_count"] for r in retail_rows)
    total_refund = sum(r["refund_amount"] for r in retail_rows)

    return {
        "gmv": round(total_gmv, 2),
        "pay_amount": round(total_pay, 2),
        "pay_conversion_rate": round(total_pay_orders / max(total_orders, 1), 4),
        "avg_order_value": round(total_pay / max(total_pay_orders, 1), 2),
        "repeat_purchase_rate": round(1 - total_users / max(total_pay_orders, 1), 4),
        "refund_rate": round(total_refund / max(total_pay, 1), 4),
    }


def main() -> None:
    start_date = "2025-01-01"
    days = 90
    dates = [(date.fromisoformat(start_date) + timedelta(days=i)).isoformat() for i in range(days)]

    daily = daily_rows(start_date, days)
    s_daily = synerise_daily(start_date, days)
    s_events = synerise_event_types(dates)
    s_products = product_topn(dates)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "latest_dt": dates[-1],
        "synerise_latest_dt": dates[-1],
        "kpis": kpis(s_daily, daily),
        "daily": daily,
        "synerise_daily": s_daily,
        "synerise_event_type": s_events,
        "synerise_product_topn": s_products,
        "synerise_product_topn_all": s_products,
        "public_dataset": asset_table(),
    }

    output_dir = Path(__file__).resolve().parents[1] / "dashboard" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "dashboard.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    # Keep the CLI output ASCII-only so the script also succeeds on Windows
    # consoles that still use a GBK code page by default.
    print(f"Generated {output_path} ({output_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
