-- 指标：支付转化率
-- 口径：支付订单量 / 下单订单量。

SELECT
  dt,
  pay_order_count,
  order_count,
  CASE WHEN order_count = 0 THEN 0 ELSE pay_order_count / order_count END AS pay_conversion_rate
FROM dws_trade_day_summary;

