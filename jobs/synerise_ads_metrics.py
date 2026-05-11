"""Build ADS metric tables for Synerise behavior analytics."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F


LOGGER = logging.getLogger("retailpulse.synerise_ads_metrics")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Synerise ADS behavior metrics.")
    parser.add_argument("--input", default="data")
    parser.add_argument("--output", default="data/ads")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--shuffle-partitions", type=int, default=96)
    parser.add_argument("--topn", type=int, default=50)
    return parser.parse_args()


def create_spark(shuffle_partitions: int) -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseSyneriseADSMetrics")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.driver.memory", os.environ.get("RETAILPULSE_SPARK_DRIVER_MEMORY", "4g"))
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


def read_parquet(spark: SparkSession, path: Path) -> DataFrame:
    return spark.read.parquet(str(path))


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


def run(args: argparse.Namespace) -> None:
    root = Path(args.input)
    output = Path(args.output)
    spark = create_spark(args.shuffle_partitions)
    try:
        day = filter_dt(read_parquet(spark, root / "dws" / "dws_synerise_behavior_day_summary"), args.start_date, args.end_date)
        event_type = filter_dt(
            read_parquet(spark, root / "dws" / "dws_synerise_event_type_day_summary"), args.start_date, args.end_date
        )
        product = filter_dt(read_parquet(spark, root / "dws" / "dws_synerise_product_day_summary"), args.start_date, args.end_date)
        category = filter_dt(read_parquet(spark, root / "dws" / "dws_synerise_category_day_summary"), args.start_date, args.end_date)

        write_table(day, output, "ads_synerise_behavior_dashboard_daily")
        write_table(event_type, output, "ads_synerise_event_type_trend")

        product_w = Window.partitionBy("dt").orderBy(F.col("pay_event_count").desc(), F.col("cart_event_count").desc())
        product_topn = product.withColumn("rank_no", F.row_number().over(product_w)).filter(F.col("rank_no") <= args.topn)
        write_table(product_topn, output, "ads_synerise_product_topn")

        category_w = Window.partitionBy("dt").orderBy(F.col("pay_event_count").desc(), F.col("cart_event_count").desc())
        category_topn = category.withColumn("rank_no", F.row_number().over(category_w)).filter(F.col("rank_no") <= args.topn)
        write_table(category_topn, output, "ads_synerise_category_topn")
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("Synerise ADS metrics failed")
        raise


if __name__ == "__main__":
    main()
