-- 指标：客单价
-- 口径：支付金额 / 支付订单量。

SELECT
  dt,
  pay_amount,
  pay_order_count,
  CASE WHEN pay_order_count = 0 THEN 0 ELSE pay_amount / pay_order_count END AS avg_order_value
FROM dws_trade_day_summary;

