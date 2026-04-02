const refreshButton = document.getElementById("refresh-button");
const refreshStatus = document.getElementById("refresh-status");
const lastUpdated = document.getElementById("last-updated");
const rankingBody = document.getElementById("ranking-body");
const updateGrowthPicker = document.getElementById("update-growth-picker");
const updateGrowthIntervals = document.getElementById("update-growth-intervals");
const insightsList = document.getElementById("insights-list");
const focusGroupCaption = document.getElementById("focus-group-caption");
const focusMemberPicker = document.getElementById("focus-member-picker");
const focusApplyButton = document.getElementById("focus-apply-button");
const focusAutoButton = document.getElementById("focus-auto-button");

const metricMembers = document.getElementById("metric-members");
const metricTotalFans = document.getElementById("metric-total-fans");
const metricTotalGrowth = document.getElementById("metric-total-growth");
const metricRecentGrowth = document.getElementById("metric-recent-growth");

const fansChart = echarts.init(document.getElementById("fans-chart"));
const focusChart = echarts.init(document.getElementById("focus-chart"));
const updateGrowthChart = echarts.init(document.getElementById("update-growth-chart"));

let latestDashboardData = null;
let manualFocusTags = null;
let manualUpdateGrowthTags = null;
let updateGrowthInterval = 1;

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(value ?? 0);
}

function formatDelta(value) {
  const formatted = formatNumber(Math.abs(value ?? 0));
  if ((value ?? 0) > 0) return `+${formatted}`;
  if ((value ?? 0) < 0) return `-${formatted}`;
  return "0";
}

function renderMetrics(data) {
  metricMembers.textContent = formatNumber(data.meta.member_count);
  metricTotalFans.textContent = formatNumber(data.summary.total_fans);
  metricTotalGrowth.textContent = formatDelta(data.summary.total_growth);
  metricRecentGrowth.textContent = formatDelta(data.summary.recent_growth_total);
  lastUpdated.textContent = `Last updated: ${data.meta.last_updated || "-"}`;
}

function renderInsights(items) {
  insightsList.innerHTML = "";
  if (!items.length) {
    insightsList.innerHTML = '<article class="insight-card"><h3>No insights yet</h3><p>More samples will make the auto summary more useful.</p></article>';
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `insight-card ${item.tone || ""}`.trim();
    card.innerHTML = `<h3>${item.title}</h3><p>${item.content}</p>`;
    insightsList.appendChild(card);
  });
}

function renderRanking(items) {
  rankingBody.innerHTML = "";
  items.forEach((item, index) => {
    const row = document.createElement("tr");
    const recentClass = item.recent_growth < 0 ? "negative" : "positive";
    const totalClass = item.total_growth < 0 ? "negative" : "positive";
    const gapClass = item.gap_to_previous == null ? "neutral" : "negative";

    row.innerHTML = `
      <td><span class="rank-badge">${index + 1}</span></td>
      <td>${item.tag}</td>
      <td>${formatNumber(item.fans_num)}</td>
      <td class="${gapClass}">${item.gap_to_previous == null ? "-" : formatNumber(item.gap_to_previous)}</td>
      <td class="${totalClass}">${formatDelta(item.total_growth)}</td>
      <td class="${recentClass}">${formatDelta(item.recent_growth)}</td>
      <td>${formatNumber(item.collect_num)}</td>
      <td>${formatNumber(item.like_num)}</td>
      <td>${item.latest_time}</td>
    `;
    rankingBody.appendChild(row);
  });
}

function aggregateUpdateGrowthRows(rows, interval) {
  if (interval <= 1) return rows;

  const aggregated = [];
  for (let index = 0; index < rows.length; index += interval) {
    const chunk = rows.slice(index, index + interval);
    if (!chunk.length) continue;

    const merged = {
      time: chunk.length === 1 ? chunk[0].time : `${chunk[0].time} -> ${chunk[chunk.length - 1].time}`,
      total_delta: 0,
      deltas: {},
    };

    chunk.forEach((row) => {
      merged.total_delta += row.total_delta || 0;
      Object.entries(row.deltas || {}).forEach(([tag, value]) => {
        if (value == null) return;
        merged.deltas[tag] = (merged.deltas[tag] || 0) + value;
      });
    });

    aggregated.push(merged);
  }

  return aggregated;
}

function renderUpdateGrowthChart(data) {
  const updateGrowth = data.update_growth || {};
  const allTags = updateGrowth.tags || [];
  const tags = manualUpdateGrowthTags && manualUpdateGrowthTags.length
    ? allTags.filter((tag) => manualUpdateGrowthTags.includes(tag))
    : allTags;
  const rows = aggregateUpdateGrowthRows(updateGrowth.rows || [], updateGrowthInterval);
  const labels = rows.map((row) => row.time);
  const series = tags.map((tag) => ({
    name: tag,
    type: "line",
    smooth: true,
    showSymbol: false,
    emphasis: { focus: "series" },
    lineStyle: { width: 3 },
    data: rows.map((row) => row.deltas?.[tag] ?? null),
  }));

  updateGrowthChart.setOption({
    ...createChartBase(),
    legend: { type: "scroll", top: 0 },
    xAxis: {
      ...createChartBase().xAxis,
      data: labels,
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#5b6772" },
      splitLine: { lineStyle: { color: "rgba(31, 41, 51, 0.08)" } },
      scale: true,
    },
    series,
  }, true);
}

function renderUpdateGrowthPicker(data) {
  const allTags = data.update_growth?.tags || [];
  const activeTags = manualUpdateGrowthTags && manualUpdateGrowthTags.length
    ? manualUpdateGrowthTags
    : allTags;

  updateGrowthPicker.innerHTML = "";
  allTags.forEach((tag) => {
    const label = document.createElement("label");
    label.className = "member-chip";
    const checked = activeTags.includes(tag) ? "checked" : "";
    label.innerHTML = `
      <input type="checkbox" value="${tag}" ${checked}>
      <span>${tag}</span>
    `;
    updateGrowthPicker.appendChild(label);
  });
}

function selectedUpdateGrowthTags() {
  return Array.from(
    updateGrowthPicker.querySelectorAll('input[type="checkbox"]:checked'),
    (input) => input.value,
  );
}

function selectedUpdateGrowthInterval() {
  const checked = updateGrowthIntervals.querySelector('input[name="update-interval"]:checked');
  return checked ? Number(checked.value) : 1;
}

function renderFocusPicker(data) {
  const autoTags = data.focus_group?.tags || [];
  const activeTags = manualFocusTags && manualFocusTags.length ? manualFocusTags : autoTags;
  focusMemberPicker.innerHTML = "";

  (data.ranking || []).forEach((item) => {
    const label = document.createElement("label");
    label.className = "member-chip";
    const checked = activeTags.includes(item.tag) ? "checked" : "";
    label.innerHTML = `
      <input type="checkbox" value="${item.tag}" ${checked}>
      <span>${item.tag}</span>
    `;
    focusMemberPicker.appendChild(label);
  });
}

function selectedFocusTags() {
  return Array.from(
    focusMemberPicker.querySelectorAll('input[type="checkbox"]:checked'),
    (input) => input.value,
  );
}

function lineSeries(source) {
  return source.map((series) => ({
    name: series.name,
    type: "line",
    smooth: true,
    showSymbol: false,
    emphasis: { focus: "series" },
    lineStyle: { width: 3 },
    data: series.data,
  }));
}

function createChartBase() {
  return {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { type: "scroll", top: 0 },
    grid: { top: 54, left: 48, right: 24, bottom: 64 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      axisLabel: { color: "#5b6772" },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#5b6772" },
      splitLine: { lineStyle: { color: "rgba(31, 41, 51, 0.08)" } },
    },
    dataZoom: [
      { type: "inside", xAxisIndex: 0 },
      { type: "slider", height: 18, bottom: 12 },
    ],
  };
}

function renderCharts(data) {
  fansChart.setOption({
    ...createChartBase(),
    xAxis: {
      ...createChartBase().xAxis,
      data: data.charts.trend_labels || [],
    },
    series: lineSeries(data.charts.fans_series),
  }, true);

  const useManual = manualFocusTags && manualFocusTags.length;
  const focusSeries = useManual
    ? (data.charts.fans_series || []).filter((series) => manualFocusTags.includes(series.name))
    : (data.charts.focus_series || []);
  const focusSummary = data.focus_group;

  if (useManual && focusSeries.length) {
    focusGroupCaption.textContent = `Manual focus: ${manualFocusTags.join(", ")}`;
  } else if (focusSummary && focusSeries.length) {
    focusGroupCaption.textContent =
      `Auto focus: ${focusSummary.tags.join(", ")}. Span: ${formatNumber(focusSummary.span)} fans.`;
  } else {
    focusGroupCaption.textContent = "Not enough data to build a focus zoom view.";
  }

  focusChart.setOption({
    ...createChartBase(),
    xAxis: {
      ...createChartBase().xAxis,
      data: data.charts.trend_labels || [],
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#5b6772" },
      splitLine: { lineStyle: { color: "rgba(31, 41, 51, 0.08)" } },
      scale: true,
    },
    series: lineSeries(focusSeries),
  }, true);

}

async function loadDashboard() {
  refreshStatus.textContent = "Syncing latest data";
  try {
    const response = await fetch("/api/dashboard", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    latestDashboardData = data;
    renderMetrics(data);
    renderInsights(data.insights || []);
    renderRanking(data.ranking || []);
    renderUpdateGrowthPicker(data);
    renderUpdateGrowthChart(data);
    renderFocusPicker(data);
    renderCharts(data);
    refreshStatus.textContent = "Data synced";
  } catch (error) {
    refreshStatus.textContent = "Load failed";
    insightsList.innerHTML = `<article class="insight-card warning"><h3>Connection failed</h3><p>${error.message}</p></article>`;
  }
}

focusApplyButton.addEventListener("click", () => {
  const tags = selectedFocusTags();
  manualFocusTags = tags.length ? tags : null;
  if (latestDashboardData) renderCharts(latestDashboardData);
});

updateGrowthPicker.addEventListener("change", () => {
  const tags = selectedUpdateGrowthTags();
  manualUpdateGrowthTags = tags.length ? tags : null;
  if (latestDashboardData) {
    renderUpdateGrowthChart(latestDashboardData);
  }
});

updateGrowthIntervals.addEventListener("change", () => {
  updateGrowthInterval = selectedUpdateGrowthInterval();
  if (latestDashboardData) {
    renderUpdateGrowthChart(latestDashboardData);
  }
});

focusAutoButton.addEventListener("click", () => {
  manualFocusTags = null;
  if (latestDashboardData) {
    renderFocusPicker(latestDashboardData);
    renderCharts(latestDashboardData);
  }
});

refreshButton.addEventListener("click", loadDashboard);
window.addEventListener("resize", () => {
  fansChart.resize();
  focusChart.resize();
  updateGrowthChart.resize();
});

loadDashboard();
setInterval(loadDashboard, 60000);
