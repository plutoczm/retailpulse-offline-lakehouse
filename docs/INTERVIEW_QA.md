# Interview Q&A — RetailPulse AI Analyst

## 1. 这个项目解决什么问题？

把离线零售湖仓中的经营指标封装成一个 grounded AI 分析助手。用户可以问“支付转化率最近怎么样”，系统先检索可信指标，再让模型基于 evidence 生成回答，而不是让 LLM 自己猜数字。

## 2. 为什么这算 AI 应用开发，而不是普通 BI？

传统 BI 要用户自己选择指标和图表；这里增加了自然语言意图理解与生成式分析层。同时保留结构化指标作为事实源，模型负责解释和交互，不负责创造事实。

## 3. 为什么不直接让模型查数据库？

直接 Text-to-SQL 会引入 SQL 安全、Schema 漂移、权限、错误聚合和指标口径不一致问题。当前项目先把核心 KPI 固化在 ADS / metrics snapshot，再做受控 retrieval。后续如果加 Text-to-SQL，也应该先做 schema allowlist、read-only、query cost limit 和结果校验。

## 4. 为什么没有上 LangChain？

当前 orchestration 很薄：retrieval → evidence → provider。自己维护几十行代码更透明，也更容易测试。只有在需要复杂 tool calling、workflow、memory 或多 provider graph 时才值得引入框架。

## 5. 为什么没有向量数据库？

知识域主要是少量稳定 KPI，lexical retrieval 更简单、可解释、可离线 eval。文档规模扩大后再引入 embedding，不为技术标签提前支付复杂度成本。

## 6. 如何减少幻觉？

- 指标 allowlist；
- trusted evidence；
- prompt 约束；
- API 返回 evidence；
- 缺数据时明确拒绝推断；
- 原因和观察事实分开表达。

## 7. 数据错误怎么办？

AI 上游仍然有数据质量 gate。主键重复、关键字段空值、金额异常、维度缺失等会在 pipeline 阶段被检查。错误数据如果直接进入 LLM，会产生“有依据的错误回答”，所以数据质量本身就是 AI reliability 的一部分。

## 8. OpenAI 挂了怎么办？

`AnalystService` 捕获 provider 异常并降级到 deterministic provider。响应里会返回 warning，不隐藏降级状态。

## 9. 为什么 deterministic fallback 有价值？

它让 CI、离线开发和演示不依赖网络/API Key，而且可以验证完整的 retrieval、evidence、API contract、前端链路。

## 10. 你怎么测试 AI？

传统 pytest 测函数和 API contract；`run_ai_evals.py` 测 retrieval recall。之后还可以加 golden answers、faithfulness、prompt injection、延迟和 token cost regression。

## 11. 为什么在线服务不装 PySpark？

Spark 属于离线数据计算依赖，FastAPI 属于在线请求路径。拆分依赖可以减小镜像、降低冷启动和漏洞面，也避免让在线服务承担不必要的 JVM runtime。

## 12. Docker Compose 为什么只剩 API？

旧 compose 中 PostgreSQL、MinIO、Spark master/worker 没有被当前在线业务代码真正依赖。作品集应该展示真实使用的架构，而不是“看起来企业级”的空壳。

## 13. request id 有什么用？

每次请求都返回 `X-Request-ID`，AI 返回体使用同一个 id。线上出现错误回答或 provider timeout 时，可以通过 request id 关联日志和后续 trace。

## 14. `/healthz` 和 `/readyz` 为什么分开？

`healthz` 判断进程是否活着；`readyz` 判断指标数据是否可加载、服务是否具备业务处理条件。Kubernetes / 负载均衡通常需要区分 liveness 和 readiness。

## 15. 如果要加多轮对话怎么做？

会话历史只用于语言上下文，业务事实仍应该每轮重新 retrieval。不能因为上一轮说过某个数字，就把它当作永久可信事实。

## 16. 如果要做 Text-to-SQL，第一步是什么？

不是先让 LLM 写 SQL，而是定义：

- 允许查询的 schema/table/column；
- 只读账号；
- SQL parser / AST 校验；
- limit / timeout / scan cost；
- 指标语义层；
- query result sanity check。

## 17. 这个项目最大的 trade-off 是什么？

为了可控和可解释，当前只支持核心 KPI 问答，没有追求通用数据 Agent。作品集阶段这是有意选择：先保证一条主链路可靠，再逐步扩大能力边界。

## 18. 下一步最值得做什么？

增加结构化输出和更丰富的 ADS 维度，然后做 answer faithfulness eval。这样可以同时提升产品体验、可测试性和面试技术深度。
