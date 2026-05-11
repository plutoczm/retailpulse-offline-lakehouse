-- 指标：支付金额
-- 口径：统计周期内支付成功流水金额总和。

SELECT
  dt,
  sum(pay_amount) AS pay_amount
FROM dws_trade_day_summary
GROUP BY dt;

