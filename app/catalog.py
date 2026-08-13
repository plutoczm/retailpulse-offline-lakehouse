from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    key: str
    label: str
    definition: str
    unit: str
    keywords: tuple[str, ...]


METRIC_CATALOG: dict[str, MetricDefinition] = {
    "gmv": MetricDefinition(
        key="gmv",
        label="GMV",
        definition="提交订单形成的交易规模，按订单口径去重。",
        unit="currency",
        keywords=("gmv", "交易额", "成交额", "下单金额", "销售额", "revenue"),
    ),
    "pay_amount": MetricDefinition(
        key="pay_amount",
        label="支付金额",
        definition="支付成功流水金额，比 GMV 更接近实际收入。",
        unit="currency",
        keywords=("支付金额", "实收", "收入", "pay amount", "paid amount"),
    ),
    "pay_conversion_rate": MetricDefinition(
        key="pay_conversion_rate",
        label="支付转化率",
        definition="支付成功订单数 / 下单订单数，分子分母均按订单去重。",
        unit="rate",
        keywords=("支付转化率", "转化率", "conversion", "支付转化", "转化"),
    ),
    "avg_order_value": MetricDefinition(
        key="avg_order_value",
        label="客单价",
        definition="支付金额 / 支付成功订单数。",
        unit="currency",
        keywords=("客单价", "aov", "average order value", "订单均价"),
    ),
    "repeat_purchase_rate": MetricDefinition(
        key="repeat_purchase_rate",
        label="复购率",
        definition="当前项目采用日内多次支付用户数 / 支付用户数。",
        unit="rate",
        keywords=("复购率", "复购", "repeat purchase", "retention purchase"),
    ),
    "refund_rate": MetricDefinition(
        key="refund_rate",
        label="退款率",
        definition="审核通过退款金额 / 成功支付金额。",
        unit="rate",
        keywords=("退款率", "退款", "refund", "退货"),
    ),
}


def select_metric_keys(
    question: str,
    available_keys: set[str] | list[str] | tuple[str, ...],
    max_items: int = 4,
) -> list[str]:
    normalized = question.casefold()
    available = set(available_keys)
    scored: list[tuple[int, str]] = []

    for key, definition in METRIC_CATALOG.items():
        if key not in available:
            continue
        score = 0
        if key.casefold() in normalized:
            score += 4
        for keyword in definition.keywords:
            if keyword.casefold() in normalized:
                score += 3
        if definition.label.casefold() in normalized:
            score += 4
        if score:
            scored.append((score, key))

    if scored:
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [key for _, key in scored[:max_items]]

    defaults = [
        "gmv",
        "pay_amount",
        "pay_conversion_rate",
        "refund_rate",
        "avg_order_value",
        "repeat_purchase_rate",
    ]
    return [key for key in defaults if key in available][:max_items]
