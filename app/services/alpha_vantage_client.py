"""
Alpha Vantage client (MVP, free tier).

Implements a small subset needed for:
- UI-lite identity + latest price (overview + global quote)
- Heavy backfill (daily adjusted, fundamentals)

All responses include provider metadata for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional

import os
import time
import requests


ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"


@dataclass(frozen=True)
class AlphaVantageConfig:
    api_key: str
    base_url: str = ALPHAVANTAGE_BASE_URL
    # Best-effort local rate limit (does not coordinate across workers).
    min_interval_seconds: float = 12.5  # ~5 calls/min


class AlphaVantageClient:
    def __init__(self, config: Optional[AlphaVantageConfig] = None, session: Optional[requests.Session] = None):
        self.mock_enabled = (os.getenv("ALPHAVANTAGE_MOCK") or "").strip() in ("1", "true", "TRUE", "yes", "YES")
        if config is None:
            api_key = (os.getenv("ALPHAVANTAGE_API_KEY") or "").strip()
            if not api_key and not self.mock_enabled:
                raise ValueError("ALPHAVANTAGE_API_KEY is not set")
            config = AlphaVantageConfig(api_key=(api_key or "MOCK"))
        self.config = config
        self.session = session or requests.Session()
        self._last_call_ts: Optional[float] = None

    def _throttle(self):
        if self.mock_enabled:
            return
        if self._last_call_ts is None:
            return
        elapsed = time.time() - self._last_call_ts
        sleep_for = self.config.min_interval_seconds - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)

    def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_enabled:
            from app.services.alpha_vantage_mock import mock_response

            fn = params.get("function")
            return mock_response(fn, params)
        self._throttle()
        params = {**params, "apikey": self.config.api_key}
        resp = self.session.get(self.config.base_url, params=params, timeout=30)
        self._last_call_ts = time.time()
        resp.raise_for_status()
        data = resp.json()
        # Alpha Vantage error signals
        if isinstance(data, dict):
            if data.get("Error Message"):
                raise ValueError(data.get("Error Message"))
            if data.get("Note"):
                # Common for rate limit responses
                raise RuntimeError(data.get("Note"))
        return data

    def get_company_overview(self, symbol: str) -> Dict[str, Any]:
        data = self._get({"function": "OVERVIEW", "symbol": symbol})
        return {
            "provider": "alpha_vantage",
            "endpoint": "OVERVIEW",
            "symbol": symbol,
            "fetched_at": datetime.utcnow().isoformat(),
            "payload": data,
        }

    def get_global_quote(self, symbol: str) -> Dict[str, Any]:
        data = self._get({"function": "GLOBAL_QUOTE", "symbol": symbol})
        return {
            "provider": "alpha_vantage",
            "endpoint": "GLOBAL_QUOTE",
            "symbol": symbol,
            "fetched_at": datetime.utcnow().isoformat(),
            "payload": data,
        }

    def get_daily_adjusted(self, symbol: str, outputsize: str = "full") -> Dict[str, Any]:
        data = self._get({"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol, "outputsize": outputsize})
        return {
            "provider": "alpha_vantage",
            "endpoint": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "fetched_at": datetime.utcnow().isoformat(),
            "payload": data,
        }

    def get_daily_adjusted_compact(self, symbol: str) -> Dict[str, Any]:
        return self.get_daily_adjusted(symbol, outputsize="compact")

    def get_income_statement(self, symbol: str) -> Dict[str, Any]:
        data = self._get({"function": "INCOME_STATEMENT", "symbol": symbol})
        return {
            "provider": "alpha_vantage",
            "endpoint": "INCOME_STATEMENT",
            "symbol": symbol,
            "fetched_at": datetime.utcnow().isoformat(),
            "payload": data,
        }

    def get_balance_sheet(self, symbol: str) -> Dict[str, Any]:
        data = self._get({"function": "BALANCE_SHEET", "symbol": symbol})
        return {
            "provider": "alpha_vantage",
            "endpoint": "BALANCE_SHEET",
            "symbol": symbol,
            "fetched_at": datetime.utcnow().isoformat(),
            "payload": data,
        }

    def get_cash_flow(self, symbol: str) -> Dict[str, Any]:
        data = self._get({"function": "CASH_FLOW", "symbol": symbol})
        return {
            "provider": "alpha_vantage",
            "endpoint": "CASH_FLOW",
            "symbol": symbol,
            "fetched_at": datetime.utcnow().isoformat(),
            "payload": data,
        }

    def symbol_search(self, keywords: str) -> Dict[str, Any]:
        data = self._get({"function": "SYMBOL_SEARCH", "keywords": keywords})
        return {
            "provider": "alpha_vantage",
            "endpoint": "SYMBOL_SEARCH",
            "keywords": keywords,
            "fetched_at": datetime.utcnow().isoformat(),
            "payload": data,
        }


def parse_global_quote_price(global_quote_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      { "price": float|None, "as_of_date": date|None, "raw": ... }
    """
    payload = global_quote_payload.get("payload") if isinstance(global_quote_payload, dict) else None
    if not isinstance(payload, dict):
        return {"price": None, "as_of_date": None, "raw": global_quote_payload}
    gq = payload.get("Global Quote")
    if not isinstance(gq, dict):
        return {"price": None, "as_of_date": None, "raw": payload}
    price_str = gq.get("05. price")
    date_str = gq.get("07. latest trading day")
    try:
        price = float(price_str) if price_str is not None and price_str != "" else None
    except Exception:
        price = None
    try:
        as_of = date.fromisoformat(date_str) if date_str else None
    except Exception:
        as_of = None
    return {"price": price, "as_of_date": as_of, "raw": payload}


