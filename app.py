"""
NSE/MCX Premium Terminal — Streamlit Spike Monitor (single-file)
"""
from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
IST = ZoneInfo("Asia/Kolkata")

def now_ist() -> datetime:
    return datetime.now(IST)

def time_only() -> str:
    return now_ist().strftime("%H:%M:%S")

def is_market_hours() -> bool:
    d = now_ist()
    if d.weekday() >= 5:
        return False
    mins = d.hour * 60 + d.minute
    return (9 * 60 + 15) <= mins <= (15 * 60 + 30)

def fmt(n: float, d: int = 2) -> str:
    return f"{n:,.{d}f}"

def atm_strike(spot: float, step: float) -> int:
    return int(round(spot / step) * step)

def _randn() -> float:
    u = v = 0.0
    while u == 0:
        u = random.random()
    while v == 0:
        v = random.random()
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)

# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------
SYMBOLS: Dict[str, dict] = {
    "NIFTY":      {"name": "NIFTY 50",    "baseSpot": 24850, "step": 50,  "basePrem": 185,  "lot": 25},
    "BANKNIFTY":  {"name": "BANK NIFTY",  "baseSpot": 51200, "step": 100, "basePrem": 420,  "lot": 15},
    "FINNIFTY":   {"name": "FIN NIFTY",   "baseSpot": 23800, "step": 50,  "basePrem": 160,  "lot": 25},
    "SENSEX":     {"name": "SENSEX",      "baseSpot": 81200, "step": 100, "basePrem": 580,  "lot": 10},
    "RELIANCE":   {"name": "RELIANCE",    "baseSpot": 2980,  "step": 20,  "basePrem": 48,   "lot": 250},
    "HDFCBANK":   {"name": "HDFC BANK",   "baseSpot": 1685,  "step": 10,  "basePrem": 28,   "lot": 550},
    "CRUDEOIL":   {"name": "CRUDE OIL",   "baseSpot": 6200,  "step": 50,  "basePrem": 95,   "lot": 100},
    "GOLD":       {"name": "GOLD",        "baseSpot": 72100, "step": 100, "basePrem": 420,  "lot": 1},
    "SILVER":     {"name": "SILVER",      "baseSpot": 84500, "step": 250, "basePrem": 680,  "lot": 1},
    "NATURALGAS": {"name": "NATURAL GAS", "baseSpot": 210,   "step": 5,   "basePrem": 12,   "lot": 1250},
}

@dataclass
class Tick:
    t: float
    time: str
    spot: float
    prem: float
    ce: float
    pe: float
    pct: float
    strike: int
    iv: float
    vol: int

@dataclass
class SimulatorState:
    history: Dict[str, List[Tick]] = field(default_factory=dict)
    open_prem: Dict[str, float] = field(default_factory=dict)
    alerts: List[dict] = field(default_factory=list)
    spike_count: int = 0

    def __post_init__(self) -> None:
        for s in SYMBOLS:
            self.history[s] = []
            self.open_prem[s] = SYMBOLS[s]["basePrem"] * (0.94 + random.random() * 0.12)

def generate_tick(sym: str, state: SimulatorState) -> Tick:
    cfg = SYMBOLS[sym]
    last = state.history[sym][-1] if state.history[sym] else None

    if not last:
        spot = cfg["baseSpot"] + _randn() * cfg["baseSpot"] * 0.0018
        prem = state.open_prem[sym]
        vol = random.randint(80, 330)
    else:
        spot = last.spot + _randn() * cfg["baseSpot"] * 0.00075
        d_prem = (state.open_prem[sym] - last.prem) * 0.018 + _randn() * (cfg["basePrem"] * 0.011)
        if random.random() < 0.07:
            d_prem += (1 if random.random() > 0.4 else -1) * cfg["basePrem"] * (0.05 + random.random() * 0.09)
        d_prem -= cfg["basePrem"] * 0.0007
        prem = max(cfg["basePrem"] * 0.38, last.prem + d_prem)
        vol = random.randint(80, 330)
        if abs(d_prem) > cfg["basePrem"] * 0.03:
            vol = int(vol * (3 + random.random() * 3))

    split = 0.43 + random.random() * 0.14
    ce = prem * split
    pe = prem * (1 - split)
    pct = ((prem - state.open_prem[sym]) / state.open_prem[sym]) * 100
    strike = atm_strike(spot, cfg["step"])
    iv = 11.5 + abs(pct) * 0.32 + random.random() * 3.8

    return Tick(
        t=time.time(), time=time_only(),
        spot=round(spot, 2), prem=round(prem, 2),
        ce=round(ce, 2), pe=round(pe, 2),
        pct=round(pct, 2), strike=strike,
        iv=round(iv, 1), vol=vol,
    )

def push_tick(sym: str, tick: Tick, state: SimulatorState, threshold: float) -> None:
    hist = state.history[sym]
    hist.append(tick)
    if len(hist) > 180:
        hist.pop(0)

    prev = hist[-2] if len(hist) > 1 else None
    jump = ((tick.prem - prev.prem) / prev.prem) * 100 if prev else 0.0

    if abs(tick.pct) >= threshold or abs(jump) >= threshold:
        abs_pct = tick.pct if abs(tick.pct) >= threshold else jump
        recent = next((a for a in state.alerts if a["sym"] == sym and (time.time() - a["ts"]) < 22), None)
        if not recent:
            state.spike_count += 1
            state.alerts.insert(0, {
                "ts": time.time(), "time": tick.time, "sym": sym,
                "pct": abs_pct, "prem": tick.prem, "spot": tick.spot,
            })
            if len(state.alerts) > 50:
                state.alerts.pop()

def seed_history(state: SimulatorState, n: int = 50) -> None:
    for i in range(n):
        for sym in SYMBOLS:
            t = generate_tick(sym, state)
            t.t = time.time() - (n - i) * 3.5
            if sym in ("GOLD", "NIFTY", "CRUDEOIL") and i > n - 8:
                t.prem = state.open_prem[sym] * (1.06 + random.random() * 0.04)
                t.pct = ((t.prem - state.open_prem[sym]) / state.open_prem[sym]) * 100
                t.ce = round(t.prem * 0.48, 2)
                t.pe = round(t.prem * 0.52, 2)
            state.history[sym].append(t)

# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NSE/MCX Premium Terminal | Spike Monitor",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace !important; }
.stApp { background-color: #05080f; }
section[data-testid="stSidebar"] { background-color: #0d121d; border-right: 1px solid #1e293b; }
div[data-testid="stMetric"] { background: #151b2b; border: 1px solid #1e293b; border-radius: 4px; padding: 10px 14px; }
div[data-testid="stMetric"] label { color: #64748b !important; font-size: 11px !important; text-transform: uppercase; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #e2e8f0 !important; font-size: 18px !important; }
h1, h2, h3 { color: #fbbf24 !important; font-family: 'JetBrains Mono', monospace !important; }
.stButton > button { background: #151b2b; color: #e2e8f0; border: 1px solid #1e293b; border-radius: 3px; font-family: 'JetBrains Mono', monospace !important; }
.stButton > button:hover { border-color: #06b6d4; color: #06b6d4; }
.footer-note { color: #64748b; font-size: 11px; border-top: 1px solid #1e293b; padding-top: 8px; margin-top: 12px; }
.dot-open { color: #10b981; }
.dot-closed { color: #ef4444; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "sim" not in st.session_state:
    st.session_state.sim = SimulatorState()
    seed_history(st.session_state.sim, n=50)
    st.session_state.paused = False
    st.session_state.threshold = 5.0
    st.session_state.only_spikes = True
    st.session_state.active_sym = "NIFTY"
    st.session_state.last_tick = time.time()
    st.session_state.view = "dashboard"
    st.session_state.tick_interval = 2.5

sim: SimulatorState = st.session_state.sim

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚡ CONTROLS")
    st.caption("Data mode: **SIMULATED**")

    threshold = st.number_input("Spike Threshold (%)", 1.0, 30.0, float(st.session_state.threshold), 0.5)
    st.session_state.threshold = threshold

    only_spikes = st.checkbox("Show only ≥ threshold", value=st.session_state.only_spikes)
    st.session_state.only_spikes = only_spikes

    tf = st.selectbox("Timeframe (refresh)", ["1 min", "5 min", "15 min"], index=1)
    st.session_state.tick_interval = {"1 min": 1.5, "5 min": 2.5, "15 min": 4.0}[tf]

    c1, c2 = st.columns(2)
    with c1:
        if st.button("⏸ Pause" if not st.session_state.paused else "▶ Resume"):
            st.session_state.paused = not st.session_state.paused
            st.rerun()
    with c2:
        if st.button("↻ Reset"):
            st.session_state.sim = SimulatorState()
            seed_history(st.session_state.sim, n=30)
            st.session_state.paused = False
            st.rerun()

    st.markdown("---")
    st.markdown("### 📊 SESSION STATS")
    active = st.session_state.active_sym
    hist = sim.history.get(active, [])
    if hist:
        prems = [t.prem for t in hist]
        st.metric("Max Prem", f"₹{fmt(max(prems))}")
        st.metric("Min Prem", f"₹{fmt(min(prems))}")
        st.metric("Avg Prem", f"₹{fmt(sum(prems)/len(prems))}")
        events = sum(1 for a in sim.alerts if a["sym"] == active)
        st.metric("Vol Events", str(events))
        st.caption(f"Symbol: {SYMBOLS[active]['name']}")
    else:
        st.info("No data yet")

    st.markdown("---")
    st.markdown(
        '<div class="footer-note">'
        "Combined Prem = ATM Call LTP + ATM Put LTP<br>"
        "≥ threshold spike w/o big spot move ≈ IV expansion<br>"
        "Data simulated for demo · DhanHQ ready"
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Tick engine
# ---------------------------------------------------------------------------
def run_ticks() -> None:
    if st.session_state.paused:
        return
    now = time.time()
    if now - st.session_state.last_tick < st.session_state.tick_interval:
        return
    for sym in SYMBOLS:
        t = generate_tick(sym, sim)
        push_tick(sym, t, sim, st.session_state.threshold)
    st.session_state.last_tick = now

run_ticks()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
open_mkt = is_market_hours()
status_cls = "dot-open" if open_mkt else "dot-closed"
status_txt = "MARKET OPEN · SIM LIVE" if open_mkt else "MARKET CLOSED · SIM CONTINUES"
clock = now_ist().strftime("%Y-%m-%d %H:%M:%S IST")

st.markdown(
    f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:8px 0 12px 0;border-bottom:1px solid #1e293b;margin-bottom:12px;">
      <div>
        <span style="font-size:18px;font-weight:800;color:#fbbf24;letter-spacing:1px;">
          NSE/MCX PREMIUM TERMINAL
        </span>
        <span style="color:#64748b;font-size:12px;margin-left:10px;">
          ATM Combined Premium Spike Monitor
        </span>
      </div>
      <div style="text-align:right;font-size:12px;">
        <span class="{status_cls}">●</span> {status_txt}<br>
        <span style="color:#e2e8f0;">{clock}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Ticker strip
# ---------------------------------------------------------------------------
ticker_cols = st.columns(len(SYMBOLS))
for i, sym in enumerate(SYMBOLS):
    h = sim.history[sym]
    with ticker_cols[i]:
        if not h:
            st.caption(f"{SYMBOLS[sym]['name']}: —")
        else:
            t = h[-1]
            color = "#10b981" if t.pct >= 0 else "#ef4444"
            spike = " ⚡" if abs(t.pct) >= st.session_state.threshold else ""
            arrow = "▲" if t.pct >= 0 else "▼"
            st.markdown(
                f"<div style='font-size:11px;white-space:nowrap;'>"
                f"<b>{SYMBOLS[sym]['name']}</b><br>"
                f"<span style='color:{color}'>{arrow}{abs(t.pct):.2f}%{spike}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

st.markdown("")

# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
if st.session_state.view == "chart":
    sym = st.session_state.active_sym
    st.markdown(f"### 📈 {SYMBOLS[sym]['name']} — Spot vs Combined Premium & Volume")
    if st.button("← Back to Dashboard"):
        st.session_state.view = "dashboard"
        st.rerun()

    h = sim.history[sym]
    if not h:
        st.warning("No history yet for this symbol.")
    else:
        df = pd.DataFrame({
            "time": [t.time for t in h],
            "spot": [t.spot for t in h],
            "prem": [t.prem for t in h],
            "vol":  [t.vol  for t in h],
        })
        min_s, max_s = df["spot"].min(), df["spot"].max()
        min_p, max_p = df["prem"].min(), df["prem"].max()
        range_s = max_s - min_s or 1
        range_p = max_p - min_p or 1
        df["spot_scaled"] = min_p + ((df["spot"] - min_s) / range_s) * range_p

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=df["time"], y=df["vol"], name="Volume",
                             marker_color="rgba(100,116,139,0.35)", opacity=0.7), secondary_y=False)
        fig.add_trace(go.Scatter(x=df["time"], y=df["prem"], name="Combined Premium",
                                 line=dict(color="#fbbf24", width=2.5),
                                 fill="tozeroy", fillcolor="rgba(251,191,36,0.08)"), secondary_y=True)
        fig.add_trace(go.Scatter(x=df["time"], y=df["spot_scaled"], name="Spot (scaled)",
                                 line=dict(color="#06b6d4", width=1.5, dash="dash")), secondary_y=True)

        base = sim.open_prem[sym]
        upper = base * (1 + st.session_state.threshold / 100)
        lower = base * (1 - st.session_state.threshold / 100)
        fig.add_hline(y=upper, line_dash="dot", line_color="#f97316", opacity=0.5, secondary_y=True)
        fig.add_hline(y=lower, line_dash="dot", line_color="#f97316", opacity=0.5, secondary_y=True)

        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#05080f", plot_bgcolor="#0d121d",
            font=dict(family="JetBrains Mono, monospace", color="#94a3b8", size=11),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(l=40, r=40, t=40, b=40), height=560, hovermode="x unified",
        )
        fig.update_xaxes(gridcolor="rgba(30,41,59,0.5)", tickfont=dict(size=10))
        fig.update_yaxes(title_text="Volume", gridcolor="rgba(30,41,59,0.5)", secondary_y=False)
        fig.update_yaxes(title_text="Premium (₹) / Spot scaled", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Last Prem", f"₹{fmt(h[-1].prem)}")
        c2.metric("% Chg", f"{h[-1].pct:+.2f}%")
        c3.metric("ATM IV", f"{h[-1].iv}%")
        c4.metric("Spot", fmt(h[-1].spot, 1 if h[-1].spot > 1000 else 2))

else:
    left, right = st.columns([1.7, 1], gap="medium")

    with left:
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"border-bottom:1px solid #1e293b;padding-bottom:6px;margin-bottom:10px;'>"
            f"<span style='color:#fbbf24;font-size:13px;letter-spacing:1px;'>⚡ SPIKE ALERTS</span>"
            f"<span style='color:#f97316;font-size:12px;'>{sim.spike_count} today</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        if not sim.alerts:
            st.caption("Waiting for spikes…")
        else:
            for a in sim.alerts[:12]:
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"background:#151b2b;border-left:3px solid #f97316;"
                    f"padding:6px 10px;margin-bottom:5px;border-radius:2px;font-size:12px;'>"
                    f"<div><span style='color:#64748b;'>{a['time']}</span> "
                    f"<span style='color:#06b6d4;font-weight:700;'>{SYMBOLS[a['sym']]['name']}</span></div>"
                    f"<div style='color:#f97316;font-weight:700;'>{a['pct']:+.1f}%</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    with right:
        st.markdown(
            f"<div style='border-bottom:1px solid #1e293b;padding-bottom:6px;margin-bottom:10px;'>"
            f"<span style='color:#fbbf24;font-size:13px;letter-spacing:1px;'>ACTIVE · {SYMBOLS[st.session_state.active_sym]['name']}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        h = sim.history.get(st.session_state.active_sym, [])
        if h:
            t = h[-1]
            m1, m2 = st.columns(2)
            m1.metric("Comb. Prem", f"₹{fmt(t.prem)}", f"{t.pct:+.2f}%")
            m2.metric("ATM IV", f"{t.iv}%")
            m3, m4 = st.columns(2)
            m3.metric("CE", f"₹{fmt(t.ce)}")
            m4.metric("PE", f"₹{fmt(t.pe)}")
            st.metric("Spot / ATM", f"{fmt(t.spot, 1 if t.spot > 1000 else 2)} / {t.strike}")
        else:
            st.caption("No ticks yet")

    st.markdown("---")

    filter_badge = (
        f"[Showing ONLY ≥{st.session_state.threshold}% Spikes]"
        if st.session_state.only_spikes else "[Showing All Symbols]"
    )
    st.markdown(
        f"**F&O Watchlist — Combined Premium Monitor**  "
        f"<span style='color:#f97316;font-size:12px;'>{filter_badge}</span>",
        unsafe_allow_html=True,
    )

    rows = []
    for sym, cfg in SYMBOLS.items():
        h = sim.history[sym]
        if not h:
            continue
        t = h[-1]
        if st.session_state.only_spikes and abs(t.pct) < st.session_state.threshold:
            continue
        rows.append({
            "Symbol": cfg["name"], "sym_key": sym, "Expiry": "SIM",
            "Spot": t.spot, "ATM": t.strike, "Comb.Prem": t.prem,
            "% Chg": t.pct, "CE": t.ce, "PE": t.pe, "ATM IV": t.iv,
            "Status": "SPIKE" if abs(t.pct) >= st.session_state.threshold else ("Rising" if t.pct >= 0 else "Falling"),
        })

    if not rows:
        st.info(f"No symbols currently exceeding {st.session_state.threshold}% threshold. Waiting for spikes…")
    else:
        df = pd.DataFrame(rows).sort_values("% Chg", key=lambda s: s.abs(), ascending=False)

        def color_pct(val):
            return f"color: {'#10b981' if val >= 0 else '#ef4444'}; font-weight: 600"

        def color_status(val):
            if val == "SPIKE":
                return "background-color: rgba(249,115,22,0.18); color: #f97316; font-weight: 700"
            return "color: #64748b"

        styled = (
            df.drop(columns=["sym_key"])
            .style
            .format({
                "Spot": lambda x: fmt(x, 1 if x > 1000 else 2),
                "Comb.Prem": "₹{:.2f}", "% Chg": "{:+.2f}%",
                "CE": "{:.2f}", "PE": "{:.2f}", "ATM IV": "{:.1f}%",
            })
            .map(color_pct, subset=["% Chg"])
            .map(color_status, subset=["Status"])
        )
        st.dataframe(styled, use_container_width=True, hide_index=True, height=min(420, 48 + 36 * len(df)))

        st.caption("Open full-page chart:")
        btn_cols = st.columns(min(5, len(df)))
        for i, (_, row) in enumerate(df.iterrows()):
            with btn_cols[i % len(btn_cols)]:
                if st.button(f"📈 {row['Symbol']}", key=f"chart_{row['sym_key']}"):
                    st.session_state.active_sym = row["sym_key"]
                    st.session_state.view = "chart"
                    st.rerun()

# Auto-refresh
if not st.session_state.paused:
    time.sleep(0.4)
    st.rerun()
