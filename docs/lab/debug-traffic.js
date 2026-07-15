// D159/D160 (2026-07-15): "did a parallel chunk-analysis burst (D156) momentarily exceed
// NVIDIA's free-tier ~40rpm ceiling" (the figure nvidia-keypool-guard.py already
// documents from real 429 history). Plots a rolling 60s request count over the last 5
// minutes, with a "40 rpm 한도(추정)" reference line.
//
// D159 shipped counting only requests THIS TAB initiated (LabLLM.getRequestLog()) --
// server-side retries inside worker/nvidia-proxy.js's queue() were invisible to the
// browser, so a burst that looked under 40 here could still be over budget once retries
// were counted. D160 adds GET ?traffic=1 on the proxy Worker itself, which records every
// ACTUAL fetch() to NVIDIA (first attempt + every retry, from every client going through
// that same deployed Worker) -- this is now the primary source when reachable.
//
// Still not literally "every request against this NVIDIA key from anywhere" -- SETUP.md
// explicitly lets teammates deploy their OWN proxy Worker and point their own tab at it,
// and traffic through a *different* deployed Worker instance isn't visible to this one.
// Falls back to the old tab-only count if the proxy isn't configured or the traffic
// endpoint can't be reached, and says which mode is active rather than presenting a
// possibly-partial number as if it were the complete picture.
const DebugTraffic = (() => {
  const RATE_LIMIT_THRESHOLD = 40; // requests/60s -- nvidia-keypool-guard.py's documented free-tier figure
  const WINDOW_MS = 60 * 1000;
  const HISTORY_MS = 5 * 60 * 1000; // how far back the chart looks
  const SAMPLE_INTERVAL_MS = 2000; // how often the rolling count re-samples
  const REFRESH_MS = 2000;

  let svgEl, statEl, sourceEl, tooltipEl, containerEl;
  let usingServerData = false;

  async function fetchServerTimestamps() {
    const proxyUrl = LabConfig.get("proxy-url");
    if (!proxyUrl) return null;
    try {
      const base = proxyUrl.split("?")[0];
      const res = await fetch(`${base}?traffic=1`);
      if (!res.ok) return null;
      const data = await res.json();
      return Array.isArray(data.timestamps) ? data.timestamps : null;
    } catch (e) {
      return null; // proxy unreachable/misconfigured -- caller falls back to tab-only data
    }
  }

  function rollingCountsOverTime(log) {
    const now = Date.now();
    const points = [];
    for (let t = now - HISTORY_MS; t <= now; t += SAMPLE_INTERVAL_MS) {
      const windowStart = t - WINDOW_MS;
      const count = log.filter((ts) => ts > windowStart && ts <= t).length;
      points.push({ t, count });
    }
    return points;
  }

  function render(log) {
    if (!containerEl) return;
    const points = rollingCountsOverTime(log);
    const current = points.length ? points[points.length - 1].count : 0;

    if (statEl) {
      statEl.textContent = `${current} / ${RATE_LIMIT_THRESHOLD}`;
      statEl.classList.toggle("over", current >= RATE_LIMIT_THRESHOLD);
    }
    if (sourceEl) {
      sourceEl.textContent = usingServerData
        ? "서버 기준(이 프록시를 거친 모든 요청 + 재시도 포함)"
        : "이 탭 기준만(서버 응답 없음 — 재시도·다른 팀원 트래픽 안 잡힘)";
    }
    if (!svgEl) return;

    const maxVal = Math.max(RATE_LIMIT_THRESHOLD, ...points.map((p) => p.count)) * 1.15;
    const W = 900, H = 160, padL = 8, padR = 8, padT = 10, padB = 8;
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const xAt = (i) => padL + (i / Math.max(1, points.length - 1)) * plotW;
    const yAt = (v) => padT + plotH - (v / maxVal) * plotH;

    const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(p.count).toFixed(1)}`).join(" ");
    const areaPath = points.length
      ? `${linePath} L${xAt(points.length - 1).toFixed(1)},${(padT + plotH).toFixed(1)} L${xAt(0).toFixed(1)},${(padT + plotH).toFixed(1)} Z`
      : "";
    const thresholdY = yAt(RATE_LIMIT_THRESHOLD).toFixed(1);

    const dots = points.map((p, i) => {
      if (i % 5 !== 0 && i !== points.length - 1) return "";
      return `<circle class="debug-traffic-dot" cx="${xAt(i).toFixed(1)}" cy="${yAt(p.count).toFixed(1)}" r="7" fill="transparent" stroke="none"
        data-t="${new Date(p.t).toLocaleTimeString()}" data-v="${p.count}"></circle>`;
    }).join("");

    svgEl.innerHTML = `
      <line x1="${padL}" y1="${thresholdY}" x2="${W - padR}" y2="${thresholdY}" class="debug-traffic-threshold" />
      <text x="${W - padR}" y="${Math.max(10, Number(thresholdY) - 4)}" class="debug-traffic-threshold-label" text-anchor="end">40 rpm 한도(추정)</text>
      <path d="${areaPath}" class="debug-traffic-area" />
      <path d="${linePath}" class="debug-traffic-line" />
      ${dots}
    `;
  }

  async function tick() {
    const serverTimestamps = await fetchServerTimestamps();
    usingServerData = serverTimestamps !== null;
    render(usingServerData ? serverTimestamps : LabLLM.getRequestLog());
  }

  function wireTooltip() {
    tooltipEl = containerEl.querySelector("#debug-traffic-tooltip");
    svgEl.addEventListener("mousemove", (e) => {
      const target = e.target.closest(".debug-traffic-dot");
      if (!target) { tooltipEl.classList.add("hidden"); return; }
      tooltipEl.textContent = `${target.dataset.t} · 최근 60초간 ${target.dataset.v}건`;
      tooltipEl.classList.remove("hidden");
      const rect = containerEl.getBoundingClientRect();
      tooltipEl.style.left = `${e.clientX - rect.left + 12}px`;
      tooltipEl.style.top = `${e.clientY - rect.top - 8}px`;
    });
    svgEl.addEventListener("mouseleave", () => tooltipEl.classList.add("hidden"));
  }

  function init() {
    containerEl = document.getElementById("debug-traffic");
    if (!containerEl) return;
    svgEl = containerEl.querySelector("#debug-traffic-svg");
    statEl = containerEl.querySelector("#debug-traffic-current");
    sourceEl = containerEl.querySelector("#debug-traffic-source");
    wireTooltip();
    tick();
    setInterval(tick, REFRESH_MS);
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", DebugTraffic.init);
