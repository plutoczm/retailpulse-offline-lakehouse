"""Build Synerise DWD unified user behavior detail table."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import broadcast


LOGGER = logging.getLogger("retailpulse.synerise_dwd_behavior")


@dataclass(frozen=True)
class EventSourceSpec:
    ods_table: str
    source_event_type: str
    event_type: str
    value_column: str | None


EVENT_SOURCES = {
    "page_visit": EventSourceSpec("ods_synerise_page_visit", "page_visit", "view", "url"),
    "search_query": EventSourceSpec("ods_synerise_search_query", "search_query", "search", "query"),
    "add_to_cart": EventSourceSpec("ods_synerise_add_to_cart", "add_to_cart", "cart", "sku"),
    "remove_from_cart": EventSourceSpec("ods_synerise_remove_from_cart", "remove_from_cart", "remove_cart", "sku"),
    "product_buy": EventSourceSpec("ods_synerise_product_buy", "product_buy", "pay", "sku"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Synerise DWD user behavior detail.")
    parser.add_argument("--input", default="data/ods")
    parser.add_argument("--output", default="data/dwd")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--tables", default="all", help="Comma-separated source names or 'all'.")
    parser.add_argument("--limit-per-table", type=int, default=0)
    parser.add_argument("--shuffle-partitions", type=int, default=96)
    parser.add_argument("--output-partitions", type=int, default=96)
    parser.add_argument("--deduplicate", action="store_true")
    parser.add_argument("--broadcast-products", action="store_true")
    return parser.parse_args()


def create_spark(shuffle_partitions: int) -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseSyneriseDWDBehavior")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "Asia/Shanghai")
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        .config("spark.sql.parquet.compression.codec", "snappy")
        .config("spark.sql.autoBroadcastJoinThreshold", 96 * 1024 * 1024)
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


def selected_event_sources(tables: str) -> list[EventSourceSpec]:
    if tables.strip().lower() == "all":
        return list(EVENT_SOURCES.values())
    names = [item.strip() for item in tables.split(",") if item.strip()]
    unknown = [name for name in names if name not in EVENT_SOURCES]
    if unknown:
        raise ValueError(f"Unknown Synerise event source(s): {', '.join(unknown)}")
    return [EVENT_SOURCES[name] for name in names]


def read_table(spark: SparkSession, base: Path, table: str) -> DataFrame:
    return spark.read.parquet(str(base / table))


def filter_dt(df: DataFrame, start_date: str | None, end_date: str | None) -> DataFrame:
    if start_date:
        df = df.filter(F.col("dt") >= F.lit(start_date))
    if end_date:
        df = df.filter(F.col("dt") <= F.lit(end_date))
    return df


def apply_limit(df: DataFrame, limit_per_table: int) -> DataFrame:
    return df.limit(limit_per_table) if limit_per_table and limit_per_table > 0 else df


def base_event_columns(df: DataFrame, spec: EventSourceSpec) -> DataFrame:
    value_col = spec.value_column
    event = (
        df.withColumn("client_id", F.col("client_id").cast("long"))
        .withColumn("event_time", F.to_timestamp("event_time"))
        .withColumn("source_dataset", F.lit("synerise_recsys_2025"))
        .withColumn("source_event_type", F.lit(spec.source_event_type))
        .withColumn("event_type", F.lit(spec.event_type))
        .withColumn("user_id", F.concat(F.lit("syn_u_"), F.col("client_id").cast("string")))
    )
    if value_col == "sku":
        event = event.withColumn("sku", F.col("sku").cast("long"))
    else:
        event = event.withColumn("sku", F.lit(None).cast("long"))
    if value_col == "url":
        event = event.withColumn("url_id", F.col("url").cast("long"))
    else:
        event = event.withColumn("url_id", F.lit(None).cast("long"))
    if value_col == "query":
        event = event.withColumn("query_text", F.col("query").cast("string"))
    else:
        event = event.withColumn("query_text", F.lit(None).cast("string"))

    return event.select(
        "client_id",
        "user_id",
        "event_time",
        "source_dataset",
        "source_event_type",
        "event_type",
        "sku",
        "url_id",
        "query_text",
        "dt",
    )


def load_product_properties(spark: SparkSession, ods: Path, broadcast_products: bool) -> DataFrame:
    product = (
        read_table(spark, ods, "ods_synerise_product_properties")
        .select(
            F.col("sku").cast("long").alias("sku"),
            F.col("category_id").cast("long").alias("category_id"),
            F.col("price").cast("double").alias("product_price"),
            F.col("product_name").cast("string").alias("product_name"),
        )
        .filter(F.col("sku").isNotNull())
        .dropDuplicates(["sku"])
    )
    return broadcast(product) if broadcast_products else product


def add_event_id(df: DataFrame) -> DataFrame:
    query_hash = F.sha2(F.coalesce(F.col("query_text"), F.lit("")), 256)
    return (
        df.withColumn("query_hash", F.when(F.col("query_text").isNotNull(), query_hash))
        .withColumn(
            "event_id",
            F.sha2(
                F.concat_ws(
                    "||",
                    F.col("source_dataset"),
                    F.col("source_event_type"),
                    F.col("client_id").cast("string"),
                    F.date_format("event_time", "yyyy-MM-dd HH:mm:ss"),
                    F.coalesce(F.col("sku").cast("string"), F.lit("")),
                    F.coalesce(F.col("url_id").cast("string"), F.lit("")),
                    F.coalesce(F.col("query_hash"), F.lit("")),
                ),
                256,
            ),
        )
    )


def write_table(df: DataFrame, output: Path, output_partitions: int) -> None:
    target = str(output / "dwd_synerise_user_behavior_detail")
    LOGGER.info("Writing dwd_synerise_user_behavior_detail to %s", target)
    if output_partitions > 0:
        df = df.repartition(output_partitions, "dt")
    df.write.mode("overwrite").partitionBy("dt").parquet(target)


def run(args: argparse.Namespace) -> None:
    ods = Path(args.input)
    output = Path(args.output)
    spark = create_spark(args.shuffle_partitions)
    try:
        event_frames: list[DataFrame] = []
        specs = selected_event_sources(args.tables)
        for spec in specs:
            LOGGER.info("Reading ODS source %s", spec.ods_table)
            frame = read_table(spark, ods, spec.ods_table)
            frame = filter_dt(frame, args.start_date, args.end_date)
            frame = apply_limit(frame, args.limit_per_table)
            event_frames.append(base_event_columns(frame, spec))
        if not event_frames:
            raise ValueError("No Synerise event sources selected.")

        all_events = event_frames[0]
        for frame in event_frames[1:]:
            all_events = all_events.unionByName(frame)

        all_events = (
            all_events.filter(F.col("client_id").isNotNull())
            .filter(F.col("event_time").isNotNull())
            .filter(F.col("dt").isNotNull())
        )

        has_sku_sources = any(spec.value_column == "sku" for spec in specs)
        sku_events = all_events.filter(F.col("sku").isNotNull())
        non_sku_events = all_events.filter(F.col("sku").isNull()).withColumn("category_id", F.lit(None).cast("long")).withColumn(
            "product_price", F.lit(None).cast("double")
        ).withColumn("product_name", F.lit(None).cast("string"))

        product: DataFrame | None = None
        if has_sku_sources:
            product = load_product_properties(spark, ods, args.broadcast_products)
            product.persist(StorageLevel.MEMORY_AND_DISK)
            sku_events = sku_events.join(product, "sku", "left")
            unified = sku_events.unionByName(non_sku_events)
        else:
            unified = non_sku_events
        unified = add_event_id(unified)
        if args.deduplicate:
            LOGGER.info("Deduplicating Synerise behavior by event_id")
            unified = unified.dropDuplicates(["event_id"])

        result = unified.select(
            "event_id",
            "client_id",
            "user_id",
            "event_type",
            "source_event_type",
            "event_time",
            "sku",
            F.when(F.col("sku").isNotNull(), F.concat(F.lit("syn_sku_"), F.col("sku").cast("string"))).alias(
                "product_id"
            ),
            "category_id",
            "product_price",
            "product_name",
            "url_id",
            "query_hash",
            "query_text",
            "source_dataset",
            "dt",
        )
        write_table(result, output, args.output_partitions)
        if product is not None:
            product.unpersist()
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("Synerise DWD behavior build failed")
        raise


if __name__ == "__main__":
    main()
