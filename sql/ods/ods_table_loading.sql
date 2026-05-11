-- ODS 层保留源表结构，统一日期字段和加载时间。
-- 实际执行由 jobs/ods_load.py 完成，以下 SQL 用于说明建模逻辑。

CREATE TABLE IF NOT EXISTS ods_orders (
  order_id STRING,
  user_id STRING,
  shop_id STRING,
  order_time TIMESTAMP,
  order_status STRING,
  total_amount DECIMAL(18,2),
  discount_amount DECIMAL(18,2),
  payable_amount DECIMAL(18,2),
  province STRING,
  city STRING,
  ods_load_time TIMESTAMP
)
USING PARQUET
PARTITIONED BY (dt STRING);

