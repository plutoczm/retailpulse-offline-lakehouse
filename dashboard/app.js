const labels = {
  gmv: "GMV",
  pay_amount: "支付金额",
  pay_conversion_rate: "支付转化率",
  avg_order_value: "客单价",
  repeat_purchase_rate: "复购率",
  refund_rate: "退款率",
};

const rateKeys = new Set(["pay_conversion_rate", "repeat_purchase_rate", "refund_rate"]);
const currencyKeys = new Set(["gmv", "pay_amount", "avg_order_value"]);

function formatMetric(key, value) {
  if (rateKeys.has(key)) return `${(Number(value) * 100).toFixed(2)}%`;
  if (currencyKeys.has(key)) {
    return new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: "CNY",
      maximumFractionDigits: key === "avg_order_value" ? 2 : 0,
    }).format(Number(value));
  }
  return String(value);
}

async function loadStatus() {
  const response = await fetch("/readyz");
  const data = await response.json();
  document.querySelector("#providerBadge").textContent =
    `${data.provider ?? "unavailable"} · ${data.model ?? "n/a"}`;
}

async function loadMetrics() {
  const response = await fetch("/api/v1/metrics");
  if (!response.ok) throw new Error("指标数据暂不可用");
  const data = await response.json();
  document.querySelector("#latestDt").textContent = `latest: ${data.latest_dt ?? "-"}`;

  const grid = document.querySelector("#kpiGrid");
  grid.innerHTML = "";
  for (const [key, value] of Object.entries(data.kpis)) {
    if (!(key in labels)) continue;
    const card = document.createElement("article");
    card.className = "kpi-card";
    card.innerHTML = `
      <div class="kpi-label">${labels[key]}</div>
      <div class="kpi-value">${formatMetric(key, value)}</div>
    `;
    grid.appendChild(card);
  }
}

function renderEvidence(items) {
  const list = document.querySelector("#evidenceList");
  list.innerHTML = "";
  for (const item of items) {
    const div = document.createElement("div");
    div.className = "evidence-item";
    div.innerHTML = `
      <strong>${item.label}: ${formatMetric(item.metric, item.value)}</strong>
      <span>${item.definition}</span>
    `;
    list.appendChild(div);
  }
}

document.querySelector("#askForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.querySelector("#askButton");
  const question = document.querySelector("#question").value.trim();
  const panel = document.querySelector("#answerPanel");
  const answer = document.querySelector("#answer");

  button.disabled = true;
  button.textContent = "分析中…";
  panel.classList.remove("hidden");
  answer.textContent = "正在检索可信指标并生成回答…";

  try {
    const response = await fetch("/api/v1/ask", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question, top_k: 4}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "请求失败");

    answer.textContent = data.answer;
    document.querySelector("#answerProvider").textContent =
      `provider: ${data.provider}/${data.model}`;
    document.querySelector("#answerLatency").textContent = `${data.latency_ms} ms`;
    renderEvidence(data.evidence);
  } catch (error) {
    answer.textContent = `请求失败：${error.message}`;
    document.querySelector("#evidenceList").innerHTML = "";
  } finally {
    button.disabled = false;
    button.textContent = "生成经营洞察";
  }
});

Promise.all([loadStatus(), loadMetrics()]).catch((error) => {
  console.error(error);
  document.querySelector("#providerBadge").textContent = "not ready";
});
