# 企业级公开数据集

## 选型结论

本项目新增真实公开大规模数据入口，默认使用 RecSys Challenge 2025 / Synerise Online Retail Dataset。

| 数据集 | 规模 | 业务匹配度 | 下载位置 |
| --- | ---: | --- | --- |
| RecSys Challenge 2025 / Synerise | 约 1.9GB 压缩包，解压后仍低于 40GB | 真实在线零售用户行为，包含购买、加购、移除购物车、页面访问、搜索、商品属性 | `external_data/synerise-recsys-2025/` |

选择原因：

- 数据来自真实在线零售场景，比纯模拟数据更适合解释企业级用户行为分析。
- 体量足够大，适合验证 Spark 批处理、分区、Parquet 和指标聚合链路。
- 官方提供直接下载地址，不依赖 Kaggle 登录或浏览器手工下载。
- 字段能补强当前 RetailPulse 的行为日志和商品侧数据资产。

## 下载命令

```powershell
conda activate retailpulse-lakehouse
cd E:\Projects\retailpulse-offline-lakehouse

python scripts/download_public_data.py --dataset synerise-recsys-2025 --extract
```

下载后目录：

```text
external_data/
  synerise-recsys-2025/
    synerise_dataset.tar.gz
    dataset_manifest.json
    extracted/
```

`dataset_manifest.json` 会记录数据源页面、下载 URL、文件大小、SHA256 和下载时间，便于简历项目复盘。

当前本机已下载并解压，画像见 `reports/public_dataset_profile.md`。数据总占用约 4.35GB，其中 `page_visit.parquet` 约 1.99 亿行，适合用于 Spark 大表扫描、过滤、分区和聚合优化演示。

完整入仓验收见 `reports/synerise_pipeline_report.md`。

## 与 RetailPulse 的关系

当前主链路仍使用 RetailPulse 自研模拟交易数据，保证完整的 ODS/DWD/DIM/DWS/ADS 分层和数据质量闭环可复现。

Synerise 数据作为企业级外部数据资产，已经通过以下作业纳入 ODS/DWD：

```powershell
python scripts/run_synerise_pipeline.py --input external_data/synerise-recsys-2025/extracted --data-root data
```

输出表：

| 层级 | 表 |
| --- | --- |
| ODS | `ods_synerise_page_visit`、`ods_synerise_search_query`、`ods_synerise_add_to_cart`、`ods_synerise_remove_from_cart`、`ods_synerise_product_buy`、`ods_synerise_product_properties` |
| DWD | `dwd_synerise_user_behavior_detail` |
| DWS | `dws_synerise_behavior_day_summary`、`dws_synerise_event_type_day_summary`、`dws_synerise_product_day_summary`、`dws_synerise_category_day_summary` |
| ADS | `ads_synerise_behavior_dashboard_daily`、`ads_synerise_event_type_trend`、`ads_synerise_product_topn`、`ads_synerise_category_topn` |

后续可继续用于以下扩展：

- 替换或增强 `user_events` 行为日志。
- 构建真实用户行为漏斗：访问 -> 加购 -> 购买。
- 做商品召回、推荐特征、用户兴趣画像。
- 用 Spark 将原始行为数据落入 HDFS/ODS，再产出行为宽表和留存分析。

## 其他备选

| 数据集 | 取舍 |
| --- | --- |
| RetailRocket recommender dataset | 经典电商行为数据，但体量更小，部分下载渠道需要登录。 |
| Instacart Market Basket Analysis | 适合购物篮和复购分析，但公开下载常依赖 Kaggle 授权。 |
| Amazon Reviews 2023 | 品类多、规模大，但部分品类很大且偏评论/商品元数据，不如 Synerise 行为链路贴合当前项目。 |
