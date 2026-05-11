"""Clean ODS tables into DWD detail fact tables."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import broadcast


LOGGER = logging.getLogger("retailpulse.dwd_clean")
VALID_EVENTS = ["view", "search", "cart", "favorite", "order", "pay"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean ODS tables into DWD detail tables.")
    parser.add_argument("--input", default="data/ods")
    parser.add_argument("--output", default="data/dwd")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    return parser.parse_args()


def create_spark() -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseDWDClean")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.autoBroadcastJoinThreshold", 64 * 1024 * 1024)
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


def read_table(spark: SparkSession, base: Path, table: str) -> DataFrame:
    return spark.read.parquet(str(base / table))


def filter_dt(df: DataFrame, start_date: str | None, end_date: str | None) -> DataFrame:
    if "dt" not in df.columns:
        return df
    if start_date:
        df = df.filter(F.col("dt") >= F.lit(start_date))
    if end_date:
        df = df.filter(F.col("dt") <= F.lit(end_date))
    return df


def write_table(df: DataFrame, output: Path, table: str, partitions: int = 2) -> None:
    target = str(output / table)
    LOGGER.info("Writing %s to %s", table, target)
    df.coalesce(partitions).write.mode("overwrite").partitionBy("dt").parquet(target)


def build_order_detail(spark: SparkSession, ods: Path) -> DataFrame:
    orders = read_table(spark, ods, "ods_orders").dropDuplicates(["order_id"])
    items = read_table(spark, ods, "ods_order_items").dropDuplicates(["order_item_id"])
    products = read_table(spark, ods, "ods_products").dropDuplicates(["product_id"])

    orders_clean = (
        orders.withColumn("order_time", F.to_timestamp("order_time"))
        .withColumn("order_status", F.lower(F.trim("order_status")))
        .withColumn("total_amount", F.col("total_amount").cast("double"))
        .withColumn("discount_amount", F.col("discount_amount").cast("double"))
        .withColumn("payable_amount", F.col("payable_amount").cast("double"))
        .filter(F.col("order_id").isNotNull() & F.col("user_id").isNotNull())
        .filter((F.col("total_amount") >= 0) & (F.col("payable_amount") >= 0))
        .select(
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
            F.col("dt").alias("order_dt"),
        )
    )

    items_clean = (
        items.withColumn("quantity", F.col("quantity").cast("int"))
        .withColumn("sale_price", F.col("sale_price").cast("double"))
        .withColumn("item_amount", F.col("item_amount").cast("double"))
        .filter(F.col("order_item_id").isNotNull() & F.col("order_id").isNotNull())
        .filter((F.col("quantity") > 0) & (F.col("sale_price") >= 0) & (F.col("item_amount") >= 0))
        .select(
            "order_item_id",
            "order_id",
            "product_id",
            "category_id",
            "sku_id",
            "quantity",
            "sale_price",
            "item_amount",
            F.col("dt").alias("item_dt"),
        )
    )

    product_dim = products.select(
        "product_id",
        F.col("category_name").alias("product_category_name"),
        "brand",
        F.col("shop_id").alias("product_shop_id"),
        F.col("list_price").cast("double").alias("list_price"),
        F.col("cost_price").cast("double").alias("cost_price"),
    )

    return (
        items_clean.join(orders_clean, "order_id", "inner")
        .join(broadcast(product_dim), "product_id", "left")
        .withColumn("category_name", F.coalesce("product_category_name", F.lit("unknown")))
        .withColumn("dt", F.col("order_dt"))
        .select(
            "order_item_id",
            "order_id",
            "user_id",
            "shop_id",
            "product_id",
            "category_id",
            "category_name",
            "brand",
            "sku_id",
            "quantity",
            "sale_price",
            "item_amount",
            "total_amount",
            "discount_amount",
            "payable_amount",
            "order_status",
            "order_time",
            "province",
            "city",
            "dt",
        )
    )


def build_payment_detail(spark: SparkSession, ods: Path) -> DataFrame:
    payments = read_table(spark, ods, "ods_payments").dropDuplicates(["payment_id"])
    orders = read_table(spark, ods, "ods_orders").dropDuplicates(["order_id"])
    order_ref = orders.select(
        "order_id",
        F.col("shop_id").alias("order_shop_id"),
        F.to_timestamp("order_time").alias("order_time"),
        F.col("payable_amount").cast("double").alias("order_payable_amount"),
    )
    return (
        payments.withColumn("pay_time", F.to_timestamp("pay_time"))
        .withColumn("pay_status", F.lower(F.trim("pay_status")))
        .withColumn("pay_amount", F.col("pay_amount").cast("double"))
        .filter(F.col("payment_id").isNotNull() & F.col("order_id").isNotNull())
        .filter(F.col("pay_amount") >= 0)
        .join(broadcast(order_ref), "order_id", "left")
        .select(
            "payment_id",
            "order_id",
            "user_id",
            F.col("order_shop_id").alias("shop_id"),
            "pay_time",
            "order_time",
            "pay_method",
            "pay_amount",
            "order_payable_amount",
            "pay_status",
            "dt",
        )
    )


def build_refund_detail(spark: SparkSession, ods: Path) -> DataFrame:
    refunds = read_table(spark, ods, "ods_refunds").dropDuplicates(["refund_id"])
    payments = read_table(spark, ods, "ods_payments").filter(F.col("pay_status") == "success")
    payment_ref = payments.select(
        "order_id",
        F.col("payment_id").alias("paid_payment_id"),
        F.col("pay_amount").cast("double").alias("paid_amount"),
        F.to_timestamp("pay_time").alias("pay_time"),
    )
    return (
        refunds.withColumn("refund_time", F.to_timestamp("refund_time"))
        .withColumn("refund_status", F.lower(F.trim("refund_status")))
        .withColumn("refund_amount", F.col("refund_amount").cast("double"))
        .filter(F.col("refund_id").isNotNull() & F.col("order_id").isNotNull())
        .filter(F.col("refund_amount") >= 0)
        .join(broadcast(payment_ref), "order_id", "left")
        .select(
            "refund_id",
            "order_id",
            "user_id",
            "refund_time",
            "refund_amount",
            "refund_reason",
            "refund_status",
            "paid_payment_id",
            "paid_amount",
            "pay_time",
            "dt",
        )
    )


def build_behavior_detail(spark: SparkSession, ods: Path) -> DataFrame:
    events = read_table(spark, ods, "ods_user_events").dropDuplicates(["event_id"])
    return (
        events.withColumn("event_type", F.lower(F.trim("event_type")))
        .withColumn("event_time", F.to_timestamp("event_time"))
        .filter(F.col("event_id").isNotNull() & F.col("user_id").isNotNull())
        .filter(F.col("event_type").isin(VALID_EVENTS))
        .select(
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
        )
    )


def build_inventory_detail(spark: SparkSession, ods: Path) -> DataFrame:
    logs = read_table(spark, ods, "ods_inventory_logs").dropDuplicates(["inventory_log_id"])
    return (
        logs.withColumn("change_time", F.to_timestamp("change_time"))
        .withColumn("change_quantity", F.col("change_quantity").cast("int"))
        .withColumn("before_quantity", F.col("before_quantity").cast("int"))
        .withColumn("after_quantity", F.col("after_quantity").cast("int"))
        .withColumn("change_type", F.lower(F.trim("change_type")))
        .filter(F.col("inventory_log_id").isNotNull() & F.col("product_id").isNotNull())
        .filter((F.col("before_quantity") >= 0) & (F.col("after_quantity") >= 0))
        .select(
            "inventory_log_id",
            "product_id",
            "shop_id",
            "change_type",
            "change_quantity",
            "before_quantity",
            "after_quantity",
            "change_time",
            "dt",
        )
    )


def run(args: argparse.Namespace) -> None:
    ods = Path(args.input)
    output = Path(args.output)
    spark = create_spark()
    try:
        order_detail = filter_dt(build_order_detail(spark, ods), args.start_date, args.end_date)
        order_detail.persist(StorageLevel.MEMORY_AND_DISK)
        write_table(order_detail, output, "dwd_trade_order_detail")

        payment_detail = filter_dt(build_payment_detail(spark, ods), args.start_date, args.end_date)
        write_table(payment_detail, output, "dwd_trade_payment_detail")

        refund_detail = filter_dt(build_refund_detail(spark, ods), args.start_date, args.end_date)
        write_table(refund_detail, output, "dwd_trade_refund_detail")

        behavior_detail = filter_dt(build_behavior_detail(spark, ods), args.start_date, args.end_date)
        write_table(behavior_detail, output, "dwd_user_behavior_detail")

        inventory_detail = filter_dt(build_inventory_detail(spark, ods), args.start_date, args.end_date)
        write_table(inventory_detail, output, "dwd_inventory_change_detail")
        order_detail.unpersist()
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("DWD clean failed")
        raise


if __name__ == "__main__":
    main()
