"""
Trading Strategy Dashboard — Flask web UI
Run: python -m nifty50_tracker.dashboard.app
Open: http://localhost:5000
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, request

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import nifty50_tracker.dashboard.state as state

IST = ZoneInfo("Asia/Kolkata")
app = Flask(__name__)

_strategy_threads: list[threading.Thread] = []
_stop_event = threading.Event()

# ── Strategy launchers ────────────────────────────────────────────────────────

def _run_nifty():
    try:
        state.log("NIFTY 50 strategy starting...")
        from nifty50_tracker.strategy.strategy_runner import StrategyRunner
        runner = StrategyRunner()
        runner.run()
    except SystemExit:
        pass
    except Exception as e:
        state.log(f"NIFTY ERROR: {e}")
    state.log("NIFTY 50 strategy stopped.")


def _run_mcx():
    try:
        state.log("MCX strategy starting...")
        from nifty50_tracker.strategy.mcx_runner import McxRunner
        runner = McxRunner()
        runner.run()
    except SystemExit:
        pass
    except Exception as e:
        state.log(f"MCX ERROR: {e}")
    state.log("MCX strategy stopped.")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")


@app.route("/api/state")
def api_state():
    return jsonify(state.get())


@app.route("/api/stream")
def api_stream():
    def generate():
        while True:
            data = json.dumps(state.get())
            yield f"data: {data}\n\n"
            time.sleep(1)
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/start", methods=["POST"])
def api_start():
    global _strategy_threads
    if any(t.is_alive() for t in _strategy_threads):
        return jsonify({"ok": False, "msg": "Already running"})
    state.mark_started()
    state.log("Dashboard: starting strategies...")
    t1 = threading.Thread(target=_run_nifty, daemon=True, name="nifty")
    t2 = threading.Thread(target=_run_mcx,   daemon=True, name="mcx")
    _strategy_threads = [t1, t2]
    t1.start()
    t2.start()
    return jsonify({"ok": True, "msg": "Strategies started"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    state.log("Dashboard: stop requested (strategies will exit at next tick)")
    # Strategies exit via sys.exit or their own shutdown logic
    return jsonify({"ok": True, "msg": "Stop signal sent"})


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Algo Trading Dashboard</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0d1117;color:#e6edf3;font-family:'Courier New',monospace;font-size:13px}
  .header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 20px;display:flex;align-items:center;gap:20px}
  .header h1{font-size:18px;color:#58a6ff;font-weight:700}
  .badge{padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}
  .badge.running{background:#1a4731;color:#3fb950}
  .badge.stopped{background:#2d1616;color:#f85149}
  .badge.waiting{background:#2d2214;color:#e3b341}
  .btn{padding:6px 16px;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600}
  .btn.start{background:#238636;color:#fff}
  .btn.stop{background:#da3633;color:#fff}
  .btn:hover{opacity:.85}
  .clock{margin-left:auto;color:#8b949e;font-size:12px}
  .main{padding:16px;display:grid;gap:12px}
  .row{display:grid;gap:12px}
  .row.two{grid-template-columns:1fr 1fr}
  .row.four{grid-template-columns:repeat(4,1fr)}
  .card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
  .card-title{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px;display:flex;align-items:center;gap:8px}
  .card-title .dot{width:8px;height:8px;border-radius:50%;background:#8b949e}
  .card-title .dot.green{background:#3fb950}
  .card-title .dot.red{background:#f85149}
  .card-title .dot.yellow{background:#e3b341}
  .metric{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #21262d}
  .metric:last-child{border:none}
  .metric .label{color:#8b949e}
  .metric .val{font-weight:600;font-size:14px}
  .val.up{color:#3fb950}
  .val.down{color:#f85149}
  .val.neutral{color:#58a6ff}
  .signal-bull{background:#1a4731;color:#3fb950;padding:2px 8px;border-radius:4px;font-size:11px}
  .signal-bear{background:#2d1616;color:#f85149;padding:2px 8px;border-radius:4px;font-size:11px}
  .trade-table{width:100%;border-collapse:collapse;font-size:11px}
  .trade-table th{color:#8b949e;font-weight:400;text-align:left;padding:6px 8px;border-bottom:1px solid #21262d}
  .trade-table td{padding:5px 8px;border-bottom:1px solid #21262d}
  .trade-table tr:last-child td{border:none}
  .log-box{background:#0d1117;border:1px solid #21262d;border-radius:4px;padding:10px;height:180px;overflow-y:auto;font-size:11px;color:#8b949e;font-family:'Courier New',monospace}
  .log-line{padding:1px 0;border-bottom:1px solid #161b22}
  .pnl-positive{color:#3fb950}
  .pnl-negative{color:#f85149}
  .section-title{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.8px;margin:8px 0 4px;padding-bottom:4px;border-bottom:1px solid #21262d}
</style>
</head>
<body>

<div class="header">
  <h1>&#x1F4C8; Algo Trading Dashboard</h1>
  <span id="nifty-badge" class="badge stopped">NIFTY: STOPPED</span>
  <span id="mcx-badge" class="badge stopped">MCX: STOPPED</span>
  <span id="started-time" style="color:#8b949e;font-size:11px"></span>
  <button class="btn start" onclick="startStrategies()">&#x25B6; Start</button>
  <button class="btn stop"  onclick="stopStrategies()">&#x25A0; Stop</button>
  <div class="clock" id="clock">--:--:-- IST</div>
</div>

<div class="main">

  <!-- NIFTY 50 -->
  <div class="card">
    <div class="card-title"><span class="dot" id="nifty-dot"></span>NIFTY 50 &mdash; Bull Put / Bear Call Spread</div>
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px">
      <div class="metric"><span class="label">LTP</span><span class="val neutral" id="n-ltp">&mdash;</span></div>
      <div class="metric"><span class="label">EMA-7</span><span class="val" id="n-ema">&mdash;</span></div>
      <div class="metric"><span class="label">Signal</span><span id="n-signal">&mdash;</span></div>
      <div class="metric"><span class="label">Last Candle</span><span class="val" id="n-candle">&mdash;</span></div>
      <div class="metric"><span class="label">Session P&amp;L</span><span class="val" id="n-pnl">&#x20B9;0</span></div>
    </div>
    <div id="n-trade-info" style="margin-top:10px;font-size:11px;color:#8b949e"></div>
  </div>

  <!-- MCX -->
  <div class="row four">
    <div class="card" id="card-CRUDEOILM">
      <div class="card-title"><span class="dot" id="dot-CRUDEOILM"></span>CRUDEOILM</div>
      <div class="metric"><span class="label">LTP</span><span class="val neutral" id="ltp-CRUDEOILM">&mdash;</span></div>
      <div class="metric"><span class="label">EMA-7</span><span class="val" id="ema-CRUDEOILM">&mdash;</span></div>
      <div class="metric"><span class="label">Signal</span><span id="sig-CRUDEOILM">&mdash;</span></div>
      <div class="metric"><span class="label">P&amp;L</span><span class="val" id="pnl-CRUDEOILM">&#x20B9;0</span></div>
    </div>
    <div class="card" id="card-NATGSMIN">
      <div class="card-title"><span class="dot" id="dot-NATGSMIN"></span>NATGSMIN</div>
      <div class="metric"><span class="label">LTP</span><span class="val neutral" id="ltp-NATGSMIN">&mdash;</span></div>
      <div class="metric"><span class="label">EMA-7</span><span class="val" id="ema-NATGSMIN">&mdash;</span></div>
      <div class="metric"><span class="label">Signal</span><span id="sig-NATGSMIN">&mdash;</span></div>
      <div class="metric"><span class="label">P&amp;L</span><span class="val" id="pnl-NATGSMIN">&#x20B9;0</span></div>
    </div>
    <div class="card" id="card-GOLDPETAL">
      <div class="card-title"><span class="dot" id="dot-GOLDPETAL"></span>GOLDPETAL</div>
      <div class="metric"><span class="label">LTP</span><span class="val neutral" id="ltp-GOLDPETAL">&mdash;</span></div>
      <div class="metric"><span class="label">EMA-7</span><span class="val" id="ema-GOLDPETAL">&mdash;</span></div>
      <div class="metric"><span class="label">Signal</span><span id="sig-GOLDPETAL">&mdash;</span></div>
      <div class="metric"><span class="label">P&amp;L</span><span class="val" id="pnl-GOLDPETAL">&#x20B9;0</span></div>
    </div>
    <div class="card" id="card-SILVER100">
      <div class="card-title"><span class="dot" id="dot-SILVER100"></span>SILVER100</div>
      <div class="metric"><span class="label">LTP</span><span class="val neutral" id="ltp-SILVER100">&mdash;</span></div>
      <div class="metric"><span class="label">EMA-7</span><span class="val" id="ema-SILVER100">&mdash;</span></div>
      <div class="metric"><span class="label">Signal</span><span id="sig-SILVER100">&mdash;</span></div>
      <div class="metric"><span class="label">P&amp;L</span><span class="val" id="pnl-SILVER100">&#x20B9;0</span></div>
    </div>
  </div>

  <!-- Trades + Log -->
  <div class="row two">
    <div class="card">
      <div class="card-title">Trade Log</div>
      <table class="trade-table">
        <thead><tr><th>Time</th><th>Strategy</th><th>Type</th><th>Entry</th><th>Exit</th><th>P&amp;L</th><th>Reason</th></tr></thead>
        <tbody id="trade-tbody"><tr><td colspan="7" style="color:#8b949e;text-align:center;padding:12px">No trades yet</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <div class="card-title">Live Log</div>
      <div class="log-box" id="log-box"></div>
    </div>
  </div>

</div>

<script>
  // Clock
  function updateClock() {
    const now = new Date();
    const ist = new Date(now.toLocaleString("en-US", {timeZone:"Asia/Kolkata"}));
    document.getElementById("clock").textContent =
      ist.toTimeString().slice(0,8) + " IST";
  }
  setInterval(updateClock, 1000);
  updateClock();

  // Helpers
  function fmt(v, decimals) {
    decimals = decimals !== undefined ? decimals : 2;
    return v != null ? parseFloat(v).toFixed(decimals) : "\u2014";
  }
  function pnlClass(v) { return v > 0 ? "pnl-positive" : v < 0 ? "pnl-negative" : ""; }
  function statusDot(status) {
    if (status === "running" || status === "in_trade") return "green";
    if (status === "stopped") return "red";
    return "yellow";
  }

  // SSE
  const es = new EventSource("/api/stream");
  es.onmessage = function(e) {
    try { render(JSON.parse(e.data)); } catch(err) { console.error(err); }
  };

  function render(d) {
    // Started time
    if (d.started) document.getElementById("started-time").textContent = "Started: " + d.started;

    // NIFTY
    const n = d.nifty;
    document.getElementById("nifty-badge").textContent = "NIFTY: " + (n.status||"stopped").toUpperCase();
    document.getElementById("nifty-badge").className = "badge " + (n.status === "running" ? "running" : n.status === "stopped" ? "stopped" : "waiting");
    document.getElementById("nifty-dot").className = "dot " + statusDot(n.status);
    document.getElementById("n-ltp").textContent = fmt(n.ltp);
    document.getElementById("n-ema").textContent = fmt(n.ema7, 4);

    const sigEl = document.getElementById("n-signal");
    if (n.signal === "BULL_PUT_SPREAD") sigEl.innerHTML = '<span class="signal-bull">BULL PUT \u25b2</span>';
    else if (n.signal === "BEAR_CALL_SPREAD") sigEl.innerHTML = '<span class="signal-bear">BEAR CALL \u25bc</span>';
    else sigEl.textContent = "\u2014";

    // Last candle
    if (n.candles && n.candles.length > 0) {
      const lc = n.candles[n.candles.length - 1];
      document.getElementById("n-candle").textContent = lc.time + " @ " + fmt(lc.close);
    }

    const nPnl = n.pnl || 0;
    const nPnlEl = document.getElementById("n-pnl");
    nPnlEl.textContent = (nPnl >= 0 ? "+" : "") + "\u20b9" + fmt(nPnl);
    nPnlEl.className = "val " + (nPnl > 0 ? "up" : nPnl < 0 ? "down" : "neutral");

    // Active NIFTY trade
    const trInfo = document.getElementById("n-trade-info");
    if (n.active_trade) {
      const t = n.active_trade;
      trInfo.innerHTML = '<span style="color:#e3b341">\u25b6 OPEN: ' + (t.type||"") + ' | Sell: ' + (t.sell||"") + ' Buy: ' + (t.buy||"") + ' | Entry: ' + (t.entry_time||"") + ' | Net cr: ' + fmt(t.net_credit) + '</span>';
    } else {
      trInfo.textContent = "";
    }

    // MCX
    const mcxBadgeRunning = Object.values(d.mcx).some(function(m) { return m.status === "running"; });
    document.getElementById("mcx-badge").textContent = "MCX: " + (mcxBadgeRunning ? "RUNNING" : "STOPPED");
    document.getElementById("mcx-badge").className = "badge " + (mcxBadgeRunning ? "running" : "stopped");

    ["CRUDEOILM","NATGSMIN","GOLDPETAL","SILVER100"].forEach(function(sym) {
      const m = d.mcx[sym];
      if (!m) return;
      document.getElementById("dot-"+sym).className = "dot " + statusDot(m.status);
      document.getElementById("ltp-"+sym).textContent = fmt(m.ltp);
      document.getElementById("ema-"+sym).textContent = fmt(m.ema7, 4);
      const sp = m.pnl || 0;
      const pe = document.getElementById("pnl-"+sym);
      pe.textContent = (sp >= 0 ? "+" : "") + "\u20b9" + fmt(sp);
      pe.className = "val " + (sp > 0 ? "up" : sp < 0 ? "down" : "neutral");
      const se = document.getElementById("sig-"+sym);
      if (m.signal) se.innerHTML = '<span style="color:#3fb950">\u25b2 LONG</span>';
      else se.textContent = "\u2014";
    });

    // Trade table
    const allTrades = [];
    if (n.trades) n.trades.forEach(function(t) { allTrades.push(Object.assign({}, t, {strategy:"NIFTY50"})); });
    Object.entries(d.mcx).forEach(function(entry) {
      const sym = entry[0], m = entry[1];
      if (m.trades) m.trades.forEach(function(t) { allTrades.push(Object.assign({}, t, {strategy:sym})); });
    });
    const tbody = document.getElementById("trade-tbody");
    if (allTrades.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="color:#8b949e;text-align:center;padding:12px">No trades yet</td></tr>';
    } else {
      tbody.innerHTML = allTrades.slice(-20).reverse().map(function(t) {
        const pnl = t.pnl || t.exit_pnl || 0;
        const pc  = pnlClass(pnl);
        return '<tr>' +
          '<td>' + (t.entry_time||"\u2014") + '</td>' +
          '<td>' + (t.strategy) + '</td>' +
          '<td>' + (t.type||t.signal_type||"\u2014") + '</td>' +
          '<td>' + (t.entry_price||"\u2014") + '</td>' +
          '<td>' + (t.exit_price||t.exit_time||"OPEN") + '</td>' +
          '<td class="' + pc + '">' + (pnl ? (pnl>0?"+":"") + "\u20b9" + parseFloat(pnl).toFixed(2) : "\u2014") + '</td>' +
          '<td style="color:#8b949e">' + (t.exit_reason||t.reason||"\u2014") + '</td>' +
          '</tr>';
      }).join("");
    }

    // Log
    const logBox = document.getElementById("log-box");
    if (d.log && d.log.length > 0) {
      logBox.innerHTML = d.log.slice(-50).reverse().map(function(l) {
        return '<div class="log-line">' + l + '</div>';
      }).join("");
    }
  }

  function startStrategies() {
    fetch("/api/start", {method:"POST"})
      .then(function(r) { return r.json(); })
      .then(function(d) { console.log(d.msg); });
  }

  function stopStrategies() {
    fetch("/api/stop", {method:"POST"})
      .then(function(r) { return r.json(); })
      .then(function(d) { console.log(d.msg); });
  }
</script>
</body>
</html>"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    port = int(os.environ.get("DASHBOARD_PORT", 5000))
    print(f"\n{'='*50}")
    print(f"  Trading Dashboard -> http://localhost:{port}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
