-- 指标：复购率
-- 口径：统计日内支付订单数大于等于 2 的用户数 / 支付用户数。

SELECT
  dt,
  count(DISTINCT CASE WHEN pay_order_count >= 2 THEN user_id END) AS repeat_paid_users,
  count(DISTINCT CASE WHEN pay_order_count > 0 THEN user_id END) AS paid_users,
  CASE
    WHEN count(DISTINCT CASE WHEN pay_order_count > 0 THEN user_id END) = 0 THEN 0
    ELSE count(DISTINCT CASE WHEN pay_order_count >= 2 THEN user_id END)
      / count(DISTINCT CASE WHEN pay_order_count > 0 THEN user_id END)
  END AS repeat_purchase_rate
FROM dws_user_day_summary
GROUP BY dt;

