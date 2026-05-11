import csv
import subprocess
import sys
from pathlib import Path


EXPECTED_FILES = {
    "users.csv",
    "products.csv",
    "shops.csv",
    "orders.csv",
    "order_items.csv",
    "payments.csv",
    "refunds.csv",
    "user_events.csv",
    "inventory_logs.csv",
}


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_generate_tiny_outputs_all_source_tables(tmp_path: Path) -> None:
    out_dir = tmp_path / "raw"
    subprocess.run(
        [
            sys.executable,
            "scripts/generate_data.py",
            "--output",
            str(out_dir),
            "--scale",
            "tiny",
            "--days",
            "7",
            "--seed",
            "7",
        ],
        check=True,
    )

    assert {p.name for p in out_dir.glob("*.csv")} == EXPECTED_FILES

    users = read_rows(out_dir / "users.csv")
    orders = read_rows(out_dir / "orders.csv")
    order_items = read_rows(out_dir / "order_items.csv")

    assert {"user_id", "register_time", "gender", "age", "city", "user_level", "channel", "is_member"} <= set(
        users[0]
    )
    assert {"order_id", "user_id", "shop_id", "order_time", "payable_amount", "dt"} <= set(orders[0])
    assert {"order_item_id", "order_id", "product_id", "quantity", "sale_price", "item_amount", "dt"} <= set(
        order_items[0]
    )
    assert len(orders) == 600
    assert len(order_items) >= len(orders)


def test_order_amounts_are_non_negative(tmp_path: Path) -> None:
    out_dir = tmp_path / "raw"
    subprocess.run(
        [
            sys.executable,
            "scripts/generate_data.py",
            "--output",
            str(out_dir),
            "--users",
            "20",
            "--products",
            "15",
            "--shops",
            "5",
            "--orders",
            "30",
            "--order-items",
            "60",
            "--payments",
            "20",
            "--refunds",
            "3",
            "--events",
            "80",
            "--inventory-logs",
            "30",
            "--days",
            "3",
        ],
        check=True,
    )

    for order in read_rows(out_dir / "orders.csv"):
        total = float(order["total_amount"])
        discount = float(order["discount_amount"])
        payable = float(order["payable_amount"])
        assert total >= 0
        assert discount >= 0
        assert payable >= 0
        assert payable <= total

