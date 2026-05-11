-- 指标：商品销售 TopN
-- 口径：按统计日商品销售额降序排名。

SELECT *
FROM (
  SELECT
    dt,
    product_id,
    sales_quantity,
    sales_amount,
    row_number() OVER (PARTITION BY dt ORDER BY sales_amount DESC, sales_quantity DESC) AS rank_no
  FROM dws_product_day_summary
) t
WHERE rank_no <= 20;

