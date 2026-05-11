-- 指标：品类销售 TopN
-- 口径：按统计日品类销售额降序排名。

SELECT *
FROM (
  SELECT
    dt,
    category_id,
    category_name,
    sales_quantity,
    sales_amount,
    row_number() OVER (PARTITION BY dt ORDER BY sales_amount DESC) AS rank_no
  FROM dws_category_day_summary
) t
WHERE rank_no <= 20;

