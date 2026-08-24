import streamlit as st
import pandas as pd
import datetime
import time
import os
import json
import plotly.express as px
from dhan_service import DhanDataService
import config

# --- Single Panel Viewport Layout Initialization ---
st.set_page_config(page_title="NSE/MCX Premium Terminal", layout="wide", initial_sidebar_state="collapsed")

# Inject Custom High-Density CSS Styles for Compact Grid
st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        .main .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; max-width: 98% !important; }
        div[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 700 !important; }
        div[data-testid="stMetricDelta"] { font-size: 0.9rem !important; }
        .stTabs [data-baseweb="tab"] { font-size: 14px !important; padding: 8px 12px !important; }
    </style>
""", unsafe_allow_html=True)

# Cache System Registries
if "watchlist" not in st.session_state:
    st.session_state.watchlist = set()
if "history" not in st.session_state:
    st.session_state.history = {}
if "dhan_service" not in st.session_state:
    st.session_state.dhan_service = DhanDataService()

def get_frozen_baselines():
    if os.path.exists(config.BASELINE_FILE):
        with open(config.BASELINE_FILE, "r") as f:
            return json.load(f)
    fallback_seeds = {
        "NIFTY": {"date": "2026-08-24", "spot": 24250.00, "expiry": "2026-08-27", "strike": 24250, "combined_premium": 310.00},
        "BANKNIFTY": {"date": "2026-08-24", "spot": 52100.00, "expiry": "2026-08-27", "strike": 52100, "combined_premium": 820.00},
        "CRUDEOIL": {"date": "2026-08-24", "spot": 6320.00, "expiry": "2026-09-18", "strike": 6300, "combined_premium": 380.00}
    }
    with open(config.BASELINE_FILE, "w") as f:
        json.dump(fallback_seeds, f, indent=4)
    return fallback_seeds

frozen_baselines = get_frozen_baselines()

# --- TOP HEADER CONTROL ROW ---
c_title, c_thresh, c_win, c_conn = st.columns([4, 3, 2, 3])
with c_title:
    st.markdown("<h2 style='margin:0; padding:0;'>⚡ NSE/MCX Premium Terminal</h2>", unsafe_allow_html=True)
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    st.caption(f"**ATM Combined Premium Spike Monitor** | Simulated Live: `{current_time} IST`")

with c_thresh:
    threshold = st.slider("Spike Threshold (%)", min_value=1.0, max_value=25.0, value=5.0, step=0.5)

with c_win:
    poll_interval = st.number_input("Interval (Sec)", min_value=3, max_value=60, value=10)

with c_conn:
    is_connected = st.session_state.dhan_service.is_live
    status_color = "#00E676" if is_connected else "#FF3D00"
    status_label = "PRODUCTION LIVE" if is_connected else "SIMULATED FALLBACK"
    st.markdown(f"""
        <div style='text-align:right; margin-top:5px;'>
            <span style='background:{status_color}; color:#000; padding:4px 10px; border-radius:4px; font-weight:bold; font-size:12px;'>
                {status_label}
            </span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- PIPELINE ENGINE PROCESSING CORNER ---
grid_data = []
for sym_key, inst_meta in config.TRACKED_INSTRUMENTS.items():
    base = frozen_baselines.get(sym_key)
    if not base: continue
    
    target_strike = base["strike"]
    live_feed, feed_source = st.session_state.dhan_service.get_live_option_chain_snapshot(
        symbol=inst_meta["symbol"],
        segment=inst_meta["segment"],
        security_id=inst_meta["security_id"],
        strike_step=inst_meta["strike_step"],
        expiry=inst_meta["expiry"],
        target_strike=target_strike
    )
    
    live_spot = live_feed["spot"]
    ce_ltp = live_feed["ce_ltp"]
    pe_ltp = live_feed["pe_ltp"]
    combined_today = round(ce_ltp + pe_ltp, 2)
    
    base_premium = base["combined_premium"]
    spurt_pct = round(((combined_today - base_premium) / base_premium) * 100, 2)
    
    if abs(spurt_pct) >= threshold:
        st.session_state.watchlist.add(sym_key)
        
    status = "🚨 SPIKE" if sym_key in st.session_state.watchlist else "🟢 MONITORING"
    
    if sym_key not in st.session_state.history:
        st.session_state.history[sym_key] = []
    st.session_state.history[sym_key].append({"Time": current_time, "Combined Premium": combined_today})
    if len(st.session_state.history[sym_key]) > 40:
        st.session_state.history[sym_key].pop(0)
        
    grid_data.append({
        "Symbol": sym_key, "Spot": live_spot, "Expiry": live_feed["expiry"],
        "ATM Strike": target_strike, "CE LTP": ce_ltp, "PE LTP": pe_ltp,
        "Comb.Prem": combined_today, "% Chg": spurt_pct, "Status": status, "Source": feed_source
    })

df_report = pd.DataFrame(grid_data)

# --- TERMINAL CONTENT LAYOUT SPLIT ---
col_grid, col_chart = st.columns([7, 5])

with col_grid:
    st.markdown("##### 📁 F&O Watchlist — Combined Premium Monitor")
    
    # Formatted High Density Live Table Mapping
    styled_df = df_report.copy()
    styled_df["Spot"] = styled_df["Spot"].map("₹{:,.2f}".format)
    styled_df["CE LTP"] = styled_df["CE LTP"].map("₹{:,.2f}".format)
    styled_df["PE LTP"] = styled_df["PE LTP"].map("₹{:,.2f}".format)
    styled_df["Comb.Prem"] = styled_df["Comb.Prem"].map("₹{:,.2f}".format)
    styled_df["% Chg"] = styled_df["% Chg"].map("{:+.2f}%".format)
    
    st.dataframe(
        styled_df[["Symbol", "Expiry", "Spot", "ATM Strike", "Comb.Prem", "% Chg", "CE LTP", "PE LTP", "Status"]],
        use_container_width=True,
        hide_index=True
    )
    
    # Active Watchlist Alerts Section
    st.markdown("##### 🚨 Active Day-Locked Alerts (≥ Threshold)")
    df_active = df_report[df_report["Symbol"].isin(st.session_state.watchlist)]
    if not df_active.empty:
        st.dataframe(
            df_active[["Symbol", "ATM Strike", "Comb.Prem", "% Chg", "Status"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Waiting for premium spikes to cross the threshold barrier.")

with col_chart:
    st.markdown("##### 📈 Volatility Session Timeline")
    selected_chart_sym = st.radio("Switch Chart Stream:", list(config.TRACKED_INSTRUMENTS.keys()), horizontal=True)
    
    if selected_chart_sym in st.session_state.history:
        chart_df = pd.DataFrame(st.session_state.history[selected_chart_sym])
        if not chart_df.empty:
            fig = px.line(
                chart_df, x="Time", y="Combined Premium",
                title=f"{selected_chart_sym} At-The-Money Premium Drift Trajectory",
                markers=True, line_shape="linear"
            )
            fig.update_traces(line=dict(color="#FF4B4B", width=2.5))
            fig.update_layout(
                margin=dict(l=10, r=10, t=30, b=10),
                height=280,
                xaxis_title="Timeline Feed",
                yaxis_title="Premium Index Value (₹)"
            )
            st.plotly_chart(fig, use_container_width=True, use_container_height=False)

# Bottom Status Footer Banner Bar
st.markdown("---")
st.caption("ℹ️ **Rule Key:** Combined Premium = ATM Call LTP + ATM Put LTP. A ≥5% premium spike without a large movement in the spot price indicates a volatility expansion event.")

# Native Clock Thread Drivers
time.sleep(poll_interval)
st.rerun()
