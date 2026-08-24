import time
import requests
import random
from config import DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN, RATE_LIMIT_BUFFER, CACHE_EXPIRY_SECONDS

class DhanDataService:
    def __init__(self):
        self.client_id = DHAN_CLIENT_ID
        self.access_token = DHAN_ACCESS_TOKEN
        self.is_live = False
        self.last_api_call_time = 0.0
        self.chain_cache = {}
        self.base_url = "https://dhan.co"  # Production API Root Gateway
        
        # Validate that real production credentials exist
        if self.client_id and self.access_token and "MOCK" not in self.client_id:
            self.is_live = True
            self.headers = {
                "access-token": self.access_token,
                "client-id": self.client_id,
                "Content-Type": "application/json"
            }

    def _throttle_call(self):
        """Enforces §8 global request throttling: ≤ 1 unique request per 3 seconds"""
        now = time.time()
        elapsed = now - self.last_api_call_time
        if elapsed < RATE_LIMIT_BUFFER:
            time.sleep(RATE_LIMIT_BUFFER - elapsed)
        self.last_api_call_time = time.time()

    def get_live_option_chain_snapshot(self, symbol, segment, security_id, strike_step, expiry, target_strike):
        """
        Fetches option chains from Dhan using the production market feed API.
        Defensively matches specific strike structures.
        """
        cache_key = f"{symbol}_{expiry}_{target_strike}"
        now = time.time()

        if cache_key in self.chain_cache:
            cache_entry = self.chain_cache[cache_key]
            if now - cache_entry["timestamp"] < CACHE_EXPIRY_SECONDS:
                return cache_entry["data"], "LIVE_CACHE"

        if not self.is_live:
            return self._generate_simulated_fallback(symbol, strike_step, expiry, target_strike), "SIM"

        try:
            self._throttle_call()
            
            # Step A: Get Live Underlying Spot Price First
            spot_url = f"{self.base_url}/v2/marketfeed/ltp"
            spot_payload = {"instruments": [{"exchangeSegment": segment, "securityId": security_id}]}
            
            spot_res = requests.post(spot_url, json=spot_payload, headers=self.headers, timeout=5)
            live_spot = 0.0
            
            if spot_res.status_code == 200:
                spot_data = spot_res.json()
                # Parse standard Dhan dict response array format safely
                live_spot = float(spot_data.get("data", [{}])[0].get("lastPrice", 0.0))

            # Step B: Get Option Chain Instruments DataFrame via Data API 
            chain_url = f"{self.base_url}/v2/optionchain"
            chain_payload = {
                "underlyingSymbol": symbol,
                "exchangeSegment": segment,
                "expiryDate": expiry
            }
            
            response = requests.post(chain_url, json=chain_payload, headers=self.headers, timeout=6)
            
            if response.status_code == 200:
                chain_data = response.json().get("data", {})
                option_chain_entries = chain_data.get("optionChain", [])
                
                ce_ltp, pe_ltp = 0.0, 0.0
                
                # Filter precisely by the required target strike (§3.1)
                for item in option_chain_entries:
                    if int(float(item.get("strikePrice", 0))) == int(target_strike):
                        if item.get("optionType") == "CE":
                            ce_ltp = float(item.get("lastPrice", 0.0)) or float(item.get("bidPrice", 0.0))
                        elif item.get("optionType") == "PE":
                            pe_ltp = float(item.get("lastPrice", 0.0)) or float(item.get("bidPrice", 0.0))
                
                # Failsafe default protection if option legs have 0 volume/LTP initially
                if ce_ltp == 0.0 and pe_ltp == 0.0:
                    return self._generate_simulated_fallback(symbol, strike_step, expiry, target_strike), "LIVE_EMPTY_FALLBACK"

                result_data = {
                    "spot": live_spot if live_spot > 0 else float(target_strike),
                    "strike": target_strike,
                    "ce_ltp": round(ce_ltp, 2),
                    "pe_ltp": round(pe_ltp, 2),
                    "expiry": expiry
                }
                
                self.chain_cache[cache_key] = {"timestamp": time.time(), "data": result_data}
                return result_data, "LIVE"
                
            else:
                return self._generate_simulated_fallback(symbol, strike_step, expiry, target_strike), f"HTTP_{response.status_code}"

        except Exception as api_err:
            print(f"[LIVE CRITICAL CRASH] {symbol} fetch aborted: {api_err}")
            return self._generate_simulated_fallback(symbol, strike_step, expiry, target_strike), "ERROR"

    def _generate_simulated_fallback(self, symbol, strike_step, expiry, target_strike):
        base_spots = {"NIFTY": 24250.00, "BANKNIFTY": 52100.00, "CRUDEOIL": 6320.00}
        sim_spot = round(base_spots.get(symbol, float(target_strike)) + random.uniform(-10.0, 10.0), 2)
        return {
            "spot": sim_spot,
            "strike": target_strike,
            "ce_ltp": round(random.uniform(110.0, 180.0), 2),
            "pe_ltp": round(random.uniform(110.0, 180.0), 2),
            "expiry": expiry
        }
