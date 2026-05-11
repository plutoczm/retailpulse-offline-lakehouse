# Spark 性能优化说明

## 为什么使用 Parquet

Parquet 是列式存储格式，适合离线分析场景。经营指标通常只读取部分字段，例如 `dt`、`order_id`、`pay_amount`，列式读取可以减少 IO。Parquet 还支持压缩和谓词下推，比 CSV 更适合作为 ODS 之后的湖仓存储格式。

## 为什么按 dt 分区

电商离线指标大多按天计算，`dt` 是最常见的增量边界。按 `dt` 分区后，单日重跑只需要扫描对应日期的数据，质量检查也能快速发现某天分区是否缺失。

## broadcast join 适用场景

维表通常远小于事实表，例如商品、店铺、用户快照相对订单明细更小。DWD 和 ADS 中对商品、店铺等维表使用 `broadcast()`，可以避免大表和小表之间产生高成本 shuffle join。

## cache/persist 的使用位置

`dwd_clean.py` 中的订单明细在后续写出和检查中会复用，使用 `MEMORY_AND_DISK`。`dws_aggregate.py` 中订单明细和支付流水会被多个主题汇总复用，也使用 `persist`。这样可以避免重复扫描 Parquet 和重复计算上游依赖。

## shuffle 产生的原因

Spark 中 `groupBy`、`distinct`、`join`、窗口排序等宽依赖会触发 shuffle。本项目中 DWS 日汇总、商品排行、留存 cohort、RFM 聚合都会产生 shuffle。通过合理分区数、broadcast join 和提前过滤日期范围降低 shuffle 数据量。

## 数据倾斜如何处理

可能倾斜的字段包括热门商品、头部店铺和大促日期。处理方式包括：

- 先按 `dt` 过滤，减少单次处理范围。
- 对小维表使用 broadcast join。
- 对严重倾斜 key 可做 salting，将热点 key 加随机前缀后两阶段聚合。
- 对 TopN 先做局部聚合，再做全局排序。
- 大促日期可以独立调大 executor 和 shuffle partitions。

## 小文件问题如何处理

本地项目输出前使用 `coalesce(1)` 或 `coalesce(2)` 控制文件数量。生产环境不应所有表都 coalesce 到 1，而应根据数据量设置合理分区，或者使用合并小文件作业、表格式 compaction、动态分区写入治理。

## 百万级到亿级如何扩展

- 存储从本地目录迁移到 HDFS、S3 或 MinIO。
- 调度从本地脚本迁移到 Airflow、DolphinScheduler 或类似平台。
- 计算从 `local[*]` 切换到 Spark standalone、YARN 或 Kubernetes。
- DWD 按天增量写入，避免全量重算。
- 对订单、行为等大表使用更细粒度分区或 bucketing。
- 指标层拆分为日增量、周月汇总和历史快照。
- 引入 Delta/Iceberg/Hudi 管理 ACID、schema evolution 和 compaction。

## 当前代码中的优化点

| 位置 | 优化 |
| --- | --- |
| `ods_load.py` | CSV 只作为入口，后续统一写 Parquet |
| `dwd_clean.py` | 维表关联使用 `broadcast`，事实表去重清洗 |
| `dws_aggregate.py` | 复用的订单明细和支付流水使用 `persist` |
| `ads_metrics.py` | TopN 使用窗口函数，商品和店铺维表 broadcast |
| 全链路 | 输出按 `dt` 分区并控制小文件数量 |

