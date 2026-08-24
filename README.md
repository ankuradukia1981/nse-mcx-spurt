# NSE/MCX Combined-Premium Terminal (v4 — Single Panel, Live)

A single-page, Bloomberg-terminal-style Streamlit dashboard that tracks
**ATM combined option premium** (ATM Call LTP + ATM Put LTP, i.e. the
short-straddle value) across NSE indices, NSE stocks, and MCX
commodities, pulling live data from the **Dhan API**.

## What's in this version

- **No sidebar** — everything lives on one panel: header, ticker strip,
  controls, an Alerts/Stats pair, and the watchlist, matching
  `premium-terminal-static.html`'s layout.
- **Watchlist shows spikes only.** It always filters to instruments
  whose combined premium has moved `>= threshold%` (default 5%) from
  the session baseline — there's no "show all" toggle. The ticker strip
  above it still shows every instrument, unfiltered.
- **Expiry is shown next to Spot** for every row and in the Session
  Stats panel, so you always know which option-chain expiry the
  spot/ATM numbers are quoted against.
- **Stops polling after market close.** Once `is_market_hours()` goes
  false, the app stops fetching new ticks *and* stops auto-rerunning —
  it freezes on the last tick instead of continuing to hit the Dhan
  API. The badge next to the clock reads **LIVE** or **MARKET CLOSE**
  accordingly. A separate badge (**DHAN LIVE** / **SIMULATED**) tells
  you whether the numbers themselves are real broker data or the
  fallback simulation.
- Click **Chart** on any watchlist row to open a full-page Spot vs
  Combined Premium vs Total OI chart for that symbol; **Back to
  Dashboard** returns you to the panel.

## Project layout

```
├── app.py                        # Streamlit entry point (single panel)
├── config.py                     # instrument universe (indices/stocks/commodities)
├── dhan_service.py                # Dhan API wrapper + simulated fallback feed
├── requirements.txt
├── .env.example                  # copy -> .env and fill in your keys
├── .streamlit/
│   ├── config.toml               # dark theme matching the terminal palette
│   └── secrets.toml.example      # template for Streamlit Cloud secrets
└── .gitignore                    # keeps .env and secrets.toml out of git
```

## 1. Run locally

```bash
git clone <your-repo-url>
cd nse-mcx-premium-terminal
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env
# then edit .env and paste your DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN

streamlit run app.py
```

Get your credentials from **dhan.co → My Profile → DhanHQ Trading APIs**
(generate an Access Token there). Access tokens on Dhan's standard plan
expire periodically — if the app suddenly shows the SIMULATED badge
again, regenerate the token.

If you don't add credentials at all, the app still runs fine — it just
runs on a realistic simulated feed (clearly labeled SIMULATED) so you
can try the UI without a broker account.

## 2. Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (your real `.env` is git-ignored — it never
   gets committed).
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo,
   set the main file to `app.py`.
3. In **App settings → Secrets**, paste (see `.streamlit/secrets.toml.example`):
   ```toml
   DHAN_CLIENT_ID = "your_client_id"
   DHAN_ACCESS_TOKEN = "your_access_token"
   ```
4. Deploy. Any time the token expires, update it in Secrets and reboot the app.

## How the data flows

- **Indices** (NIFTY, BANKNIFTY, FINNIFTY, SENSEX) use Dhan's stable
  index security IDs (`IDX_I` segment).
- **Stocks** and **MCX commodities** don't have fixed IDs worth
  hardcoding — commodity futures contracts roll monthly — so their
  security IDs are resolved at runtime from Dhan's public scrip master
  (cached 6 hours).
- For the resolved underlying, the app calls Dhan's **Option Chain
  API** (`expiry_list` + `option_chain`) and reads the nearest-expiry
  ATM strike's CE/PE last price directly.
- Any failure at any step (expired token, market closed, rate limit,
  symbol not resolvable) falls back per-instrument to the simulated
  feed rather than crashing.
- **Market-hours gating**: `is_market_hours()` (IST, NSE cash/index
  session 9:15–15:30, Mon–Fri) controls both whether the app fetches a
  new tick this cycle and whether it auto-reruns at all. Outside those
  hours the dashboard is frozen on its last known state.

## Notes

- Combined Premium = ATM Call LTP + ATM Put LTP (straddle value). A
  spike with a flat spot often signals rising IV / event risk; a drop
  with a flat spot suggests theta/IV crush.
- This tool is for monitoring/education — **not investment advice**.
- Dhan's Option Chain API is rate-limited to ~1 unique request per 3
  seconds per underlying/expiry — keep auto-refresh at 10s+ if you
  expand the instrument universe.
