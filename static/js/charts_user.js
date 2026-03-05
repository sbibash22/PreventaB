(function () {
  if (!window.Chart) {
    console.error("Chart.js not loaded. Check head.html CDN script.");
    return;
  }

  const el = document.getElementById("user-chart-data");
  if (!el) {
    console.error("No user chart data found (user-chart-data).");
    return;
  }

  const payload = JSON.parse(el.textContent || "{}");
  const labels = Array.isArray(payload.labels) ? payload.labels : [];

  function toNumberArray(raw, nLabels) {
    const out = [];
    for (let i = 0; i < nLabels; i++) {
      const num = Number(raw?.[i]);
      out.push(Number.isFinite(num) ? num : null);
    }
    return out;
  }

  const cpu = toNumberArray(payload.cpu, labels.length);
  const ram = toNumberArray(payload.ram, labels.length);
  const disk = toNumberArray(payload.disk, labels.length);

  window._charts = window._charts || {};

  function buildChart(canvasId, data, colorSet) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (window._charts[canvasId]) window._charts[canvasId].destroy();

    //  compute theme colors INSIDE buildChart so it updates on toggle
    const isDark = document.documentElement.classList.contains("dark");
    const tickColor = isDark ? "rgba(226,232,240,0.92)" : "rgba(15,23,42,0.95)";
    const gridColor = isDark ? "rgba(148,163,184,0.18)" : "rgba(15,23,42,0.12)";

    const tooltipBg = isDark ? "rgba(15,23,42,0.95)" : "rgba(255,255,255,0.98)";
    const tooltipTitle = isDark ? "rgba(226,232,240,1)" : "rgba(15,23,42,0.95)";
    const tooltipBody = isDark ? "rgba(226,232,240,0.95)" : "rgba(15,23,42,0.90)";
    const tooltipBorder = isDark ? "rgba(148,163,184,0.25)" : "rgba(15,23,42,0.18)";

    window._charts[canvasId] = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [{
          data,
          borderColor: colorSet.line,
          backgroundColor: colorSet.fill,
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 4,
          tension: 0.3,
          fill: true,
          spanGaps: true,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: true,
            backgroundColor: tooltipBg,
            titleColor: tooltipTitle,
            bodyColor: tooltipBody,
            borderColor: tooltipBorder,
            borderWidth: 1,
          },
        },
        interaction: { mode: "nearest", intersect: false },
        scales: {
          x: {
            ticks: {
              color: tickColor,
              autoSkip: true,
              maxTicksLimit: 5,
              maxRotation: 25,
              minRotation: 25,
              padding: 6,
            },
            grid: { color: gridColor }
          },
          y: {
            min: 0,
            max: 100,
            ticks: {
              color: tickColor,
              maxTicksLimit: 6,
              callback: function (value) { return value + "%"; }
            },
            grid: { color: gridColor }
          },
        }
      }
    });
  }

  function currentColors() {
    const isDark = document.documentElement.classList.contains("dark");
    return {
      cpu: { line: isDark ? "rgba(96,165,250,1)" : "rgba(37,99,235,1)", fill: isDark ? "rgba(96,165,250,0.18)" : "rgba(37,99,235,0.12)" },
      ram: { line: isDark ? "rgba(34,197,94,1)" : "rgba(22,163,74,1)", fill: isDark ? "rgba(34,197,94,0.16)" : "rgba(22,163,74,0.10)" },
      disk:{ line: isDark ? "rgba(251,146,60,1)" : "rgba(234,88,12,1)", fill: isDark ? "rgba(251,146,60,0.16)" : "rgba(234,88,12,0.10)" },
    };
  }

  // initial render
  (function renderAll() {
    const c = currentColors();
    buildChart("cpuChart", cpu, c.cpu);
    buildChart("ramChart", ram, c.ram);
    buildChart("diskChart", disk, c.disk);
  })();

  //  redraw instantly when theme toggles (no refresh)
  window.addEventListener("preventab:theme-changed", function () {
    const c = currentColors();
    buildChart("cpuChart", cpu, c.cpu);
    buildChart("ramChart", ram, c.ram);
    buildChart("diskChart", disk, c.disk);
  });
})();