from app.catalog import METRIC_CATALOG, select_metric_keys


def test_retrieval_selects_business_metric() -> None:
    result = select_metric_keys(
        "退款率最近是否异常？",
        set(METRIC_CATALOG),
        max_items=3,
    )
    assert result[0] == "refund_rate"


def test_retrieval_supports_multiple_metrics() -> None:
    result = select_metric_keys(
        "对比支付转化率和退款率",
        set(METRIC_CATALOG),
        max_items=3,
    )
    assert "pay_conversion_rate" in result
    assert "refund_rate" in result
