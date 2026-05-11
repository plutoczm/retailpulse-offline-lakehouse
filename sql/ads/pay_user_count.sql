-- 指标：支付用户数
-- 口径：统计周期内支付成功的去重用户数。

SELECT
  dt,
  sum(pay_user_count) AS pay_user_count
FROM dws_trade_day_summary
GROUP BY dt;

