from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify
from flask_cors import CORS
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")

DASHBOARD_PWD = os.getenv("DASHBOARD_PWD", "Nifty@2026")

def check_password(pwd):
    return pwd == DASHBOARD_PWD

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "nifty_db"),
        user=os.getenv("DB_USER", "nifty"),
        password=os.getenv("DB_PASS", "Nifty@2026")
    )

def get_distinct_dates():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT SUBSTR(timestamp, 1, 10) as data_date
            FROM option_chain
            ORDER BY data_date DESC
        """)
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except:
        return []

def get_timestamps_for_date(selected_date):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT timestamp
            FROM option_chain
            WHERE timestamp LIKE %s
            ORDER BY timestamp DESC
        """, (f"{selected_date}%",))
        rows = c.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except:
        return []

def get_snapshot(timestamp):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT tag, ce_oi, ce_coi, ce_volume, ce_ltp,
                   strike, pe_ltp, pe_volume, pe_coi, pe_oi
            FROM option_chain
            WHERE timestamp = %s
            ORDER BY strike ASC
        """, (timestamp,))
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []

def get_latest_snapshot():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT timestamp FROM option_chain
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = c.fetchone()
        conn.close()
        if not row:
            return None, []
        latest_ts = row[0]
        return latest_ts, get_snapshot(latest_ts)
    except:
        return None, []

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nifty Option Chain Dashboard</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0d1117; color:#e6edf3; font-family:'Segoe UI',Arial,sans-serif; font-size:13px; }
.login-wrap { min-height:100vh; display:flex; align-items:center; justify-content:center; }
.login-box { background:#161b22; border:1px solid #30363d; border-radius:16px; padding:40px 36px; width:340px; text-align:center; }
.login-logo { font-size:36px; margin-bottom:12px; }
.login-box h2 { color:#2196f3; font-size:20px; margin-bottom:6px; }
.login-box p { color:#8b949e; font-size:12px; margin-bottom:24px; }
.login-box input { width:100%; padding:12px 16px; background:#21262d; border:1px solid #30363d; border-radius:8px; color:#e6edf3; font-size:14px; margin-bottom:12px; outline:none; }
.login-box input:focus { border-color:#2196f3; }
.login-btn { width:100%; padding:12px; background:linear-gradient(135deg,#1565c0,#2196f3); color:#fff; border:none; border-radius:8px; font-size:14px; font-weight:bold; cursor:pointer; }
.login-btn:hover { opacity:0.9; }
.error-msg { color:#ef5350; font-size:12px; margin-top:12px; padding:8px; background:#1a0000; border-radius:6px; }
.header { background:linear-gradient(135deg,#0a2342,#1a3a5c); padding:10px 14px; display:flex; justify-content:space-between; align-items:center; position:sticky; top:0; z-index:100; }
.header-title { color:#2196f3; font-size:15px; font-weight:bold; }
.header-sub { color:#90caf9; font-size:11px; margin-top:2px; }
.header-right { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.live-badge { background:#0d2137; border:1px solid #2196f3; color:#64b5f6; padding:4px 10px; border-radius:20px; font-size:11px; display:flex; align-items:center; gap:6px; }
.live-dot { width:7px; height:7px; border-radius:50%; background:#4caf50; animation:blink 1.2s infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.2} }
.logout-btn { color:#ef5350; font-size:11px; text-decoration:none; padding:4px 10px; border:1px solid #ef5350; border-radius:6px; }
.filter-section { background:#161b22; border-bottom:1px solid #30363d; }
.filter-label { padding:6px 12px 2px 12px; font-size:10px; text-transform:uppercase; color:#8b949e; letter-spacing:1px; }
.ts-bar { padding:6px 12px 10px 12px; display:flex; gap:6px; overflow-x:auto; scrollbar-width:none; }
.ts-btn { background:#21262d; color:#8b949e; border:1px solid #30363d; padding:5px 12px; border-radius:6px; font-size:11px; cursor:pointer; white-space:nowrap; }
.ts-btn.active { background:#2196f3; color:#fff; border-color:#2196f3; font-weight:bold; }
.ts-btn:hover:not(.active) { background:#30363d; color:#e6edf3; }
.date-btn.active { background:#2ea44f; color:#fff; border-color:#2ea44f; font-weight:bold; }
.active-ts { background:#0d1117; padding:6px 14px; border-bottom:1px solid #30363d; display:flex; align-items:center; gap:8px; }
.active-ts-badge { background:#0d2137; color:#2196f3; padding:4px 14px; border-radius:20px; font-size:11px; border:1px solid #2196f3; }
.latest-tag { background:#1b5e20; color:#a5d6a7; padding:2px 8px; border-radius:10px; font-size:10px; }
.main-content { display:block; }
.table-side { min-width:0; }
.chart-side { display:none; }
.table-wrap { overflow-x:auto; padding:10px; -webkit-overflow-scrolling:touch; }
table { width:100%; border-collapse:collapse; min-width:580px; }
.ce-head { background:#0d2137; color:#64b5f6; }
.st-head { background:#0a1628; color:#fff; }
.pe-head { background:#1a0d2e; color:#ce93d8; }
th { padding:7px 6px; text-align:center; font-size:11px; font-weight:700; letter-spacing:0.5px; }
td { padding:7px 6px; text-align:center; border-bottom:1px solid #1c2128; font-size:12px; }
tr:nth-child(even) td { background:#0d1117; }
tr:nth-child(odd) td { background:#161b22; }
tr:hover td { background:#1c2128; }
.atm-row td { background:#0d2137; border-top:2px solid #2196f3; border-bottom:2px solid #2196f3; }
.strike-col { color:#ffd700; font-weight:bold; font-size:13px; }
.atm-badge { display:inline-block; background:#2196f3; color:#fff; font-size:9px; padding:1px 5px; border-radius:4px; margin-left:4px; vertical-align:middle; }
.highest-oi { background:#1b5e20; color:#a5d6a7; font-weight:bold; border-radius:4px; padding:2px 4px; }
.lowest-oi { background:#b71c1c; color:#ef9a9a; font-weight:bold; border-radius:4px; padding:2px 4px; }
.highest-vol { background:#0d47a1; color:#90caf9; font-weight:bold; border-radius:4px; padding:2px 4px; }
.drastic-coi { background:#e65100; color:#ffcc80; font-weight:bold; border-radius:4px; padding:2px 4px; }
.positive-coi { color:#4caf50; font-weight:bold; }
.negative-coi { color:#ef5350; font-weight:bold; }
.neutral-coi { color:#8b949e; }
.ce-val { color:#90caf9; }
.pe-val { color:#ce93d8; }
.legend { display:flex; flex-wrap:wrap; gap:10px; padding:10px 14px; background:#161b22; border-top:1px solid #30363d; }
.legend-item { display:flex; align-items:center; gap:5px; font-size:11px; color:#8b949e; }
.legend-dot { width:12px; height:12px; border-radius:3px; flex-shrink:0; }
.no-data { text-align:center; padding:60px 20px; color:#8b949e; font-size:14px; }
.no-data .icon { font-size:48px; margin-bottom:12px; }
@media (min-width:1024px) {
  .main-content { display:grid; grid-template-columns:1fr 440px; align-items:start; }
  .chart-side { display:flex; flex-direction:column; position:sticky; top:54px; height:calc(100vh - 54px); border-left:1px solid #30363d; }
  .chart-header { background:#0a2342; padding:8px 14px; border-bottom:1px solid #30363d; }
  .chart-title { color:#2196f3; font-size:13px; font-weight:bold; }
  .chart-subtitle { color:#8b949e; font-size:10px; }
  .tv-widget-wrap { flex:1; min-height:0; position:relative; }
  .tv-widget-wrap > div, .tv-widget-wrap iframe { width:100% !important; height:100% !important; }
}
@media (min-width:768px) and (max-width:1023px) {
  .header-title { font-size:17px; }
  .ts-btn { font-size:12px; padding:8px 16px; }
  td, th { font-size:13px; padding:9px 8px; }
}
</style>
</head>
<body>
{% if not logged_in %}
<div class="login-wrap">
  <div class="login-box">
    <div class="login-logo">📊</div>
    <h2>Nifty Option Chain</h2>
    <p>Enter your password to access the dashboard</p>
    <form method="POST" action="/login">
      <input type="password" name="password" placeholder="Enter Password" autofocus>
      <button type="submit" class="login-btn">Login</button>
    </form>
    {% if error %}<div class="error-msg">Wrong password! Please try again.</div>{% endif %}
  </div>
</div>
{% else %}
<div class="header">
  <div>
    <div class="header-title">📈 Nifty 50 Option Chain</div>
    <div class="header-sub">Live data from Angel One — Every 5 minutes</div>
  </div>
  <div class="header-right">
    <div class="live-badge"><span class="live-dot"></span>Refresh in <span id="cd">300</span>s</div>
    <a href="/logout" class="logout-btn">Logout</a>
  </div>
</div>
<div class="filter-section">
  <div class="filter-label">Select Date</div>
  <div class="ts-bar" id="dateBar">
    {% for dt in dates %}
    <button class="ts-btn date-btn {% if dt == selected_date %}active{% endif %}" onclick="changeDate('{{ dt }}')">{{ dt }}</button>
    {% endfor %}
  </div>
  <div class="filter-label">Select Time</div>
  <div class="ts-bar" id="tsBar">
    {% for ts in timestamps %}
    <button class="ts-btn {% if ts == selected_ts %}active{% endif %}" onclick="loadTs('{{ selected_date }}','{{ ts }}')">{{ ts[11:16] }}</button>
    {% endfor %}
  </div>
</div>
<div class="active-ts">
  <span class="active-ts-badge">Active Snapshot: {{ selected_ts }}</span>
  {% if global_latest_ts and selected_ts == global_latest_ts %}<span class="latest-tag">LATEST</span>{% endif %}
</div>
<div class="main-content">
  <div class="table-side">
    <div class="table-wrap">
    {% if rows %}
    <table>
      <thead>
        <tr>
          <th class="ce-head" colspan="4">CALL (CE) ◀️</th>
          <th class="st-head">STRIKE</th>
          <th class="pe-head" colspan="4">▶️ PUT (PE)</th>
        </tr>
        <tr>
          <th class="ce-head">OI</th><th class="ce-head">CHG OI</th><th class="ce-head">VOLUME</th><th class="ce-head">LTP</th>
          <th class="st-head"></th>
          <th class="pe-head">LTP</th><th class="pe-head">VOLUME</th><th class="pe-head">CHG OI</th><th class="pe-head">OI</th>
        </tr>
      </thead>
      <tbody>
      {% for row in rows %}
      <tr class="{% if row.tag == 'ATM' %}atm-row{% endif %}">
        <td class="{{ row.ce_oi_class }}">{{ "{:,}".format(row.ce_oi) }}</td>
        <td class="{{ row.ce_coi_class }}">{% if row.ce_coi > 0 %}+{% endif %}{{ "{:,}".format(row.ce_coi) }}</td>
        <td class="{{ row.ce_vol_class }}">{{ "{:,}".format(row.ce_volume) }}</td>
        <td class="ce-val">{{ row.ce_ltp }}</td>
        <td class="strike-col">{{ "{:,}".format(row.strike) }}{% if row.tag == 'ATM' %}<span class="atm-badge">ATM</span>{% endif %}</td>
        <td class="pe-val">{{ row.pe_ltp }}</td>
        <td class="{{ row.pe_vol_class }}">{{ "{:,}".format(row.pe_volume) }}</td>
        <td class="{{ row.pe_coi_class }}">{% if row.pe_coi > 0 %}+{% endif %}{{ "{:,}".format(row.pe_coi) }}</td>
        <td class="{{ row.pe_oi_class }}">{{ "{:,}".format(row.pe_oi) }}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div class="no-data"><div class="icon">📭</div>No data available for this snapshot.</div>
    {% endif %}
    </div>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#1b5e20"></div>Highest OI</div>
      <div class="legend-item"><div class="legend-dot" style="background:#b71c1c"></div>Lowest OI</div>
      <div class="legend-item"><div class="legend-dot" style="background:#0d47a1"></div>Highest Volume</div>
      <div class="legend-item"><div class="legend-dot" style="background:#e65100"></div>Drastic COI Change</div>
      <div class="legend-item"><div class="legend-dot" style="background:#4caf50"></div>Positive COI</div>
      <div class="legend-item"><div class="legend-dot" style="background:#ef5350"></div>Negative COI</div>
    </div>
  </div>
  <div class="chart-side">
    <div class="chart-header">
      <div class="chart-title">📊 NIFTY 50 — Live Chart</div>
      <div class="chart-subtitle">TradingView · 5-min candles</div>
    </div>
    <div class="tv-widget-wrap"><div id="tv_chart_container"></div></div>
  </div>
</div>
{% endif %}
<script>
var secs = 300;
var el = document.getElementById("cd");
if(el){ setInterval(function(){ secs--; if(secs<=0){window.location.reload();} el.textContent=secs; },1000); }
function changeDate(dt){ window.location.href="/?date="+encodeURIComponent(dt); }
function loadTs(dt,ts){ window.location.href="/?date="+encodeURIComponent(dt)+"&ts="+encodeURIComponent(ts); }
var activeDate=document.querySelector(".date-btn.active");
if(activeDate){activeDate.scrollIntoView({behavior:"smooth",inline:"center",block:"nearest"});}
var activeTime=document.querySelector(".ts-btn.active:not(.date-btn)");
if(activeTime){activeTime.scrollIntoView({behavior:"smooth",inline:"center",block:"nearest"});}
if(window.innerWidth>=1024){
  var tvScript=document.createElement("script");
  tvScript.src="https://s3.tradingview.com/tv.js";
  tvScript.async=true;
  tvScript.onload=function(){
    new TradingView.widget({autosize:true,symbol:"NSE:NIFTY",interval:"5",timezone:"Asia/Kolkata",theme:"dark",style:"1",locale:"en",toolbar_bg:"#0d1117",enable_publishing:false,hide_side_toolbar:false,allow_symbol_change:true,container_id:"tv_chart_container",studies:["Volume@tv-basicstudies"]});
  };
  document.head.appendChild(tvScript);
}
</script>
</body>
</html>
"""

@app.route("/login", methods=["POST"])
def login():
    pwd = request.form.get("password", "")
    if check_password(pwd):
        session["logged_in"] = True
        session.permanent = True
        return redirect(url_for("index"))
    return render_template_string(HTML, logged_in=False, error=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/")
def index():
    if not session.get("logged_in"):
        return render_template_string(HTML, logged_in=False, error=False)
    dates = get_distinct_dates()
    if not dates:
        return render_template_string(HTML, logged_in=True, dates=[], timestamps=[], rows=[], selected_date="", selected_ts="", global_latest_ts="")
    selected_date = request.args.get("date", "")
    if not selected_date or selected_date not in dates:
        selected_date = dates[0]
    timestamps = get_timestamps_for_date(selected_date)
    selected_ts = request.args.get("ts", "")
    if not selected_ts or selected_ts not in timestamps:
        selected_ts = timestamps[0] if timestamps else ""
    global_latest_ts = ""
    if dates:
        all_latest_ts = get_timestamps_for_date(dates[0])
        if all_latest_ts:
            global_latest_ts = all_latest_ts[0]
    raw_rows = get_snapshot(selected_ts)
    if not raw_rows:
        return render_template_string(HTML, logged_in=True, dates=dates, timestamps=timestamps, rows=[], selected_date=selected_date, selected_ts=selected_ts, global_latest_ts=global_latest_ts)
    all_oi = []
    all_vol = []
    for r in raw_rows:
        _, ce_oi, _, ce_vol, _, _, _, pe_vol, _, pe_oi = r
        if ce_oi > 0: all_oi.append(ce_oi)
        if pe_oi > 0: all_oi.append(pe_oi)
        if ce_vol > 0: all_vol.append(ce_vol)
        if pe_vol > 0: all_vol.append(pe_vol)
    max_oi = max(all_oi) if all_oi else 0
    min_oi = min(all_oi) if all_oi else 0
    max_vol = max(all_vol) if all_vol else 0
    def oi_class(oi, side):
        if oi == max_oi: return "highest-oi"
        if oi == min_oi: return "lowest-oi"
        return f"{side}-val"
    def vol_class(vol, side):
        if vol == max_vol: return "highest-vol"
        return f"{side}-val"
    def coi_class(coi, oi):
        if oi > 0 and abs(coi)/oi*100 > 20: return "drastic-coi"
        if coi > 0: return "positive-coi"
        if coi < 0: return "negative-coi"
        return "neutral-coi"
    rows = []
    for r in raw_rows:
        tag, ce_oi, ce_coi, ce_vol, ce_ltp, strike, pe_ltp, pe_vol, pe_coi, pe_oi = r
        rows.append({
            "tag": tag, "ce_oi": ce_oi, "ce_coi": ce_coi, "ce_volume": ce_vol,
            "ce_ltp": ce_ltp, "strike": strike, "pe_ltp": pe_ltp,
            "pe_volume": pe_vol, "pe_coi": pe_coi, "pe_oi": pe_oi,
            "ce_oi_class": oi_class(ce_oi, "ce"),
            "pe_oi_class": oi_class(pe_oi, "pe"),
            "ce_vol_class": vol_class(ce_vol, "ce"),
            "pe_vol_class": vol_class(pe_vol, "pe"),
            "ce_coi_class": coi_class(ce_coi, ce_oi),
            "pe_coi_class": coi_class(pe_coi, pe_oi),
        })
    return render_template_string(HTML, logged_in=True, dates=dates, timestamps=timestamps, rows=rows, selected_date=selected_date, selected_ts=selected_ts, global_latest_ts=global_latest_ts)

@app.route("/api/chain")
def api_chain():
    try:
        latest_ts, raw_rows = get_latest_snapshot()
        if not latest_ts or not raw_rows:
            return jsonify({"error": "No data available"}), 404
        data = []
        for r in raw_rows:
            tag, ce_oi, ce_coi, ce_vol, ce_ltp, strike, pe_ltp, pe_vol, pe_coi, pe_oi = r
            data.append({
                "tag": tag, "strike": strike,
                "ce_oi": ce_oi, "ce_coi": ce_coi, "ce_volume": ce_vol, "ce_ltp": ce_ltp,
                "pe_ltp": pe_ltp, "pe_volume": pe_vol, "pe_coi": pe_coi, "pe_oi": pe_oi,
            })
        return jsonify({"timestamp": latest_ts, "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/summary")
def api_summary():
    try:
        latest_ts, raw_rows = get_latest_snapshot()
        if not latest_ts or not raw_rows:
            return jsonify({"error": "No data available"}), 404
        atm_strike = None
        total_ce_oi = 0
        total_pe_oi = 0
        for r in raw_rows:
            tag, ce_oi, ce_coi, ce_vol, ce_ltp, strike, pe_ltp, pe_vol, pe_coi, pe_oi = r
            total_ce_oi += ce_oi
            total_pe_oi += pe_oi
            if tag == "ATM":
                atm_strike = strike
        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 0
        if pcr >= 1.3:
            sentiment = "Bullish"
        elif pcr <= 0.7:
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"
        return jsonify({
            "timestamp": latest_ts, "atm_strike": atm_strike,
            "total_ce_oi": total_ce_oi, "total_pe_oi": total_pe_oi,
            "pcr": pcr, "sentiment": sentiment
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
