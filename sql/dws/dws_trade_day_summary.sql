-- DWS 交易日汇总：每日经营大盘粒度。

WITH order_fact AS (
  SELECT
    dt,
    order_id,
    user_id,
    max(payable_amount) AS payable_amount
  FROM dwd_trade_order_detail
  GROUP BY dt, order_id, user_id
),
pay_fact AS (
  SELECT
    dt,
    order_id,
    user_id,
    pay_amount
  FROM dwd_trade_payment_detail
  WHERE pay_status = 'success'
),
refund_fact AS (
  SELECT
    dt,
    order_id,
    refund_amount
  FROM dwd_trade_refund_detail
  WHERE refund_status = 'approved'
)
SELECT
  o.dt,
  count(DISTINCT o.order_id) AS order_count,
  count(DISTINCT o.user_id) AS order_user_count,
  sum(o.payable_amount) AS gmv,
  count(DISTINCT p.order_id) AS pay_order_count,
  count(DISTINCT p.user_id) AS pay_user_count,
  sum(p.pay_amount) AS pay_amount,
  count(DISTINCT r.order_id) AS refund_order_count,
  sum(r.refund_amount) AS refund_amount
FROM order_fact o
LEFT JOIN pay_fact p ON o.order_id = p.order_id
LEFT JOIN refund_fact r ON o.order_id = r.order_id
GROUP BY o.dt;

