import * as THREE from "./vendor/three.module.min.js";

const $ = (id) => document.getElementById(id);
const CHINESE_FONT = '"Microsoft YaHei UI","Microsoft YaHei","PingFang SC","Noto Sans CJK SC","Source Han Sans SC","SimHei",sans-serif';
const FONT = {
  axis: 14,
  body: 15,
  legend: 16,
  panel: 16,
  big: 42,
};

function canvasFont(size, weight = 600) {
  return `${weight} ${size}px ${CHINESE_FONT}`;
}

const fmt = {
  number(value) {
    return Number(value || 0).toLocaleString("zh-CN");
  },
  compact(value) {
    const n = Number(value || 0);
    if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
    if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)}万`;
    return n.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  },
  money(value) {
    return `¥${fmt.compact(value)}`;
  },
  pct(value) {
    return `${(Number(value || 0) * 100).toFixed(2)}%`;
  },
};

const state = {
  payload: null,
  domain: "all",
  metric: "event_count",
  startDate: null,
  endDate: null,
  selectedDate: null,
  depth: 62,
  chartZoom: 1,
};

const tooltip = $("tooltip");
let sceneHandles = null;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function showTooltip(event, lines) {
  tooltip.innerHTML = lines.filter(Boolean).join("<br>");
  tooltip.style.left = `${Math.min(window.innerWidth - 380, event.clientX + 16)}px`;
  tooltip.style.top = `${Math.min(window.innerHeight - 160, event.clientY + 16)}px`;
  tooltip.classList.add("visible");
}

function hideTooltip() {
  tooltip.classList.remove("visible");
}

function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  ctx.font = canvasFont(FONT.body);
  ctx.textBaseline = "alphabetic";
  drawCanvasShell(ctx, rect.width, rect.height);
  return { ctx, width: rect.width, height: rect.height };
}

function drawCanvasShell(ctx, width, height) {
  const glow = ctx.createRadialGradient(width * 0.5, height * 0.46, 0, width * 0.5, height * 0.46, Math.max(width, height) * 0.72);
  glow.addColorStop(0, "rgba(55,231,255,0.11)");
  glow.addColorStop(0.48, "rgba(40,241,196,0.035)");
  glow.addColorStop(1, "rgba(2,5,10,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalAlpha = 0.38;
  ctx.strokeStyle = "rgba(55,231,255,0.13)";
  ctx.lineWidth = 1;
  for (let x = 18; x < width; x += 34) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x - 18, height);
    ctx.stroke();
  }
  ctx.restore();

  const corner = 22;
  ctx.strokeStyle = "rgba(255,190,84,0.46)";
  ctx.lineWidth = 1.2;
  [
    [10, 10, 1, 1],
    [width - 10, 10, -1, 1],
    [10, height - 10, 1, -1],
    [width - 10, height - 10, -1, -1],
  ].forEach(([x, y, sx, sy]) => {
    ctx.beginPath();
    ctx.moveTo(x, y + sy * corner);
    ctx.lineTo(x, y);
    ctx.lineTo(x + sx * corner, y);
    ctx.stroke();
  });
}

function registerHits(canvas, hits, onClick) {
  canvas.onmousemove = (event) => {
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = hits.find((item) => x >= item.x && x <= item.x + item.w && y >= item.y && y <= item.y + item.h);
    if (hit) showTooltip(event, hit.tooltip);
    else hideTooltip();
  };
  canvas.onmouseleave = hideTooltip;
  canvas.onclick = (event) => {
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const hit = hits.find((item) => x >= item.x && x <= item.x + item.w && y >= item.y && y <= item.y + item.h);
    if (hit && onClick) onClick(hit);
  };
  canvas.onwheel = (event) => {
    event.preventDefault();
    state.chartZoom = clamp(state.chartZoom + (event.deltaY > 0 ? -0.08 : 0.08), 0.68, 1.8);
    render();
  };
}

function rowsInRange(rows, dateKey = "dt") {
  const filtered = rows.filter((row) => {
    const dt = String(row[dateKey] || "");
    if (state.startDate && dt < state.startDate) return false;
    if (state.endDate && dt > state.endDate) return false;
    return true;
  });
  const source = filtered.length ? filtered : rows;
  const count = Math.max(2, Math.floor(source.length * state.chartZoom));
  return source.slice(Math.max(0, source.length - count));
}

function maxOf(rows, keys) {
  return Math.max(1, ...rows.flatMap((row) => keys.map((key) => Number(row[key] || 0))));
}

function drawEmpty(ctx, width, height, text) {
  ctx.save();
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(243,249,255,0.72)";
  ctx.font = canvasFont(17, 700);
  ctx.fillText(text, width / 2, height / 2);
  ctx.restore();
}

function drawGrid(ctx, width, height, pad) {
  ctx.strokeStyle = "rgba(54, 218, 255, 0.15)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = pad.t + ((height - pad.t - pad.b) * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(width - pad.r, y);
    ctx.stroke();
  }
  ctx.save();
  ctx.globalAlpha = 0.55;
  ctx.strokeStyle = "rgba(255,190,84,0.12)";
  const baseY = height - pad.b;
  const centerX = width / 2;
  for (let i = -4; i <= 4; i += 1) {
    const x = pad.l + ((width - pad.l - pad.r) * (i + 4)) / 8;
    ctx.beginPath();
    ctx.moveTo(x, baseY);
    ctx.lineTo(centerX + i * 16, pad.t);
    ctx.stroke();
  }
  ctx.restore();
}

function drawLineArea(canvas, rows, series, options = {}) {
  const { ctx, width, height } = setupCanvas(canvas);
  if (!rows.length) {
    drawEmpty(ctx, width, height, "暂无可展示数据");
    registerHits(canvas, []);
    return;
  }
  const pad = { t: 36, r: 24, b: 40, l: 68 };
  drawGrid(ctx, width, height, pad);
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const max = maxOf(rows, series.map((item) => item.key));
  const hits = [];

  series.forEach((item, si) => {
    const focusActive = series.some((candidate) => candidate.key === state.metric);
    const isFocus = !focusActive || item.key === state.metric;
    const pts = rows.map((row, i) => {
      const x = pad.l + (plotW * i) / Math.max(rows.length - 1, 1);
      const y = pad.t + plotH - (plotH * Number(row[item.key] || 0)) / max;
      return { x, y, row };
    });
    const gradient = ctx.createLinearGradient(0, pad.t, 0, height - pad.b);
    gradient.addColorStop(0, `${item.color}5f`);
    gradient.addColorStop(1, `${item.color}03`);
    ctx.beginPath();
    pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.lineTo(pad.l + plotW, height - pad.b);
    ctx.lineTo(pad.l, height - pad.b);
    ctx.closePath();
    ctx.globalAlpha = isFocus ? 1 : 0.32;
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.shadowBlur = isFocus ? 18 : 7;
    ctx.shadowColor = item.color;
    ctx.strokeStyle = item.color;
    ctx.lineWidth = isFocus ? 2.8 : 1.5;
    ctx.beginPath();
    pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.stroke();
    ctx.shadowBlur = 0;
    pts.forEach((p, i) => {
      if (i % Math.ceil(rows.length / 16 || 1) !== 0 && i !== rows.length - 1) return;
      ctx.beginPath();
      ctx.fillStyle = item.color;
      ctx.shadowBlur = isFocus ? 12 : 0;
      ctx.arc(p.x, p.y, isFocus ? 3.2 : 2.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });
    ctx.globalAlpha = 1;

    ctx.fillStyle = item.color;
    ctx.font = canvasFont(FONT.legend, 800);
    ctx.fillText(item.label, pad.l + si * 104, 23);
    ctx.font = canvasFont(FONT.axis);

    pts.forEach((p) => {
      hits.push({
        x: p.x - 8,
        y: p.y - 8,
        w: 16,
        h: 16,
        row: p.row,
        tooltip: [
          `<strong>${p.row.dt}</strong>`,
          `${item.label}: ${item.format(p.row[item.key])}`,
          "点击联动中心日期",
        ],
      });
    });
  });

  ctx.fillStyle = "#91a5bb";
  ctx.font = canvasFont(FONT.axis);
  rows.forEach((row, i) => {
    if (i % Math.ceil(rows.length / 6 || 1) !== 0 && i !== rows.length - 1) return;
    const x = pad.l + (plotW * i) / Math.max(rows.length - 1, 1);
    ctx.fillText(String(row.dt).slice(5), x - 16, height - 12);
  });
  const selectedIndex = rows.findIndex((row) => row.dt === state.selectedDate);
  if (selectedIndex >= 0) {
    const x = pad.l + (plotW * selectedIndex) / Math.max(rows.length - 1, 1);
    ctx.strokeStyle = "rgba(255,190,84,0.58)";
    ctx.shadowBlur = 14;
    ctx.shadowColor = "#ffbe54";
    ctx.beginPath();
    ctx.moveTo(x, pad.t);
    ctx.lineTo(x, height - pad.b);
    ctx.stroke();
    ctx.shadowBlur = 0;
  }
  if (options.unit) {
    ctx.fillStyle = "#91a5bb";
    ctx.font = canvasFont(FONT.axis);
    ctx.fillText(options.unit, 10, 18);
  }
  registerHits(canvas, hits, (hit) => {
    state.selectedDate = hit.row.dt;
    render();
  });
}

function drawBars3D(canvas, rows, labelKey, valueKey, color, formatter = fmt.compact) {
  const { ctx, width, height } = setupCanvas(canvas);
  if (!rows.length) {
    drawEmpty(ctx, width, height, "当前日期暂无排行数据");
    registerHits(canvas, []);
    return;
  }
  const pad = { t: 20, r: 22, b: 20, l: 16 };
  const maxRows = clamp(Math.floor((height - pad.t - pad.b) / 30), 4, 9);
  const shownRows = rows.slice(0, maxRows);
  const max = Math.max(1, ...shownRows.map((row) => Number(row[valueKey] || 0)));
  const rowH = (height - pad.t - pad.b) / Math.max(shownRows.length, 1);
  const hits = [];
  shownRows.forEach((row, i) => {
    const value = Number(row[valueKey] || 0);
    const x = pad.l + 8;
    const y = pad.t + i * rowH + 4;
    const h = Math.max(10, rowH - 10);
    const w = ((width - 132) * value) / max;
    const depth = 10;
    const grad = ctx.createLinearGradient(x, y, x + w + depth, y + h);
    grad.addColorStop(0, color);
    grad.addColorStop(0.68, i % 3 === 0 ? "#28f1c4" : color);
    grad.addColorStop(1, "rgba(255,190,84,0.85)");
    ctx.shadowBlur = 17;
    ctx.shadowColor = color;
    ctx.fillStyle = grad;
    ctx.fillRect(x, y + depth, w, h);
    ctx.shadowBlur = 0;
    ctx.fillStyle = "rgba(255,255,255,0.22)";
    ctx.beginPath();
    ctx.moveTo(x, y + depth);
    ctx.lineTo(x + depth, y);
    ctx.lineTo(x + w + depth, y);
    ctx.lineTo(x + w, y + depth);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "rgba(0,0,0,0.34)";
    ctx.beginPath();
    ctx.moveTo(x + w, y + depth);
    ctx.lineTo(x + w + depth, y);
    ctx.lineTo(x + w + depth, y + h);
    ctx.lineTo(x + w, y + h + depth);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#f2f8ff";
    ctx.font = canvasFont(FONT.axis, 800);
    const label = compactProductLabel(row, labelKey);
    ctx.fillText(label, x + 8, y + depth + h / 2 + 4);
    ctx.textAlign = "right";
    ctx.fillStyle = "#91a5bb";
    ctx.font = canvasFont(FONT.axis, 700);
    ctx.fillText(formatter(value), width - pad.r, y + depth + h / 2 + 4);
    ctx.textAlign = "left";
    hits.push({
      x,
      y,
      w: Math.max(40, w + depth),
      h: h + depth,
      tooltip: [`<strong>${label}</strong>`, `购买事件: ${formatter(value)}`, row.active_user_count ? `活跃用户: ${fmt.compact(row.active_user_count)}` : "", row.dt ? `日期: ${row.dt}` : ""],
    });
  });
  registerHits(canvas, hits);
}

function compactProductLabel(row, labelKey) {
  if (row.sku !== undefined && row.sku !== null) return `SKU ${row.sku}`;
  const raw = String(row[labelKey] ?? "-");
  return raw.length > 14 ? `${raw.slice(0, 13)}…` : raw;
}

function drawScatter(canvas, rows) {
  const { ctx, width, height } = setupCanvas(canvas);
  if (!rows.length) {
    drawEmpty(ctx, width, height, "暂无转化分布数据");
    registerHits(canvas, []);
    return;
  }
  const pad = { t: 30, r: 26, b: 42, l: 68 };
  drawGrid(ctx, width, height, pad);
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const maxUsers = Math.max(1, ...rows.map((row) => Number(row.active_user_count || 0)));
  const maxEvents = Math.max(1, ...rows.map((row) => Number(row.event_count || 0)));
  const maxRate = Math.max(0.001, ...rows.map((row) => Number(row.view_to_pay_rate || 0)));
  const hits = [];
  rows.forEach((row) => {
    const x = pad.l + (plotW * Number(row.active_user_count || 0)) / maxUsers;
    const y = pad.t + plotH - (plotH * Number(row.view_to_pay_rate || 0)) / maxRate;
    const r = 4 + 12 * Math.sqrt(Number(row.event_count || 0) / maxEvents);
    const selected = row.dt === state.selectedDate;
    ctx.shadowBlur = selected ? 26 : 16;
    ctx.shadowColor = selected ? "#ffbe54" : "#28f1c4";
    ctx.fillStyle = selected ? "rgba(255,190,84,0.82)" : "rgba(40,241,196,0.62)";
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = selected ? "rgba(255,255,255,0.72)" : "rgba(55,231,255,0.22)";
    ctx.beginPath();
    ctx.arc(x, y, r + 5, 0, Math.PI * 2);
    ctx.stroke();
    hits.push({
      x: x - r,
      y: y - r,
      w: r * 2,
      h: r * 2,
      tooltip: [`<strong>${row.dt}</strong>`, `活跃用户: ${fmt.compact(row.active_user_count)}`, `访问购买率: ${fmt.pct(row.view_to_pay_rate)}`, `事件量: ${fmt.compact(row.event_count)}`],
    });
  });
  ctx.fillStyle = "#91a5bb";
  ctx.font = canvasFont(FONT.axis);
  ctx.fillText("活跃用户", width - 86, height - 12);
  ctx.save();
  ctx.translate(16, height / 2 + 34);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("访问购买率", 0, 0);
  ctx.restore();
  registerHits(canvas, hits);
}

function drawHeatmap(canvas, rows) {
  const { ctx, width, height } = setupCanvas(canvas);
  if (!rows.length) {
    drawEmpty(ctx, width, height, "暂无行为热力数据");
    registerHits(canvas, []);
    return;
  }
  const typeLabels = [
    ["view", "访问"],
    ["search", "搜索"],
    ["cart", "加购"],
    ["remove_cart", "移除"],
    ["pay", "购买"],
  ];
  const dates = [...new Set(rows.map((row) => row.dt))].sort();
  const filteredDates = dates.filter((dt) => (!state.startDate || dt >= state.startDate) && (!state.endDate || dt <= state.endDate));
  const sourceDates = filteredDates.length ? filteredDates : dates;
  const shownDates = sourceDates.slice(-Math.floor(Math.min(42, Math.max(14, sourceDates.length * state.chartZoom))));
  const map = new Map(rows.map((row) => [`${row.dt}|${row.event_type}`, row]));
  const max = Math.max(1, ...rows.map((row) => Number(row.event_count || 0)));
  const pad = { t: 26, r: 16, b: 38, l: 72 };
  const cellW = (width - pad.l - pad.r) / Math.max(shownDates.length, 1);
  const cellH = (height - pad.t - pad.b) / typeLabels.length;
  const hits = [];
  typeLabels.forEach(([type, label], yi) => {
    ctx.fillStyle = "#91a5bb";
    ctx.font = canvasFont(FONT.axis, 700);
    ctx.fillText(label, 16, pad.t + yi * cellH + cellH / 2 + 5);
    shownDates.forEach((dt, xi) => {
      const row = map.get(`${dt}|${type}`);
      const value = Number(row?.event_count || 0);
      const intensity = Math.sqrt(value / max);
      const x = pad.l + xi * cellW;
      const y = pad.t + yi * cellH;
      ctx.fillStyle = `rgba(${42 + intensity * 213}, ${120 + intensity * 100}, ${188 - intensity * 80}, ${0.18 + intensity * 0.8})`;
      ctx.shadowBlur = 10 * intensity;
      ctx.shadowColor = "#31e6ff";
      ctx.fillRect(x + 1, y + 2, Math.max(1, cellW - 2), Math.max(1, cellH - 4));
      ctx.shadowBlur = 0;
      hits.push({ x, y, w: cellW, h: cellH, tooltip: [`<strong>${dt}</strong>`, `行为: ${label}`, `事件数: ${fmt.compact(value)}`] });
    });
  });
  ctx.fillStyle = "#91a5bb";
  ctx.font = canvasFont(FONT.axis);
  shownDates.forEach((dt, i) => {
    if (i % Math.ceil(shownDates.length / 6 || 1) !== 0 && i !== shownDates.length - 1) return;
    ctx.fillText(dt.slice(5), pad.l + i * cellW - 10, height - 12);
  });
  registerHits(canvas, hits);
}

function drawFunnel(canvas, row) {
  const { ctx, width, height } = setupCanvas(canvas);
  if (!row || !row.dt) {
    drawEmpty(ctx, width, height, "暂无行为转化数据");
    registerHits(canvas, []);
    return;
  }
  const steps = [
    ["访问", Number(row.view_event_count || 0), "#31e6ff"],
    ["搜索", Number(row.search_event_count || 0), "#a9f45a"],
    ["加购", Number(row.cart_event_count || 0), "#ffb84a"],
    ["购买", Number(row.pay_event_count || 0), "#ff5e88"],
  ];
  const max = Math.max(1, ...steps.map((step) => step[1]));
  const cx = width / 2;
  const cy = height * 0.47;
  const hits = [];

  ctx.save();
  ctx.translate(cx, cy);
  for (let i = 0; i < 18; i += 1) {
    const angle = (i / 18) * Math.PI * 2;
    const inner = 36;
    const outer = 188;
    ctx.strokeStyle = i % 3 === 0 ? "rgba(55,231,255,0.24)" : "rgba(55,231,255,0.08)";
    ctx.beginPath();
    ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
    ctx.lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer);
    ctx.stroke();
  }
  steps.forEach(([label, value, color], i) => {
    const radius = 38 + i * 38;
    const rate = value / max;
    ctx.lineWidth = 13;
    ctx.strokeStyle = "rgba(49,230,255,0.10)";
    ctx.beginPath();
    ctx.arc(0, 0, radius, -Math.PI * 0.82, Math.PI * 1.18);
    ctx.stroke();
    ctx.shadowBlur = 24;
    ctx.shadowColor = color;
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(0, 0, radius, -Math.PI * 0.82, -Math.PI * 0.82 + Math.PI * 2 * rate);
    ctx.stroke();
    ctx.shadowBlur = 0;
    const lx = Math.cos(-Math.PI * 0.82 + Math.PI * 2 * rate) * radius;
    const ly = Math.sin(-Math.PI * 0.82 + Math.PI * 2 * rate) * radius;
    hits.push({
      x: cx + lx - 18,
      y: cy + ly - 18,
      w: 36,
      h: 36,
      tooltip: [`<strong>${label}</strong>`, `事件数: ${fmt.compact(value)}`, `日期: ${row.dt}`],
    });
  });
  ctx.restore();

  ctx.textAlign = "center";
  ctx.fillStyle = "#f2f8ff";
  ctx.font = canvasFont(FONT.big, 800);
  ctx.fillText(fmt.compact(row.event_count), cx, cy + 8);
  ctx.font = canvasFont(16, 700);
  ctx.fillStyle = "#91a5bb";
  ctx.fillText("真实行为事件", cx, cy + 38);
  ctx.textAlign = "left";

  steps.forEach(([label, value, color], i) => {
    const x = 18 + (width - 36) * (i / steps.length);
    const y = height - 34;
    ctx.fillStyle = color;
    ctx.fillRect(x, y - 9, 10, 10);
    ctx.fillStyle = "#f2f8ff";
    ctx.font = canvasFont(FONT.axis, 700);
    ctx.fillText(`${label} ${fmt.compact(value)}`, x + 16, y);
  });
  registerHits(canvas, hits);
}

function behaviorRow(payload) {
  const rows = payload.synerise_daily || [];
  const target = state.selectedDate || payload.synerise_latest_dt;
  return rows.find((row) => row.dt === target) || rows.find((row) => row.dt === payload.synerise_latest_dt) || rows.at(-1) || {};
}

function renderKpis(payload, row) {
  const k = payload.kpis || {};
  const cards = [
    ["GMV", fmt.money(k.gmv), `支付转化 ${fmt.pct(k.pay_conversion_rate)}`],
    ["支付金额", fmt.money(k.pay_amount), `客单价 ${fmt.money(k.avg_order_value)}`],
    ["交易复购", fmt.pct(k.repeat_purchase_rate), `退款率 ${fmt.pct(k.refund_rate)}`],
    ["真实事件", fmt.compact(row.event_count), `${fmt.compact(row.active_user_count)} 活跃`],
    ["购买事件", fmt.compact(row.pay_event_count), `加购 ${fmt.compact(row.cart_event_count)}`],
    ["访问购买", fmt.pct(row.view_to_pay_rate), `加购购买 ${fmt.pct(row.cart_to_pay_rate)}`],
  ];
  $("kpiStrip").innerHTML = cards.map(([name, value, sub]) => `<article class="kpi-card"><span>${name}</span><strong>${value}</strong><small>${sub}</small></article>`).join("");
}

function renderAssets(rows) {
  $("assetRows").innerHTML = rows
    .map((row) => `<tr><td>${row.table}</td><td>${fmt.compact(row.rows)}</td><td>${Number(row.size_mb || 0).toFixed(1)} MB</td></tr>`)
    .join("");
}

function renderInsights(payload, row, productRows) {
  const viewPay = Number(row.view_to_pay_rate || 0);
  const cartPay = Number(row.cart_to_pay_rate || 0);
  const trendRows = rowsInRange(payload.synerise_daily || []);
  const avgViewPay = trendRows.reduce((sum, item) => sum + Number(item.view_to_pay_rate || 0), 0) / Math.max(trendRows.length, 1);
  const lift = avgViewPay ? (viewPay - avgViewPay) / avgViewPay : 0;
  const topSku = productRows[0] ? `SKU ${productRows[0].sku}` : "暂无";
  const signal = viewPay >= avgViewPay ? "高于窗口均值" : "低于窗口均值";
  $("insights").innerHTML = [
    `访问购买率 <b>${fmt.pct(viewPay)}</b>，${signal} <b>${fmt.pct(Math.abs(lift))}</b>，适合联动投放与推荐策略复盘。`,
    `加购购买率 <b>${fmt.pct(cartPay)}</b>，购买事件 <b>${fmt.compact(row.pay_event_count)}</b>，可用于识别转化断点。`,
    `当前热销商品 <b>${topSku}</b>，活跃用户 <b>${fmt.compact(row.active_user_count)}</b>，支撑用户分层和商品运营看板。`,
  ].map((text) => `<div class="insight">${text}</div>`).join("");
}

function render() {
  const payload = state.payload;
  if (!payload) return;
  const row = behaviorRow(payload);
  document.documentElement.style.setProperty("--depth", state.depth);
  document.body.dataset.domain = state.domain;
  $("retailDate").textContent = payload.latest_dt || "-";
  $("behaviorDate").textContent = row.dt || payload.synerise_latest_dt || "-";
  $("generatedAt").textContent = payload.generated_at || "-";
  $("coreEventCount").textContent = fmt.compact(row.event_count);
  $("productDate").textContent = row.dt || "-";

  const retailRows = rowsInRange(payload.daily || []);
  const behaviorRows = rowsInRange(payload.synerise_daily || []);
  const productSource = payload.synerise_product_topn_all || payload.synerise_product_topn || [];
  const currentProducts = productSource.filter((item) => item.dt === row.dt);
  const productRows = (currentProducts.length ? currentProducts : payload.synerise_product_topn || productSource)
    .sort((a, b) => Number(b.pay_event_count || 0) - Number(a.pay_event_count || 0))
    .slice(0, 10);

  renderKpis(payload, row);
  renderAssets(payload.public_dataset || []);
  renderInsights(payload, row, productRows);

  drawLineArea($("retailTrend"), retailRows, [
    { key: "gmv", label: "GMV", color: "#31e6ff", format: fmt.money },
    { key: "pay_amount", label: "支付", color: "#ffb84a", format: fmt.money },
    { key: "order_count", label: "订单", color: "#24f2c7", format: fmt.number },
  ]);
  drawBars3D($("productRank"), productRows, "sku", "pay_event_count", "#31e6ff", fmt.number);
  drawFunnel($("funnelChart"), row);
  drawLineArea($("behaviorWave"), behaviorRows, [
    { key: "event_count", label: "事件", color: "#31e6ff", format: fmt.compact },
    { key: "active_user_count", label: "活跃", color: "#b7f46b", format: fmt.compact },
    { key: "pay_event_count", label: "购买", color: "#ff5c8a", format: fmt.compact },
  ]);
  drawScatter($("conversionScatter"), behaviorRows);
  drawHeatmap($("eventHeatmap"), payload.synerise_event_type || []);
  updateSceneData(payload, row);
}

function initControls(payload) {
  const dates = (payload.synerise_daily || []).map((row) => row.dt).sort();
  state.startDate = dates[Math.max(0, dates.length - 42)] || dates[0] || null;
  state.endDate = payload.synerise_latest_dt || dates.at(-1) || null;
  state.selectedDate = state.endDate;
  $("startDate").value = state.startDate || "";
  $("endDate").value = state.endDate || "";
  $("depthControl").value = String(state.depth);

  $("domainFilter").onchange = (event) => {
    state.domain = event.target.value;
    render();
  };
  $("metricFilter").onchange = (event) => {
    state.metric = event.target.value;
    render();
  };
  $("startDate").onchange = (event) => {
    state.startDate = event.target.value || null;
    render();
  };
  $("endDate").onchange = (event) => {
    state.endDate = event.target.value || null;
    state.selectedDate = state.endDate;
    render();
  };
  $("depthControl").oninput = (event) => {
    state.depth = Number(event.target.value);
    render();
  };
  $("resetView").onclick = () => {
    state.startDate = dates[Math.max(0, dates.length - 42)] || dates[0] || null;
    state.endDate = payload.synerise_latest_dt || dates.at(-1) || null;
    state.selectedDate = state.endDate;
    state.depth = 62;
    state.chartZoom = 1;
    $("startDate").value = state.startDate || "";
    $("endDate").value = state.endDate || "";
    $("depthControl").value = "62";
    render();
  };
}

function initThreeScene() {
  const canvas = $("webgl");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(58, window.innerWidth / window.innerHeight, 0.1, 1800);
  camera.position.set(0, 42, 124);

  const root = new THREE.Group();
  root.rotation.x = -0.08;
  scene.add(root);

  const cyanLight = new THREE.PointLight(0x37e7ff, 1.7, 260);
  cyanLight.position.set(0, 56, 40);
  scene.add(cyanLight);
  const amberLight = new THREE.PointLight(0xffbe54, 0.8, 210);
  amberLight.position.set(-58, 24, 16);
  scene.add(amberLight);

  const particles = makeParticles();
  root.add(particles);
  const beams = makeBeams();
  root.add(beams);

  const grid = new THREE.GridHelper(210, 42, 0x31e6ff, 0x123247);
  grid.position.y = -34;
  grid.material.transparent = true;
  grid.material.opacity = 0.22;
  root.add(grid);

  const rings = new THREE.Group();
  root.add(rings);
  [22, 32, 43].forEach((radius, i) => {
    const geo = new THREE.TorusGeometry(radius, 0.13, 8, 160);
    const mat = new THREE.MeshBasicMaterial({ color: i === 2 ? 0xffb84a : 0x31e6ff, transparent: true, opacity: 0.44 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = Math.PI / 2;
    mesh.position.y = -5 + i * 0.4;
    rings.add(mesh);
  });

  const barGroup = new THREE.Group();
  root.add(barGroup);

  let dragging = false;
  let previousX = 0;
  canvas.addEventListener("pointerdown", (event) => {
    dragging = true;
    previousX = event.clientX;
  });
  window.addEventListener("pointerup", () => {
    dragging = false;
  });
  window.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    root.rotation.y += (event.clientX - previousX) * 0.0025;
    previousX = event.clientX;
  });
  canvas.addEventListener("wheel", (event) => {
    camera.position.z = clamp(camera.position.z + event.deltaY * 0.035, 82, 180);
  });

  function resize() {
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", () => {
    resize();
    render();
  });
  resize();

  function animate(time) {
    const t = time * 0.001;
    particles.rotation.y = t * 0.012;
    beams.rotation.y = -t * 0.018;
    beams.children.forEach((line, i) => {
      line.material.opacity = 0.18 + Math.sin(t * 1.6 + i) * 0.06;
    });
    rings.rotation.z = t * 0.14;
    rings.children.forEach((mesh, i) => {
      mesh.rotation.z = t * (0.12 + i * 0.035);
      mesh.position.y = -5 + Math.sin(t + i) * 0.6;
    });
    barGroup.children.forEach((mesh, i) => {
      mesh.position.y += Math.sin(t * 1.4 + i) * 0.004;
      mesh.rotation.y = Math.sin(t * 0.7 + i) * 0.04;
    });
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
  sceneHandles = { barGroup };
}

function makeParticles() {
  const count = 2200;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const cyan = new THREE.Color("#31e6ff");
  const amber = new THREE.Color("#ffb84a");
  for (let i = 0; i < count; i += 1) {
    positions[i * 3] = (Math.random() - 0.5) * 260;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 96;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 220;
    const c = cyan.clone().lerp(amber, Math.random() * 0.34);
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  return new THREE.Points(geo, new THREE.PointsMaterial({ size: 0.72, vertexColors: true, transparent: true, opacity: 0.72 }));
}

function makeBeams() {
  const group = new THREE.Group();
  const colors = [0x37e7ff, 0x28f1c4, 0xffbe54, 0xff5c8a];
  for (let i = 0; i < 28; i += 1) {
    const angle = (i / 28) * Math.PI * 2;
    const radius = 18 + (i % 7) * 7;
    const points = [
      new THREE.Vector3(Math.cos(angle) * radius, -30 + (i % 4) * 4, Math.sin(angle) * radius - 20),
      new THREE.Vector3(Math.cos(angle + 0.18) * (radius + 40), -4 + (i % 5) * 3, Math.sin(angle + 0.18) * (radius + 40) - 20),
    ];
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({
      color: colors[i % colors.length],
      transparent: true,
      opacity: 0.18,
    });
    group.add(new THREE.Line(geo, mat));
  }
  return group;
}

function updateSceneData(payload, row) {
  if (!sceneHandles) return;
  while (sceneHandles.barGroup.children.length) {
    const child = sceneHandles.barGroup.children[0];
    sceneHandles.barGroup.remove(child);
    child.geometry?.dispose?.();
    child.material?.dispose?.();
  }
  const productSource = payload.synerise_product_topn_all || payload.synerise_product_topn || [];
  const currentRows = productSource.filter((item) => item.dt === row.dt);
  const rows = (currentRows.length ? currentRows : payload.synerise_product_topn || productSource)
    .sort((a, b) => Number(b.pay_event_count || 0) - Number(a.pay_event_count || 0))
    .slice(0, 36);
  if (!rows.length) return;
  const max = Math.max(1, ...rows.map((item) => Number(item.pay_event_count || 0)));
  rows.forEach((item, i) => {
    const h = 2 + 26 * (Number(item.pay_event_count || 0) / max);
    const geo = new THREE.BoxGeometry(1.4, h, 1.4);
    const mat = new THREE.MeshBasicMaterial({
      color: i % 4 === 0 ? 0xffb84a : 0x31e6ff,
      transparent: true,
      opacity: 0.42,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const angle = (i / rows.length) * Math.PI * 2;
    const radius = 36 + (i % 3) * 7;
    mesh.position.set(Math.cos(angle) * radius, -28 + h / 2, Math.sin(angle) * radius - 18);
    sceneHandles.barGroup.add(mesh);
  });
}

async function boot() {
  initThreeScene();
  const response = await fetch("data/dashboard.json", { cache: "no-store" });
  state.payload = await response.json();
  initControls(state.payload);
  render();
}

boot().catch((error) => {
  console.error(error);
  $("assetRows").innerHTML = `<tr><td colspan="3">大屏数据加载失败，请先生成 dashboard/data/dashboard.json</td></tr>`;
});
