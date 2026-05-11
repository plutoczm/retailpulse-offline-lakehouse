"""Run RetailPulse data quality checks and write a Markdown report."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession
else:
    DataFrame = Any
    SparkSession = Any


LOGGER = logging.getLogger("retailpulse.quality")
VALID_EVENTS = ["view", "search", "cart", "favorite", "order", "pay"]


@dataclass
class CheckResult:
    rule_id: str
    rule_name: str
    table_name: str
    status: str
    error_count: int
    description: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RetailPulse data quality checks.")
    parser.add_argument("--input", default="data", help="Project data root.")
    parser.add_argument("--output", default="reports/data_quality_report.md")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    return parser.parse_args()


def create_spark() -> SparkSession:
    from pyspark.sql import SparkSession

    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseDataQuality")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )


def ensure_windows_hadoop_home() -> None:
    if os.name != "nt":
        return
    configured = os.environ.get("HADOOP_HOME")
    candidate = Path(configured).resolve() if configured else Path(__file__).resolve().parents[1] / ".runtime" / "hadoop"
    if (candidate / "bin" / "winutils.exe").exists():
        os.environ["HADOOP_HOME"] = str(candidate)
        os.environ["hadoop.home.dir"] = str(candidate)
        hadoop_bin = str(candidate / "bin")
        if hadoop_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = hadoop_bin + os.pathsep + os.environ.get("PATH", "")


def status_from_count(error_count: int) -> str:
    return "PASS" if error_count == 0 else "FAIL"


def duplicate_count(df: DataFrame, keys: list[str]) -> int:
    from pyspark.sql import functions as F

    return df.groupBy(*keys).count().filter(F.col("count") > 1).count()


def null_count(df: DataFrame, columns: list[str]) -> int:
    from pyspark.sql import functions as F

    condition = None
    for col_name in columns:
        expr = F.col(col_name).isNull() | (F.trim(F.col(col_name).cast("string")) == "")
        condition = expr if condition is None else condition | expr
    return df.filter(condition).count() if condition is not None else 0


def expected_dates(start_date: str | None, end_date: str | None) -> list[str]:
    if not start_date or not end_date:
        return []
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    dates = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def read_table(spark: SparkSession, root: Path, layer: str, table: str) -> DataFrame:
    return spark.read.parquet(str(root / layer / table))


def append_result(results: list[CheckResult], rule_id: str, rule_name: str, table: str, count: int, description: str) -> None:
    results.append(CheckResult(rule_id, rule_name, table, status_from_count(count), int(count), description))


def run_checks(spark: SparkSession, root: Path, start_date: str | None, end_date: str | None) -> list[CheckResult]:
    from pyspark.sql import functions as F
    from pyspark.sql.functions import broadcast

    results: list[CheckResult] = []

    orders = read_table(spark, root, "dwd", "dwd_trade_order_detail")
    payments = read_table(spark, root, "dwd", "dwd_trade_payment_detail")
    refunds = read_table(spark, root, "dwd", "dwd_trade_refund_detail")
    events = read_table(spark, root, "ods", "ods_user_events")
    inventory = read_table(spark, root, "dwd", "dwd_inventory_change_detail")
    dim_user = read_table(spark, root, "dim", "dim_user").dropDuplicates(["user_id"])
    dim_product = read_table(spark, root, "dim", "dim_product").dropDuplicates(["product_id"])
    dim_shop = read_table(spark, root, "dim", "dim_shop").dropDuplicates(["shop_id"])

    append_result(
        results,
        "DQ001",
        "主键重复检查",
        "dwd_trade_order_detail",
        duplicate_count(orders, ["order_item_id"]),
        "订单明细主键 order_item_id 不应重复。",
    )
    append_result(
        results,
        "DQ002",
        "关键字段为空检查",
        "dwd_trade_order_detail",
        null_count(orders, ["order_id", "user_id", "product_id", "shop_id", "dt"]),
        "交易明细关键字段不能为空。",
    )

    order_amount_errors = (
        orders.dropDuplicates(["order_id"])
        .filter(
            (F.col("total_amount") < 0)
            | (F.col("discount_amount") < 0)
            | (F.col("payable_amount") < 0)
            | (F.abs((F.col("total_amount") - F.col("discount_amount")) - F.col("payable_amount")) > 1.0)
        )
        .count()
    )
    append_result(results, "DQ003", "订单金额异常检查", "dwd_trade_order_detail", order_amount_errors, "订单金额、优惠金额和应付金额需满足基本金额关系。")

    payment_amount_errors = (
        payments.filter(F.col("pay_status") == "success")
        .filter(F.abs(F.col("pay_amount") - F.col("order_payable_amount")) > 1.0)
        .count()
    )
    append_result(results, "DQ004", "支付金额与订单金额一致性检查", "dwd_trade_payment_detail", payment_amount_errors, "成功支付金额应与订单应付金额基本一致。")

    pay_time_errors = payments.filter(F.col("order_time").isNotNull() & (F.col("pay_time") < F.col("order_time"))).count()
    append_result(results, "DQ005", "支付时间早于下单时间检查", "dwd_trade_payment_detail", pay_time_errors, "支付时间不能早于下单时间。")

    refund_amount_errors = refunds.filter(F.col("paid_amount").isNotNull() & (F.col("refund_amount") > F.col("paid_amount"))).count()
    append_result(results, "DQ006", "退款金额大于支付金额检查", "dwd_trade_refund_detail", refund_amount_errors, "退款金额不能超过成功支付金额。")

    dim_missing = (
        orders.join(broadcast(dim_user.select("user_id").withColumn("has_user", F.lit(1))), "user_id", "left")
        .join(broadcast(dim_product.select("product_id").withColumn("has_product", F.lit(1))), "product_id", "left")
        .join(broadcast(dim_shop.select("shop_id").withColumn("has_shop", F.lit(1))), "shop_id", "left")
        .filter(F.col("has_user").isNull() | F.col("has_product").isNull() | F.col("has_shop").isNull())
        .count()
    )
    append_result(results, "DQ007", "维表关联缺失检查", "dwd_trade_order_detail", dim_missing, "交易明细中的用户、商品、店铺必须能关联到维表。")

    dates = expected_dates(start_date, end_date)
    if dates:
        existing = {
            row["dt"]
            for row in orders.select(F.date_format(F.to_date("dt"), "yyyy-MM-dd").alias("dt")).distinct().collect()
        }
        empty_partitions = len([dt for dt in dates if dt not in existing])
    else:
        empty_partitions = 0
    append_result(results, "DQ008", "每日分区为空检查", "dwd_trade_order_detail", empty_partitions, "指定日期范围内每日应有交易分区。")

    invalid_events = events.filter(~F.lower(F.col("event_type")).isin(VALID_EVENTS)).count()
    append_result(results, "DQ009", "用户行为事件类型非法检查", "ods_user_events", invalid_events, "事件类型必须属于 view/search/cart/favorite/order/pay。")

    inventory_errors = (
        inventory.filter(
            (F.col("before_quantity") < 0)
            | (F.col("after_quantity") < 0)
            | ((F.col("before_quantity") + F.col("change_quantity")) != F.col("after_quantity"))
            | (F.abs(F.col("change_quantity")) > 100000)
        )
        .count()
    )
    append_result(results, "DQ010", "库存流水数量异常检查", "dwd_inventory_change_detail", inventory_errors, "库存流水需满足 before + change = after，且数量不能异常放大。")

    append_result(
        results,
        "DQ011",
        "支付主键重复检查",
        "dwd_trade_payment_detail",
        duplicate_count(payments, ["payment_id"]),
        "支付流水 payment_id 不应重复。",
    )
    append_result(
        results,
        "DQ012",
        "退款关键字段为空检查",
        "dwd_trade_refund_detail",
        null_count(refunds, ["refund_id", "order_id", "user_id", "refund_time", "dt"]),
        "退款明细关键字段不能为空。",
    )
    return results


def render_report(results: list[CheckResult]) -> str:
    total = len(results)
    failed = sum(1 for item in results if item.status != "PASS")
    lines = [
        "# RetailPulse 数据质量报告",
        "",
        f"- 检查项总数：{total}",
        f"- 通过：{total - failed}",
        f"- 失败：{failed}",
        "",
        "| 规则ID | 规则名称 | 检查表 | 状态 | 异常数 | 说明 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for item in results:
        lines.append(
            f"| {item.rule_id} | {item.rule_name} | `{item.table_name}` | {item.status} | {item.error_count} | {item.description} |"
        )
    lines.extend(
        [
            "",
            "## 解读",
            "",
            "该报告用于离线批处理完成后的基础质量验收。若出现 FAIL，应优先排查源数据生成、DWD 清洗逻辑和维表装载是否一致。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    output = Path(args.output)
    spark = create_spark()
    try:
        results = run_checks(spark, Path(args.input), args.start_date, args.end_date)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_report(results), encoding="utf-8")
        LOGGER.info("Data quality report written to %s", output)
    except Exception:
        LOGGER.exception("Data quality checks failed")
        raise
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
