/* keenetic-maxprobe Web UI (no external libs) */

function $(id) { return document.getElementById(id); }

function formatTime(tsSec) {
  try {
    const d = new Date(tsSec * 1000);
    return d.toLocaleString();
  } catch (e) {
    return String(tsSec);
  }
}

function parseProgress(progStr) {
  // "3/17"
  if (!progStr) return {cur: 0, total: 0, pct: 0};
  const m = progStr.match(/^(\d+)\s*\/\s*(\d+)$/);
  if (!m) return {cur: 0, total: 0, pct: 0};
  const cur = parseInt(m[1], 10);
  const total = parseInt(m[2], 10);
  const pct = total > 0 ? Math.min(100, Math.max(0, Math.round(cur * 100 / total))) : 0;
  return {cur, total, pct};
}

function getToken() {
  const u = new URL(window.location.href);
  const t = u.searchParams.get("token");
  if (t) return t;
  return localStorage.getItem("kmp_token") || "";
}

function setToken(t) {
  localStorage.setItem("kmp_token", t);
}

async function apiFetch(path, opts = {}) {
  const token = getToken();
  opts.headers = opts.headers || {};
  if (token) {
    opts.headers["X-KMP-Token"] = token;
  }
  opts.headers["Content-Type"] = "application/json; charset=utf-8";
  const res = await fetch(path, opts);
  if (res.status === 401) {
    throw new Error("Unauthorized: token is missing or invalid");
  }
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`HTTP ${res.status}: ${txt}`);
  }
  return await res.json();
}

function showError(msg) {
  const box = $("apiError");
  if (!msg) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  box.hidden = false;
  box.textContent = msg;
}

function formToParams() {
  const params = {};
  params["LANG_UI"] = $("langSelect").value;
  params["MODE"] = $("modeSelect").value;
  params["PROFILE"] = $("profileSelect").value;
  params["COLLECTORS"] = $("collectorsSelect").value;
  params["CUSTOM_COLLECTORS"] = $("customCollectorsInput").value.trim();

  params["OUTBASE_POLICY"] = $("outPolicySelect").value;
  params["OUTBASE_OVERRIDE"] = $("outOverrideInput").value.trim();

  params["CLEAN_OLD"] = $("cleanOldChk").checked;
  params["CLEAN_TMP"] = $("cleanTmpChk").checked;

  params["DEPS_LEVEL"] = $("depsLevelSelect").value;
  params["DEPS_MODE"] = $("depsModeSelect").value;
  params["NO_INSTALL"] = $("noInstallChk").checked;

  params["MAX_CPU"] = $("maxCpuInput").value || "85";
  params["MAX_MEM"] = $("maxMemInput").value || "95";
  params["JOBS"] = $("jobsInput").value || "auto";

  params["DEBUG"] = $("debugChk").checked;

  return params;
}

function applyConfig(cfg) {
  $("langSelect").value = cfg.LANG_UI || "ru";
  $("modeSelect").value = cfg.MODE || "full";
  $("profileSelect").value = cfg.PROFILE || "auto";
  $("collectorsSelect").value = cfg.COLLECTORS || "all";
  $("customCollectorsInput").value = cfg.CUSTOM_COLLECTORS || "";

  $("outPolicySelect").value = cfg.OUTBASE_POLICY || "auto";
  $("outOverrideInput").value = cfg.OUTBASE_OVERRIDE || "";

  $("cleanOldChk").checked = String(cfg.CLEAN_OLD || "0") === "1";
  $("cleanTmpChk").checked = String(cfg.CLEAN_TMP || "0") === "1";

  $("depsLevelSelect").value = cfg.DEPS_LEVEL || "core";
  $("depsModeSelect").value = cfg.DEPS_MODE || "cleanup";
  $("noInstallChk").checked = String(cfg.NO_INSTALL || "0") === "1";

  $("maxCpuInput").value = cfg.MAX_CPU || "85";
  $("maxMemInput").value = cfg.MAX_MEM || "95";
  $("jobsInput").value = cfg.JOBS || "auto";

  $("debugChk").checked = String(cfg.DEBUG || "1") === "1";
}

function updateStatus(status) {
  const running = !!status.running;
  $("stateValue").textContent = running ? "running" : "idle";
  $("pidValue").textContent = status.pid ? String(status.pid) : "—";
  $("cmdValue").textContent = status.cmd && status.cmd.length ? status.cmd.join(" ") : "—";

  const latest = status.latest || {};
  $("startedValue").textContent = latest.started_utc || "—";
  $("phaseValue").textContent = latest.phase || "—";
  $("progressValue").textContent = latest.progress || "—";
  $("workdirValue").textContent = latest.workdir || "—";
  $("opkgValue").textContent = latest.opkg_storage_hint || (latest.summary && latest.summary.opkg_storage_hint) || "—";
  $("outbaseValue").textContent = latest.outbase || (latest.summary && latest.summary.outbase) || "—";

  const summ = latest.summary || null;
  if (summ) {
    const tv = summ.tool_version || "";
    const ports = Array.isArray(summ.listen_ports_list) ? summ.listen_ports_list.join(", ") : "";
    $("toolValue").textContent = tv || "—";
    $("portsValue").textContent = ports || "—";
  } else {
    $("toolValue").textContent = "—";
    $("portsValue").textContent = "—";
  }

  const p = parseProgress(latest.progress || "");
  $("progressBar").value = p.pct;
}

function renderArchives(archives) {
  const tbody = $("archivesBody");
  tbody.innerHTML = "";
  if (!archives || !archives.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.className = "muted";
    td.textContent = "No archives";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  const token = getToken();
  for (const a of archives) {
    const tr = document.createElement("tr");
    const nameTd = document.createElement("td");
    nameTd.textContent = a.name || "";
    const sizeTd = document.createElement("td");
    sizeTd.textContent = a.size_h || "";
    const modTd = document.createElement("td");
    modTd.textContent = a.mtime ? formatTime(a.mtime) : "";
    const dlTd = document.createElement("td");
    const link = document.createElement("a");
    link.href = `/download/${encodeURIComponent(a.name)}?token=${encodeURIComponent(token)}`;
    link.textContent = "download";
    dlTd.appendChild(link);

    tr.appendChild(nameTd);
    tr.appendChild(sizeTd);
    tr.appendChild(modTd);
    tr.appendChild(dlTd);
    tbody.appendChild(tr);
  }
}

async function refreshAll() {
  try {
    showError("");
    const st = await apiFetch("/api/status");
    updateStatus(st);
    renderArchives(st.archives || []);
  } catch (e) {
    showError(String(e.message || e));
  }
}

async function refreshLogs() {
  const kind = $("logKindSelect").value;
  try {
    const data = await apiFetch(`/api/log?kind=${encodeURIComponent(kind)}`);
    $("logBox").textContent = data.text || "";
  } catch (e) {
    // keep previous logs, show error in status box
    showError(String(e.message || e));
  }
}

async function init() {
  // Token init
  const tok = getToken();
  $("tokenInput").value = tok || "";

  $("tokenSaveBtn").addEventListener("click", () => {
    const t = $("tokenInput").value.trim();
    setToken(t);
    const u = new URL(window.location.href);
    u.searchParams.set("token", t);
    window.history.replaceState({}, "", u.toString());
    refreshAll();
  });

  $("refreshBtn").addEventListener("click", async () => {
    await refreshAll();
    await refreshLogs();
  });

  $("logKindSelect").addEventListener("change", refreshLogs);

  // Load config
  try {
    const cfg = await apiFetch("/api/config");
    if (cfg && cfg.config) {
      applyConfig(cfg.config);
    }
  } catch (e) {
    showError(String(e.message || e));
  }

  // Start run
  $("runForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const params = formToParams();
    try {
      showError("");
      const res = await apiFetch("/api/run", {method: "POST", body: JSON.stringify(params)});
      if (!res.ok) throw new Error(res.error || "Failed to start");
      await refreshAll();
      await refreshLogs();
    } catch (e) {
      showError(String(e.message || e));
    }
  });

  $("stopBtn").addEventListener("click", async () => {
    try {
      showError("");
      await apiFetch("/api/stop", {method: "POST", body: JSON.stringify({})});

  $("saveDefaultsBtn").addEventListener("click", async () => {
    const params = formToParams();
    const cfg = {
      "LANG_UI": params.LANG_UI,
      "MODE": params.MODE,
      "PROFILE": params.PROFILE,
      "COLLECTORS": params.COLLECTORS,
      "CUSTOM_COLLECTORS": params.CUSTOM_COLLECTORS,

      "OUTBASE_POLICY": params.OUTBASE_POLICY,
      "OUTBASE_OVERRIDE": params.OUTBASE_OVERRIDE,

      "CLEAN_OLD": params.CLEAN_OLD ? "1" : "0",
      "CLEAN_TMP": params.CLEAN_TMP ? "1" : "0",

      "DEPS_LEVEL": params.DEPS_LEVEL,
      "DEPS_MODE": params.DEPS_MODE,
      "NO_INSTALL": params.NO_INSTALL ? "1" : "0",

      "MAX_CPU": params.MAX_CPU,
      "MAX_MEM": params.MAX_MEM,
      "JOBS": params.JOBS,

      "DEBUG": params.DEBUG ? "1" : "0",
      "SPINNER": "0",
      "YES": "1"
    };

    try {
      showError("");
      await apiFetch("/api/config", {method: "POST", body: JSON.stringify(cfg)});
    } catch (e) {
      showError(String(e.message || e));
    }
  });

  $("loadReportBtn").addEventListener("click", async () => {
    const lang = $("reportLangSelect").value;
    try {
      showError("");
      const data = await apiFetch(`/api/report?lang=${encodeURIComponent(lang)}`);
      $("reportBox").textContent = data.text || "";
    } catch (e) {
      showError(String(e.message || e));
    }
  });
      await refreshAll();
      await refreshLogs();
    } catch (e) {
      showError(String(e.message || e));
    }
  });

  // Poll
  setInterval(refreshAll, 1500);
  setInterval(refreshLogs, 2000);

  await refreshAll();
  await refreshLogs();
}

window.addEventListener("DOMContentLoaded", init);
