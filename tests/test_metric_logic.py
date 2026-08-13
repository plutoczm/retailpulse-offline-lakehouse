from __future__ import annotations

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from jobs.ads_metrics import rfm_segment, safe_div


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    session = (
        SparkSession.builder.master("local[1]")
        .appName("RetailPulseMetricLogicTests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    yield session
    session.stop()


def test_safe_div_uses_production_expression(spark: SparkSession) -> None:
    rows = [(1, 80.0, 100.0), (2, 1.0, 0.0)]
    actual = (
        spark.createDataFrame(rows, ["id", "numerator", "denominator"])
        .select("id", safe_div(F.col("numerator"), F.col("denominator")).alias("result"))
        .orderBy("id")
        .collect()
    )

    assert [row["result"] for row in actual] == [0.8, 0.0]


def test_rfm_segment_uses_production_expression(spark: SparkSession) -> None:
    rows = [
        (1, 5, 5, 5, "高价值用户"),
        (2, 4, 3, 2, "潜力用户"),
        (3, 1, 5, 5, "流失风险用户"),
        (4, 3, 2, 2, "一般用户"),
    ]
    actual = (
        spark.createDataFrame(rows, ["id", "r_score", "f_score", "m_score", "expected"])
        .select(
            "id",
            "expected",
            rfm_segment(F.col("r_score"), F.col("f_score"), F.col("m_score")).alias("actual"),
        )
        .orderBy("id")
        .collect()
    )

    assert [row["actual"] for row in actual] == [row["expected"] for row in actual]
