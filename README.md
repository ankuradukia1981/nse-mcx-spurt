# NSE/MCX Premium Terminal — Spike Monitor

Terminal-style Streamlit dashboard that monitors **ATM Combined Premium** (ATM Call LTP + ATM Put LTP) across major NSE indices, stocks and MCX commodities. Spikes above a configurable threshold are highlighted as potential IV-expansion events.

![Theme](https://img.shields.io/badge/theme-terminal%20dark-06b6d4) ![Stack](https://img.shields.io/badge/stack-Streamlit%20%7C%20Plotly%20%7C%20DhanHQ-fbbf24)

---

## Features

| Feature | Description |
|--------|-------------|
| **2-panel layout** | Main dashboard + sticky stats sidebar |
| **Terminal theme** | Dark void background (`#05080f`), cyan / amber / green accents, JetBrains Mono |
| **Spike detection** | Configurable % threshold; optional “show only spikes” filter |
| **Interactive charts** | Full-page Plotly view — Combined Premium, scaled Spot, Volume + threshold bands |
| **Real-time updates** | Auto-refresh loop with pause / resume / reset |
| **DhanHQ ready** | Live option-chain path implemented; defaults to high-fidelity simulation |
| **GitHub-ready** | Clean structure, `.env.example`, `.gitignore`, requirements, docs |

---

## Quick Start

```bash
# 1. Clone / unzip
cd nse-mcx-premium-terminal

# 2. Virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install deps
pip install -r requirements.txt

# 4. (Optional) Live data — copy credentials
cp .env.example .env
# edit .env → set DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
# set USE_SIMULATION=false

# 5. Run
streamlit run app.py
```

Open the URL shown in the terminal (default `http://localhost:8501`).

---

## Project Structure

```
nse-mcx-premium-terminal/
├── app.py                 # Main Streamlit entry-point
├── requirements.txt
├── .env.example           # DhanHQ credentials template
├── .gitignore
├── README.md
├── .streamlit/
│   └── config.toml        # Dark terminal theme
├── data/
│   └── simulator.py       # High-fidelity tick generator (mirrors original HTML)
├── services/
│   └── dhan_client.py     # DhanHQ option-chain wrapper (live path)
└── utils/
    └── helpers.py         # IST clock, market hours, formatting
```

---

## Configuration

### Simulation (default)

No credentials needed. The simulator produces realistic spot / premium / IV / volume paths and injects occasional spikes so the watchlist is never empty.

### Live DhanHQ

1. Create an API app at [dhanhq.co](https://dhanhq.co) → Profile → API.
2. Put credentials in `.env`:

```env
DHAN_CLIENT_ID=1000xxxxxx
DHAN_ACCESS_TOKEN=eyJ...
USE_SIMULATION=false
```

3. Update security IDs in `services/dhan_client.py` → `UNDERLYINGS` map if needed (NIFTY=13, BANKNIFTY=25, etc.).

The client falls back to simulation automatically if the package is missing, credentials are empty, or an API call fails.

---

## How Spike Logic Works

```
Combined Premium  =  ATM Call LTP  +  ATM Put LTP
% Change          =  (current_prem − session_open_prem) / session_open_prem × 100
```

A spike is recorded when `|% Change|` or the bar-to-bar jump exceeds the threshold (default 5 %). Alerts are de-duplicated for ~22 s per symbol.

Large premium moves **without** a commensurate spot move are classic signs of **IV expansion** — useful for premium sellers / buyers and straddle/strangle monitors.

---

## Controls

| Control | Effect |
|---------|--------|
| Spike Threshold (%) | Alert / filter level (1–30) |
| Show only ≥ threshold | Hide non-spike symbols from the table |
| Timeframe | Adjusts internal tick interval (UI refresh cadence) |
| Pause / Resume | Freeze or resume the simulation loop |
| Reset | Clear history, reseed, restart counters |
| 📈 buttons | Open full-page Plotly chart for that symbol |

---

## Tech Notes

- **Streamlit** ≥ 1.32 with dark theme via `.streamlit/config.toml`
- **Plotly** dual-axis charts (premium + volume bars, scaled spot overlay)
- **pandas** styling for the watchlist dataframe
- Auto-rerun loop keeps the UI “live”; pause stops both data generation and the sleep/rerun cycle
- Original HTML terminal logic is faithfully ported into `data/simulator.py`

---

## Roadmap / Extensions

- [ ] Wire live DhanHQ ticks into the same history buffers
- [ ] WebSocket market feed for true real-time
- [ ] Alert sound / Telegram webhook on spike
- [ ] Multi-expiry ATM premium surface
- [ ] Historical spike replay from saved sessions

---

## License

MIT — use freely for personal or commercial trading tools.

---

**NSE/MCX Premium Terminal v3.1 · Spike Monitor**  
Combined Prem = ATM Call LTP + ATM Put LTP · Data simulated for demo · DhanHQ integration ready
