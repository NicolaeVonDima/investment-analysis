"""
Deterministic mock payloads for Alpha Vantage (local debugging).

Enabled via env var: ALPHAVANTAGE_MOCK=1
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def mock_response(function: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a minimal Alpha Vantage-like JSON payload for a subset of functions used in the app.
    """
    fn = (function or "").upper()
    symbol = (params.get("symbol") or "").upper().strip()
    keywords = (params.get("keywords") or "").upper().strip()

    if fn == "SYMBOL_SEARCH":
        # Minimal payload shape: { "bestMatches": [...] }
        # Include AAPL so ticker validation can succeed without network calls.
        if keywords in ("AAPL", "APPLE", "APPL"):
            return {
                "bestMatches": [
                    {
                        "1. symbol": "AAPL",
                        "2. name": "Apple Inc",
                        "3. type": "Equity",
                        "4. region": "United States",
                        "8. currency": "USD",
                        "9. matchScore": "1.0000",
                    }
                ],
                "_mocked_at": _iso_now(),
            }
        # A couple seeded examples
        if keywords in ("ADBE", "ADOBE"):
            return {
                "bestMatches": [
                    {
                        "1. symbol": "ADBE",
                        "2. name": "Adobe Inc",
                        "3. type": "Equity",
                        "4. region": "United States",
                        "8. currency": "USD",
                        "9. matchScore": "1.0000",
                    }
                ],
                "_mocked_at": _iso_now(),
            }
        if keywords in ("GOOG", "GOOGL", "GOOGLE"):
            return {
                "bestMatches": [
                    {
                        "1. symbol": "GOOGL",
                        "2. name": "Alphabet Inc - Class A",
                        "3. type": "Equity",
                        "4. region": "United States",
                        "8. currency": "USD",
                        "9. matchScore": "1.0000",
                    }
                ],
                "_mocked_at": _iso_now(),
            }
        return {"bestMatches": [], "_mocked_at": _iso_now()}

    if fn == "TIME_SERIES_DAILY_ADJUSTED":
        # Minimal payload shape used by parse_daily_adjusted_latest:
        # { "Time Series (Daily)": { "YYYY-MM-DD": {"4. close": "..."} } }
        if symbol == "AAPL":
            return {
                "Meta Data": {"2. Symbol": "AAPL", "3. Last Refreshed": "2025-12-12"},
                "Time Series (Daily)": {
                    "2025-12-12": {"4. close": "198.1234"},
                    "2025-12-11": {"4. close": "196.0000"},
                },
                "_mocked_at": _iso_now(),
            }
        if symbol == "ADBE":
            return {
                "Meta Data": {"2. Symbol": "ADBE", "3. Last Refreshed": "2025-12-12"},
                "Time Series (Daily)": {
                    "2025-12-12": {"4. close": "612.3456"},
                    "2025-12-11": {"4. close": "600.0000"},
                },
                "_mocked_at": _iso_now(),
            }
        if symbol == "GOOGL":
            return {
                "Meta Data": {"2. Symbol": "GOOGL", "3. Last Refreshed": "2025-12-12"},
                "Time Series (Daily)": {
                    "2025-12-12": {"4. close": "170.1250"},
                    "2025-12-11": {"4. close": "169.0000"},
                },
                "_mocked_at": _iso_now(),
            }
        return {"Meta Data": {"2. Symbol": symbol}, "Time Series (Daily)": {}, "_mocked_at": _iso_now()}

    if fn == "GLOBAL_QUOTE":
        # Minimal payload shape used by parse_global_quote_price
        return {
            "Global Quote": {
                "01. symbol": symbol or keywords,
                "05. price": "123.4500",
                "07. latest trading day": "2025-12-12",
            },
            "_mocked_at": _iso_now(),
        }

    if fn == "OVERVIEW":
        return {
            "Symbol": symbol,
            "Name": {"AAPL": "Apple Inc", "ADBE": "Adobe Inc", "GOOGL": "Alphabet Inc"}.get(symbol, symbol),
            "Currency": "USD",
            "_mocked_at": _iso_now(),
        }

    # Unsupported mock endpoint: return empty payload (acts like "not found")
    return {"_mocked_at": _iso_now()}


