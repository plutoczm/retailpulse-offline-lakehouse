# Retail Analytics Agent Design

## 目标

RetailPulse Agent 将自然语言经营问题转换成 **可审计的受控分析计划**，执行 ADS serving mart，再让模型基于真实 ToolResult 生成结构化结论。

它不是可以任意访问数据库的 autonomous agent。Agent 能力包括多步计划、工具选择、工具执行、能力缺口识别和 evidence-key grounding。

## Planner

当前 `QueryPlanner` 是确定性 `rules-v2` planner。每次最多 6 个调用，模型不能指定 SQL、表名、文件路径或代码。

## Tool surface

- `get_kpi`：读取指标目录中的 KPI。
- `compare_periods`：相邻时间窗口对比；比例指标按分子分母重新聚合，不平均 daily rate。
- `breakdown_by_dimension`：受控维度下钻。
- `get_topn`：白名单维度排序，最多 10 条。
- `detect_anomaly`：日序列 population z-score 运营提示，至少 5 个观测。

支持维度：

- `product`
- `category`
- `shop`
- `channel`
- `refund_reason`
- `user_segment`

其中 `channel` 指 **用户获客渠道**，数据来自 `dim_user.channel -> dws_channel_day_summary -> ads_channel_summary`。它不是行为日志的 `source_channel`。

当前已知 coverage gaps：`campaign`、`region`。

## Grounding contract

成功工具返回唯一 `evidence_key`，例如：

```text
kpi:gmv
compare:gmv:3d
breakdown_by_dimension:channel:gmv
get_topn:product:sales_amount
```

模型返回严格结构化 `summary / observations / actions / caveats`，每条 observation 的 `evidence_keys` 都必须是本次成功工具结果的子集。违反契约会触发 deterministic fallback。

## 为什么规则 Planner 仍然合理

当前 intent 小且稳定，规则 Planner 的优势是可解释、低延迟、零额外 token、离线可重复 eval。等 routing intent 规模明显扩大，再替换为 structured LLM planner；Tool schema、参数校验、调用上限和 grounding policy 保持不变。

## Evaluation

CI 同时运行：

1. KPI retrieval recall。
2. Tool routing recall（工具、维度、coverage gap）。
3. Agent/API 单测。
4. Docker 内真实 Agent 请求。
5. Spark 数据单测，包括 channel 聚合口径。
6. tiny lakehouse 端到端 quality gate。

## 下一阶段

1. 基于订单 `province/city` 建 region serving mart。
2. 如果引入真实 campaign/promotion 数据，再建 campaign attribution；不要只为 Agent 造字段。
3. 增加 contribution analysis，回答“哪个维度贡献了总指标变化”。
4. 增加 tool-result → answer 的 numeric faithfulness eval。
5. 多实例部署时将进程内 cache/rate limiter 迁移到 Redis。
