"""Load raw RetailPulse CSV files into ODS Parquet tables."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


LOGGER = logging.getLogger("retailpulse.ods_load")

RAW_TABLES = {
    "users": "ods_users",
    "products": "ods_products",
    "shops": "ods_shops",
    "orders": "ods_orders",
    "order_items": "ods_order_items",
    "payments": "ods_payments",
    "refunds": "ods_refunds",
    "user_events": "ods_user_events",
    "inventory_logs": "ods_inventory_logs",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load raw CSV files to ODS Parquet.")
    parser.add_argument("--input", default="data/raw")
    parser.add_argument("--output", default="data/ods")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    return parser.parse_args()


def create_spark() -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseODSLoad")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
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


def filter_by_dt(df: DataFrame, start_date: str | None, end_date: str | None) -> DataFrame:
    if "dt" not in df.columns:
        return df
    if start_date:
        df = df.filter(F.col("dt") >= F.lit(start_date))
    if end_date:
        df = df.filter(F.col("dt") <= F.lit(end_date))
    return df


def normalize_df(df: DataFrame, table_name: str, load_dt: str) -> DataFrame:
    normalized = df
    for col_name in normalized.columns:
        normalized = normalized.withColumnRenamed(col_name, col_name.strip().lower())
    if "dt" not in normalized.columns:
        normalized = normalized.withColumn("dt", F.lit(load_dt))
    else:
        normalized = normalized.withColumn("dt", F.to_date("dt").cast("string"))
    normalized = normalized.withColumn("ods_load_time", F.current_timestamp())
    normalized = normalized.withColumn("source_table", F.lit(table_name))
    return normalized


def write_table(df: DataFrame, output_dir: Path, table_name: str) -> None:
    target = str(output_dir / table_name)
    LOGGER.info("Writing %s to %s", table_name, target)
    df.coalesce(2).write.mode("overwrite").partitionBy("dt").parquet(target)


def run(args: argparse.Namespace) -> None:
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    load_dt = args.dt or args.end_date or args.start_date or "1970-01-01"

    spark = create_spark()
    try:
        for raw_name, ods_name in RAW_TABLES.items():
            csv_path = input_dir / f"{raw_name}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Raw source file not found: {csv_path}")
            LOGGER.info("Loading raw table %s from %s", raw_name, csv_path)
            df = spark.read.option("header", True).option("inferSchema", True).csv(str(csv_path))
            df = normalize_df(df, raw_name, load_dt)
            df = filter_by_dt(df, args.start_date, args.end_date)
            write_table(df, output_dir, ods_name)
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("ODS load failed")
        raise


if __name__ == "__main__":
    main()
