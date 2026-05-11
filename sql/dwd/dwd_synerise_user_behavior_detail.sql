-- Unified DWD behavior detail for the Synerise public ecommerce dataset.

CREATE TABLE IF NOT EXISTS dwd_synerise_user_behavior_detail (
  event_id STRING,
  client_id BIGINT,
  user_id STRING,
  event_type STRING,
  source_event_type STRING,
  event_time TIMESTAMP,
  sku BIGINT,
  product_id STRING,
  category_id BIGINT,
  product_price DOUBLE,
  product_name STRING,
  url_id BIGINT,
  query_hash STRING,
  query_text STRING,
  source_dataset STRING
)
USING PARQUET
PARTITIONED BY (dt STRING);

-- Event type mapping:
-- page_visit       -> view
-- search_query     -> search
-- add_to_cart      -> cart
-- remove_from_cart -> remove_cart
-- product_buy      -> pay

SELECT
  event_id,
  client_id,
  user_id,
  event_type,
  source_event_type,
  event_time,
  sku,
  product_id,
  category_id,
  product_price,
  product_name,
  url_id,
  query_hash,
  query_text,
  source_dataset,
  dt
FROM dwd_synerise_user_behavior_detail;
