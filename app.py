"""
NSE / MCX Combined-Premium Terminal — Single-Panel Live Edition (v4)
---------------------------------------------------------------------
Single-page Streamlit dashboard (no sidebar) that mirrors the
premium-terminal-static.html mockup: header + ticker strip + controls
row, an Alerts/Stats panel pair, and a watchlist table — plus a
full-page per-symbol chart view you reach by clicking "Chart" on a row.

Behavior differences from earlier versions:
  - Watchlist ALWAYS shows only symbols whose combined-premium move vs
    session baseline is >= the threshold (default 5%). There's no
    "show all" toggle — that's the whole point of a spike monitor.
  - Every watchlist row (and the focused stat panel) shows the option
    chain's Expiry alongside Spot, so you always know which contract
    the spot/ATM numbers belong to.
  - The refresh loop is gated on market hours: once is_market_hours()
    goes False, the app stops auto-refreshing / auto-rerunning and
    freezes on the last tick — it will NOT keep polling the Dhan API
    after the close. A badge next to the clock reads LIVE or MARKET
    CLOSE accordingly.

Requires a .env (local) or Streamlit Secrets (cloud) with:
    DHAN_CLIENT_ID=...
    DHAN_ACCESS_TOKEN=...
If those are missing/invalid, every reading transparently falls back
to a simulated feed (source tag SIM) rather than crashing.

Run:
    streamlit run app.py
"""
import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (
    ALL_INSTRUMENTS, DEFAULT_THRESHOLD_PCT, DEFAULT_REFRESH_SECONDS, MAX_HISTORY_POINTS,
)
from dhan_service import (
    get_dhan, dhan_is_connected, fetch_atm_combined_premium,
    resolve_mcx_underlying, resolve_equity_underlying,
    init_sim_state, step_sim, is_market_hours,
)

st.set_page_config(
    page_title="NSE/MCX Premium Terminal",
    page_icon="\U0001F4C8",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================================================
# THEME — ported 1:1 from premium-terminal-static.html's CSS variables
# ==========================================================================
st.markdown("""
<style>
:root{
  --bg-void:#05080f; --bg-panel:#0d121d; --bg-alt:#151b2b; --border:#1e293b;
  --text-main:#e2e8f0; --text-dim:#64748b;
  --amber:#fbbf24; --cyan:#06b6d4; --up:#10b981; --down:#ef4444; --alert:#f97316;
}
html, body, [class*="css"] { font-family:'JetBrains Mono','SF Mono',Consolas,monospace; }
.stApp{ background:var(--bg-void); }
#MainMenu, header[data-testid="stHeader"], footer{ visibility:hidden; height:0; }
.block-container{ padding-top:1rem; max-width:1400px; }
h1,h2,h3,h4,h5{ color:var(--text-main)!important; font-family:'JetBrains Mono',monospace!important; }

.row-header{ display:flex; justify-content:space-between; align-items:center;
  padding:10px 16px; background:var(--bg-panel); border:1px solid var(--border);
  border-radius:4px; margin-bottom:8px; }
.brand{ font-size:17px; font-weight:800; color:var(--amber); letter-spacing:1px; }
.brand span{ color:var(--text-dim); font-size:11px; font-weight:400; margin-left:10px; }
.status-bar{ display:flex; gap:16px; align-items:center; }
.pill{ display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:4px;
  font-size:11px; font-weight:700; letter-spacing:.5px; text-transform:uppercase; }
.pill::before{ content:''; width:7px; height:7px; border-radius:50%; }
.pill-live{ background:rgba(16,185,129,.15); color:var(--up); border:1px solid rgba(16,185,129,.35); }
.pill-live::before{ background:var(--up); box-shadow:0 0 6px var(--up); }
.pill-closed{ background:rgba(239,68,68,.15); color:var(--down); border:1px solid rgba(239,68,68,.35); }
.pill-closed::before{ background:var(--down); }
.pill-src-live{ background:rgba(6,182,212,.15); color:var(--cyan); border:1px solid rgba(6,182,212,.35); }
.pill-src-live::before{ background:var(--cyan); }
.pill-src-sim{ background:rgba(251,191,36,.15); color:var(--amber); border:1px solid rgba(251,191,36,.35); }
.pill-src-sim::before{ background:var(--amber); }
.clock{ color:var(--text-main); font-size:13px; font-variant-numeric:tabular-nums; }

.row-ticker{ background:var(--bg-alt); border:1px solid var(--border); border-radius:4px;
  padding:6px 14px; display:flex; gap:20px; overflow-x:auto; white-space:nowrap;
  font-size:11px; margin-bottom:8px; }
.tick-up{ color:var(--up); font-weight:600; } .tick-down{ color:var(--down); font-weight:600; }
.tick-spike{ color:var(--alert); font-weight:800; }

.panel{ background:var(--bg-panel); border:1px solid var(--border); border-radius:4px;
  padding:12px 14px; height:100%; }
.panel-title{ font-size:11px; color:var(--amber); text-transform:uppercase; letter-spacing:1px;
  margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid var(--border);
  display:flex; justify-content:space-between; }
.alert-row{ display:flex; justify-content:space-between; align-items:center;
  padding:6px 8px; background:var(--bg-alt); border-left:3px solid var(--alert);
  border-radius:2px; font-size:11px; margin-bottom:6px; }
.alert-time{ color:var(--text-dim); font-size:10px; }
.alert-sym{ color:var(--cyan); font-weight:700; }
.alert-pct{ color:var(--alert); font-weight:700; }
.empty-state{ color:var(--text-dim); font-style:italic; font-size:11px; text-align:center; padding:20px 0; }
.stat-row{ display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed var(--border); font-size:12px; }
.stat-lbl{ color:var(--text-dim); } .stat-val{ color:var(--text-main); font-weight:700; }

.wl-header{ padding:8px 4px; font-size:11px; color:var(--amber); text-transform:uppercase;
  letter-spacing:1px; display:flex; gap:12px; align-items:center; }
.wl-badge{ color:var(--alert); font-weight:700; }
.wl-count{ color:var(--text-dim); font-weight:400; }
.wl-row{ display:flex; align-items:center; padding:7px 10px; border-bottom:1px solid var(--border);
  font-size:12px; background:rgba(249,115,22,0.05); border-radius:2px; margin-bottom:2px; }
.tag-spike{ background:rgba(249,115,22,.18); color:var(--alert); padding:2px 7px; border-radius:3px;
  font-size:10px; font-weight:700; }
.text-up{ color:var(--up); } .text-down{ color:var(--down); }

.stButton>button{ background:var(--bg-alt); border:1px solid var(--border); color:var(--text-main);
  font-family:'JetBrains Mono',monospace; font-size:11px; border-radius:3px; padding:4px 12px; }
.stButton>button:hover{ border-color:var(--cyan); color:var(--cyan); }

.foot{ font-size:10px; color:var(--text-dim); padding:8px 4px; }
</style>
""", unsafe_allow_html=True)

# ==========================================================================
# STATE
# ==========================================================================
_defaults = {
    "history": {sym: [] for sym in ALL_INSTRUMENTS},
    "sim_state": {sym: init_sim_state(cfg) for sym, cfg in ALL_INSTRUMENTS.items()},
    "alerts": [],
    "resolved_ids": {},
    "paused": False,
    "spike_count_today": 0,
    "view": "dashboard",
    "active_sym": "NIFTY",
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

dhan_client = get_dhan()
LIVE = dhan_is_connected(dhan_client)
MARKET_OPEN = is_market_hours()

# ==========================================================================
# DATA LAYER
# ==========================================================================
def resolve_security_id(sym: str, cfg: dict):
    if cfg["security_id"] is not None:
        return cfg["security_id"], cfg["segment"]
    cached = st.session_state.resolved_ids.get(sym)
    if cached:
        return cached[0], cfg["segment"]
    if cfg["asset_class"] == "COMMODITY":
        sec_id, _expiry, _tsym = resolve_mcx_underlying(cfg["lookup_symbol"])
    elif cfg["asset_class"] == "EQUITY":
        sec_id = resolve_equity_underlying(cfg["lookup_symbol"])
    else:
        sec_id = None
    st.session_state.resolved_ids[sym] = (sec_id, cfg["segment"])
    return sec_id, cfg["segment"]


def get_reading(sym: str, cfg: dict):
    if LIVE:
        try:
            security_id, segment = resolve_security_id(sym, cfg)
            if security_id is not None:
                reading = fetch_atm_combined_premium(dhan_client, security_id, segment, cfg["strike_step"])
                if reading is not None:
                    reading["source"] = "LIVE"
                    return reading
        except Exception:
            pass
    reading = step_sim(st.session_state.sim_state[sym])
    reading["source"] = "SIM"
    return reading


def run_universe_tick(threshold: float):
    """Fetches one reading for every instrument, updates history + alerts."""
    now_str = datetime.now().strftime("%H:%M:%S")
    for sym, cfg in ALL_INSTRUMENTS.items():
        reading = get_reading(sym, cfg)
        hist = st.session_state.history[sym]
        baseline = hist[0]["combined_premium"] if hist else reading["combined_premium"]
        pct_chg = ((reading["combined_premium"] - baseline) / baseline) * 100 if baseline else 0.0
        is_spike = abs(pct_chg) >= threshold

        record = {**reading, "time": now_str, "pct_chg": pct_chg, "is_spike": is_spike, "baseline": baseline}
        hist.append(record)
        if len(hist) > MAX_HISTORY_POINTS:
            hist.pop(0)

        if is_spike:
            already_recent = any(
                a["symbol"] == sym and (datetime.now() - a["ts"]).seconds < 25 for a in st.session_state.alerts
            )
            if not already_recent:
                st.session_state.alerts.insert(0, {
                    "symbol": sym, "ts": datetime.now(), "time": now_str, "pct": pct_chg,
                    "premium": reading["combined_premium"], "spot": reading["spot"],
                    "expiry": reading.get("expiry", "-"),
                })
                st.session_state.alerts = st.session_state.alerts[:50]
                st.session_state.spike_count_today += 1


# ==========================================================================
# CONTROLS (rendered first so `threshold` is available to the tick loop)
# ==========================================================================
ctrl1, ctrl2, ctrl3, ctrl4, ctrl5 = st.columns([1.4, 1.4, 1, 1, 4])
with ctrl1:
    threshold = st.number_input("Spike threshold (%)", min_value=0.5, max_value=50.0,
                                 value=DEFAULT_THRESHOLD_PCT, step=0.5)
with ctrl2:
    refresh_secs = st.slider("Auto-refresh (s)", 5, 60, DEFAULT_REFRESH_SECONDS)
with ctrl3:
    if st.button("\u23f8\ufe0f Pause" if not st.session_state.paused else "\u25b6\ufe0f Resume"):
        st.session_state.paused = not st.session_state.paused
        st.rerun()
with ctrl4:
    if st.button("\U0001F504 Reset"):
        st.session_state.history = {s: [] for s in ALL_INSTRUMENTS}
        st.session_state.sim_state = {s: init_sim_state(c) for s, c in ALL_INSTRUMENTS.items()}
        st.session_state.alerts = []
        st.session_state.spike_count_today = 0
        st.rerun()

# ==========================================================================
# REFRESH: only pull fresh ticks while the market is open and not paused.
# Once MARKET_OPEN goes False, we stop fetching AND stop auto-rerunning —
# the dashboard freezes on the last tick instead of polling Dhan after hours.
# ==========================================================================
have_any_history = any(st.session_state.history[s] for s in ALL_INSTRUMENTS)
should_fetch = (MARKET_OPEN and not st.session_state.paused) or not have_any_history
if should_fetch:
    run_universe_tick(threshold)

current_records = {sym: st.session_state.history[sym][-1] for sym in ALL_INSTRUMENTS if st.session_state.history[sym]}

# ==========================================================================
# HEADER
# ==========================================================================
market_pill = '<span class="pill pill-live">LIVE</span>' if MARKET_OPEN else '<span class="pill pill-closed">MARKET CLOSE</span>'
src_pill = '<span class="pill pill-src-live">DHAN LIVE</span>' if LIVE else '<span class="pill pill-src-sim">SIMULATED</span>'
now = datetime.now()
st.markdown(
    f'<div class="row-header">'
    f'<div class="brand">\u25c6 NSE/MCX PREMIUM TERMINAL<span>ATM Combined Premium Spike Monitor</span></div>'
    f'<div class="status-bar">{src_pill}{market_pill}'
    f'<span class="clock">{now.strftime("%H:%M:%S")} IST &nbsp;|&nbsp; {now.strftime("%d %b %Y")}</span></div>'
    f'</div>', unsafe_allow_html=True,
)

# ==========================================================================
# TICKER STRIP — every instrument, regardless of the watchlist filter
# ==========================================================================
ticker_html = '<div class="row-ticker">'
for sym, cfg in ALL_INSTRUMENTS.items():
    r = current_records.get(sym)
    if not r:
        continue
    cls = "tick-spike" if r["is_spike"] else ("tick-up" if r["pct_chg"] >= 0 else "tick-down")
    arrow = "\u25b2" if r["pct_chg"] >= 0 else "\u25bc"
    ticker_html += (f'<span><b>{cfg["label"]}</b> \u20b9{r["combined_premium"]:.1f} '
                     f'<span class="{cls}">{arrow}{r["pct_chg"]:+.2f}%</span></span>')
ticker_html += '</div>'
st.markdown(ticker_html, unsafe_allow_html=True)

# ==========================================================================
# CHART VIEW (full page — reached via a watchlist row's "Chart" button)
# ==========================================================================
if st.session_state.view == "chart" and st.session_state.active_sym in ALL_INSTRUMENTS:
    sym = st.session_state.active_sym
    inst = ALL_INSTRUMENTS[sym]
    hist = st.session_state.history[sym]

    top_l, top_r = st.columns([5, 1])
    with top_l:
        st.markdown(f"### {inst['label']} — Spot vs Combined Premium & OI")
    with top_r:
        if st.button("\u2190 Back to Dashboard"):
            st.session_state.view = "dashboard"
            st.rerun()

    if hist:
        df = pd.DataFrame(hist)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["time"], y=df["combined_premium"], name="Combined Premium",
                                  line=dict(color="#fbbf24", width=2.5), fill="tozeroy",
                                  fillcolor="rgba(251,191,36,0.08)", yaxis="y1"))
        fig.add_trace(go.Scatter(x=df["time"], y=df["spot"], name="Spot",
                                  line=dict(color="#06b6d4", width=1.5, dash="dash"), yaxis="y2"))
        total_oi = (df["ce_oi"] + df["pe_oi"]) if "ce_oi" in df and "pe_oi" in df else None
        if total_oi is not None:
            fig.add_trace(go.Bar(x=df["time"], y=total_oi, name="Total OI (CE+PE)",
                                  marker_color="rgba(100,116,139,0.35)", yaxis="y3"))
        latest = hist[-1]
        fig.update_layout(
            height=460, margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="#0d121d", plot_bgcolor="#0d121d",
            font=dict(color="#e2e8f0", family="JetBrains Mono"),
            legend=dict(orientation="h", y=1.08, font=dict(size=10)),
            xaxis=dict(showgrid=True, gridcolor="#1e293b", nticks=12),
            yaxis=dict(title="Premium (\u20b9)", showgrid=True, gridcolor="#1e293b"),
            yaxis2=dict(title="Spot", overlaying="y", side="right", showgrid=False),
            yaxis3=dict(overlaying="y", side="left", showgrid=False, visible=False, rangemode="tozero"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"Expiry: {latest.get('expiry', '-')} \u2022 Source: {latest.get('source', '-')} "
                   f"\u2022 ATM strike: {latest.get('atm_strike', '-')} \u2022 PCR: {latest.get('pcr', '-')}")
    else:
        st.caption("No ticks yet for this symbol.")

# ==========================================================================
# DASHBOARD VIEW
# ==========================================================================
else:
    p_left, p_right = st.columns(2)
    with p_left:
        alerts_html = '<div class="panel"><div class="panel-title"><span>\u26a1 Spike Alerts</span>' \
                      f'<span style="color:var(--alert)">{st.session_state.spike_count_today} today</span></div>'
        if not st.session_state.alerts:
            alerts_html += '<div class="empty-state">Waiting for spikes\u2026</div>'
        else:
            for a in st.session_state.alerts[:8]:
                direction = "\u25b2" if a["pct"] >= 0 else "\u25bc"
                label = ALL_INSTRUMENTS.get(a["symbol"], {}).get("label", a["symbol"])
                alerts_html += (
                    f'<div class="alert-row"><span><span class="alert-time">{a["time"]}</span> '
                    f'<span class="alert-sym">{label}</span> (exp {a.get("expiry", "-")})</span>'
                    f'<span class="alert-pct">{direction}{a["pct"]:+.2f}%</span></div>'
                )
        alerts_html += '</div>'
        st.markdown(alerts_html, unsafe_allow_html=True)

    with p_right:
        active = st.session_state.active_sym
        h = st.session_state.history.get(active, [])
        stats_html = '<div class="panel"><div class="panel-title"><span>Session Stats</span>' \
                     f'<span style="color:var(--text-dim)">{ALL_INSTRUMENTS.get(active, {}).get("label", active)}</span></div>'
        if h:
            prems = [x["combined_premium"] for x in h]
            sym_events = sum(1 for a in st.session_state.alerts if a["symbol"] == active)
            for lbl, val in [
                ("Expiry", h[-1].get("expiry", "-")),
                ("Max Prem", f"\u20b9{max(prems):.2f}"),
                ("Min Prem", f"\u20b9{min(prems):.2f}"),
                ("Avg Prem", f"\u20b9{sum(prems)/len(prems):.2f}"),
                ("Vol Events", f"{sym_events}"),
            ]:
                stats_html += f'<div class="stat-row"><span class="stat-lbl">{lbl}</span><span class="stat-val">{val}</span></div>'
        else:
            stats_html += '<div class="empty-state">No ticks yet.</div>'
        stats_html += '</div>'
        st.markdown(stats_html, unsafe_allow_html=True)

    st.write("")

    # ---- WATCHLIST: only symbols currently at/above the spike threshold ----
    spiking = [(s, r) for s, r in current_records.items() if abs(r.get("pct_chg", 0)) >= threshold]
    spiking.sort(key=lambda x: abs(x[1]["pct_chg"]), reverse=True)

    st.markdown(
        f'<div class="wl-header">F&O Watchlist — Combined Premium Monitor '
        f'<span class="wl-badge">\u2265{threshold:.1f}% ONLY</span>'
        f'<span class="wl-count">{len(spiking)} of {len(ALL_INSTRUMENTS)} instruments</span></div>',
        unsafe_allow_html=True,
    )

    if not spiking:
        st.markdown('<div class="empty-state">No instrument has crossed the '
                     f'\u00b1{threshold:.1f}% threshold yet.</div>', unsafe_allow_html=True)
    else:
        hdr = st.columns([1.3, 1.1, 1, 1, 1.1, 0.9, 0.8, 0.8, 0.8, 0.9, 0.8])
        for c, label in zip(hdr, ["Symbol", "Expiry", "Spot", "ATM", "Comb.Prem", "%Chg",
                                    "CE", "PE", "IV", "Status", ""]):
            c.markdown(f'<span style="color:var(--text-dim);font-size:10px;text-transform:uppercase">{label}</span>',
                       unsafe_allow_html=True)

        for sym, r in spiking:
            label = ALL_INSTRUMENTS[sym]["label"]
            pct_cls = "text-up" if r["pct_chg"] >= 0 else "text-down"
            cols = st.columns([1.3, 1.1, 1, 1, 1.1, 0.9, 0.8, 0.8, 0.8, 0.9, 0.8])
            cols[0].markdown(f"**{label}**")
            cols[1].markdown(f"{r.get('expiry', '-')}")
            cols[2].markdown(f"{r['spot']:,.2f}")
            cols[3].markdown(f"{r['atm_strike']:,.0f}")
            cols[4].markdown(f"\u20b9{r['combined_premium']:.2f}")
            cols[5].markdown(f'<span class="{pct_cls}">{r["pct_chg"]:+.2f}%</span>', unsafe_allow_html=True)
            cols[6].markdown(f"{r['ce_ltp']:.2f}")
            cols[7].markdown(f"{r['pe_ltp']:.2f}")
            cols[8].markdown(f"{r.get('atm_iv', '-')}")
            cols[9].markdown('<span class="tag-spike">SPIKE</span>', unsafe_allow_html=True)
            if cols[10].button("Chart", key=f"chart_{sym}"):
                st.session_state.active_sym = sym
                st.session_state.view = "chart"
                st.rerun()

    st.markdown(
        '<div class="foot">Combined Premium = ATM Call LTP + ATM Put LTP (straddle value). '
        'Watchlist shows only instruments at/above the spike threshold vs session baseline — '
        'not investment advice.</div>', unsafe_allow_html=True,
    )

# ==========================================================================
# AUTO-REFRESH — gated on market hours; stops polling/rerunning after close
# ==========================================================================
if MARKET_OPEN and not st.session_state.paused:
    time.sleep(refresh_secs)
    st.rerun()
