# ⚡ Dhan Premium Terminal — Single-Panel Active Monitor

An automated, high-density options trading dashboard built with **Streamlit** and powered by the **DhanHQ API** framework. It tracks intraday options premium expansion and contract spikes.

## 🎛️ Redesigned Single-Panel Architecture
This single-panel interface groups all critical market data into a unified dashboard layout:
1. **Header Control Matrix:** Inline threshold controls, refresh timers, and live connectivity status indicators.
2. **Horizontal Monitor Grid:** A consolidated table showing spot changes, option legs, and combined premium metrics.
3. **Day-Locked Alerts Module:** Tracks instruments that have broken past your defined premium threshold.
4. **Asynchronous Visualizer Panel:** Real-time charting window to track option premium trends over time.

## 📁 Repository Directory Structure
```bash
├── .env                       # Local private security file (Ignored by Git)
├── .gitignore                 # File exclusion matrix
├── config.py                  # Static parameters and exchange mappings
├── dhan_service.py            # API request engine and rate throttler
├── app.py                     # High-density single-panel UI dashboard
└── requirements.txt           # Python dependency configuration
```

## 🛠️ Rapid Production Setup

1. **Clone the repository workspace down locally:**
   ```bash
   git clone https://github.com
   cd dhan-premium-monitor
   ```

2. **Populate your secure credentials into a local `.env` file:**
   ```ini
   DHAN_CLIENT_ID="your_genuine_client_id_here"
   DHAN_ACCESS_TOKEN="your_genuine_secret_token_here"
   TERMINAL_ENV="PRODUCTION"
   ```

3. **Install the required system dependencies using pip:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the core dashboard application interface:**
   ```bash
   streamlit run app.py
   ```
