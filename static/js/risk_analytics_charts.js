(function () {
  if (!window.Chart) return;

  const el = document.getElementById("risk-analytics-data");
  if (!el) return;

  const payload = JSON.parse(el.textContent || "{}");
  const website = payload.website || {};
  const kaggle = payload.kaggle || {};
  const mc = payload.modelCard || {};

  function themeColors() {
    const isDark = document.documentElement.classList.contains("dark");
    return {
      tick: isDark ? "rgba(226,232,240,0.92)" : "rgba(15,23,42,0.95)",
      grid: isDark ? "rgba(148,163,184,0.18)" : "rgba(15,23,42,0.12)",
      tooltipBg: isDark ? "rgba(15,23,42,0.95)" : "rgba(255,255,255,0.98)",
      tooltipText: isDark ? "rgba(226,232,240,0.95)" : "rgba(15,23,42,0.90)",
    };
  }

  window._riskCharts = window._riskCharts || {};
  function destroy(id) {
    if (window._riskCharts[id]) {
      window._riskCharts[id].destroy();
      delete window._riskCharts[id];
    }
  }

  function fillModelCard() {
    const byId = (id) => document.getElementById(id);

    if (byId("mc-model")) byId("mc-model").textContent = mc.model_type || mc.selected_model || "—";
    if (byId("mc-roc")) byId("mc-roc").textContent = (mc.roc_auc_test != null) ? mc.roc_auc_test : "—";
    if (byId("mc-ap")) byId("mc-ap").textContent = (mc.average_precision_test != null) ? mc.average_precision_test : "—";
    if (byId("mc-thr")) byId("mc-thr").textContent = (mc.suggested_threshold_max_f1 != null) ? mc.suggested_threshold_max_f1 : "—";
    if (byId("mc-cloud")) byId("mc-cloud").textContent = mc.dataset_cloud_handle || "—";
    if (byId("mc-win")) byId("mc-win").textContent = mc.dataset_windows_logs_handle || "—";

    if (byId("web-n")) byId("web-n").textContent = website.n != null ? website.n : "—";
    if (byId("kg-n")) byId("kg-n").textContent = kaggle.n_test != null ? kaggle.n_test : "—";
    if (byId("kg-pos")) byId("kg-pos").textContent = kaggle.pos_rate_test != null ? kaggle.pos_rate_test : "—";
    if (byId("kg-mean")) byId("kg-mean").textContent = kaggle.proba_mean != null ? kaggle.proba_mean : "—";
  }

  function buildTrend() {
    const id = "riskTrendChart";
    const canvas = document.getElementById(id);
    if (!canvas) return;

    destroy(id);
    const c = themeColors();

    const trend = (website.trend || {});
    const labels = trend.labels || [];
    const scores = trend.scores || [];

    // Kaggle is not time-series here. It's only a mean reference line.
    const kaggleMean = (kaggle.proba_mean != null) ? Number(kaggle.proba_mean) : null;
    const kaggleLine = kaggleMean != null ? labels.map(() => kaggleMean) : [];

    const datasets = [
      { label: "Website (Live Telemetry)", data: scores, borderWidth: 2, tension: 0.3, pointRadius: 2 }
    ];

    if (kaggleLine.length) {
      datasets.push({
        label: "Kaggle mean probability (reference)",
        data: kaggleLine,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0,
        borderDash: [6, 4],
      });
    }

    window._riskCharts[id] = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: false },
        plugins: {
          legend: { display: true },
          tooltip: {
            backgroundColor: c.tooltipBg,
            titleColor: c.tooltipText,
            bodyColor: c.tooltipText,
            callbacks: {
              //  FIX: only show device for Website dataset
              afterLabel: function (ctx) {
                const label = (ctx.dataset && ctx.dataset.label) ? ctx.dataset.label : "";
                if (!label.includes("Website")) {
                  // Kaggle reference line: don't show website device name
                  return "Kaggle reference (no device)";
                }

                const i = ctx.dataIndex;
                const dev = (trend.devices || [])[i] || "";
                return dev ? ("Device: " + dev) : "";
              }
            }
          }
        },
        scales: {
          x: { ticks: { color: c.tick }, grid: { color: c.grid } },
          y: { ticks: { color: c.tick }, grid: { color: c.grid }, suggestedMin: 0, suggestedMax: 1 }
        }
      }
    });
  }

  // Compare as % (accurate) and show counts in tooltip
  function buildLevelCompare() {
    const id = "riskLevelCompareChart";
    const canvas = document.getElementById(id);
    if (!canvas) return;

    destroy(id);
    const c = themeColors();

    const labels = ["LOW", "MEDIUM", "HIGH"];
    const w = website.levels || { counts: {}, pct: {} };
    const k = kaggle.levels || { counts: {}, pct: {} };

    const wPct = [w.pct?.LOW || 0, w.pct?.MEDIUM || 0, w.pct?.HIGH || 0];
    const kPct = [k.pct?.LOW || 0, k.pct?.MEDIUM || 0, k.pct?.HIGH || 0];

    window._riskCharts[id] = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Website (Live) %", data: wPct, borderWidth: 1 },
          { label: "Kaggle (Notebook) %", data: kPct, borderWidth: 1 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true },
          tooltip: {
            backgroundColor: c.tooltipBg,
            titleColor: c.tooltipText,
            bodyColor: c.tooltipText,
            callbacks: {
              label: function (ctx) {
                const level = ctx.label;
                const datasetLabel = ctx.dataset.label.includes("Website") ? "Website" : "Kaggle";
                const pct = ctx.raw;
                const counts = (datasetLabel === "Website" ? w.counts : k.counts) || {};
                const cnt = counts[level] || 0;
                return `${datasetLabel}: ${pct}% (count: ${cnt})`;
              }
            }
          }
        },
        scales: {
          x: { ticks: { color: c.tick }, grid: { color: c.grid } },
          y: {
            ticks: { color: c.tick, callback: (v) => v + "%" },
            grid: { color: c.grid },
            beginAtZero: true,
            suggestedMax: 100
          }
        }
      }
    });
  }

  function buildHistogramCompare() {
    const id = "riskHistCompareChart";
    const canvas = document.getElementById(id);
    if (!canvas) return;

    destroy(id);
    const c = themeColors();

    const w = website.hist || { labels: [], counts: [], pct: [] };
    const k = kaggle.hist || { labels: w.labels || [], counts: [], pct: [] };

    const labels = w.labels || [];
    const wPct = w.pct || [];
    const kPct = k.pct || [];

    window._riskCharts[id] = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Website (Live) %", data: wPct, borderWidth: 1 },
          { label: "Kaggle (Notebook) %", data: kPct, borderWidth: 1 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true },
          tooltip: {
            backgroundColor: c.tooltipBg,
            titleColor: c.tooltipText,
            bodyColor: c.tooltipText,
            callbacks: {
              label: function (ctx) {
                const isWeb = ctx.dataset.label.includes("Website");
                const pct = ctx.raw;
                const cnt = isWeb ? (w.counts?.[ctx.dataIndex] || 0) : (k.counts?.[ctx.dataIndex] || 0);
                return `${ctx.dataset.label}: ${pct}% (count: ${cnt})`;
              }
            }
          }
        },
        scales: {
          x: { ticks: { color: c.tick }, grid: { color: c.grid } },
          y: {
            ticks: { color: c.tick, callback: (v) => v + "%" },
            grid: { color: c.grid },
            beginAtZero: true,
            suggestedMax: 100
          }
        }
      }
    });
  }

  function buildAvgByDevice() {
    const id = "avgDeviceChart";
    const canvas = document.getElementById(id);
    if (!canvas) return;

    destroy(id);
    const c = themeColors();

    const avg = website.avgByDevice || {};
    window._riskCharts[id] = new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: { labels: avg.labels || [], datasets: [{ label: "Avg Risk", data: avg.values || [], borderWidth: 1 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: c.tick }, grid: { color: c.grid } },
          y: { ticks: { color: c.tick }, grid: { color: c.grid }, suggestedMin: 0, suggestedMax: 1 }
        }
      }
    });
  }

  function buildROC() {
    const id = "rocChart";
    const canvas = document.getElementById(id);
    if (!canvas) return;

    const roc = kaggle.roc_curve || {};
    if (!roc.fpr || !roc.tpr) return;

    destroy(id);
    const c = themeColors();

    const pts = roc.fpr.map((x, i) => ({ x: Number(x), y: Number(roc.tpr[i]) }));

    window._riskCharts[id] = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { datasets: [{ label: "ROC (Kaggle Test)", data: pts, borderWidth: 2, pointRadius: 0, tension: 0 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        plugins: { legend: { display: true } },
        scales: {
          x: { type: "linear", min: 0, max: 1, ticks: { color: c.tick }, grid: { color: c.grid }, title: { display: true, text: "FPR", color: c.tick } },
          y: { type: "linear", min: 0, max: 1, ticks: { color: c.tick }, grid: { color: c.grid }, title: { display: true, text: "TPR", color: c.tick } }
        }
      }
    });
  }

  function renderAll() {
    fillModelCard();
    buildTrend();
    buildLevelCompare();
    buildHistogramCompare();
    buildROC();
    buildAvgByDevice();
  }

  renderAll();
  window.addEventListener("preventab:theme-changed", renderAll);
})();