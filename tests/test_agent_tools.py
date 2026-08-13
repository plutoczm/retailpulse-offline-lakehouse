from app.agent import QueryPlanner, RetailToolbox


def _payload() -> dict:
    daily = [
        {"dt": "2025-01-01", "order_count": 10, "pay_order_count": 8, "gmv": 100, "pay_amount": 80, "refund_amount": 2},
        {"dt": "2025-01-02", "order_count": 10, "pay_order_count": 8, "gmv": 110, "pay_amount": 82, "refund_amount": 2},
        {"dt": "2025-01-03", "order_count": 10, "pay_order_count": 9, "gmv": 120, "pay_amount": 90, "refund_amount": 3},
        {"dt": "2025-01-04", "order_count": 10, "pay_order_count": 9, "gmv": 130, "pay_amount": 100, "refund_amount": 3},
        {"dt": "2025-01-05", "order_count": 10, "pay_order_count": 9, "gmv": 140, "pay_amount": 110, "refund_amount": 3},
        {"dt": "2025-01-06", "order_count": 10, "pay_order_count": 9, "gmv": 150, "pay_amount": 120, "refund_amount": 3},
        {"dt": "2025-01-07", "order_count": 10, "pay_order_count": 9, "gmv": 300, "pay_amount": 240, "refund_amount": 10},
    ]
    return {
        "_source": "demo.json",
        "latest_dt": "2025-01-07",
        "kpis": {
            "gmv": 1050,
            "pay_amount": 822,
            "pay_conversion_rate": 0.8714,
            "avg_order_value": 13.48,
            "repeat_purchase_rate": 0.18,
            "refund_rate": 0.0316,
        },
        "daily": daily,
        "product_topn": [
            {"product_id": "p1", "product_name": "A", "sales_amount": 500, "sales_quantity": 5, "buyer_count": 4},
            {"product_id": "p2", "product_name": "B", "sales_amount": 300, "sales_quantity": 4, "buyer_count": 3},
        ],
        "category_topn": [
            {"category_id": "c1", "category_name": "食品", "sales_amount": 800, "sales_quantity": 10, "buyer_count": 8}
        ],
        "refund_analysis": [
            {"refund_reason": "质量问题", "refund_status": "approved", "refund_amount": 20, "refund_count": 2, "refund_order_count": 2}
        ],
    }


def test_planner_routes_topn_product() -> None:
    payload = _payload()
    plan = QueryPlanner().plan("销售额最高的 Top2 商品是什么？", payload, top_k=2)
    assert any(
        call.tool == "get_topn" and call.arguments["dimension"] == "product"
        for call in plan.calls
    )
    results = RetailToolbox().execute(plan, payload)
    topn = next(result for result in results if result.tool == "get_topn")
    assert topn.data["rows"][0]["product_name"] == "A"


def test_planner_diagnoses_refund_with_reason_breakdown() -> None:
    payload = _payload()
    plan = QueryPlanner().plan("为什么最近退款率上升？", payload)
    assert any(call.tool == "compare_periods" for call in plan.calls)
    assert any(
        call.tool == "breakdown_by_dimension"
        and call.arguments["dimension"] == "refund_reason"
        for call in plan.calls
    )


def test_planner_surfaces_unsupported_channel_dimension() -> None:
    plan = QueryPlanner().plan("按渠道分析 GMV", _payload())
    assert "channel" in plan.coverage_gaps


def test_anomaly_tool_returns_controlled_result() -> None:
    payload = _payload()
    plan = QueryPlanner().plan("GMV 是否有异常波动？", payload)
    result = next(
        result
        for result in RetailToolbox().execute(plan, payload)
        if result.tool == "detect_anomaly"
    )
    assert result.status == "ok"
    assert result.data["sample_size"] == 7
