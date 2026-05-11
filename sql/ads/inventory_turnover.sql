-- 指标：库存周转率
-- 口径：销售数量 / 平均库存。

SELECT
  i.dt,
  i.product_id,
  i.shop_id,
  coalesce(p.sales_quantity, 0) AS sales_quantity,
  (i.avg_before_quantity + i.ending_quantity) / 2 AS avg_inventory,
  CASE
    WHEN (i.avg_before_quantity + i.ending_quantity) = 0 THEN 0
    ELSE coalesce(p.sales_quantity, 0) / ((i.avg_before_quantity + i.ending_quantity) / 2)
  END AS inventory_turnover_rate
FROM dws_inventory_day_summary i
LEFT JOIN dws_product_day_summary p
  ON i.dt = p.dt
 AND i.product_id = p.product_id;

