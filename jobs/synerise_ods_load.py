"""Load Synerise public ecommerce Parquet files into ODS tables."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


LOGGER = logging.getLogger("retailpulse.synerise_ods_load")


@dataclass(frozen=True)
class SyneriseTableSpec:
    source_name: str
    ods_name: str
    value_column: str | None
    is_event: bool = True


TABLE_SPECS = {
    "page_visit": SyneriseTableSpec("page_visit", "ods_synerise_page_visit", "url"),
    "search_query": SyneriseTableSpec("search_query", "ods_synerise_search_query", "query"),
    "add_to_cart": SyneriseTableSpec("add_to_cart", "ods_synerise_add_to_cart", "sku"),
    "remove_from_cart": SyneriseTableSpec("remove_from_cart", "ods_synerise_remove_from_cart", "sku"),
    "product_buy": SyneriseTableSpec("product_buy", "ods_synerise_product_buy", "sku"),
    "product_properties": SyneriseTableSpec(
        "product_properties", "ods_synerise_product_properties", None, is_event=False
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Synerise public dataset into ODS Parquet tables.")
    parser.add_argument("--input", default="external_data/synerise-recsys-2025/extracted")
    parser.add_argument("--output", default="data/ods")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument(
        "--tables",
        default="all",
        help="Comma-separated table names or 'all'. Example: page_visit,product_buy",
    )
    parser.add_argument("--sample-fraction", type=float, default=0.0)
    parser.add_argument("--limit-per-table", type=int, default=0)
    parser.add_argument("--shuffle-partitions", type=int, default=64)
    parser.add_argument("--output-partitions", type=int, default=64)
    parser.add_argument("--mode", default="overwrite", choices=["overwrite", "append"])
    return parser.parse_args()


def create_spark(shuffle_partitions: int) -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseSyneriseODSLoad")
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


def selected_specs(tables: str) -> list[SyneriseTableSpec]:
    if tables.strip().lower() == "all":
        return list(TABLE_SPECS.values())
    names = [item.strip() for item in tables.split(",") if item.strip()]
    unknown = [name for name in names if name not in TABLE_SPECS]
    if unknown:
        raise ValueError(f"Unknown Synerise table(s): {', '.join(unknown)}")
    return [TABLE_SPECS[name] for name in names]


def apply_dev_sampling(df: DataFrame, sample_fraction: float, limit_per_table: int) -> DataFrame:
    if sample_fraction and 0 < sample_fraction < 1:
        df = df.sample(withReplacement=False, fraction=sample_fraction, seed=20260511)
    if limit_per_table and limit_per_table > 0:
        df = df.limit(limit_per_table)
    return df


def filter_dt(df: DataFrame, start_date: str | None, end_date: str | None) -> DataFrame:
    if start_date:
        df = df.filter(F.col("dt") >= F.lit(start_date))
    if end_date:
        df = df.filter(F.col("dt") <= F.lit(end_date))
    return df


def normalize_event_table(df: DataFrame, spec: SyneriseTableSpec) -> DataFrame:
    value_col = spec.value_column
    assert value_col is not None
    normalized = (
        df.select(
            F.col("client_id").cast("long").alias("client_id"),
            F.col("timestamp").cast("string").alias("raw_timestamp"),
            F.to_timestamp("timestamp").alias("event_time"),
            F.col(value_col).alias(value_col),
        )
        .withColumn("dt", F.to_date("event_time").cast("string"))
        .withColumn("source_dataset", F.lit("synerise_recsys_2025"))
        .withColumn("source_table", F.lit(spec.source_name))
        .withColumn("ods_load_time", F.current_timestamp())
    )
    return normalized.filter(F.col("dt").isNotNull())


def normalize_product_properties(df: DataFrame, load_dt: str) -> DataFrame:
    return (
        df.select(
            F.col("sku").cast("long").alias("sku"),
            F.col("category").cast("long").alias("category_id"),
            F.col("price").cast("double").alias("price"),
            F.col("name").cast("string").alias("product_name"),
        )
        .withColumn("dt", F.lit(load_dt))
        .withColumn("source_dataset", F.lit("synerise_recsys_2025"))
        .withColumn("source_table", F.lit("product_properties"))
        .withColumn("ods_load_time", F.current_timestamp())
    )


def write_table(df: DataFrame, output: Path, table: str, mode: str, output_partitions: int) -> None:
    target = str(output / table)
    LOGGER.info("Writing %s to %s", table, target)
    if output_partitions > 0:
        df = df.repartition(output_partitions, "dt")
    df.write.mode(mode).partitionBy("dt").parquet(target)


def run(args: argparse.Namespace) -> None:
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    load_dt = args.dt or args.end_date or args.start_date or date.today().isoformat()

    spark = create_spark(args.shuffle_partitions)
    try:
        for spec in selected_specs(args.tables):
            source_path = input_dir / f"{spec.source_name}.parquet"
            if not source_path.exists():
                raise FileNotFoundError(f"Synerise source file not found: {source_path}")
            LOGGER.info("Loading Synerise table %s from %s", spec.source_name, source_path)
            df = spark.read.parquet(str(source_path))
            df = apply_dev_sampling(df, args.sample_fraction, args.limit_per_table)
            if spec.is_event:
                normalized = normalize_event_table(df, spec)
                normalized = filter_dt(normalized, args.start_date, args.end_date)
            else:
                normalized = normalize_product_properties(df, load_dt)
            write_table(normalized, output_dir, spec.ods_name, args.mode, args.output_partitions)
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("Synerise ODS load failed")
        raise


if __name__ == "__main__":
    main()
