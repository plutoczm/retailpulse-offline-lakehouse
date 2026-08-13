# Retail Analytics Agent Design

## 1. 目标

RetailPulse Agent 将自然语言经营问题转换成 **可审计的受控分析计划**，执行已有 ADS serving mart，再让模型基于真实工具结果生成结构化结论。

它不是一个可以任意访问数据库的 autonomous agent。这里的“Agent”强调：

- 能把问题拆成多步分析；
- 能选择不同工具；
- 能执行工具并消费结果；
- 能识别当前数据能力不足；
- 最终答案能追溯到具体工具证据。

## 2. Planner contract

`QueryPlanner` 当前是确定性规则 planner，版本写入 `planner_version`。这是一项刻意设计：小而稳定的经营域优先获得可测试、可重复、低成本的 routing；未来再考虑 LLM planner。

Planner 最多生成 6 个工具调用，并返回：

```json
{
  "planner_version": "rules-v1",
  "intent": "diagnostic",
  "calls": [
    {
      "call_id": "get_kpi:refund_rate",
      "tool": "get_kpi",
      "arguments": {"metric": "refund_rate"},
      "reason": "读取 refund_rate 的可信快照"
    }
  ],
  "coverage_gaps": []
}
```

## 3. Tool surface

### `get_kpi`

读取受指标目录约束的 KPI 当前值。适合“GMV 是多少”“退款率如何”。

### `compare_periods`

用日级 serving data 做两个相邻窗口的对比。金额类求和；转化率、退款率、客单价按分子/分母重新聚合，避免简单平均比例产生统计错误。

### `breakdown_by_dimension`

从已有 ADS 聚合结果做受控维度下钻。目前支持：

- `product`
- `category`
- `shop`
- `refund_reason`
- `user_segment`

返回的是 serving mart 聚合，不是任意原始明细。

### `get_topn`

按白名单维度和指标返回排序结果，单次最多 10 条。

### `detect_anomaly`

对日序列执行 population z-score 提示，至少需要 5 个观测。它是运营提示而非统计显著性/因果分析，因此结果包含明确 caveat。

## 4. Coverage gaps

当前明确不支持：

- `channel`
- `campaign`
- `region`

例如问题“按渠道分析 GMV”不会伪造渠道数据，而会返回：

```json
{
  "coverage_gaps": ["channel"]
}
```

这既是产品能力边界，也是下一阶段数据建模 backlog。

## 5. Grounding contract

Tool 成功后返回唯一 `evidence_key`，例如：

```text
kpi:gmv
compare:gmv:3d
get_topn:product:sales_amount
breakdown_by_dimension:refund_reason:refund_amount
```

LLM 输出是严格结构化的 `AnalysisContent`：

```text
summary
observations[] -> evidence_keys[]
actions[]
caveats[]
```

服务端在响应前再次校验：每个 observation 引用的 key 都必须来自本次成功的工具结果。模型引用不存在的 evidence key 会触发 grounding failure，并进入 deterministic fallback。

## 6. 为什么工具执行不交给模型

目前模型只负责基于工具结果进行自然语言综合，不负责直接提交任意工具参数。原因：

- 当前业务域小，确定性 planner 已能覆盖主要 intent；
- 规则 planner 可以完全离线 eval；
- 避免模型构造任意路径、SQL、代码或高成本请求；
- 更容易解释错误到底来自 routing、data、tool 还是 synthesis。

未来若 intent 数量显著增长，可以把 planner 替换为 structured LLM planner，但工具 schema、参数 validator、调用上限和 coverage policy 保持不变。

## 7. Evaluation

Agent 有两类离线 eval：

1. `retrieval_cases.json`：KPI retrieval recall。
2. `tool_routing_cases.json`：工具、维度和 coverage-gap routing recall。

CI 阈值当前均为 0.95。除此之外，pytest 覆盖：

- Top-N 路由和执行；
- refund diagnostic 自动下钻；
- unsupported dimension；
- anomaly execution；
- API response grounding；
- version-aware cache；
- rate limiting；
- production demo fallback policy。

## 8. 下一阶段演进

优先级从高到低：

1. 在 DWS/ADS 增加 `channel`、`campaign`、`region` 的真实聚合表，消除最有价值的 coverage gaps。
2. 增加 contribution analysis：将总指标变化拆成维度贡献，而不是只返回 Top-N。
3. 增加 tool-result faithfulness eval，验证最终 observation 是否准确反映工具数值。
4. 在多实例部署时用 Redis 替换进程内 cache/rate limiter。
5. 当规则 planner 的 intent 覆盖成为瓶颈后，再引入 structured LLM planner。

这个演进顺序确保每增加一个 AI 能力，都先有可靠的数据契约和 eval，而不是反过来让模型能力推动不可控复杂度。
