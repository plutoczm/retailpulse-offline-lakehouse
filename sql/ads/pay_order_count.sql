-- 指标：支付订单量
-- 口径：统计周期内支付成功的订单数，按 order_id 去重。

SELECT
  dt,
  sum(pay_order_count) AS pay_order_count
FROM dws_trade_day_summary
GROUP BY dt;

