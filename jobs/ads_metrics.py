"""Build ADS metric tables for dashboard and analysis."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.functions import broadcast

LOGGER = logging.getLogger("retailpulse.ads_metrics")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ADS metrics.")
    parser.add_argument("--input", default="data")
    parser.add_argument("--output", default="data/ads")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    return parser.parse_args()


def create_spark() -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseADSMetrics")
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
    candidate = (
        Path(configured).resolve()
        if configured
        else Path(__file__).resolve().parents[1] / ".runtime" / "hadoop"
    )
    if (candidate / "bin" / "winutils.exe").exists():
        os.environ["HADOOP_HOME"] = str(candidate)
        os.environ["hadoop.home.dir"] = str(candidate)
        hadoop_bin = str(candidate / "bin")
        if hadoop_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = hadoop_bin + os.pathsep + os.environ.get("PATH", "")


def read_parquet(spark: SparkSession, path: Path) -> DataFrame:
    return spark.read.parquet(str(path))


def filter_dt(
    df: DataFrame,
    start_date: str | None,
    end_date: str | None,
) -> DataFrame:
    if "dt" not in df.columns:
        return df
    if start_date:
        df = df.filter(F.col("dt") >= F.lit(start_date))
    if end_date:
        df = df.filter(F.col("dt") <= F.lit(end_date))
    return df


def write_table(
    df: DataFrame,
    output: Path,
    table: str,
    partitions: int = 2,
) -> None:
    target = str(output / table)
    LOGGER.info("Writing %s to %s", table, target)
    df.coalesce(partitions).write.mode("overwrite").partitionBy("dt").parquet(target)


def safe_div(numerator: F.Column, denominator: F.Column) -> F.Column:
    """Return a Spark expression that divides safely when denominator is zero."""
    return F.when(denominator == 0, F.lit(0.0)).otherwise(numerator / denominator)


def rfm_segment(
    r_score: F.Column,
    f_score: F.Column,
    m_score: F.Column,
) -> F.Column:
    """Return the production RFM segmentation expression used by ADS."""
    return (
        F.when(
            (r_score >= 4) & (f_score >= 4) & (m_score >= 4),
            F.lit("高价值用户"),
        )
        .when((r_score >= 4) & (f_score >= 3), F.lit("潜力用户"))
        .when(r_score <= 2, F.lit("流失风险用户"))
        .otherwise(F.lit("一般用户"))
    )


def run(args: argparse.Namespace) -> None:
    root = Path(args.input)
    output = Path(args.output)
    spark = create_spark()
    try:
        trade = filter_dt(
            read_parquet(spark, root / "dws" / "dws_trade_day_summary"),
            args.start_date,
            args.end_date,
        )
        channel = filter_dt(
            read_parquet(spark, root / "dws" / "dws_channel_day_summary"),
            args.start_date,
            args.end_date,
        )
        product = filter_dt(
            read_parquet(spark, root / "dws" / "dws_product_day_summary"),
            args.start_date,
            args.end_date,
        )
        category = filter_dt(
            read_parquet(spark, root / "dws" / "dws_category_day_summary"),
            args.start_date,
            args.end_date,
        )
        shop = filter_dt(
            read_parquet(spark, root / "dws" / "dws_shop_day_summary"),
            args.start_date,
            args.end_date,
        )
        retention = filter_dt(
            read_parquet(spark, root / "dws" / "dws_user_retention_summary"),
            args.start_date,
            args.end_date,
        )
        inventory = filter_dt(
            read_parquet(spark, root / "dws" / "dws_inventory_day_summary"),
            args.start_date,
            args.end_date,
        )
        user_day = filter_dt(
            read_parquet(spark, root / "dws" / "dws_user_day_summary"),
            args.start_date,
            args.end_date,
        )
        payments = filter_dt(
            read_parquet(spark, root / "dwd" / "dwd_trade_payment_detail"),
            args.start_date,
            args.end_date,
        )
        refunds = filter_dt(
            read_parquet(spark, root / "dwd" / "dwd_trade_refund_detail"),
            args.start_date,
            args.end_date,
        )
        dim_product = read_parquet(spark, root / "dim" / "dim_product").dropDuplicates(
            ["product_id"]
        )
        dim_shop = read_parquet(spark, root / "dim" / "dim_shop").dropDuplicates(
            ["shop_id"]
        )

        trade.persist(StorageLevel.MEMORY_AND_DISK)

        dashboard = (
            trade.withColumn("order_amount", F.col("gmv"))
            .withColumn("repeat_purchase_rate", F.lit(None).cast("double"))
            .select(
                "dt",
                "gmv",
                "order_count",
                "order_user_count",
                "pay_order_count",
                "pay_user_count",
                "pay_amount",
                "pay_conversion_rate",
                "avg_order_value",
                "refund_order_count",
                "refund_amount",
                "refund_rate",
                "repeat_purchase_rate",
            )
        )
        repeat_rate = (
            user_day.filter(F.col("pay_order_count") > 0)
            .groupBy("dt")
            .agg(
                F.countDistinct("user_id").alias("paid_users"),
                F.countDistinct(
                    F.when(F.col("pay_order_count") >= 2, F.col("user_id"))
                ).alias("repeat_paid_users"),
            )
            .withColumn(
                "repeat_purchase_rate",
                safe_div(F.col("repeat_paid_users"), F.col("paid_users")),
            )
            .select("dt", "repeat_purchase_rate")
        )
        dashboard = (
            dashboard.drop("repeat_purchase_rate")
            .join(repeat_rate, "dt", "left")
            .na.fill({"repeat_purchase_rate": 0.0})
        )
        write_table(dashboard, output, "ads_retail_dashboard_daily")

        write_table(channel, output, "ads_channel_summary")

        product_rank_w = Window.partitionBy("dt").orderBy(
            F.col("sales_amount").desc(),
            F.col("sales_quantity").desc(),
        )
        product_topn = (
            product.join(
                broadcast(
                    dim_product.select("product_id", "product_name", "shop_id")
                ),
                "product_id",
                "left",
            )
            .withColumn("rank_no", F.row_number().over(product_rank_w))
            .filter(F.col("rank_no") <= 20)
        )
        write_table(product_topn, output, "ads_product_topn")

        category_rank_w = Window.partitionBy("dt").orderBy(F.col("sales_amount").desc())
        category_topn = category.withColumn(
            "rank_no",
            F.row_number().over(category_rank_w),
        ).filter(F.col("rank_no") <= 20)
        write_table(category_topn, output, "ads_category_topn")

        shop_rank_w = Window.partitionBy("dt").orderBy(F.col("sales_amount").desc())
        shop_rank = (
            shop.join(
                broadcast(dim_shop.select("shop_id", "shop_name", "shop_type", "city")),
                "shop_id",
                "left",
            )
            .withColumn("rank_no", F.row_number().over(shop_rank_w))
            .filter(F.col("rank_no") <= 100)
        )
        write_table(shop_rank, output, "ads_shop_rank")

        retention_ads = retention.filter(F.col("day_diff").isin([1, 7])).select(
            "cohort_dt",
            "day_diff",
            "cohort_users",
            "retained_users",
            "retention_rate",
            "dt",
        )
        write_table(retention_ads, output, "ads_user_retention")

        successful_payments = payments.filter(F.col("pay_status") == "success")
        rfm_base = (
            successful_payments.groupBy("user_id")
            .agg(
                F.max("pay_time").alias("last_pay_time"),
                F.countDistinct("order_id").alias("frequency"),
                F.sum("pay_amount").alias("monetary"),
            )
            .withColumn("as_of_dt", F.lit(args.dt or args.end_date or "2099-12-31"))
            .withColumn(
                "recency_days",
                F.datediff(F.to_date("as_of_dt"), F.to_date("last_pay_time")),
            )
        )
        rfm = (
            rfm_base.withColumn(
                "r_score",
                F.when(F.col("recency_days") <= 7, 5)
                .when(F.col("recency_days") <= 30, 4)
                .when(F.col("recency_days") <= 60, 3)
                .when(F.col("recency_days") <= 90, 2)
                .otherwise(1),
            )
            .withColumn(
                "f_score",
                F.when(F.col("frequency") >= 10, 5)
                .when(F.col("frequency") >= 5, 4)
                .when(F.col("frequency") >= 3, 3)
                .when(F.col("frequency") >= 2, 2)
                .otherwise(1),
            )
            .withColumn(
                "m_score",
                F.when(F.col("monetary") >= 10000, 5)
                .when(F.col("monetary") >= 5000, 4)
                .when(F.col("monetary") >= 2000, 3)
                .when(F.col("monetary") >= 500, 2)
                .otherwise(1),
            )
            .withColumn(
                "user_segment",
                rfm_segment(
                    F.col("r_score"),
                    F.col("f_score"),
                    F.col("m_score"),
                ),
            )
            .withColumn("dt", F.col("as_of_dt"))
            .select(
                "user_id",
                "recency_days",
                "frequency",
                "monetary",
                "r_score",
                "f_score",
                "m_score",
                "user_segment",
                "dt",
            )
        )
        write_table(rfm, output, "ads_rfm_user_segment")

        refund_analysis = refunds.groupBy(
            "dt",
            "refund_reason",
            "refund_status",
        ).agg(
            F.countDistinct("refund_id").alias("refund_count"),
            F.countDistinct("order_id").alias("refund_order_count"),
            F.sum("refund_amount").alias("refund_amount"),
        )
        write_table(refund_analysis, output, "ads_refund_analysis")

        product_sales = product.select(
            "dt",
            "product_id",
            "sales_quantity",
            "sales_amount",
        )
        inventory_turnover = (
            inventory.join(product_sales, ["dt", "product_id"], "left")
            .na.fill({"sales_quantity": 0, "sales_amount": 0.0})
            .withColumn(
                "avg_inventory",
                (F.col("avg_before_quantity") + F.col("ending_quantity")) / 2,
            )
            .withColumn(
                "inventory_turnover_rate",
                safe_div(F.col("sales_quantity"), F.col("avg_inventory")),
            )
            .select(
                "dt",
                "product_id",
                "shop_id",
                "sales_quantity",
                "sales_amount",
                "in_quantity",
                "out_quantity",
                "ending_quantity",
                "avg_inventory",
                "inventory_turnover_rate",
            )
        )
        write_table(inventory_turnover, output, "ads_inventory_turnover")

        trade.unpersist()
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("ADS metrics failed")
        raise


if __name__ == "__main__":
    main()
