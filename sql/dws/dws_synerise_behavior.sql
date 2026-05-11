-- Synerise DWS behavior summaries.

CREATE TABLE IF NOT EXISTS dws_synerise_behavior_day_summary (
  event_count BIGINT,
  active_user_count BIGINT,
  view_user_count BIGINT,
  search_user_count BIGINT,
  cart_user_count BIGINT,
  remove_cart_user_count BIGINT,
  pay_user_count BIGINT,
  view_event_count BIGINT,
  search_event_count BIGINT,
  cart_event_count BIGINT,
  remove_cart_event_count BIGINT,
  pay_event_count BIGINT,
  view_to_cart_rate DOUBLE,
  cart_to_pay_rate DOUBLE,
  view_to_pay_rate DOUBLE
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS dws_synerise_event_type_day_summary (
  event_type STRING,
  event_count BIGINT,
  active_user_count BIGINT,
  active_sku_count BIGINT
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS dws_synerise_product_day_summary (
  sku BIGINT,
  category_id BIGINT,
  product_name STRING,
  event_count BIGINT,
  cart_event_count BIGINT,
  remove_cart_event_count BIGINT,
  pay_event_count BIGINT,
  active_user_count BIGINT,
  avg_product_price DOUBLE
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS dws_synerise_category_day_summary (
  category_id BIGINT,
  event_count BIGINT,
  cart_event_count BIGINT,
  remove_cart_event_count BIGINT,
  pay_event_count BIGINT,
  active_user_count BIGINT,
  active_sku_count BIGINT
)
USING PARQUET
PARTITIONED BY (dt STRING);
