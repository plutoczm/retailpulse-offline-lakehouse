-- Synerise ADS behavior metrics.

CREATE TABLE IF NOT EXISTS ads_synerise_behavior_dashboard_daily
USING PARQUET
PARTITIONED BY (dt STRING)
AS
SELECT *
FROM dws_synerise_behavior_day_summary;

CREATE TABLE IF NOT EXISTS ads_synerise_event_type_trend
USING PARQUET
PARTITIONED BY (dt STRING)
AS
SELECT *
FROM dws_synerise_event_type_day_summary;

CREATE TABLE IF NOT EXISTS ads_synerise_product_topn
USING PARQUET
PARTITIONED BY (dt STRING)
AS
SELECT *
FROM (
  SELECT
    *,
    row_number() OVER (PARTITION BY dt ORDER BY pay_event_count DESC, cart_event_count DESC) AS rank_no
  FROM dws_synerise_product_day_summary
) t
WHERE rank_no <= 50;

CREATE TABLE IF NOT EXISTS ads_synerise_category_topn
USING PARQUET
PARTITIONED BY (dt STRING)
AS
SELECT *
FROM (
  SELECT
    *,
    row_number() OVER (PARTITION BY dt ORDER BY pay_event_count DESC, cart_event_count DESC) AS rank_no
  FROM dws_synerise_category_day_summary
) t
WHERE rank_no <= 50;
