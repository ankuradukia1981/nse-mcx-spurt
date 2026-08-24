# NSE/MCX Combined-Premium Terminal (v5 — Single Panel, Live)

A single-page, Bloomberg-terminal-style Streamlit dashboard that tracks
**ATM combined option premium** (Call LTP + Put LTP) across NSE indices,
NSE stocks, and MCX commodities via the **Dhan API**.

## What's in this version (v5)

- **Nearest expiry only** — always the most recent active expiry.
- **Liquidity-weighted ATM strike** — theoretical ATM ±2 strikes, scored
  by `(CE_OI + PE_OI) + 2×(CE_vol + PE_vol)`. Prefers the strike the
  market is actually trading; far more stable at the high-vol open than
  pure nearest-to-spot.
- **Post-open spurt baseline** — % change uses the **first valid Combined
  Premium after 09:15 IST** as baseline. No spurt calculation pre-open.
- **Day-persistent watchlist** — once a symbol crosses ±threshold (default
  5%) it stays locked on the watchlist until the **next trading day**,
  even if premium later falls back. Cleared automatically on day rollover.
- **One row per symbol** — single expiry + single strike only.
- **Watchlist columns**: Symbol | Expiry | Strike | CE | PE | Comb.Prem |
  %Chg | Status | Chart.
- **Chart** = Combined Premium (primary) + Volume bars (OI fallback) + Spot.
- **Stops polling after market close** — freezes on last tick; no Dhan
  calls after hours. Badges: **LIVE / MARKET CLOSE** and **DHAN LIVE /
  SIMULATED**.

## Project layout

```
├── app.py                        # Streamlit entry point (single panel)
├── config.py                     # instrument universe (indices/stocks/commodities)
├── dhan_service.py               # Dhan API wrapper + simulated fallback feed
├── requirements.txt
├── .env.example                  # copy -> .env and fill in your keys
├── .gitignore                    # keeps .env and secrets.toml out of git
└── README.md
```

## 1. Run locally

```bash
git clone <your-repo-url>
cd nse-mcx-premium-terminal
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN

streamlit run app.py
```

Get credentials from **dhan.co → My Profile → DhanHQ Trading APIs**.

Without credentials the app runs on a simulated feed (labeled SIMULATED).

## 2. Deploy to Streamlit Community Cloud

1. Push to GitHub (`.env` is git-ignored).
2. Connect repo at share.streamlit.io, main file `app.py`.
3. Secrets:
   ```toml
   DHAN_CLIENT_ID = "your_client_id"
   DHAN_ACCESS_TOKEN = "your_access_token"
   ```

## Core rules summary

| Rule | Behaviour |
|------|-----------|
| Expiry | Nearest active only |
| Strike | Liquidity-weighted near-ATM (±2 steps) |
| Baseline | First valid Combined Premium **after** open |
| Watchlist | Symbols that crossed ±threshold stay locked for the day |
| Chart | Combined Premium + Volume (OI fallback) |

## Notes

- Combined Premium = selected-strike Call LTP + Put LTP (straddle value).
- Monitoring/education tool — **not investment advice**.
- Dhan Option Chain is rate-limited; keep auto-refresh ≥ 10s.
