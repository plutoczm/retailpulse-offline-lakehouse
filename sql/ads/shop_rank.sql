-- 指标：店铺销售排行
-- 口径：按统计日店铺销售额降序排名。

SELECT *
FROM (
  SELECT
    dt,
    shop_id,
    sales_quantity,
    sales_amount,
    buyer_count,
    row_number() OVER (PARTITION BY dt ORDER BY sales_amount DESC) AS rank_no
  FROM dws_shop_day_summary
) t
WHERE rank_no <= 100;

