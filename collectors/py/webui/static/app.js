/* Keenetic MaxProbe Web UI — app.js */

function $(id) { return document.getElementById(id); }

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;"
  }[c]));
}

function parseProgress(prog) {
  // "3/15" -> {cur:3, total:15, pct:20}
  const m = String(prog || "").match(/(\d+)\s*\/\s*(\d+)/);
  if (!m) return {cur: 0, total: 0, pct: 0};
  const cur = Number(m[1]);
  const total = Number(m[2]);
  const pct = total > 0 ? Math.max(0, Math.min(100, Math.round(cur * 100 / total))) : 0;
  return {cur, total, pct};
}

function parseMetricsLine(tsv) {
  // metrics_current.tsv: ts\tcpu\tmem\tavail\tload1
  const line = String(tsv || "").trim().split(/\r?\n/).pop() || "";
  const parts = line.split("\t");
  if (parts.length < 5) return null;
  return {ts: parts[0], cpu: parts[1], mem: parts[2], avail: parts[3], load1: parts[4]};
}

async function fetchJSON(url) {
  const r = await fetch(url, {cache: "no-store"});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

async function fetchText(url) {
  const r = await fetch(url, {cache: "no-store"});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.text();
}

function renderArchives(data) {
  const el = $("archives");
  if (!data) { el.innerHTML = ""; return; }

  const archives = data.archives || [];
  const workdirs = data.workdirs || [];
  const outdirs = data.outdirs || [];

  let html = "";
  html += `<div class="mono small">outdirs: ${esc(outdirs.join(", "))}</div>`;

  html += `<h3>Архивы</h3>`;
  if (archives.length === 0) {
    html += `<div class="hint">Архивов пока нет.</div>`;
  } else {
    html += `<table class="tbl"><thead><tr>
      <th>mtime</th><th>name</th><th>size</th><th>download</th><th>sha256</th>
    </tr></thead><tbody>`;
    for (const a of archives) {
      const dt = new Date((a.mtime || 0) * 1000).toISOString();
      const size = a.size ? `${a.size}` : "—";
      const dl = `/download?path=${encodeURIComponent(a.path)}`;
      const sha = a.sha256_path ? `/download?path=${encodeURIComponent(a.sha256_path)}` : "";
      html += `<tr>
        <td class="mono small">${esc(dt)}</td>
        <td class="mono">${esc(a.name)}</td>
        <td class="mono small">${esc(size)}</td>
        <td><a class="mono" href="${dl}">download</a></td>
        <td>${sha ? `<a class="mono small" href="${sha}">.sha256</a>` : `<span class="hint">—</span>`}</td>
      </tr>`;
    }
    html += `</tbody></table>`;
  }

  html += `<h3>Рабочие папки</h3>`;
  if (workdirs.length === 0) {
    html += `<div class="hint">workdir не найден.</div>`;
  } else {
    html += `<table class="tbl"><thead><tr><th>mtime</th><th>name</th><th>path</th></tr></thead><tbody>`;
    for (const w of workdirs) {
      const dt = new Date((w.mtime || 0) * 1000).toISOString();
      html += `<tr>
        <td class="mono small">${esc(dt)}</td>
        <td class="mono">${esc(w.name)}</td>
        <td class="mono small">${esc(w.path)}</td>
      </tr>`;
    }
    html += `</tbody></table>`;
  }

  el.innerHTML = html;
}

async function startRun(preset) {
  const lang = $("langSelect").value || "ru";
  $("startResult").textContent = "starting…";
  try {
    const r = await fetchJSON(`/api/start?preset=${encodeURIComponent(preset)}&lang=${encodeURIComponent(lang)}`);
    $("startResult").textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    $("startResult").textContent = `start error: ${e}`;
  }
}

async function stopRun() {
  $("startResult").textContent = "stopping…";
  try {
    const r = await fetchJSON(`/api/stop`);
    $("startResult").textContent = JSON.stringify(r, null, 2);
  } catch (e) {
    $("startResult").textContent = `stop error: ${e}`;
  }
}

async function tickStatus() {
  try {
    const data = await fetchJSON("/api/status");
    $("utc").textContent = data.utc || "—";

    const st = data.state || {};
    const meta = data.meta || {};

    $("workdir").textContent = meta.workdir || "—";
    $("phase").textContent = meta.phase || "—";
    $("progress").textContent = meta.progress || "—";

    const p = parseProgress(meta.progress);
    $("progressFill").style.width = `${p.pct}%`;

    const m = parseMetricsLine(meta.metrics_current);
    if (m) {
      $("metrics").textContent = `CPU~${m.cpu}% MEM~${m.mem}% load1=${m.load1}`;
    } else {
      $("metrics").textContent = "—";
    }

    const active = st.active ? "active" : "idle";
    const started = st.started_utc ? `started=${st.started_utc}` : "";
    const rc = (st.returncode !== undefined) ? `rc=${st.returncode}` : "";
    const err = st.error ? `error=${st.error}` : "";
    $("runState").textContent = `${active} ${started} ${rc} ${err}`.trim();

    $("spin").style.opacity = st.active ? "1" : "0.2";
  } catch (_) {
    // ignore
  }
}

async function tickLog() {
  try {
    const txt = await fetchText("/api/log?n=250");
    $("logBox").textContent = txt || "";
  } catch (_) {
    // ignore
  }
}

async function tickRuns() {
  try {
    const data = await fetchJSON("/api/runs");
    renderArchives(data);
  } catch (_) {
    // ignore
  }
}

function wireUI() {
  document.querySelectorAll("button[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => startRun(btn.getAttribute("data-preset")));
  });
  $("stopBtn").addEventListener("click", stopRun);
}

wireUI();
tickStatus(); tickLog(); tickRuns();
setInterval(tickStatus, 1000);
setInterval(tickLog, 2000);
setInterval(tickRuns, 5000);
