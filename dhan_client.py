"""
DhanHQ integration layer.

Currently returns simulated data. When DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN
are present in the environment (and USE_SIMULATION is not true), the client
will attempt to fetch live option-chain snapshots and compute ATM combined
premiums.

Security IDs (Dhan internal):
  NIFTY 50 index   → 13   (IDX_I)
  BANK NIFTY       → 25   (IDX_I)
  FIN NIFTY        → 27   (IDX_I)
  SENSEX           → 51   (IDX_I)  # verify latest
  RELIANCE         → 2885 (NSE_EQ)  # approximate; look up via instruments master
  etc.

Update the UNDERLYINGS map with correct security_ids for your account.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Try import; graceful fallback if package missing or credentials absent
try:
    from dhanhq import DhanContext, dhanhq  # type: ignore
    DHAN_AVAILABLE = True
except ImportError:
    DHAN_AVAILABLE = False
    DhanContext = None  # type: ignore
    dhanhq = None  # type: ignore


UNDERLYINGS: Dict[str, dict] = {
    "NIFTY": {"security_id": 13, "segment": "IDX_I", "step": 50, "name": "NIFTY 50"},
    "BANKNIFTY": {"security_id": 25, "segment": "IDX_I", "step": 100, "name": "BANK NIFTY"},
    "FINNIFTY": {"security_id": 27, "segment": "IDX_I", "step": 50, "name": "FIN NIFTY"},
    # Add more as needed after looking up security_ids from Dhan instruments master
}


class DhanClient:
    """Thin wrapper around DhanHQ option-chain endpoints."""

    def __init__(self) -> None:
        self.client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
        self.access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
        force_sim = os.getenv("USE_SIMULATION", "true").lower() in ("1", "true", "yes")
        self.use_live = (
            DHAN_AVAILABLE
            and bool(self.client_id)
            and bool(self.access_token)
            and not force_sim
        )
        self._dhan = None
        if self.use_live:
            try:
                ctx = DhanContext(self.client_id, self.access_token)
                self._dhan = dhanhq(ctx)
            except Exception:
                self.use_live = False

    @property
    def mode(self) -> str:
        return "LIVE (DhanHQ)" if self.use_live else "SIMULATED"

    def get_expiry_list(self, symbol: str) -> List[str]:
        if not self.use_live or symbol not in UNDERLYINGS:
            return []
        meta = UNDERLYINGS[symbol]
        try:
            resp = self._dhan.expiry_list(
                under_security_id=meta["security_id"],
                under_exchange_segment=meta["segment"],
            )
            # Response shape may vary by SDK version; normalise to list of date strings
            data = resp.get("data", resp) if isinstance(resp, dict) else resp
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict) and "expiry" in data:
                return [str(x) for x in data["expiry"]]
            return []
        except Exception:
            return []

    def get_option_chain(self, symbol: str, expiry: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full option chain and return a simplified dict:
        {
          "spot": float,
          "atm_strike": int,
          "ce_ltp": float,
          "pe_ltp": float,
          "combined_prem": float,
          "atm_iv": float,
          "raw": <original response>
        }
        """
        if not self.use_live or symbol not in UNDERLYINGS:
            return None
        meta = UNDERLYINGS[symbol]
        try:
            resp = self._dhan.option_chain(
                under_security_id=meta["security_id"],
                under_exchange_segment=meta["segment"],
                expiry=expiry,
            )
            data = resp.get("data", resp) if isinstance(resp, dict) else resp
            if not isinstance(data, dict):
                return None

            spot = float(data.get("last_price") or data.get("underlying_ltp") or 0)
            oc = data.get("oc") or data.get("option_chain") or {}
            if not oc or spot <= 0:
                return None

            step = meta["step"]
            atm = int(round(spot / step) * step)
            # Keys in oc are often string floats e.g. "24850.000000"
            key = None
            for k in oc:
                try:
                    if abs(float(k) - atm) < 0.01:
                        key = k
                        break
                except (TypeError, ValueError):
                    continue
            if key is None:
                # nearest strike
                strikes = sorted(float(k) for k in oc)
                atm = min(strikes, key=lambda s: abs(s - spot))
                for k in oc:
                    if abs(float(k) - atm) < 0.01:
                        key = k
                        break
            if key is None:
                return None

            ce = oc[key].get("ce") or {}
            pe = oc[key].get("pe") or {}
            ce_ltp = float(ce.get("last_price") or 0)
            pe_ltp = float(pe.get("last_price") or 0)
            iv_ce = float(ce.get("implied_volatility") or 0)
            iv_pe = float(pe.get("implied_volatility") or 0)
            atm_iv = (iv_ce + iv_pe) / 2 if (iv_ce or iv_pe) else 0.0

            return {
                "spot": spot,
                "atm_strike": int(atm),
                "ce_ltp": ce_ltp,
                "pe_ltp": pe_ltp,
                "combined_prem": ce_ltp + pe_ltp,
                "atm_iv": round(atm_iv, 2),
                "raw": data,
            }
        except Exception:
            return None


def get_client() -> DhanClient:
    return DhanClient()
