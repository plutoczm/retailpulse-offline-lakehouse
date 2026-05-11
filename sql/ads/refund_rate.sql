-- 指标：退款率
-- 口径：已通过退款金额 / 支付成功金额。

SELECT
  dt,
  refund_amount,
  pay_amount,
  CASE WHEN pay_amount = 0 THEN 0 ELSE refund_amount / pay_amount END AS refund_rate
FROM dws_trade_day_summary;

