# RetailPulse 项目计划

## 项目定位

RetailPulse 是一个面向电商零售经营分析的个人原创离线湖仓项目。项目以模拟业务数据为输入，构建从 `raw -> ODS -> DWD/DIM -> DWS -> ADS -> report` 的完整批处理链路，用于展示数据生成、数仓建模、Spark ETL、指标分析、数据质量治理和性能优化能力。

## 业务范围

项目覆盖一家电商零售平台的核心交易链路：

1. 用户注册
2. 浏览、搜索、收藏、加购商品
3. 下单与订单明细
4. 支付与支付转化
5. 发货、收货与评价扩展
6. 退款与售后分析
7. 库存变更与库存周转
8. 用户留存、复购与 RFM 分层

## 技术范围

| 模块 | 技术选择 | 说明 |
| --- | --- | --- |
| 数据生成 | Python | 生成贴近业务的 CSV 源数据 |
| 批处理 | PySpark / Spark SQL | 本地模式可运行，适配 Windows 11 |
| 存储格式 | Parquet | 模拟离线湖仓分层目录 |
| 数据分区 | `dt` | 按业务日期分区，便于增量加工 |
| 质量校验 | PySpark + Markdown Report | 输出可读的数据质量报告 |
| 调度入口 | Makefile / Python / PowerShell | 支持一键执行 |
| 测试 | pytest | 覆盖数据生成、质量规则和指标逻辑 |
| 可选环境 | Docker Compose | 提供 Spark、PostgreSQL、MinIO 示例环境 |

## 里程碑

### M1：项目骨架与设计文档

- 创建项目目录结构。
- 输出项目计划、Agent 分工、业务流程、数仓设计和架构说明。
- 明确 Windows 11 + VSCode + 本地 PySpark 的运行方式。

验收标准：

- `docs/PROJECT_PLAN.md`、`docs/AGENTS.md`、`docs/BUSINESS_PROCESS.md`、`docs/DATA_WAREHOUSE_DESIGN.md` 内容完整。
- README 中能够解释项目价值、架构和运行方式。

### M2：模拟数据生成

- 实现 `scripts/generate_data.py`。
- 默认支持 90 天数据生成。
- 支持命令行参数控制用户、商品、店铺、订单、行为、库存等数据量。
- 输出到 `data/raw/`。

验收标准：

- 生成 9 张源表 CSV。
- 字段符合项目数据模型。
- 小规模参数下可快速运行，用于本地验证。

### M3：离线湖仓分层加工

- 实现 ODS、DWD、DIM、DWS、ADS 五层 PySpark 作业。
- 输出 Parquet，统一使用 `dt` 分区。
- 作业支持 `--input`、`--output`、`--dt`、`--start-date`、`--end-date`。
- 维表关联使用 broadcast join，复用 DataFrame 使用 cache/persist。

验收标准：

- 至少一条链路可运行：`raw -> ODS -> DWD -> DIM -> DWS -> ADS`。
- 每层产出非空 Parquet 数据。
- 作业有日志和异常处理。

### M4：指标与质量治理

- 实现 GMV、订单量、支付转化率、客单价、退款率、复购率、留存、TopN、RFM、库存周转等指标。
- 为每个核心指标提供 SQL 文件和口径说明。
- 实现不少于 10 项数据质量检查。

验收标准：

- `sql/ads/` 下存在指标 SQL。
- `docs/METRICS.md` 说明指标定义、依赖表、公式和面试话术。
- `reports/data_quality_report.md` 能通过脚本生成或刷新。

### M5：性能优化、DevOps 与面试包装

- 输出 Spark 优化文档。
- 提供 Makefile、PowerShell、Python 一键运行入口。
- 输出 30 个以上面试问答。
- README 包含简历写法和 3 分钟讲解稿。

验收标准：

- `make all` 或等价 Python/PowerShell 命令可运行小规模链路。
- `make test` 可执行测试。
- 项目能作为简历项目独立展示。

## 本地执行策略

默认推荐使用本地 Python + PySpark：

```bash
python -m venv .venv
pip install -r requirements.txt
python scripts/run_all.py --scale tiny
python scripts/run_quality_checks.py --input data --output reports/data_quality_report.md
pytest
```

Windows PowerShell 可使用：

```powershell
.\scripts\run_all.ps1 -Scale tiny
```

## 数据量策略

默认参数面向简历展示和完整性，数据量较大：

- 用户：10,000
- 商品：5,000
- 店铺：500
- 订单：300,000
- 订单明细：约 600,000
- 支付：约 260,000
- 退款：约 30,000
- 用户行为：2,000,000
- 库存流水：300,000

为了方便本地快速验证，额外提供 `tiny` 和 `small` 规模：

| 规模 | 适用场景 |
| --- | --- |
| `tiny` | 功能验证、pytest、本地快速演示 |
| `small` | README 截图和指标样例 |
| `default` | 简历项目完整数据规模 |

## 风险与控制

| 风险 | 控制方式 |
| --- | --- |
| Windows Spark 环境配置复杂 | 默认使用 `pyspark` 本地模式，不强依赖集群 |
| 默认数据量较大导致运行慢 | 提供 `--scale tiny/small/default` |
| Parquet 覆盖写误删数据 | 作业只写项目内 `data/` 目录 |
| 小文件过多 | 输出前使用 `coalesce` 或合理 `repartition` |
| 指标口径不清 | `docs/METRICS.md` 与 SQL 一一对应 |
| 项目像模板 | 业务模型、表设计、指标和文档围绕 RetailPulse 独立设计 |

## 阶段交付清单

- 项目计划：`docs/PROJECT_PLAN.md`
- Agent 分工：`docs/AGENTS.md`
- 数据生成：`scripts/generate_data.py`
- 一键执行：`scripts/run_all.py`、`scripts/run_all.ps1`
- 数据质量：`scripts/run_quality_checks.py`
- Spark 作业：`jobs/*.py`
- 指标 SQL：`sql/**/*.sql`
- 文档：`README.md`、`docs/*.md`
- 报告：`reports/*.md`
- 测试：`tests/*.py`

