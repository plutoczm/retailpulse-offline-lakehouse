# 公开大规模数据集画像

数据集：RecSys Challenge 2025 / Synerise Online Retail Dataset

本地位置：

```text
external_data/synerise-recsys-2025/
```

下载结果：

| 项目 | 数值 |
| --- | ---: |
| 压缩包大小 | 1.92GB |
| 解压后项目占用 | 4.35GB |
| SHA256 | `e90b8fded8bc7a87b8c51ced7d5eead75f6deb09852ea701f5f22934e78b66e7` |

明细表：

| 文件 | 行数 | 列 | 文件大小 |
| --- | ---: | --- | ---: |
| `page_visit.parquet` | 199,451,980 | `client_id`, `timestamp`, `url` | 1,917.7MB |
| `search_query.parquet` | 13,223,769 | `client_id`, `timestamp`, `query` | 335.7MB |
| `add_to_cart.parquet` | 7,541,117 | `client_id`, `timestamp`, `sku` | 100.5MB |
| `remove_from_cart.parquet` | 2,688,894 | `client_id`, `timestamp`, `sku` | 34.8MB |
| `product_buy.parquet` | 2,318,502 | `client_id`, `timestamp`, `sku` | 30.1MB |
| `product_properties.parquet` | 1,534,050 | `sku`, `category`, `price`, `name` | 64.2MB |

用途：

- 用作 RetailPulse 企业级行为日志扩展数据。
- 验证 Spark 读取 Parquet 大表、按时间字段派生分区、构建用户行为漏斗。
- 与当前模拟交易事实表形成互补：模拟数据负责完整交易链路，公开数据负责真实行为规模。
