"""Aggregate DWD detail tables into DWS subject summaries."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F


LOGGER = logging.getLogger("retailpulse.dws_aggregate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate DWS subject tables.")
    parser.add_argument("--input", default="data")
    parser.add_argument("--output", default="data/dws")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    return parser.parse_args()


def create_spark() -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseDWSAggregate")
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


def read_dwd(spark: SparkSession, root: Path, table: str) -> DataFrame:
    return spark.read.parquet(str(root / "dwd" / table))


def filter_dt(df: DataFrame, start_date: str | None, end_date: str | None) -> DataFrame:
    if start_date:
        df = df.filter(F.col("dt") >= F.lit(start_date))
    if end_date:
        df = df.filter(F.col("dt") <= F.lit(end_date))
    return df


def write_table(df: DataFrame, output: Path, table: str, partitions: int = 2) -> None:
    target = str(output / table)
    LOGGER.info("Writing %s to %s", table, target)
    df.coalesce(partitions).write.mode("overwrite").partitionBy("dt").parquet(target)


def safe_div(numerator: F.Column, denominator: F.Column) -> F.Column:
    return F.when(denominator == 0, F.lit(0.0)).otherwise(numerator / denominator)


def run(args: argparse.Namespace) -> None:
    root = Path(args.input)
    output = Path(args.output)
    spark = create_spark()
    try:
        order_detail = filter_dt(read_dwd(spark, root, "dwd_trade_order_detail"), args.start_date, args.end_date)
        payment = filter_dt(read_dwd(spark, root, "dwd_trade_payment_detail"), args.start_date, args.end_date)
        refund = filter_dt(read_dwd(spark, root, "dwd_trade_refund_detail"), args.start_date, args.end_date)
        behavior = filter_dt(read_dwd(spark, root, "dwd_user_behavior_detail"), args.start_date, args.end_date)
        inventory = filter_dt(read_dwd(spark, root, "dwd_inventory_change_detail"), args.start_date, args.end_date)

        order_detail.persist(StorageLevel.MEMORY_AND_DISK)
        payment.persist(StorageLevel.MEMORY_AND_DISK)

        order_fact = (
            order_detail.groupBy("order_id", "user_id", "shop_id", "order_time", "order_status", "dt")
            .agg(
                F.first("total_amount").alias("total_amount"),
                F.first("discount_amount").alias("discount_amount"),
                F.first("payable_amount").alias("payable_amount"),
                F.sum("quantity").alias("item_quantity"),
            )
            .persist(StorageLevel.MEMORY_AND_DISK)
        )

        payment_success = payment.filter(F.col("pay_status") == "success")
        refund_approved = refund.filter(F.col("refund_status") == "approved")

        order_day = order_fact.groupBy("dt").agg(
            F.countDistinct("order_id").alias("order_count"),
            F.countDistinct("user_id").alias("order_user_count"),
            F.sum("payable_amount").alias("gmv"),
        )
        pay_day = payment_success.groupBy("dt").agg(
            F.countDistinct("order_id").alias("pay_order_count"),
            F.countDistinct("user_id").alias("pay_user_count"),
            F.sum("pay_amount").alias("pay_amount"),
        )
        refund_day = refund_approved.groupBy("dt").agg(
            F.countDistinct("order_id").alias("refund_order_count"),
            F.sum("refund_amount").alias("refund_amount"),
        )
        dws_trade_day = (
            order_day.join(pay_day, "dt", "left")
            .join(refund_day, "dt", "left")
            .na.fill(0)
            .withColumn("pay_conversion_rate", safe_div(F.col("pay_order_count"), F.col("order_count")))
            .withColumn("avg_order_value", safe_div(F.col("pay_amount"), F.col("pay_order_count")))
            .withColumn("refund_rate", safe_div(F.col("refund_amount"), F.col("pay_amount")))
        )
        write_table(dws_trade_day, output, "dws_trade_day_summary")

        user_order = order_fact.groupBy("dt", "user_id").agg(
            F.countDistinct("order_id").alias("order_count"),
            F.sum("payable_amount").alias("order_amount"),
        )
        user_pay = payment_success.groupBy("dt", "user_id").agg(
            F.countDistinct("order_id").alias("pay_order_count"),
            F.sum("pay_amount").alias("pay_amount"),
        )
        user_refund = refund_approved.groupBy("dt", "user_id").agg(
            F.countDistinct("order_id").alias("refund_order_count"),
            F.sum("refund_amount").alias("refund_amount"),
        )
        user_event = behavior.groupBy("dt", "user_id").agg(
            F.count("*").alias("event_count"),
            F.sum(F.when(F.col("event_type") == "view", 1).otherwise(0)).alias("view_count"),
            F.sum(F.when(F.col("event_type") == "cart", 1).otherwise(0)).alias("cart_count"),
        )
        dws_user_day = (
            user_order.join(user_pay, ["dt", "user_id"], "full")
            .join(user_refund, ["dt", "user_id"], "full")
            .join(user_event, ["dt", "user_id"], "full")
            .na.fill(0)
        )
        write_table(dws_user_day, output, "dws_user_day_summary")

        dws_product_day = order_detail.groupBy("dt", "product_id", "category_id", "category_name", "brand").agg(
            F.sum("quantity").alias("sales_quantity"),
            F.sum("item_amount").alias("sales_amount"),
            F.countDistinct("order_id").alias("order_count"),
            F.countDistinct("user_id").alias("buyer_count"),
        )
        write_table(dws_product_day, output, "dws_product_day_summary")

        dws_shop_day = order_detail.groupBy("dt", "shop_id").agg(
            F.sum("quantity").alias("sales_quantity"),
            F.sum("item_amount").alias("sales_amount"),
            F.countDistinct("order_id").alias("order_count"),
            F.countDistinct("user_id").alias("buyer_count"),
        )
        write_table(dws_shop_day, output, "dws_shop_day_summary")

        dws_category_day = order_detail.groupBy("dt", "category_id", "category_name").agg(
            F.sum("quantity").alias("sales_quantity"),
            F.sum("item_amount").alias("sales_amount"),
            F.countDistinct("order_id").alias("order_count"),
            F.countDistinct("user_id").alias("buyer_count"),
        )
        write_table(dws_category_day, output, "dws_category_day_summary")

        active_users = behavior.select(F.col("dt").alias("active_dt"), "user_id").dropDuplicates()
        cohorts = active_users.select(F.col("active_dt").alias("cohort_dt"), "user_id")
        retained = (
            cohorts.join(active_users, "user_id", "inner")
            .withColumn("day_diff", F.datediff(F.col("active_dt"), F.col("cohort_dt")))
            .filter(F.col("day_diff").isin([1, 7]))
            .groupBy("cohort_dt", "day_diff")
            .agg(F.countDistinct("user_id").alias("retained_users"))
        )
        cohort_size = cohorts.groupBy("cohort_dt").agg(F.countDistinct("user_id").alias("cohort_users"))
        dws_retention = (
            retained.join(cohort_size, "cohort_dt", "left")
            .withColumn("retention_rate", safe_div(F.col("retained_users"), F.col("cohort_users")))
            .withColumn("dt", F.col("cohort_dt"))
            .select("cohort_dt", "day_diff", "cohort_users", "retained_users", "retention_rate", "dt")
        )
        write_table(dws_retention, output, "dws_user_retention_summary")

        w = Window.partitionBy("dt", "product_id", "shop_id").orderBy(F.col("change_time").desc())
        dws_inventory = (
            inventory.withColumn("rn", F.row_number().over(w))
            .groupBy("dt", "product_id", "shop_id")
            .agg(
                F.sum(F.when(F.col("change_quantity") > 0, F.col("change_quantity")).otherwise(0)).alias("in_quantity"),
                F.sum(F.when(F.col("change_quantity") < 0, -F.col("change_quantity")).otherwise(0)).alias("out_quantity"),
                F.max(F.when(F.col("rn") == 1, F.col("after_quantity"))).alias("ending_quantity"),
                F.avg("before_quantity").alias("avg_before_quantity"),
            )
        )
        write_table(dws_inventory, output, "dws_inventory_day_summary")

        order_fact.unpersist()
        order_detail.unpersist()
        payment.unpersist()
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("DWS aggregate failed")
        raise


if __name__ == "__main__":
    main()
