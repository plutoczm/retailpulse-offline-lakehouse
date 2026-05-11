# 数据仓库设计

## 建模目标

RetailPulse 数仓围绕电商零售经营分析建设，目标是同时支撑交易分析、支付转化、退款分析、复购留存、商品排行、用户分层和库存周转。

## ODS 层

ODS 保留源系统结构，只做字段名规范、日期格式统一、加载时间补充。

| 表 | 来源 | 粒度 | 分区 |
| --- | --- | --- | --- |
| `ods_users` | `users.csv` | 用户 | `dt` 装载日期 |
| `ods_products` | `products.csv` | 商品 | `dt` 装载日期 |
| `ods_shops` | `shops.csv` | 店铺 | `dt` 装载日期 |
| `ods_orders` | `orders.csv` | 订单 | `dt` 订单日期 |
| `ods_order_items` | `order_items.csv` | 订单明细 | `dt` 订单日期 |
| `ods_payments` | `payments.csv` | 支付流水 | `dt` 支付日期 |
| `ods_refunds` | `refunds.csv` | 退款流水 | `dt` 退款日期 |
| `ods_user_events` | `user_events.csv` | 用户行为事件 | `dt` 事件日期 |
| `ods_inventory_logs` | `inventory_logs.csv` | 库存流水 | `dt` 变更日期 |
| `ods_synerise_page_visit` | Synerise `page_visit.parquet` | 用户页面访问 | `dt` 事件日期 |
| `ods_synerise_search_query` | Synerise `search_query.parquet` | 用户搜索 | `dt` 事件日期 |
| `ods_synerise_add_to_cart` | Synerise `add_to_cart.parquet` | 用户加购 | `dt` 事件日期 |
| `ods_synerise_remove_from_cart` | Synerise `remove_from_cart.parquet` | 用户移除购物车 | `dt` 事件日期 |
| `ods_synerise_product_buy` | Synerise `product_buy.parquet` | 用户购买 | `dt` 事件日期 |
| `ods_synerise_product_properties` | Synerise `product_properties.parquet` | 商品属性快照 | `dt` 装载日期 |

## DWD 层

DWD 是清洗后的事实明细层，负责去重、空值处理、状态标准化、时间标准化和金额基础校验。

| 表 | 粒度 | 主要用途 |
| --- | --- | --- |
| `dwd_trade_order_detail` | 订单商品行 | GMV、商品销售、品类销售、店铺销售 |
| `dwd_trade_payment_detail` | 支付流水 | 支付金额、支付转化、RFM |
| `dwd_trade_refund_detail` | 退款流水 | 退款率、退款原因分析 |
| `dwd_user_behavior_detail` | 用户行为事件 | 行为漏斗、活跃、留存 |
| `dwd_inventory_change_detail` | 库存流水 | 库存出入库、库存周转 |
| `dwd_synerise_user_behavior_detail` | 真实公开用户行为事件 | 真实行为漏斗、活跃、搜索、加购、购买分析 |

### Synerise 行为明细接入

Synerise 公开数据作为企业级真实行为数据资产接入，与 RetailPulse 自研模拟交易数据并行保留。ODS 层保持源表语义，DWD 层统一为 `dwd_synerise_user_behavior_detail`：

| 源表 | DWD `event_type` | 关键字段 |
| --- | --- | --- |
| `page_visit` | `view` | `client_id`, `url_id`, `event_time` |
| `search_query` | `search` | `client_id`, `query_hash`, `query_text`, `event_time` |
| `add_to_cart` | `cart` | `client_id`, `sku`, `category_id`, `event_time` |
| `remove_from_cart` | `remove_cart` | `client_id`, `sku`, `category_id`, `event_time` |
| `product_buy` | `pay` | `client_id`, `sku`, `category_id`, `event_time` |

`event_id` 使用 `source_dataset + source_event_type + client_id + event_time + sku/url/query_hash` 生成 SHA256，保证同一源事件可重复计算出稳定主键。SKU 类行为会关联 `ods_synerise_product_properties` 补充品类、价格和商品名称。

## DIM 层

| 表 | 主键 | 说明 |
| --- | --- | --- |
| `dim_user` | `user_id` | 用户属性、年龄段、会员状态 |
| `dim_product` | `product_id` | 商品属性、品牌、价格、品类、店铺 |
| `dim_shop` | `shop_id` | 店铺属性、类型、城市、评分 |
| `dim_category` | `category_id` | 品类维度 |
| `dim_date` | `date_id` | 日期维度 |

维表输出也带 `dt` 分区。用户、商品、店铺等维表使用处理日期作为快照分区；日期维度使用自然日期作为分区。

## DWS 层

| 表 | 粒度 | 指标方向 |
| --- | --- | --- |
| `dws_trade_day_summary` | 日期 | GMV、订单、支付、退款 |
| `dws_user_day_summary` | 日期 + 用户 | 用户下单、支付、行为、退款 |
| `dws_product_day_summary` | 日期 + 商品 | 商品销量、销售额、买家数 |
| `dws_shop_day_summary` | 日期 + 店铺 | 店铺销售和买家 |
| `dws_category_day_summary` | 日期 + 品类 | 品类销售排行 |
| `dws_user_retention_summary` | cohort 日期 + 留存天数 | 次日、7 日留存 |
| `dws_inventory_day_summary` | 日期 + 商品 + 店铺 | 入库、出库、期末库存 |
| `dws_synerise_behavior_day_summary` | 日期 | 真实行为事件量、活跃用户、漏斗转化 |
| `dws_synerise_event_type_day_summary` | 日期 + 行为类型 | 访问、搜索、加购、购买趋势 |
| `dws_synerise_product_day_summary` | 日期 + SKU | 真实商品行为 TopN |
| `dws_synerise_category_day_summary` | 日期 + 品类 | 真实品类行为 TopN |

## ADS 层

| 表 | 应用场景 |
| --- | --- |
| `ads_retail_dashboard_daily` | 经营大盘 |
| `ads_product_topn` | 商品销售 TopN |
| `ads_category_topn` | 品类销售 TopN |
| `ads_shop_rank` | 店铺销售排行 |
| `ads_user_retention` | 留存分析 |
| `ads_rfm_user_segment` | 用户分层 |
| `ads_refund_analysis` | 退款原因和退款状态分析 |
| `ads_inventory_turnover` | 库存周转 |
| `ads_synerise_behavior_dashboard_daily` | 真实行为数据大盘 |
| `ads_synerise_event_type_trend` | 真实行为类型趋势 |
| `ads_synerise_product_topn` | 真实商品购买 TopN |
| `ads_synerise_category_topn` | 真实品类购买 TopN |

## 分区策略

- 交易、支付、退款、行为、库存事实表按业务发生日期 `dt` 分区。
- 维表按快照日期或自然日期 `dt` 分区。
- DWS 和 ADS 延续 `dt` 分区，便于增量重跑单日数据。

## 事实表与维度表划分

- 事实表记录业务过程和可度量数值，例如订单金额、支付金额、退款金额、库存变动数量。
- 维度表描述分析视角，例如用户属性、商品品类、店铺类型、日期属性。
- DWD 事实表尽量保持明细粒度，DWS 再做主题汇总，ADS 面向看板输出。

## 指标口径原则

- GMV 使用下单应付金额，不要求支付成功。
- 支付金额只统计 `pay_status = 'success'`。
- 退款金额只统计 `refund_status = 'approved'`。
- 转化率和退款率都使用安全除法，分母为 0 时结果为 0。
- 留存基于用户行为活跃，cohort 为某日活跃用户集合。
- RFM 使用支付成功流水计算最近一次消费、消费频次和消费金额。
