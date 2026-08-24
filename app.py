import streamlit as st
import pandas as pd
import datetime
import time
import os
import json
import random
import plotly.express as px
from dotenv import load_dotenv

# Load environmental variables from secure local storage
load_dotenv()

# --- Configuration & Setup ---
st.set_page_config(page_title="NSE/MCX Premium Terminal", layout="wide")

# Persistent State Initialization
if "watchlist" not in st.session_state:
    st.session_state.watchlist = set()  
if "history" not in st.session_state:
    st.session_state.history = {}       

# --- Core Token Resolution Hub ---
# Prioritizes secure system variables over manual input fields
env_client_id = os.getenv("DHAN_CLIENT_ID", "")
env_access_token = os.getenv("DHAN_ACCESS_TOKEN", "")

# --- Sidebar UI Controls ---
st.sidebar.title("🔐 Terminal Connectivity")

if env_client_id and env_access_token:
    st.sidebar.success("🔑 Connected via secure .env file")
    client_id = env_client_id
    access_token = env_access_token
else:
    st.sidebar.warning("⚠️ Credentials missing in environment.")
    client_id = st.sidebar.text_input("Dhan Client ID", value="", type="password")
    access_token = st.sidebar.text_input("Access Token", value="", type="password")

st.sidebar.markdown("---")
st.sidebar.title("⚙️ Rule Control Panel")
threshold = st.sidebar.slider("Spurt Threshold (%)", min_value=0.5, max_value=50.0, value=10.0, step=0.5)
poll_interval = st.sidebar.number_input("Refresh Window (Seconds)", min_value=3, max_value=60, value=10)

# --- Mock Dhan HQ Client Framework ---
class MockDhanHQ:
    def __init__(self, c_id, token):
        self.c_id = c_id
        self.token = token
    
    def get_option_chain(self, symbol, expiry, strike_step):
        base_spots = {"NIFTY": 24250.00, "BANKNIFTY": 52100.00, "CRUDEOIL": 6320.00}
        live_spot = round(base_spots.get(symbol, 1000.00) + random.uniform(-25.0, 25.0), 2)
        k_strike = round(live_spot / strike_step) * strike_step
        
        # Simulating active premium expansion/crush
        ce_ltp = round(random.uniform(90.0, 280.0), 2)
        pe_ltp = round(random.uniform(90.0, 280.0), 2)
        
        return {
            "spot": live_spot,
            "strike": k_strike,
            "ce_ltp": ce_ltp,
            "pe_ltp": pe_ltp,
            "expiry": expiry
        }

# --- Baseline Management Layer ---
BASELINE_FILE = "previous_day_baseline.json"

def load_or_create_baselines():
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE, "r") as f:
            return json.load(f)
    
    default_baselines = {
        "NIFTY": {"date": "2026-08-21", "spot": 24310.20, "expiry": "2026-08-27", "strike": 24300, "ce_ltp": 165.40, "pe_ltp": 142.10, "combined_premium": 307.50},
        "BANKNIFTY": {"date": "2026-08-21", "spot": 52080.50, "expiry": "2026-08-27", "strike": 52100, "ce_ltp": 410.20, "pe_ltp": 395.80, "combined_premium": 806.00},
        "CRUDEOIL": {"date": "2026-08-21", "spot": 6345.00, "expiry": "2026-09-18", "strike": 6350, "ce_ltp": 180.00, "pe_ltp": 195.00, "combined_premium": 375.00}
    }
    with open(BASELINE_FILE, "w") as f:
        json.dump(default_baselines, f, indent=4)
    return default_baselines

baselines = load_or_create_baselines()
dhan = MockDhanHQ(client_id, access_token)

instruments = [
    {"symbol": "NIFTY", "segment": "IDX_I", "step": 50, "expiry": "2026-08-27"},
    {"symbol": "BANKNIFTY", "segment": "IDX_I", "step": 100, "expiry": "2026-08-27"},
    {"symbol": "CRUDEOIL", "segment": "MCX_COMM", "step": 50, "expiry": "2026-09-18"}
]

# --- Main Dashboard Core ---
st.title("📊 ATM Combined Premium Spike Monitor (v6)")
st.caption(f"System State: ACTIVE RUNTIME | Active Threshold: **{threshold}%** | Update Window: **{poll_interval}s**")

current_time = datetime.datetime.now().strftime("%H:%M:%S")
grid_data = []

for inst in instruments:
    sym = inst["symbol"]
    base = baselines.get(sym)
    
    if not base:
        continue
        
    target_strike = base["strike"]
    live_chain = dhan.get_option_chain(sym, inst["expiry"], inst["step"])
    
    live_spot = live_chain["spot"]
    ce_live = live_chain["ce_ltp"]
    pe_live = live_chain["pe_ltp"]
    combined_today = round(ce_live + pe_live, 2)
    
    baseline_premium = base["combined_premium"]
    spurt_pct = round(((combined_today - baseline_premium) / baseline_premium) * 100, 2)
    
    if abs(spurt_pct) >= threshold:
        st.session_state.watchlist.add(sym)
        
    status = "SPIKE" if sym in st.session_state.watchlist else "NORMAL"
    
    if sym not in st.session_state.history:
        st.session_state.history[sym] = []
    st.session_state.history[sym].append({"Time": current_time, "Combined Premium": combined_today})
    if len(st.session_state.history[sym]) > 50:
        st.session_state.history[sym].pop(0)
        
    grid_data.append({
        "Symbol": sym,
        "Live Spot (₹)": live_spot,
        "Expiry": live_chain["expiry"],
        "Strike": target_strike,
        "CE (₹)": ce_live,
        "PE (₹)": pe_live,
        "Combined Premium (₹)": combined_today,
        "% Chg (vs Base)": spurt_pct,
        "Status": status
    })

df_all = pd.DataFrame(grid_data)

# Watchlist Display Block (§5)
st.subheader("📋 Active Day-Locked Watchlist")
df_watchlist = df_all[df_all["Symbol"].isin(st.session_state.watchlist)]

if not df_watchlist.empty:
    st.dataframe(
        df_watchlist[["Symbol", "Expiry", "Strike", "CE (₹)", "PE (₹)", "Combined Premium (₹)", "% Chg (vs Base)", "Status"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Waiting for market instruments to cross the threshold barrier.")

# Global Overview Grid
st.subheader("🔍 All Tracked Instruments")
for index, row in df_all.iterrows():
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.markdown(f"### **{row['Symbol']}**")
            st.caption(f"Spot: ₹{row['Live Spot (₹)']}")
        with col2:
            st.metric("Combined Premium", f"₹{row['Combined Premium (₹)']}", f"{row['% Chg (vs Base)']}%")
        with col3:
            st.text(f"Expiry: {row['Expiry']}")
            st.text(f"Strike: {row['Strike']}")
        with col4:
            st.text(f"CE LTP: ₹{row['CE (₹)']}")
            st.text(f"PE LTP: ₹{row['PE (₹)']}")
        with col5:
            if row['Status'] == "SPIKE":
                st.error("🚨 Day Lock: SPIKE")
            else:
                st.success("🟢 Monitoring")

# Chart Rendering Window Engine (§6)
st.markdown("---")
st.subheader("📈 Combined Premium Session Charts")
selected_symbol = st.selectbox("Select Symbol for Detailed View", [inst["symbol"] for inst in instruments])

if selected_symbol in st.session_state.history:
    chart_df = pd.DataFrame(st.session_state.history[selected_symbol])
    if not chart_df.empty:
        fig = px.line(
            chart_df, 
            x="Time", 
            y="Combined Premium", 
            title=f"{selected_symbol} - Session Timeline",
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)

# 10-Second Auto Refresh Hook Loop Engine
time.sleep(poll_interval)
st.rerun()
