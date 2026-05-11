# Synerise 真实行为数据入仓验收报告

执行日期：2026-05-11

## 数据源

| 项目 | 内容 |
| --- | --- |
| 数据集 | RecSys Challenge 2025 / Synerise Online Retail Dataset |
| 本地目录 | `external_data/synerise-recsys-2025/extracted` |
| 业务日期范围 | `2022-06-23` 至 `2022-12-08` |
| 原始压缩包 | 1.92GB |
| 解压后占用 | 约 4.35GB |

## ODS 入仓结果

| ODS 表 | 行数 | 分区数 | 体积 |
| --- | ---: | ---: | ---: |
| `ods_synerise_page_visit` | 199,451,980 | 169 | 1.792GB |
| `ods_synerise_search_query` | 13,223,769 | 169 | 0.330GB |
| `ods_synerise_add_to_cart` | 7,541,117 | 169 | 0.116GB |
| `ods_synerise_remove_from_cart` | 2,688,894 | 169 | 0.048GB |
| `ods_synerise_product_buy` | 2,318,502 | 169 | 0.041GB |
| `ods_synerise_product_properties` | 1,534,050 | 1 | 0.062GB |

## DWD 入仓结果

| DWD 表 | 行数 | 分区数 | 体积 |
| --- | ---: | ---: | ---: |
| `dwd_synerise_user_behavior_detail` | 225,224,262 | 169 | 16.211GB |

说明：DWD 行数等于五类行为事件合计，不包含商品属性表。商品属性通过 `sku` 关联补充到 SKU 类行为上。

## DWS 汇总结果

| DWS 表 | 行数 | 体积 |
| --- | ---: | ---: |
| `dws_synerise_behavior_day_summary` | 169 | 0.7MB |
| `dws_synerise_event_type_day_summary` | 845 | 0.2MB |
| `dws_synerise_product_day_summary` | 5,348,178 | 257.7MB |
| `dws_synerise_category_day_summary` | 545,435 | 13.5MB |

## ADS 结果

| ADS 表 | 行数 | 体积 |
| --- | ---: | ---: |
| `ads_synerise_behavior_dashboard_daily` | 169 | 0.7MB |
| `ads_synerise_event_type_trend` | 845 | 0.2MB |
| `ads_synerise_product_topn` | 8,450 | 1.1MB |
| `ads_synerise_category_topn` | 8,450 | 0.7MB |

## 大屏接入

`dashboard/data/dashboard.json` 已刷新，包含：

- RetailPulse 模拟交易 ADS 指标。
- Synerise 真实行为漏斗指标。
- Synerise 商品购买 TopN。
- 公开 Parquet 数据资产画像。

Synerise 原始数据最后一天只覆盖到 `2022-12-08 00:09` 左右，因此大屏会自动选择最新非稀疏日期 `2022-12-07` 作为真实行为展示日期。

`2022-12-07` 样例指标：

| 指标 | 数值 |
| --- | ---: |
| 行为事件数 | 2,005,131 |
| 活跃用户数 | 400,850 |
| 访问事件数 | 1,750,025 |
| 加购事件数 | 81,179 |
| 购买事件数 | 21,906 |
| 访问到购买转化率 | 3.17% |

## 执行命令

```powershell
$env:RETAILPULSE_SPARK_DRIVER_MEMORY='6g'
python scripts/run_synerise_pipeline.py --input external_data\synerise-recsys-2025\extracted --data-root data --start-date 2022-06-23 --end-date 2022-12-08 --shuffle-partitions 96 --output-partitions 96

python jobs/synerise_dws_aggregate.py --input data --output data\dws --start-date 2022-06-23 --end-date 2022-12-08 --shuffle-partitions 128 --output-partitions 64
python jobs/synerise_ads_metrics.py --input data --output data\ads --start-date 2022-06-23 --end-date 2022-12-08 --shuffle-partitions 96 --topn 50
python scripts/export_dashboard_data.py --data-root data --external-root external_data\synerise-recsys-2025\extracted --output dashboard\data\dashboard.json --topn 10
```
