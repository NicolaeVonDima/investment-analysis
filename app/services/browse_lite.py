"""
Browse-lite service logic (24h DB cache) per spec.

Source: Spec_Ticker_Search_Browse_AlphaVantage_24hCache.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Any, Dict, Optional, Tuple


FRESH_TTL = timedelta(hours=24)


def is_fresh(last_refresh_at: Optional[datetime], now: datetime, ttl: timedelta = FRESH_TTL) -> bool:
    if not last_refresh_at:
        return False
    return (now - last_refresh_at) < ttl


@dataclass(frozen=True)
class LitePrice:
    as_of_date: date
    close: Optional[float]
    change_pct: Optional[float]


def parse_daily_adjusted_latest(payload: Dict[str, Any]) -> Optional[LitePrice]:
    """
    Extract the latest date/close from Alpha Vantage TIME_SERIES_DAILY_ADJUSTED.
    """
    ts = payload.get("Time Series (Daily)") if isinstance(payload, dict) else None
    if not isinstance(ts, dict) or not ts:
        return None

    # Sort dates descending; keys are ISO YYYY-MM-DD.
    dates = sorted(ts.keys(), reverse=True)
    latest_key = dates[0]
    prev_key = dates[1] if len(dates) > 1 else None

    try:
        latest_date = date.fromisoformat(latest_key)
    except Exception:
        return None

    def _close(d_key: Optional[str]) -> Optional[float]:
        if not d_key:
            return None
        row = ts.get(d_key)
        if not isinstance(row, dict):
            return None
        v = row.get("4. close")
        try:
            return float(v) if v is not None and v != "" else None
        except Exception:
            return None

    latest_close = _close(latest_key)
    prev_close = _close(prev_key)

    change_pct = None
    if latest_close is not None and prev_close is not None and prev_close != 0:
        change_pct = (latest_close - prev_close) / prev_close

    return LitePrice(as_of_date=latest_date, close=latest_close, change_pct=change_pct)


