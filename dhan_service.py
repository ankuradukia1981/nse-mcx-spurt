import streamlit as st
import pandas as pd
import datetime
import time
import os
import json
import plotly.express as px

# Import custom architecture components
import config
from dhan_service import DhanDataService

# --- Initialize Session State Repositories ---
if "watchlist" not in st.session_state:
    st.session_state.watchlist = set()  # Day-locked symbols register (§4)
if "history" not in st.session_state:
    st.session_state.history = {}       # Combined premium historical log tracker

# --- Core Service Instance Hook ---
if "dhan_service" not in st.session_state:
    st.session_state.dhan_service = DhanDataService()

# --- Baseline Management Engine (§3.3) ---
def get_frozen_baselines():
    if os.path.exists(config.BASELINE_FILE):
        with open(config.BASELINE_FILE, "r") as f:
            return json.load(f)
    
    # Static fallback seeds matching the requested specification format
    fallback_seeds = {
        "NIFTY": {"date": "2026-08-21", "spot": 24310.20, "expiry": "2026-08-27", "strike": 24300, "combined_premium": 307.50},
        "BANKNIFTY": {"date": "2026-08-21", "spot": 52080.50, "expiry": "2026-08-27", "strike": 52100, "combined_premium": 806.00},
        "CRUDEOIL": {"date": "2026-08-21", "spot": 6345.00, "expiry": "2026-09-18", "strike": 6350, "combined_premium": 375.00}
    }
    with open(config.BASELINE_FILE, "w") as f:
        json.dump(fallback_seeds, f, indent=4)
    return fallback_seeds

frozen_baselines = get_frozen_baselines()

# --- Interactive Sidebar Workspace ---
st.sidebar.title("🔐 Secure Terminal Control")
st.sidebar.text_input("Dhan Connected ID", value=config.DHAN_CLIENT_ID or "NOT DETECTED", disabled=True)

# Configuration parameters configured in UI panel
st.sidebar.markdown("---")
st.sidebar.title("⚙️ Rule Configuration Panel")
threshold = st.sidebar.slider("Spurt Threshold (%)", min_value=0.5, max_value=50.0, value=10.0, step=0.5)
poll_interval = st.sidebar.number_input("Refresh Window Loop (Seconds)", min_value=3, max_value=60, value=10)

# --- Main Interface Dashboard Frame ---
st.title("📊 ATM Combined Premium Spike Monitor (v6)")
st.caption(f"Engine Mode: {config.TERMINAL_ENV} | Connection Status: {'LIVE' if st.session_state.dhan_service.is_live else 'SIM WORKSPACE FALLBACK'}")

current_time = datetime.datetime.now().strftime("%H:%M:%S")
grid_data = []

# --- Real-Time Execution Framework Loop ---
for sym_key, inst_meta in config.TRACKED_INSTRUMENTS.items():
    base = frozen_baselines.get(sym_key)
    if not base:
        continue
    
    # Enforces §3 Strike Selection Rule: Lock to previous-day target strike
    target_strike = base["strike"]
    
    # Query Data Service Network Pipeline (Includes caching and rate throttling)
    live_feed, feed_source = st.session_state.dhan_service.get_live_option_chain_snapshot(
        symbol=inst_meta["symbol"],
        segment=inst_meta["segment"],
        security_id=inst_meta["security_id"],
        strike_step=inst_meta["strike_step"],
        expiry=inst_meta["expiry"],
        target_strike=target_strike
    )
    
    # Extract structural pricing dimensions
    live_spot = live_feed["spot"]
    ce_ltp = live_feed["ce_ltp"]
    pe_ltp = live_feed["pe_ltp"]
    combined_today = round(ce_ltp + pe_ltp, 2)
    
    # Compute Spurt% against fixed previous-day baseline (§3.4)
    base_premium = base["combined_premium"]
    spurt_pct = round(((combined_today - base_premium) / base_premium) * 100, 2)
    
    # Enforce Day-Locked Watchlist Threshold Validation Check (§4)
    if abs(spurt_pct) >= threshold:
        st.session_state.watchlist.add(sym_key)
        
    status = "SPIKE" if sym_key in st.session_state.watchlist else "NORMAL"
    
    # Append values to history log for chart updates
    if sym_key not in st.session_state.history:
        st.session_state.history[sym_key] = []
    st.session_state.history[sym_key].append({"Time": current_time, "Combined Premium": combined_today})
    
    # Retain time window size constraint parameters
    if len(st.session_state.history[sym_key]) > 60:
        st.session_state.history[sym_key].pop(0)
        
    grid_data.append({
        "Symbol": sym_key,
        "Live Spot (₹)": live_spot,
        "Expiry": live_feed["expiry"],
        "Strike": target_strike,
        "CE": ce_ltp,
        "PE": pe_ltp,
        "Combined Premium (₹)": combined_today,
        "% Chg (vs Base)": spurt_pct,
        "Status": status,
        "Feed Source": feed_source
    })

df_report_cards = pd.DataFrame(grid_data)

# --- UI Render Segment: Section 5 Watchlist Layout ---
st.subheader("📋 Active Day-Locked Watchlist")
df_active_watchlist = df_report_cards[df_report_cards["Symbol"].isin(st.session_state.watchlist)]

if not df_active_watchlist.empty:
    st.dataframe(
        df_active_watchlist[["Symbol", "Expiry", "Strike", "CE", "PE", "Combined Premium (₹)", "% Chg (vs Base)", "Status", "Feed Source"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No tracked items have crossed the threshold limit during this session.")

# --- UI Render Segment: System-Wide Overview Grid ---
st.subheader("🔍 Real-Time Instrument Feed Metrics")
for index, row in df_report_cards.iterrows():
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(f"### **{row['Symbol']}**")
            st.caption(f"Live Spot: **₹{row['Live Spot (₹)']}**")
        with c2:
            st.metric("Combined Option Value", f"₹{row['Combined Premium (₹)']}", f"{row['% Chg (vs Base)']}%")
        with c3:
            st.markdown(f"Expiry: `{row['Expiry']}`")
            st.markdown(f"Strike: **{row['Strike']}**")
        with c4:
            st.text(f"Call LTP: ₹{row['CE']}")
            st.text(f"Put LTP: ₹{row['PE']}")
        with c5:
            if row["Status"] == "SPIKE":
                st.error("🚨 Day Lock Active: SPIKE")
            else:
                st.success(f"🟢 Track ({row['Feed Source']})")

# --- UI Render Segment: Section 6 Chart Presentation ---
st.markdown("---")
st.subheader("📈 Combined Premium Session Charts Only")
target_viz_symbol = st.selectbox("Select Target Underlying Engine", list(config.TRACKED_INSTRUMENTS.keys()))

if target_viz_symbol in st.session_state.history:
    session_chart_data = pd.DataFrame(st.session_state.history[target_viz_symbol])
    if not session_chart_data.empty:
        fig = px.line(
            session_chart_data,
            x="Time",
            y="Combined Premium",
            title=f"Premium Profile: {target_viz_symbol} (Strike: {frozen_baselines[target_viz_symbol]['strike']})",
            markers=True,
            line_shape="linear"
        )
        fig.update_traces(line_color="#FF4B4B", lw=2.5)
        st.plotly_chart(fig, use_container_width=True)

# --- Automatic Refresh Driver Module Execution Hook ---
time.sleep(poll_interval)
st.rerun()
