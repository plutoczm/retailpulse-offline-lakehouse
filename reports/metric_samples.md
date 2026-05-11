# RetailPulse 指标样例

运行 ADS 作业后可读取 `data/ads/` 下的 Parquet 表查看指标结果。

## 核心看板样例字段

| 表 | 字段 | 说明 |
| --- | --- | --- |
| `ads_retail_dashboard_daily` | `gmv` | 当日下单应付金额 |
| `ads_retail_dashboard_daily` | `pay_amount` | 当日成功支付金额 |
| `ads_retail_dashboard_daily` | `pay_conversion_rate` | 支付订单数 / 下单订单数 |
| `ads_product_topn` | `rank_no` | 按销售额排序的商品排名 |
| `ads_user_retention` | `retention_rate` | 留存用户数 / cohort 用户数 |
| `ads_rfm_user_segment` | `user_segment` | RFM 用户分层标签 |

## 本地查看示例

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder.master("local[*]").getOrCreate()
spark.read.parquet("data/ads/ads_retail_dashboard_daily").show(10, truncate=False)
spark.stop()
```

