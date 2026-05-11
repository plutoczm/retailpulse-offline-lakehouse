-- 指标：订单量
-- 口径：统计周期内提交订单数，按 order_id 去重。

SELECT
  dt,
  sum(order_count) AS order_count
FROM dws_trade_day_summary
GROUP BY dt;

