-- 指标：7 日留存率
-- 口径：cohort 日活跃用户中，第 7 日仍活跃的用户数 / cohort 活跃用户数。

SELECT
  cohort_dt,
  cohort_users,
  retained_users AS seven_day_retained_users,
  retention_rate AS seven_day_retention_rate,
  dt
FROM dws_user_retention_summary
WHERE day_diff = 7;

