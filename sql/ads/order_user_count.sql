-- 指标：下单用户数
-- 口径：统计周期内提交订单的去重用户数。

SELECT
  dt,
  sum(order_user_count) AS order_user_count
FROM dws_trade_day_summary
GROUP BY dt;

