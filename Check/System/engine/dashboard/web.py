from __future__ import annotations
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse
from engine.dashboard.reader import DashboardSnapshot, snapshot_to_dict
MODULE_NAME = 'dashboard.web'
DEFAULT_PORT = 8765

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="lv">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SYSTEM Command Center</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Syne:wght@600;700;800&display=swap" rel="stylesheet" />
<style>
:root {
  --bg0: #0b1214;
  --bg1: #121c20;
  --bg2: #182428;
  --line: rgba(232,168,73,0.18);
  --brand: #e8a849;
  --ink: #e8eef1;
  --muted: #7f949e;
  --live: #3ecf8e;
  --alert: #ff5f5f;
  --buy: #40c4a0;
  --sell: #f0785a;
  --wait: #b4aa5a;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; min-height: 100%;
  background:
    radial-gradient(1200px 500px at 8% -10%, rgba(232,168,73,0.14), transparent 55%),
    radial-gradient(900px 420px at 100% 0%, rgba(62,207,142,0.08), transparent 45%),
    linear-gradient(180deg, var(--bg0), #071014 70%);
  color: var(--ink);
  font-family: "IBM Plex Mono", ui-monospace, monospace;
}
body { padding: 28px 32px 48px; }
.brand-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 16px;
  align-items: end;
  margin-bottom: 22px;
}
.brand {
  font-family: Syne, sans-serif;
  font-weight: 800;
  font-size: clamp(42px, 7vw, 76px);
  letter-spacing: -0.04em;
  line-height: 0.9;
  color: var(--brand);
  text-shadow: 0 0 40px rgba(232,168,73,0.18);
  animation: brandIn 700ms ease-out both;
}
.subtitle {
  color: var(--muted);
  font-size: 13px;
  margin-top: 10px;
  max-width: 52ch;
}
.pulse {
  display: inline-flex; align-items: center; gap: 8px;
  border: 1px solid var(--line);
  background: rgba(18,28,32,0.8);
  padding: 8px 12px;
  font-size: 12px;
  color: var(--muted);
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--live);
  box-shadow: 0 0 0 0 rgba(62,207,142,0.6);
  animation: beat 1.4s infinite;
}
.layout {
  display: grid;
  grid-template-columns: 1.35fr 0.9fr;
  gap: 18px;
}
@media (max-width: 980px) {
  .layout { grid-template-columns: 1fr; }
  body { padding: 18px; }
}
.panel {
  background: linear-gradient(180deg, rgba(24,36,40,0.92), rgba(12,18,20,0.96));
  border: 1px solid var(--line);
  padding: 16px 18px 18px;
  min-height: 180px;
  animation: rise 550ms ease both;
}
.panel h2 {
  margin: 0 0 14px;
  font-family: Syne, sans-serif;
  font-size: 15px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand);
}
.instance {
  border-top: 1px solid rgba(127,148,158,0.18);
  padding: 14px 0 8px;
}
.instance:first-of-type { border-top: 0; padding-top: 0; }
.symbol {
  font-family: Syne, sans-serif;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
}
.meta { color: var(--muted); font-size: 12px; margin: 4px 0 10px; }
.kv { display: grid; grid-template-columns: 92px 1fr; gap: 4px 10px; font-size: 12px; margin: 6px 0; }
.kv span:first-child { color: var(--muted); }
.spark {
  font-size: 18px;
  letter-spacing: 1px;
  color: var(--live);
  margin: 8px 0;
  overflow: hidden;
  white-space: nowrap;
}
.decision {
  display: inline-block;
  font-family: Syne, sans-serif;
  font-weight: 700;
  font-size: 20px;
  letter-spacing: 0.04em;
}
.BUY { color: var(--buy); }
.SELL { color: var(--sell); }
.WAIT, .BLOCK { color: var(--wait); }
.pos {
  margin-top: 10px;
  padding: 10px 12px;
  border-left: 3px solid var(--live);
  background: rgba(62,207,142,0.06);
  font-size: 12px;
}
.feed {
  max-height: 72vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.event {
  display: grid;
  grid-template-columns: 74px 70px 1fr;
  gap: 8px;
  font-size: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(127,148,158,0.12);
  animation: tick 320ms ease both;
}
.kind { color: var(--brand); font-weight: 600; }
.kind.ERROR { color: var(--alert); }
.kind.TRADE, .kind.CONTROL, .kind.ACK { color: var(--live); }
.detail { color: var(--muted); word-break: break-word; }
.empty { color: var(--muted); font-size: 13px; padding: 20px 0; }
.footer {
  margin-top: 18px;
  color: var(--muted);
  font-size: 11px;
}
@keyframes beat {
  0% { box-shadow: 0 0 0 0 rgba(62,207,142,0.55); }
  70% { box-shadow: 0 0 0 10px rgba(62,207,142,0); }
  100% { box-shadow: 0 0 0 0 rgba(62,207,142,0); }
}
@keyframes brandIn {
  from { opacity: 0; transform: translateY(12px); filter: blur(4px); }
  to { opacity: 1; transform: none; filter: none; }
}
@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: none; }
}
@keyframes tick {
  from { opacity: 0; transform: translateX(6px); }
  to { opacity: 1; transform: none; }
}
</style>
</head>
<body>
  <div class="brand-row">
    <div>
      <div class="brand" id="brand">SYSTEM</div>
      <div class="subtitle">Live robot command center — every decision, control, ACK and trail from real client files. Not a simulator view.</div>
    </div>
    <div class="pulse"><span class="dot"></span><span id="stamp">connecting…</span></div>
  </div>
  <div class="layout">
    <section class="panel">
      <h2>Live instruments</h2>
      <div id="instances"><div class="empty">Waiting for PALAID + MT4 exports…</div></div>
    </section>
    <section class="panel">
      <h2>Robot action feed</h2>
      <div class="feed" id="feed"><div class="empty">No actions yet</div></div>
    </section>
  </div>
  <div class="footer" id="footer"></div>
<script>
const el = (id) => document.getElementById(id);
function ageLabel(ms) {
  if (ms === null || ms === undefined) return 'MISSING';
  if (ms < 2000) return ms + 'ms LIVE';
  if (ms < 60000) return (ms/1000).toFixed(1) + 's';
  return (ms/60000).toFixed(1) + 'm STALE';
}
function render(data) {
  el('brand').textContent = data.system_name || 'SYSTEM';
  el('stamp').textContent = (data.generated_at_utc || '') + ' · ' + (data.instance_count || 0) + ' instances';
  el('footer').textContent = (data.root_path || '') + ' · refresh 1s · read-only observer';
  const box = el('instances');
  if (!data.instances || !data.instances.length) {
    box.innerHTML = '<div class="empty">No active instances. Keep PALAID.bat running with SYSTEM_EA on M1.</div>';
  } else {
    box.innerHTML = data.instances.map(v => {
      const decision = v.last_decision || '-';
      const pos = v.open_ticket == null ? '<div class="meta">position: flat</div>' :
        `<div class="pos"><strong>${v.position_side || '-'} ${v.open_ticket}</strong> vol=${v.position_volume}
         · entry=${v.entry_price} · sl=${v.stop_loss} · tp=${v.take_profit || 0}
         · bars=${v.position_bars_open}</div>`;
      return `<div class="instance">
        <div class="symbol">${v.symbol}</div>
        <div class="meta">account ${v.account_id} · magic ${v.magic} · cycles ${v.cycle_count ?? '-'}</div>
        <div><span class="decision ${decision}">${decision}</span>
          <span class="meta"> · risk ${v.risk_result || '-'} · health ${v.instance_health || '-'}</span></div>
        <div class="kv"><span>reason</span><span>${v.last_reason || '-'}</span>
          <span>scores</span><span>buy ${v.buy_score ?? '-'} / sell ${v.sell_score ?? '-'} · ai ${v.ai_mode || '-'}</span>
          <span>market</span><span>${v.sparkline || '—'} · close ${v.last_close ?? '-'}</span>
          <span>quotes</span><span>bid ${v.bid ?? '-'} / ask ${v.ask ?? '-'} · spread ${v.current_spread ?? '-'} (${v.relative_spread ?? '-'}σ)</span>
          <span>ages</span><span>m ${ageLabel(v.market_age_ms)} · s ${ageLabel(v.sensor_age_ms)} · st ${ageLabel(v.status_age_ms)}</span>
          <span>broker</span><span>conn ${v.broker_connected ?? '?'} · trade ${v.trade_allowed ?? '?'} · eq ${v.equity ?? '-'}</span>
          <span>exec</span><span>control ${v.control_action || '-'} · trade ${v.last_trade_event || '-'}/${v.last_trade_ack || '-'} · ack ${v.last_ack_status || '-'}</span>
        </div>
        ${pos}
      </div>`;
    }).join('');
  }
  const feed = el('feed');
  if (!data.action_feed || !data.action_feed.length) {
    feed.innerHTML = '<div class="empty">Waiting for first robot action…</div>';
  } else {
    feed.innerHTML = data.action_feed.map(e => {
      const t = (e.timestamp_utc || '').replace('T',' ').replace('Z','').slice(11,19);
      return `<div class="event"><div>${t}</div><div class="kind ${e.kind}">${e.kind}</div>
        <div><strong>${e.symbol || ''} ${e.summary || ''}</strong><div class="detail">${e.detail || ''}</div></div></div>`;
    }).join('');
  }
}
async function tick() {
  try {
    const res = await fetch('/api/snapshot', { cache: 'no-store' });
    render(await res.json());
  } catch (err) {
    el('stamp').textContent = 'offline — is DASHBOARD.bat running?';
  }
}
tick();
setInterval(tick, 1000);
</script>
</body>
</html>
"""

SnapshotProvider = Callable[[], DashboardSnapshot]


def create_dashboard_handler(provider: SnapshotProvider) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {'/', '/index.html'}:
                self._send(200, DASHBOARD_HTML.encode('utf-8'), 'text/html; charset=utf-8')
                return
            if path == '/api/snapshot':
                payload = snapshot_to_dict(provider())
                body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                self._send(200, body, 'application/json; charset=utf-8')
                return
            self._send(404, b'not found', 'text/plain; charset=utf-8')

    return DashboardHandler


def start_dashboard_server(*, provider: SnapshotProvider, host: str='127.0.0.1', port: int=DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = create_dashboard_handler(provider)
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, name='system-dashboard-http', daemon=True)
    thread.start()
    return server
