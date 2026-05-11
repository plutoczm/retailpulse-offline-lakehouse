-- 指标：GMV
-- 口径：统计周期内下单订单的应付金额总和，不要求支付成功。

SELECT
  dt,
  sum(gmv) AS gmv
FROM dws_trade_day_summary
GROUP BY dt;

