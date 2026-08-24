import os
from dotenv import load_dotenv

# Explicitly discover and parse the local secure variable boundary
load_dotenv()

# --- DHAN API AUTH SEGMENT ---
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
TERMINAL_ENV = os.getenv("TERMINAL_ENV", "PRODUCTION")

# --- SECURE FAILSAFE CHECK ---
if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
    print("[WARNING] Active production credentials missing from .env environment configuration!")

# --- INSTRUMENT METADATA STRUCTURE REGISTER (§8) ---
# Maps underlyings to Dhan Exchange Segments, Strike Steps, and Security IDs
TRACKED_INSTRUMENTS = {
    "NIFTY": {
        "symbol": "NIFTY",
        "segment": "IDX_I",          # NSE Index
        "security_id": "13",          # Dhan Security Master Constant for NIFTY Index
        "strike_step": 50,
        "expiry": "2026-08-27"        # Target active execution contract
    },
    "BANKNIFTY": {
        "symbol": "BANKNIFTY",
        "segment": "IDX_I",          # NSE Index
        "security_id": "25",          # Dhan Security Master Constant for BANKNIFTY
        "strike_step": 100,
        "expiry": "2026-08-27"
    },
    "CRUDEOIL": {
        "symbol": "CRUDEOIL",
        "segment": "MCX_COMM",       # MCX Commodity Segment
        "security_id": "12001",       # Example MCX Underlying Master ID Mapping
        "strike_step": 50,
        "expiry": "2026-09-18"
    }
}

# --- GLOBAL OPERATION RULES ---
RATE_LIMIT_BUFFER = 3.0              # Enforces §8 constraint: ≤ 1 unique request / 3 seconds
CACHE_EXPIRY_SECONDS = 45            # Cache lifetime threshold for option chain snapshots
BASELINE_FILE = "previous_day_baseline.json"
