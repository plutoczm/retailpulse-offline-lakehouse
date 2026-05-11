"""Aggregate Synerise DWD behavior detail into DWS subject summaries."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


LOGGER = logging.getLogger("retailpulse.synerise_dws_aggregate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Synerise DWS behavior summaries.")
    parser.add_argument("--input", default="data")
    parser.add_argument("--output", default="data/dws")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--shuffle-partitions", type=int, default=128)
    parser.add_argument("--output-partitions", type=int, default=32)
    return parser.parse_args()


def create_spark(shuffle_partitions: int) -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseSyneriseDWSAggregate")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.driver.memory", os.environ.get("RETAILPULSE_SPARK_DRIVER_MEMORY", "6g"))
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


def filter_dt(df: DataFrame, start_date: str | None, end_date: str | None) -> DataFrame:
    if start_date:
        df = df.filter(F.col("dt") >= F.lit(start_date))
    if end_date:
        df = df.filter(F.col("dt") <= F.lit(end_date))
    return df


def write_table(df: DataFrame, output: Path, table: str, output_partitions: int) -> None:
    target = str(output / table)
    LOGGER.info("Writing %s to %s", table, target)
    if output_partitions > 0:
        df = df.coalesce(output_partitions)
    df.write.mode("overwrite").partitionBy("dt").parquet(target)


def safe_div(numerator: F.Column, denominator: F.Column) -> F.Column:
    return F.when(denominator == 0, F.lit(0.0)).otherwise(numerator / denominator)


def run(args: argparse.Namespace) -> None:
    root = Path(args.input)
    output = Path(args.output)
    spark = create_spark(args.shuffle_partitions)
    try:
        behavior = spark.read.parquet(str(root / "dwd" / "dwd_synerise_user_behavior_detail"))
        behavior = filter_dt(behavior, args.start_date, args.end_date)
        behavior = behavior.select(
            "dt",
            "event_type",
            "client_id",
            "user_id",
            "sku",
            "category_id",
            "product_price",
            "product_name",
        ).persist(StorageLevel.MEMORY_AND_DISK)

        event_type_day = behavior.groupBy("dt", "event_type").agg(
            F.count("*").alias("event_count"),
            F.approx_count_distinct("client_id").alias("active_user_count"),
            F.approx_count_distinct("sku").alias("active_sku_count"),
        )
        write_table(event_type_day, output, "dws_synerise_event_type_day_summary", args.output_partitions)

        day_summary = behavior.groupBy("dt").agg(
            F.count("*").alias("event_count"),
            F.approx_count_distinct("client_id").alias("active_user_count"),
            F.approx_count_distinct(F.when(F.col("event_type") == "view", F.col("client_id"))).alias("view_user_count"),
            F.approx_count_distinct(F.when(F.col("event_type") == "search", F.col("client_id"))).alias(
                "search_user_count"
            ),
            F.approx_count_distinct(F.when(F.col("event_type") == "cart", F.col("client_id"))).alias("cart_user_count"),
            F.approx_count_distinct(F.when(F.col("event_type") == "remove_cart", F.col("client_id"))).alias(
                "remove_cart_user_count"
            ),
            F.approx_count_distinct(F.when(F.col("event_type") == "pay", F.col("client_id"))).alias("pay_user_count"),
            F.sum(F.when(F.col("event_type") == "view", 1).otherwise(0)).alias("view_event_count"),
            F.sum(F.when(F.col("event_type") == "search", 1).otherwise(0)).alias("search_event_count"),
            F.sum(F.when(F.col("event_type") == "cart", 1).otherwise(0)).alias("cart_event_count"),
            F.sum(F.when(F.col("event_type") == "remove_cart", 1).otherwise(0)).alias("remove_cart_event_count"),
            F.sum(F.when(F.col("event_type") == "pay", 1).otherwise(0)).alias("pay_event_count"),
        )
        day_summary = (
            day_summary.withColumn("view_to_cart_rate", safe_div(F.col("cart_user_count"), F.col("view_user_count")))
            .withColumn("cart_to_pay_rate", safe_div(F.col("pay_user_count"), F.col("cart_user_count")))
            .withColumn("view_to_pay_rate", safe_div(F.col("pay_user_count"), F.col("view_user_count")))
        )
        write_table(day_summary, output, "dws_synerise_behavior_day_summary", args.output_partitions)

        sku_behavior = behavior.filter(F.col("sku").isNotNull())
        product_day = sku_behavior.groupBy("dt", "sku", "category_id", "product_name").agg(
            F.count("*").alias("event_count"),
            F.sum(F.when(F.col("event_type") == "cart", 1).otherwise(0)).alias("cart_event_count"),
            F.sum(F.when(F.col("event_type") == "remove_cart", 1).otherwise(0)).alias("remove_cart_event_count"),
            F.sum(F.when(F.col("event_type") == "pay", 1).otherwise(0)).alias("pay_event_count"),
            F.approx_count_distinct("client_id").alias("active_user_count"),
            F.avg("product_price").alias("avg_product_price"),
        )
        write_table(product_day, output, "dws_synerise_product_day_summary", args.output_partitions)

        category_day = sku_behavior.groupBy("dt", "category_id").agg(
            F.count("*").alias("event_count"),
            F.sum(F.when(F.col("event_type") == "cart", 1).otherwise(0)).alias("cart_event_count"),
            F.sum(F.when(F.col("event_type") == "remove_cart", 1).otherwise(0)).alias("remove_cart_event_count"),
            F.sum(F.when(F.col("event_type") == "pay", 1).otherwise(0)).alias("pay_event_count"),
            F.approx_count_distinct("client_id").alias("active_user_count"),
            F.approx_count_distinct("sku").alias("active_sku_count"),
        )
        write_table(category_day, output, "dws_synerise_category_day_summary", args.output_partitions)

        behavior.unpersist()
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("Synerise DWS aggregate failed")
        raise


if __name__ == "__main__":
    main()
