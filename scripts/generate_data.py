"""Generate synthetic RetailPulse ecommerce source data.

The script writes CSV files to ``data/raw`` by default.  It has a large
``default`` profile for resume/project completeness and smaller profiles for
local smoke tests.
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


LOGGER = logging.getLogger("retailpulse.generate_data")

DATE_FMT = "%Y-%m-%d"
TS_FMT = "%Y-%m-%d %H:%M:%S"

CITIES = [
    ("Zhejiang", "Hangzhou"),
    ("Shanghai", "Shanghai"),
    ("Beijing", "Beijing"),
    ("Guangdong", "Guangzhou"),
    ("Guangdong", "Shenzhen"),
    ("Jiangsu", "Nanjing"),
    ("Sichuan", "Chengdu"),
    ("Hubei", "Wuhan"),
    ("Fujian", "Xiamen"),
    ("Shaanxi", "Xi'an"),
]

CATEGORIES = [
    (1001, "手机数码"),
    (1002, "电脑办公"),
    (1003, "家用电器"),
    (1004, "美妆个护"),
    (1005, "食品生鲜"),
    (1006, "服饰鞋包"),
    (1007, "母婴玩具"),
    (1008, "运动户外"),
    (1009, "家居家装"),
    (1010, "图书文娱"),
]

BRANDS = [
    "NovaMart",
    "BluePeak",
    "UrbanNest",
    "FreshJoy",
    "MobiOne",
    "CloudNine",
    "SunField",
    "PixelPro",
    "DailyBest",
    "NorthLake",
]

CHANNELS = ["organic", "paid_search", "social", "app_store", "affiliate", "offline_event"]
PAY_METHODS = ["alipay", "wechat_pay", "bank_card", "credit_card", "wallet"]
DEVICE_TYPES = ["ios", "android", "web", "mini_program"]
EVENT_TYPES = ["view", "search", "cart", "favorite", "order", "pay"]
CHANGE_TYPES = ["purchase_in", "sale_out", "refund_in", "adjustment", "transfer_out"]


@dataclass(frozen=True)
class ScaleConfig:
    users: int
    products: int
    shops: int
    orders: int
    order_items: int
    payments: int
    refunds: int
    events: int
    inventory_logs: int


SCALE_PRESETS = {
    "tiny": ScaleConfig(
        users=120,
        products=100,
        shops=20,
        orders=600,
        order_items=1200,
        payments=520,
        refunds=60,
        events=3000,
        inventory_logs=600,
    ),
    "small": ScaleConfig(
        users=1000,
        products=500,
        shops=80,
        orders=10000,
        order_items=20000,
        payments=8600,
        refunds=1000,
        events=80000,
        inventory_logs=12000,
    ),
    "default": ScaleConfig(
        users=10000,
        products=5000,
        shops=500,
        orders=300000,
        order_items=600000,
        payments=260000,
        refunds=30000,
        events=2000000,
        inventory_logs=300000,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RetailPulse source data.")
    parser.add_argument("--output", default="data/raw", help="Output directory for CSV files.")
    parser.add_argument("--scale", choices=sorted(SCALE_PRESETS), default="default")
    parser.add_argument("--start-date", default="2025-01-01", help="Start date, format YYYY-MM-DD.")
    parser.add_argument("--days", type=int, default=90, help="Number of days to generate.")
    parser.add_argument("--seed", type=int, default=20260510)
    parser.add_argument("--users", type=int)
    parser.add_argument("--products", type=int)
    parser.add_argument("--shops", type=int)
    parser.add_argument("--orders", type=int)
    parser.add_argument("--order-items", type=int)
    parser.add_argument("--payments", type=int)
    parser.add_argument("--refunds", type=int)
    parser.add_argument("--events", type=int)
    parser.add_argument("--inventory-logs", type=int)
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> ScaleConfig:
    preset = SCALE_PRESETS[args.scale]
    values = {
        "users": args.users or preset.users,
        "products": args.products or preset.products,
        "shops": args.shops or preset.shops,
        "orders": args.orders or preset.orders,
        "order_items": args.order_items or preset.order_items,
        "payments": args.payments or preset.payments,
        "refunds": args.refunds or preset.refunds,
        "events": args.events or preset.events,
        "inventory_logs": args.inventory_logs or preset.inventory_logs,
    }
    values["order_items"] = max(values["order_items"], values["orders"])
    values["payments"] = min(values["payments"], values["orders"])
    values["refunds"] = min(values["refunds"], values["payments"])
    return ScaleConfig(**values)


def random_timestamp(start: datetime, days: int) -> datetime:
    offset_seconds = random.randint(0, max(days * 86400 - 1, 0))
    return start + timedelta(seconds=offset_seconds)


def add_seconds(ts: datetime, min_seconds: int, max_seconds: int) -> datetime:
    return ts + timedelta(seconds=random.randint(min_seconds, max_seconds))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    LOGGER.info("Wrote %s rows to %s", count, path)
    return count


def money(value: float) -> float:
    return round(max(value, 0.0), 2)


def generate_users(config: ScaleConfig, start: datetime, days: int) -> list[dict]:
    rows = []
    for i in range(1, config.users + 1):
        _, city = random.choice(CITIES)
        register_time = random_timestamp(start - timedelta(days=120), days + 120)
        rows.append(
            {
                "user_id": f"U{i:08d}",
                "register_time": register_time.strftime(TS_FMT),
                "gender": random.choices(["male", "female", "unknown"], [48, 48, 4])[0],
                "age": random.randint(18, 60),
                "city": city,
                "user_level": random.choices(["new", "silver", "gold", "platinum"], [45, 30, 18, 7])[0],
                "channel": random.choice(CHANNELS),
                "is_member": random.choices([0, 1], [70, 30])[0],
            }
        )
    return rows


def generate_shops(config: ScaleConfig, start: datetime) -> list[dict]:
    rows = []
    for i in range(1, config.shops + 1):
        _, city = random.choice(CITIES)
        rows.append(
            {
                "shop_id": f"S{i:06d}",
                "shop_name": f"{random.choice(BRANDS)} {city} Store {i}",
                "shop_type": random.choices(["self_operated", "flagship", "marketplace"], [25, 35, 40])[0],
                "city": city,
                "open_time": (start - timedelta(days=random.randint(120, 1800))).strftime(TS_FMT),
                "score": round(random.uniform(3.6, 5.0), 2),
            }
        )
    return rows


def generate_products(config: ScaleConfig, shops: list[dict], start: datetime) -> list[dict]:
    rows = []
    for i in range(1, config.products + 1):
        category_id, category_name = random.choice(CATEGORIES)
        list_price = money(random.uniform(19, 3999))
        cost_price = money(list_price * random.uniform(0.45, 0.82))
        shop = random.choice(shops)
        rows.append(
            {
                "product_id": f"P{i:08d}",
                "product_name": f"{random.choice(BRANDS)} {category_name} Item {i}",
                "category_id": category_id,
                "category_name": category_name,
                "brand": random.choice(BRANDS),
                "shop_id": shop["shop_id"],
                "list_price": list_price,
                "cost_price": cost_price,
                "create_time": (start - timedelta(days=random.randint(1, 900))).strftime(TS_FMT),
                "status": random.choices(["active", "inactive", "new"], [88, 7, 5])[0],
            }
        )
    return rows


def generate_orders_and_items(
    config: ScaleConfig,
    users: list[dict],
    shops: list[dict],
    products: list[dict],
    start: datetime,
    days: int,
    out_dir: Path,
) -> list[dict]:
    products_by_shop: dict[str, list[dict]] = {}
    for product in products:
        products_by_shop.setdefault(product["shop_id"], []).append(product)

    item_fieldnames = [
        "order_item_id",
        "order_id",
        "product_id",
        "category_id",
        "sku_id",
        "quantity",
        "sale_price",
        "item_amount",
        "dt",
    ]

    order_rows: list[dict] = []
    extra_items = config.order_items - config.orders
    remaining_extra = extra_items
    item_seq = 1

    with (out_dir / "order_items.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=item_fieldnames)
        writer.writeheader()
        for i in range(1, config.orders + 1):
            order_id = f"O{i:010d}"
            user = random.choice(users)
            shop = random.choice(shops)
            candidates = products_by_shop.get(shop["shop_id"]) or products
            order_time = random_timestamp(start, days)
            dt = order_time.strftime(DATE_FMT)
            max_extra_for_order = min(4, remaining_extra)
            add_count = random.randint(0, max_extra_for_order) if max_extra_for_order > 0 else 0
            if remaining_extra > 0 and config.orders - i < remaining_extra:
                add_count = max(add_count, 1)
            item_count = 1 + add_count
            remaining_extra -= add_count
            total_amount = 0.0
            for _ in range(item_count):
                product = random.choice(candidates)
                quantity = random.choices([1, 2, 3, 4], [70, 20, 8, 2])[0]
                sale_price = money(float(product["list_price"]) * random.uniform(0.72, 1.02))
                item_amount = money(sale_price * quantity)
                total_amount += item_amount
                writer.writerow(
                    {
                        "order_item_id": f"OI{item_seq:012d}",
                        "order_id": order_id,
                        "product_id": product["product_id"],
                        "category_id": product["category_id"],
                        "sku_id": f"SKU-{product['product_id']}-{random.randint(1, 20):02d}",
                        "quantity": quantity,
                        "sale_price": sale_price,
                        "item_amount": item_amount,
                        "dt": dt,
                    }
                )
                item_seq += 1

            total_amount = money(total_amount)
            discount_amount = money(total_amount * random.uniform(0.0, 0.18))
            payable_amount = money(total_amount - discount_amount)
            province, city = random.choice(CITIES)
            order_rows.append(
                {
                    "order_id": order_id,
                    "user_id": user["user_id"],
                    "shop_id": shop["shop_id"],
                    "order_time": order_time.strftime(TS_FMT),
                    "order_status": random.choices(
                        ["created", "paid", "shipped", "received", "closed", "cancelled"],
                        [8, 18, 24, 35, 5, 10],
                    )[0],
                    "total_amount": total_amount,
                    "discount_amount": discount_amount,
                    "payable_amount": payable_amount,
                    "province": province,
                    "city": city,
                    "dt": dt,
                }
            )
    LOGGER.info("Wrote %s rows to %s", item_seq - 1, out_dir / "order_items.csv")
    return order_rows


def generate_payments(config: ScaleConfig, orders: list[dict]) -> list[dict]:
    paid_candidates = [o for o in orders if o["order_status"] not in {"created", "cancelled"}]
    if len(paid_candidates) < config.payments:
        paid_candidates = orders
    selected_orders = random.sample(paid_candidates, min(config.payments, len(paid_candidates)))
    rows = []
    for i, order in enumerate(selected_orders, start=1):
        order_time = datetime.strptime(order["order_time"], TS_FMT)
        pay_time = add_seconds(order_time, 60, 48 * 3600)
        success = random.choices([1, 0], [97, 3])[0]
        rows.append(
            {
                "payment_id": f"PAY{i:010d}",
                "order_id": order["order_id"],
                "user_id": order["user_id"],
                "pay_time": pay_time.strftime(TS_FMT),
                "pay_method": random.choice(PAY_METHODS),
                "pay_amount": order["payable_amount"] if success else money(float(order["payable_amount"]) * random.uniform(0.2, 0.9)),
                "pay_status": "success" if success else random.choice(["failed", "processing"]),
                "dt": pay_time.strftime(DATE_FMT),
            }
        )
    return rows


def generate_refunds(config: ScaleConfig, payments: list[dict]) -> list[dict]:
    successful_payments = [p for p in payments if p["pay_status"] == "success"]
    selected = random.sample(successful_payments, min(config.refunds, len(successful_payments)))
    rows = []
    for i, payment in enumerate(selected, start=1):
        pay_time = datetime.strptime(payment["pay_time"], TS_FMT)
        refund_time = add_seconds(pay_time, 3600, 20 * 86400)
        refund_ratio = random.choices([1.0, random.uniform(0.1, 0.8)], [45, 55])[0]
        rows.append(
            {
                "refund_id": f"RF{i:010d}",
                "order_id": payment["order_id"],
                "user_id": payment["user_id"],
                "refund_time": refund_time.strftime(TS_FMT),
                "refund_amount": money(float(payment["pay_amount"]) * refund_ratio),
                "refund_reason": random.choice(["七天无理由", "商品破损", "发错货", "价格保护", "未按时发货"]),
                "refund_status": random.choices(["approved", "pending", "rejected"], [82, 10, 8])[0],
                "dt": refund_time.strftime(DATE_FMT),
            }
        )
    return rows


def generate_user_events(
    config: ScaleConfig,
    users: list[dict],
    shops: list[dict],
    products: list[dict],
    start: datetime,
    days: int,
) -> Iterable[dict]:
    product_by_id = {p["product_id"]: p for p in products}
    for i in range(1, config.events + 1):
        product = product_by_id[random.choice(products)["product_id"]]
        event_time = random_timestamp(start, days)
        yield {
            "event_id": f"E{i:012d}",
            "user_id": random.choice(users)["user_id"],
            "product_id": product["product_id"],
            "shop_id": product.get("shop_id") or random.choice(shops)["shop_id"],
            "event_type": random.choices(EVENT_TYPES, [62, 12, 10, 7, 5, 4])[0],
            "event_time": event_time.strftime(TS_FMT),
            "session_id": str(uuid.uuid4()),
            "device_type": random.choice(DEVICE_TYPES),
            "source_channel": random.choice(CHANNELS),
            "dt": event_time.strftime(DATE_FMT),
        }


def generate_inventory_logs(
    config: ScaleConfig,
    products: list[dict],
    start: datetime,
    days: int,
) -> Iterable[dict]:
    stock_by_product = {p["product_id"]: random.randint(100, 5000) for p in products}
    for i in range(1, config.inventory_logs + 1):
        product = random.choice(products)
        change_type = random.choice(CHANGE_TYPES)
        before_quantity = stock_by_product[product["product_id"]]
        if change_type in {"sale_out", "transfer_out"}:
            change_quantity = -random.randint(1, min(50, max(before_quantity, 1)))
        elif change_type == "adjustment":
            change_quantity = random.randint(-30, 80)
        else:
            change_quantity = random.randint(1, 300)
        after_quantity = max(before_quantity + change_quantity, 0)
        stock_by_product[product["product_id"]] = after_quantity
        change_time = random_timestamp(start, days)
        yield {
            "inventory_log_id": f"IL{i:012d}",
            "product_id": product["product_id"],
            "shop_id": product["shop_id"],
            "change_type": change_type,
            "change_quantity": change_quantity,
            "before_quantity": before_quantity,
            "after_quantity": after_quantity,
            "change_time": change_time.strftime(TS_FMT),
            "dt": change_time.strftime(DATE_FMT),
        }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    random.seed(args.seed)
    config = build_config(args)
    start = datetime.strptime(args.start_date, DATE_FMT)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Generating RetailPulse data: scale=%s config=%s", args.scale, config)

    users = generate_users(config, start, args.days)
    shops = generate_shops(config, start)
    products = generate_products(config, shops, start)
    orders = generate_orders_and_items(config, users, shops, products, start, args.days, out_dir)
    payments = generate_payments(config, orders)
    refunds = generate_refunds(config, payments)

    write_csv(
        out_dir / "users.csv",
        ["user_id", "register_time", "gender", "age", "city", "user_level", "channel", "is_member"],
        users,
    )
    write_csv(
        out_dir / "shops.csv",
        ["shop_id", "shop_name", "shop_type", "city", "open_time", "score"],
        shops,
    )
    write_csv(
        out_dir / "products.csv",
        [
            "product_id",
            "product_name",
            "category_id",
            "category_name",
            "brand",
            "shop_id",
            "list_price",
            "cost_price",
            "create_time",
            "status",
        ],
        products,
    )
    write_csv(
        out_dir / "orders.csv",
        [
            "order_id",
            "user_id",
            "shop_id",
            "order_time",
            "order_status",
            "total_amount",
            "discount_amount",
            "payable_amount",
            "province",
            "city",
            "dt",
        ],
        orders,
    )
    write_csv(
        out_dir / "payments.csv",
        ["payment_id", "order_id", "user_id", "pay_time", "pay_method", "pay_amount", "pay_status", "dt"],
        payments,
    )
    write_csv(
        out_dir / "refunds.csv",
        ["refund_id", "order_id", "user_id", "refund_time", "refund_amount", "refund_reason", "refund_status", "dt"],
        refunds,
    )
    write_csv(
        out_dir / "user_events.csv",
        [
            "event_id",
            "user_id",
            "product_id",
            "shop_id",
            "event_type",
            "event_time",
            "session_id",
            "device_type",
            "source_channel",
            "dt",
        ],
        generate_user_events(config, users, shops, products, start, args.days),
    )
    write_csv(
        out_dir / "inventory_logs.csv",
        [
            "inventory_log_id",
            "product_id",
            "shop_id",
            "change_type",
            "change_quantity",
            "before_quantity",
            "after_quantity",
            "change_time",
            "dt",
        ],
        generate_inventory_logs(config, products, start, args.days),
    )
    LOGGER.info("RetailPulse raw data generated under %s", out_dir)


if __name__ == "__main__":
    main()

