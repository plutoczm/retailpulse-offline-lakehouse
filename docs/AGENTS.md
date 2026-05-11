# 多 Agent 协作说明

本项目采用多 Agent 协作方式完成。每个 Agent 对应一个清晰的项目职责域，并通过文件产出和验收标准保证最终项目可运行、可解释、可写入简历。

## Agent A：Project Manager Agent

职责：

- 控制项目范围和迭代节奏。
- 制定项目里程碑。
- 确保项目能在 Windows 11 + VSCode + Docker Desktop 环境下运行。
- 确保项目最终能写进简历，并能在面试中讲清楚。

产出文件：

- `docs/PROJECT_PLAN.md`
- `README.md` 中的项目定位、运行步骤、简历写法和 3 分钟讲解稿

验收标准：

- 项目范围不依赖外部开源仓库代码。
- 本地模式至少能跑通一条完整链路。
- README 能在 5 分钟内让面试官理解项目价值。

## Agent B：Business Modeling Agent

职责：

- 设计电商零售业务域。
- 定义用户注册、浏览商品、加购、下单、支付、发货、收货、退款、评价等核心流程。
- 梳理用户、商品、店铺、订单、支付、退款、行为、库存等实体关系。

产出文件：

- `docs/BUSINESS_PROCESS.md`
- `docs/ARCHITECTURE.md` 中的业务上下文

验收标准：

- 业务流程贴近真实电商零售平台。
- 源表字段能支撑交易、转化、复购、留存、库存分析。

## Agent C：Data Warehouse Architect Agent

职责：

- 设计 ODS、DWD、DIM、DWS、ADS 分层。
- 设计事实表、维度表、主题汇总表和应用指标表。
- 设计分区策略和指标口径。

产出文件：

- `docs/DATA_WAREHOUSE_DESIGN.md`
- `sql/ods/`、`sql/dwd/`、`sql/dim/`、`sql/dws/`、`sql/ads/`

验收标准：

- 分层职责清楚。
- 每张表有明确来源、主键或粒度、分区策略。
- 指标表能支撑 README 和报表样例。

## Agent D：Data Generator Agent

职责：

- 编写模拟数据生成脚本。
- 默认生成至少 90 天数据。
- 默认支持用户 10,000、商品 5,000、店铺 500、订单 300,000、订单明细约 600,000、支付 260,000、退款 30,000、用户行为 2,000,000、库存流水 300,000。
- 支持命令行参数控制数据规模。
- 生成数据到 `data/raw/`。

产出文件：

- `scripts/generate_data.py`
- `tests/test_data_generator.py`

验收标准：

- 9 张源表均可生成。
- 字段不止 `id/name`，包含时间、金额、状态、渠道、城市、设备、库存变动等业务字段。
- 小规模生成可在本地快速完成。

## Agent E：Spark ETL Agent

职责：

- 使用 PySpark 实现 `raw -> ODS -> DWD -> DIM -> DWS -> ADS`。
- 输出 Parquet，按 `dt` 分区。
- 使用 Spark SQL 和 DataFrame API。
- 使用 broadcast join、cache/persist、coalesce/repartition 做基础优化。
- 添加日志和异常处理。

产出文件：

- `jobs/ods_load.py`
- `jobs/dwd_clean.py`
- `jobs/dim_build.py`
- `jobs/dws_aggregate.py`
- `jobs/ads_metrics.py`

验收标准：

- 每个 job 有 `main` 函数和命令行参数。
- 小规模数据能跑完整链路。
- 输出层级目录符合 `data/{ods,dwd,dim,dws,ads}/表名/`。

## Agent F：Metric Analyst Agent

职责：

- 设计并实现核心经营指标。
- 至少包含 GMV、支付订单数、下单用户数、支付用户数、支付转化率、客单价、退款率、复购率、次日留存率、7 日留存率、商品销售 TopN、品类销售 TopN、店铺销售排行、RFM 用户分层、库存周转率。
- 每个指标提供 SQL 文件和口径说明。

产出文件：

- `sql/ads/*.sql`
- `docs/METRICS.md`
- `reports/metric_samples.md`
- `tests/test_metric_logic.py`

验收标准：

- SQL 与 ADS 表设计一致。
- 指标定义包含名称、业务解释、公式、依赖表、层级和面试解释话术。

## Agent G：Data Quality Agent

职责：

- 增加数据质量校验。
- 检查主键重复、关键字段为空、金额异常、支付与订单金额不一致、支付时间早于下单时间、退款金额大于支付金额、维表关联缺失、每日分区为空、事件类型非法、库存流水数量异常。
- 输出 Markdown 报告。

产出文件：

- `scripts/run_quality_checks.py`
- `reports/data_quality_report.md`
- `tests/test_data_quality.py`

验收标准：

- 质量规则不少于 10 项。
- 报告包含规则名、检查对象、状态、异常数和说明。
- 小规模链路后可生成报告。

## Agent H：Performance Optimization Agent

职责：

- 对 Spark 作业添加性能优化。
- 解释 Parquet、`dt` 分区、broadcast join、cache/persist、shuffle、数据倾斜、小文件治理和亿级扩展方案。

产出文件：

- `docs/SPARK_OPTIMIZATION.md`
- Spark 作业中的优化注释和实现

验收标准：

- 文档能讲清楚为什么这样设计。
- 代码中体现可执行的优化动作。

## Agent I：Workflow & DevOps Agent

职责：

- 适配 Windows 11。
- 提供 Makefile、PowerShell 脚本、requirements.txt、pyproject.toml、`.env.example`、`docker-compose.yml`。
- 保证至少本地 Python + PySpark 模式可运行。
- 提供一键执行命令。

产出文件：

- `Makefile`
- `requirements.txt`
- `pyproject.toml`
- `.env.example`
- `docker-compose.yml`
- `scripts/run_all.py`
- `scripts/run_all.ps1`

验收标准：

- `make generate/ods/dwd/dim/dws/ads/quality/all/test` 命令存在。
- PowerShell 用户可以用 `.\scripts\run_all.ps1` 执行。
- Docker Compose 作为可选增强，不阻塞本地模式。

## Agent J：Documentation & Interview Agent

职责：

- 编写 README、架构文档、指标文档、面试问答和参考说明。
- README 体现独立原创项目，不写“二次开发某项目”。
- `docs/INTERVIEW_QA.md` 至少包含 30 个问答。

产出文件：

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/METRICS.md`
- `docs/INTERVIEW_QA.md`
- `docs/REFERENCES.md`

验收标准：

- 文档能支撑简历描述、项目复盘和面试追问。
- 架构图和数据流图使用 Mermaid。
- 口径、难点和优化点讲得清楚。

## 协作规则

1. 所有 Agent 围绕 RetailPulse 自有业务模型工作，不复制外部仓库代码和 README。
2. 代码优先保证本地可运行，其次考虑可扩展。
3. 每个输出文件必须有实际内容，不生成空文件。
4. 文档与代码保持一致，指标口径与 SQL 对齐。
5. 最终验收以小规模一键链路和测试结果为准。

