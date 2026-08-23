"""Utility helpers for the Premium Terminal."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def time_only() -> str:
    return now_ist().strftime("%H:%M:%S")


def is_market_hours() -> bool:
    """NSE equity/F&O market hours (approx). MCX has different sessions."""
    d = now_ist()
    if d.weekday() >= 5:  # Sat/Sun
        return False
    mins = d.hour * 60 + d.minute
    return (9 * 60 + 15) <= mins <= (15 * 60 + 30)


def fmt(n: float, d: int = 2) -> str:
    return f"{n:,.{d}f}"


def atm_strike(spot: float, step: float) -> int:
    return int(round(spot / step) * step)
