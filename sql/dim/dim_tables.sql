-- DIM 层维表：用户、商品、店铺、品类、日期。

CREATE OR REPLACE TEMP VIEW dim_category AS
SELECT DISTINCT
  category_id,
  category_name,
  1 AS category_level,
  '${process_dt}' AS dt
FROM ods_products
WHERE category_id IS NOT NULL;

