# Architecture

RetailPulse 采用“离线可信数据层 + 在线 AI 应用层”的双层架构。

```mermaid
flowchart TB
  subgraph Offline["Offline Data Plane"]
    A[Raw / Synerise] --> B[ODS]
    B --> C[DWD + DIM]
    C --> D[DWS]
    D --> E[ADS Metrics]
    C --> Q[Data Quality Gate]
    Q --> E
  end

  subgraph Online["Online AI Plane"]
    E --> X[Metrics Snapshot]
    X --> R[Metric Repository]
    K[Metric Catalog] --> T[Retriever]
    R --> T
    U[Question] --> T
    T --> V[Trusted Evidence]
    V --> P[OpenAI / Deterministic Provider]
    P --> API[FastAPI]
    API --> UI[Web UI]
  end

  EV[Retrieval Evals + pytest] --> CI[GitHub Actions]
  Q --> CI
```

关键边界：

- Spark 只负责离线数据计算；
- FastAPI 在线服务不启动 Spark；
- LLM 不直接读取任意原始表；
- evidence 是 AI 事实边界；
- provider 可以替换，业务 retrieval 不依赖具体模型厂商。

详细设计见 `AI_APPLICATION.md`。
