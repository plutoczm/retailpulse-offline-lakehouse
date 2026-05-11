-- 指标：RFM 用户分层
-- 口径：基于最近一次支付时间、支付频次、支付金额进行用户分层。

WITH rfm AS (
  SELECT
    user_id,
    datediff('${as_of_dt}', max(to_date(pay_time))) AS recency_days,
    count(DISTINCT order_id) AS frequency,
    sum(pay_amount) AS monetary
  FROM dwd_trade_payment_detail
  WHERE pay_status = 'success'
  GROUP BY user_id
)
SELECT
  user_id,
  recency_days,
  frequency,
  monetary,
  CASE
    WHEN recency_days <= 7 AND frequency >= 10 AND monetary >= 10000 THEN '高价值用户'
    WHEN recency_days <= 30 AND frequency >= 3 THEN '潜力用户'
    WHEN recency_days > 60 THEN '流失风险用户'
    ELSE '一般用户'
  END AS user_segment,
  '${as_of_dt}' AS dt
FROM rfm;

