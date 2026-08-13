const labels = {
  gmv: "GMV",
  pay_amount: "支付金额",
  pay_conversion_rate: "支付转化率",
  avg_order_value: "客单价",
  repeat_purchase_rate: "复购率",
  refund_rate: "退款率",
};

const rateKeys = new Set(["pay_conversion_rate", "repeat_purchase_rate", "refund_rate"]);
const currencyKeys = new Set(["gmv", "pay_amount", "avg_order_value", "sales_amount", "refund_amount", "monetary"]);

function formatMetric(key, value) {
  if (value === null || value === undefined) return "-";
  if (rateKeys.has(key)) return `${(Number(value) * 100).toFixed(2)}%`;
  if (currencyKeys.has(key)) {
    return new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: "CNY",
      maximumFractionDigits: key === "avg_order_value" ? 2 : 0,
    }).format(Number(value));
  }
  if (typeof value === "number") return new Intl.NumberFormat("zh-CN").format(value);
  return String(value);
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

async function loadStatus() {
  const response = await fetch("/readyz");
  const data = await response.json();
  document.querySelector("#providerBadge").textContent =
    `${data.provider ?? "unavailable"} · ${data.model ?? "n/a"}`;
}

async function loadCapabilities() {
  const response = await fetch("/api/v1/capabilities");
  if (!response.ok) return;
  const data = await response.json();
  document.querySelector("#capabilities").textContent =
    `${data.tools.length} tools · planner ${data.planner_version}`;
}

async function loadMetrics() {
  const response = await fetch("/api/v1/metrics");
  if (!response.ok) throw new Error("指标数据暂不可用");
  const data = await response.json();
  document.querySelector("#latestDt").textContent =
    `latest: ${data.latest_dt ?? "-"} · ${data.source_kind}`;

  const grid = document.querySelector("#kpiGrid");
  clear(grid);
  for (const [key, value] of Object.entries(data.kpis)) {
    if (!(key in labels)) continue;
    const card = element("article", "kpi-card");
    card.appendChild(element("div", "kpi-label", labels[key]));
    card.appendChild(element("div", "kpi-value", formatMetric(key, value)));
    grid.appendChild(card);
  }
}

function renderPlan(plan) {
  const list = document.querySelector("#planList");
  clear(list);
  list.appendChild(element("div", "intent-badge", `intent: ${plan.intent}`));

  for (const [index, call] of plan.calls.entries()) {
    const item = element("div", "plan-item");
    item.appendChild(element("span", "step-number", String(index + 1)));
    const body = element("div");
    body.appendChild(element("strong", "", call.tool));
    body.appendChild(element("p", "muted compact", call.reason));
    item.appendChild(body);
    list.appendChild(item);
  }

  if (plan.coverage_gaps.length) {
    list.appendChild(
      element("div", "coverage-gap", `coverage gap: ${plan.coverage_gaps.join(", ")}`),
    );
  }
}

function renderAnalysis(analysis) {
  document.querySelector("#analysisSummary").textContent = analysis.summary;
  const body = document.querySelector("#analysisBody");
  clear(body);

  for (const observation of analysis.observations) {
    const item = element("div", "analysis-item");
    item.appendChild(element("strong", "", observation.title));
    item.appendChild(element("p", "compact", observation.detail));
    item.appendChild(
      element("code", "evidence-key", observation.evidence_keys.join(" · ")),
    );
    body.appendChild(item);
  }

  if (analysis.actions.length) {
    body.appendChild(element("strong", "subheading", "建议动作"));
    for (const action of analysis.actions) body.appendChild(element("p", "compact", `• ${action}`));
  }
  if (analysis.caveats.length) {
    body.appendChild(element("strong", "subheading", "边界 / Caveats"));
    for (const caveat of analysis.caveats) body.appendChild(element("p", "muted compact", `• ${caveat}`));
  }
}

function summarizeToolData(result) {
  const data = result.data ?? {};
  if (result.tool === "get_kpi") {
    return `${data.metric}: ${formatMetric(data.metric, data.value)}`;
  }
  if (result.tool === "compare_periods") {
    const pct = data.change_pct === null || data.change_pct === undefined
      ? "n/a"
      : `${(Number(data.change_pct) * 100).toFixed(2)}%`;
    return `previous ${formatMetric(data.metric, data.previous)} → current ${formatMetric(data.metric, data.current)} · ${pct}`;
  }
  if (result.tool === "detect_anomaly") {
    return `${data.sample_size ?? 0} observations · ${data.anomalies?.length ?? 0} anomalies`;
  }
  if (Array.isArray(data.rows)) {
    return `${data.rows.length} ranked rows · ${data.dimension ?? "dimension"} · ${data.metric ?? "metric"}`;
  }
  return result.status;
}

function renderToolResults(results) {
  const grid = document.querySelector("#toolResults");
  clear(grid);
  for (const result of results) {
    const card = element("article", `tool-card ${result.status}`);
    const header = element("div", "tool-header");
    header.appendChild(element("strong", "", result.tool));
    header.appendChild(element("span", "status-pill", result.status));
    card.appendChild(header);
    card.appendChild(element("p", "compact", result.title));
    card.appendChild(element("p", "muted compact", summarizeToolData(result)));
    card.appendChild(element("code", "evidence-key", result.evidence_key));
    for (const note of result.notes ?? []) {
      card.appendChild(element("p", "tool-note", note));
    }
    grid.appendChild(card);
  }
}

function renderEvidence(items) {
  const list = document.querySelector("#evidenceList");
  clear(list);
  for (const item of items) {
    const div = element("div", "evidence-item");
    div.appendChild(
      element("strong", "", `${item.label}: ${formatMetric(item.metric, item.value)}`),
    );
    div.appendChild(element("span", "", item.definition));
    list.appendChild(div);
  }
}

function renderWarnings(warnings) {
  const box = document.querySelector("#warnings");
  clear(box);
  if (!warnings.length) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  box.appendChild(element("strong", "", "Warnings"));
  for (const warning of warnings) box.appendChild(element("p", "compact", `• ${warning}`));
}

async function ask(question) {
  const button = document.querySelector("#askButton");
  const panel = document.querySelector("#answerPanel");
  button.disabled = true;
  button.textContent = "执行中…";
  panel.classList.remove("hidden");
  document.querySelector("#analysisSummary").textContent = "正在规划并执行受控分析工具…";

  try {
    const response = await fetch("/api/v1/ask", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question, top_k: 5}),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error?.message ?? "请求失败");
    }

    document.querySelector("#answerProvider").textContent =
      `provider: ${data.provider}/${data.model}`;
    document.querySelector("#answerLatency").textContent = `${data.latency_ms} ms`;
    document.querySelector("#dataVersion").textContent = `data: ${data.data_version}`;
    renderPlan(data.plan);
    renderAnalysis(data.analysis);
    renderToolResults(data.tool_results);
    renderEvidence(data.evidence);
    renderWarnings(data.warnings);
  } catch (error) {
    document.querySelector("#analysisSummary").textContent = `请求失败：${error.message}`;
    clear(document.querySelector("#planList"));
    clear(document.querySelector("#toolResults"));
    clear(document.querySelector("#evidenceList"));
  } finally {
    button.disabled = false;
    button.textContent = "执行分析";
  }
}

document.querySelector("#askForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = document.querySelector("#question").value.trim();
  if (question) await ask(question);
});

for (const chip of document.querySelectorAll(".example-chip")) {
  chip.addEventListener("click", () => {
    const question = chip.dataset.question ?? "";
    document.querySelector("#question").value = question;
    document.querySelector("#question").focus();
  });
}

Promise.all([loadStatus(), loadCapabilities(), loadMetrics()]).catch((error) => {
  console.error(error);
  document.querySelector("#providerBadge").textContent = "not ready";
});
