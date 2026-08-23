"""Simulated market data generator matching the original HTML terminal logic."""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils.helpers import atm_strike, time_only

SYMBOLS: Dict[str, dict] = {
    "NIFTY": {"name": "NIFTY 50", "baseSpot": 24850, "step": 50, "basePrem": 185, "lot": 25},
    "BANKNIFTY": {"name": "BANK NIFTY", "baseSpot": 51200, "step": 100, "basePrem": 420, "lot": 15},
    "FINNIFTY": {"name": "FIN NIFTY", "baseSpot": 23800, "step": 50, "basePrem": 160, "lot": 25},
    "SENSEX": {"name": "SENSEX", "baseSpot": 81200, "step": 100, "basePrem": 580, "lot": 10},
    "RELIANCE": {"name": "RELIANCE", "baseSpot": 2980, "step": 20, "basePrem": 48, "lot": 250},
    "HDFCBANK": {"name": "HDFC BANK", "baseSpot": 1685, "step": 10, "basePrem": 28, "lot": 550},
    "CRUDEOIL": {"name": "CRUDE OIL", "baseSpot": 6200, "step": 50, "basePrem": 95, "lot": 100},
    "GOLD": {"name": "GOLD", "baseSpot": 72100, "step": 100, "basePrem": 420, "lot": 1},
    "SILVER": {"name": "SILVER", "baseSpot": 84500, "step": 250, "basePrem": 680, "lot": 1},
    "NATURALGAS": {"name": "NATURAL GAS", "baseSpot": 210, "step": 5, "basePrem": 12, "lot": 1250},
}


def _randn() -> float:
    u = v = 0.0
    while u == 0:
        u = random.random()
    while v == 0:
        v = random.random()
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)


@dataclass
class Tick:
    t: float
    time: str
    spot: float
    prem: float
    ce: float
    pe: float
    pct: float
    strike: int
    iv: float
    vol: int


@dataclass
class SimulatorState:
    history: Dict[str, List[Tick]] = field(default_factory=dict)
    open_prem: Dict[str, float] = field(default_factory=dict)
    alerts: List[dict] = field(default_factory=list)
    spike_count: int = 0

    def __post_init__(self) -> None:
        for s in SYMBOLS:
            self.history[s] = []
            self.open_prem[s] = SYMBOLS[s]["basePrem"] * (0.94 + random.random() * 0.12)


def generate_tick(sym: str, state: SimulatorState) -> Tick:
    cfg = SYMBOLS[sym]
    last = state.history[sym][-1] if state.history[sym] else None

    if not last:
        spot = cfg["baseSpot"] + _randn() * cfg["baseSpot"] * 0.0018
        prem = state.open_prem[sym]
        vol = random.randint(80, 330)
    else:
        spot = last.spot + _randn() * cfg["baseSpot"] * 0.00075
        d_prem = (state.open_prem[sym] - last.prem) * 0.018 + _randn() * (cfg["basePrem"] * 0.011)
        # Higher chance of spikes for demo
        if random.random() < 0.07:
            d_prem += (1 if random.random() > 0.4 else -1) * cfg["basePrem"] * (0.05 + random.random() * 0.09)
        d_prem -= cfg["basePrem"] * 0.0007
        prem = max(cfg["basePrem"] * 0.38, last.prem + d_prem)
        vol = random.randint(80, 330)
        if abs(d_prem) > cfg["basePrem"] * 0.03:
            vol = int(vol * (3 + random.random() * 3))

    split = 0.43 + random.random() * 0.14
    ce = prem * split
    pe = prem * (1 - split)
    pct = ((prem - state.open_prem[sym]) / state.open_prem[sym]) * 100
    strike = atm_strike(spot, cfg["step"])
    iv = 11.5 + abs(pct) * 0.32 + random.random() * 3.8

    return Tick(
        t=time.time(),
        time=time_only(),
        spot=round(spot, 2),
        prem=round(prem, 2),
        ce=round(ce, 2),
        pe=round(pe, 2),
        pct=round(pct, 2),
        strike=strike,
        iv=round(iv, 1),
        vol=vol,
    )


def push_tick(sym: str, tick: Tick, state: SimulatorState, threshold: float) -> None:
    hist = state.history[sym]
    hist.append(tick)
    if len(hist) > 180:
        hist.pop(0)

    prev = hist[-2] if len(hist) > 1 else None
    jump = ((tick.prem - prev.prem) / prev.prem) * 100 if prev else 0.0

    if abs(tick.pct) >= threshold or abs(jump) >= threshold:
        abs_pct = tick.pct if abs(tick.pct) >= threshold else jump
        recent = next((a for a in state.alerts if a["sym"] == sym and (time.time() - a["ts"]) < 22), None)
        if not recent:
            state.spike_count += 1
            state.alerts.insert(
                0,
                {
                    "ts": time.time(),
                    "time": tick.time,
                    "sym": sym,
                    "pct": abs_pct,
                    "prem": tick.prem,
                    "spot": tick.spot,
                },
            )
            if len(state.alerts) > 50:
                state.alerts.pop()


def seed_history(state: SimulatorState, n: int = 50) -> None:
    """Seed initial history so the UI is never empty on first load."""
    for i in range(n):
        for sym in SYMBOLS:
            t = generate_tick(sym, state)
            t.t = time.time() - (n - i) * 3.5
            # Force a couple of early spikes
            if sym in ("GOLD", "NIFTY", "CRUDEOIL") and i > n - 8:
                t.prem = state.open_prem[sym] * (1.06 + random.random() * 0.04)
                t.pct = ((t.prem - state.open_prem[sym]) / state.open_prem[sym]) * 100
                t.ce = round(t.prem * 0.48, 2)
                t.pe = round(t.prem * 0.52, 2)
            state.history[sym].append(t)
