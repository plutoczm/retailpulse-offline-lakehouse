-- Synerise public dataset ODS loading design.
-- Physical loading is implemented in jobs/synerise_ods_load.py because the
-- source files are Parquet and need per-table timestamp normalization.

CREATE TABLE IF NOT EXISTS ods_synerise_page_visit (
  client_id BIGINT,
  raw_timestamp STRING,
  event_time TIMESTAMP,
  url BIGINT,
  source_dataset STRING,
  source_table STRING,
  ods_load_time TIMESTAMP
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS ods_synerise_search_query (
  client_id BIGINT,
  raw_timestamp STRING,
  event_time TIMESTAMP,
  query STRING,
  source_dataset STRING,
  source_table STRING,
  ods_load_time TIMESTAMP
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS ods_synerise_add_to_cart (
  client_id BIGINT,
  raw_timestamp STRING,
  event_time TIMESTAMP,
  sku BIGINT,
  source_dataset STRING,
  source_table STRING,
  ods_load_time TIMESTAMP
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS ods_synerise_remove_from_cart (
  client_id BIGINT,
  raw_timestamp STRING,
  event_time TIMESTAMP,
  sku BIGINT,
  source_dataset STRING,
  source_table STRING,
  ods_load_time TIMESTAMP
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS ods_synerise_product_buy (
  client_id BIGINT,
  raw_timestamp STRING,
  event_time TIMESTAMP,
  sku BIGINT,
  source_dataset STRING,
  source_table STRING,
  ods_load_time TIMESTAMP
)
USING PARQUET
PARTITIONED BY (dt STRING);

CREATE TABLE IF NOT EXISTS ods_synerise_product_properties (
  sku BIGINT,
  category_id BIGINT,
  price DOUBLE,
  product_name STRING,
  source_dataset STRING,
  source_table STRING,
  ods_load_time TIMESTAMP
)
USING PARQUET
PARTITIONED BY (dt STRING);
