"""Build RetailPulse dimension tables."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


LOGGER = logging.getLogger("retailpulse.dim_build")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DIM tables.")
    parser.add_argument("--input", default="data")
    parser.add_argument("--output", default="data/dim")
    parser.add_argument("--dt")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    return parser.parse_args()


def create_spark() -> SparkSession:
    ensure_windows_hadoop_home()
    return (
        SparkSession.builder.appName("RetailPulseDIMBuild")
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


def read_ods(spark: SparkSession, root: Path, table: str) -> DataFrame:
    return spark.read.parquet(str(root / "ods" / table))


def write_table(df: DataFrame, output: Path, table: str) -> None:
    target = str(output / table)
    LOGGER.info("Writing %s to %s", table, target)
    df.coalesce(1).write.mode("overwrite").partitionBy("dt").parquet(target)


def run(args: argparse.Namespace) -> None:
    root = Path(args.input)
    output = Path(args.output)
    process_dt = args.dt or args.end_date or args.start_date or "1970-01-01"
    start_date = args.start_date or process_dt
    end_date = args.end_date or process_dt

    spark = create_spark()
    try:
        users = read_ods(spark, root, "ods_users").dropDuplicates(["user_id"])
        dim_user = (
            users.withColumn("register_time", F.to_timestamp("register_time"))
            .withColumn("age", F.col("age").cast("int"))
            .withColumn(
                "age_group",
                F.when(F.col("age") < 25, "18-24")
                .when(F.col("age") < 35, "25-34")
                .when(F.col("age") < 45, "35-44")
                .otherwise("45+"),
            )
            .withColumn("is_member", F.col("is_member").cast("int"))
            .withColumn("dt", F.lit(process_dt))
            .select("user_id", "register_time", "gender", "age", "age_group", "city", "user_level", "channel", "is_member", "dt")
        )
        write_table(dim_user, output, "dim_user")

        products = read_ods(spark, root, "ods_products").dropDuplicates(["product_id"])
        dim_product = (
            products.withColumn("list_price", F.col("list_price").cast("double"))
            .withColumn("cost_price", F.col("cost_price").cast("double"))
            .withColumn("create_time", F.to_timestamp("create_time"))
            .withColumn("dt", F.lit(process_dt))
            .select(
                "product_id",
                "product_name",
                "category_id",
                "category_name",
                "brand",
                "shop_id",
                "list_price",
                "cost_price",
                "create_time",
                "status",
                "dt",
            )
        )
        write_table(dim_product, output, "dim_product")

        shops = read_ods(spark, root, "ods_shops").dropDuplicates(["shop_id"])
        dim_shop = (
            shops.withColumn("open_time", F.to_timestamp("open_time"))
            .withColumn("score", F.col("score").cast("double"))
            .withColumn("dt", F.lit(process_dt))
            .select("shop_id", "shop_name", "shop_type", "city", "open_time", "score", "dt")
        )
        write_table(dim_shop, output, "dim_shop")

        dim_category = (
            dim_product.select("category_id", "category_name")
            .dropDuplicates(["category_id"])
            .withColumn("category_level", F.lit(1))
            .withColumn("dt", F.lit(process_dt))
        )
        write_table(dim_category, output, "dim_category")

        dates = spark.sql(
            f"""
            SELECT explode(sequence(to_date('{start_date}'), to_date('{end_date}'), interval 1 day)) AS date
            """
        )
        dim_date = (
            dates.withColumn("date_id", F.date_format("date", "yyyy-MM-dd"))
            .withColumn("year", F.year("date"))
            .withColumn("month", F.month("date"))
            .withColumn("day", F.dayofmonth("date"))
            .withColumn("week_of_year", F.weekofyear("date"))
            .withColumn("is_weekend", F.dayofweek("date").isin([1, 7]).cast("int"))
            .withColumn("dt", F.col("date_id"))
            .select("date_id", "year", "month", "day", "week_of_year", "is_weekend", "dt")
        )
        write_table(dim_date, output, "dim_date")
    finally:
        spark.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    try:
        run(args)
    except Exception:
        LOGGER.exception("DIM build failed")
        raise


if __name__ == "__main__":
    main()
