async function api(path) {
  const r = await fetch(path, { cache: 'no-store' });
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('application/json')) return await r.json();
  return await r.text();
}

function fmtTime(ts) {
  try {
    const d = new Date(ts * 1000);
    return d.toLocaleString();
  } catch {
    return String(ts);
  }
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function refresh() {
  try {
    const st = await api('/api/status');
    document.getElementById('serverTime').textContent = 'Server: ' + fmtTime(st.server_time);
    const dot = document.getElementById("aliveDot");
    if (dot) {
      const hasErr = (st.work && st.work.errors_tail && st.work.errors_tail.trim().length > 0);
      dot.className = "dot " + (hasErr ? "error" : (st.alive ? "running" : "idle"));
    }


    const work = st.work || {};
    document.getElementById('phase').textContent = work.phase || '—';
    document.getElementById('progress').textContent = work.progress || '—';
    const m = work.metrics || {};
    document.getElementById('cpu').textContent = (m.cpu_pct ?? '—') + '%';
    document.getElementById('mem').textContent = (m.mem_used_pct ?? '—') + '%';
    document.getElementById('load1').textContent = (m.load1 ?? '—');
    document.getElementById('workdir').textContent = work.workdir || '—';

    // logs
    const log = await api('/api/log?n=250');
    document.getElementById('log').textContent = log || '';

    // archives
    const runs = await api('/api/runs');
    renderArchives(runs.archives || []);

  } catch (e) {
    document.getElementById('log').textContent = 'Error: ' + e;
  }
}

function humanSize(bytes) {
  const u = ['B','KB','MB','GB','TB'];
  let b = Number(bytes || 0);
  let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return b.toFixed(i === 0 ? 0 : 1) + ' ' + u[i];
}

function renderArchives(list) {
  const el = document.getElementById('archives');
  if (!list.length) {
    el.innerHTML = '<div class="hint">Архивов пока нет.</div>';
    return;
  }
  let html = '<table><thead><tr><th>Run</th><th>Size</th><th>MTime</th><th>Download</th></tr></thead><tbody>';
  for (const a of list.slice(0, 10)) {
    const fn = a.archive.split('/').slice(-1)[0];
    const sha = fn + '.sha256';
    html += '<tr>' +
      '<td class="mono">' + esc(a.id) + '</td>' +
      '<td>' + esc(humanSize(a.size)) + '</td>' +
      '<td>' + esc(fmtTime(a.mtime)) + '</td>' +
      '<td>' +
      '<a href="/download/' + encodeURIComponent(fn) + '">.tar.gz</a> ' +
      '<a href="/download/' + encodeURIComponent(sha) + '">.sha256</a>' +
      '</td>' +
      '</tr>';
  }
  html += '</tbody></table>';
  el.innerHTML = html;
}

async function start(preset) {
  const el = document.getElementById('startMsg');
  try {
    el.textContent = 'Starting: ' + preset + ' …';
    const r = await api('/api/start?preset=' + encodeURIComponent(preset));
    if (r.ok) {
      el.textContent = 'Started: pid=' + (r.state.pid || '?');
    } else {
      el.textContent = 'Not started: ' + (r.msg || '');
    }
  } catch (e) {
    el.textContent = 'Error: ' + e;
  }
}

async function stop() {
  const el = document.getElementById('startMsg');
  try {
    const r = await api('/api/stop');
    el.textContent = r.msg || 'stop';
  } catch (e) {
    el.textContent = 'Error: ' + e;
  }
}

function setup() {
  document.querySelectorAll('button[data-preset]').forEach(btn => {
    btn.addEventListener('click', () => start(btn.getAttribute('data-preset')));
  });
  document.getElementById('stopBtn').addEventListener('click', stop);
  setInterval(refresh, 1000);
  refresh();
}

setup();
