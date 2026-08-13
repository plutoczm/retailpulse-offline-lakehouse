# AI Application Design

## 1. 目标

RetailPulse AI Analyst 的目标不是做一个“聊天壳”，而是把已有零售湖仓变成可供业务人员查询的 grounded AI 应用。

核心约束：

- LLM 不直接访问任意文件或数据库。
- 所有业务事实必须来自受控 evidence。
- 无外部模型时仍能本地开发、测试和演示。
- 在线服务不依赖 Spark runtime。
- 数据质量失败时，不应该把错误指标继续暴露给 AI。

## 2. 请求链路

```text
question
  -> metric retrieval
  -> trusted evidence
  -> provider
  -> grounded answer
  -> API response with evidence
```

`app/catalog.py` 维护小规模、稳定的业务指标知识。`app/analytics.py` 读取在线指标快照，并计算可以从日序列直接得到的趋势。

当前 retrieval 是 deterministic lexical retrieval。它的优势是：

- 可解释；
- 无额外服务；
- 延迟极低；
- 容易做 recall eval；
- 指标域扩展前不需要维护 embedding index。

## 3. Provider 抽象

`app/llm.py` 暴露统一 `generate(question, evidence)` 接口。

### OpenAIProvider

使用 OpenAI Responses API。模型名通过 `OPENAI_MODEL` 配置，Key 只从环境变量读取。

### DeterministicProvider

用于：

- 本地无 Key 演示；
- 单元测试；
- CI；
- 外部 provider 异常降级。

它不假装自己是大模型，会在回答里明确标记“离线规则模式”。

## 4. Hallucination 控制

当前采用四层约束：

1. **Evidence allowlist**：只有 catalog 中定义且快照存在的指标可以进入上下文。
2. **Prompt contract**：模型只能根据 trusted evidence 回答。
3. **Evidence return**：API 把实际证据回传给客户端。
4. **Causal boundary**：离线 fallback 明确区分“指标变化”和“业务原因”。

生产环境可继续加入：

- JSON schema structured outputs；
- semantic answer checker；
- metric freshness SLA；
- prompt injection benchmark；
- per-tenant data authorization。

## 5. Failure modes

### 指标文件缺失

`/readyz` 返回 503；`/healthz` 仍返回 200，用于区分进程存活和业务可用。

### OpenAI 调用失败

服务捕获 provider 异常，切换到 deterministic fallback，并在 `warnings` 返回降级信息。

### 问题没有明确指标关键词

Retriever 返回默认核心 KPI 集合，避免空上下文；后续可以替换成意图分类器。

### 数据口径变化

指标口径是 catalog 与 `docs/METRICS.md` 的契约。变更时需要同时更新 retrieval eval cases。

## 6. Observability

API 中间件记录：

- request_id
- method
- path
- status_code
- latency_ms

响应头返回 `X-Request-ID`，AI 响应体也携带同一个 request id，便于定位单次线上问题。

后续可增加：

- Prometheus metrics；
- OpenTelemetry traces；
- token / cost metrics；
- model error rate；
- fallback rate；
- retrieval miss rate。

## 7. Eval

当前 `scripts/run_ai_evals.py` 计算 retrieval recall。选择这个指标是因为在 grounded app 中：

> 如果检索阶段没有把正确业务指标送进模型，后续生成再强也无法可靠回答。

后续评估可以分为：

- Retrieval: recall@k / precision@k
- Generation: faithfulness / relevance
- Product: task completion / user correction rate
- Engineering: p95 latency / error rate / cost per request

## 8. 为什么删除“大数据全家桶”

原仓库包含 Hadoop、Hive、HBase、Kafka、Flink、Sqoop、ZooKeeper 配置模板，以及 PostgreSQL / MinIO compose 服务，但核心代码没有真正把它们串进运行链路。

对 AI 应用作品集，这类组件会带来三个问题：

1. 面试官会追问实际使用深度；
2. 增加部署与维护成本；
3. 稀释“业务问题 → AI 方案 → 工程落地”的主线。

因此只保留被真实数据链路使用的 PySpark 湖仓和质量检查。

## 9. 下一阶段可扩展

优先级建议：

1. 增加用户会话与多轮上下文，但业务事实仍每轮重新 grounding。
2. 增加结构化输出 schema，让前端可渲染“结论/证据/建议”字段。
3. 加入更多 ADS 维度，如渠道、活动、品类、用户分群。
4. 当知识文档规模扩大后，引入 embedding + vector store。
5. 增加离线 LLM judge / golden answer eval。
6. 部署到云环境并接 Prometheus / OpenTelemetry。
