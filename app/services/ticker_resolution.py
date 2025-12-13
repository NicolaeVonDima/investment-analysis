"""
Ticker resolution and validation helpers (v1.4.0).

Source: Spec_Ticker_Search_Validation_and_Browse_Guard.pdf
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


TICKER_RE = re.compile(r"^[A-Z0-9.\-]+$")
SYMBOL_SEARCH_TTL = timedelta(hours=24)


def normalize_query(q: str) -> str:
    return (q or "").strip().upper()


def valid_ticker_format(q: str) -> bool:
    if not q:
        return False
    return bool(TICKER_RE.match(q))


def parse_symbol_search_matches(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Alpha Vantage SYMBOL_SEARCH returns { bestMatches: [...] }.
    """
    if not isinstance(payload, dict):
        return []
    matches = payload.get("bestMatches")
    return matches if isinstance(matches, list) else []


@dataclass(frozen=True)
class ResolutionResult:
    symbol: str
    name: Optional[str]
    region: Optional[str]
    currency: Optional[str]
    resolution_source: str  # db|alias|provider
    provider_symbol: str
    suggestions: List[str]


def choose_best_match(query: str, matches: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    MVP ranking:
    - Prefer exact symbol match to query.
    - Otherwise, prefer US region results.
    - Break ties by highest matchScore.
    """
    def sym(m: Dict[str, Any]) -> str:
        return (m.get("1. symbol") or "").upper().strip()

    def region(m: Dict[str, Any]) -> str:
        return (m.get("4. region") or "").lower()

    def score(m: Dict[str, Any]) -> float:
        try:
            return float(m.get("9. matchScore") or 0.0)
        except Exception:
            return 0.0

    # suggestions: top 5 by score
    sorted_all = sorted(matches, key=score, reverse=True)
    suggestions = [sym(m) for m in sorted_all if sym(m)][:5]

    # exact symbol
    for m in matches:
        if sym(m) == query:
            return m, suggestions

    us = [m for m in matches if "united states" in region(m)]
    pool = us if us else matches
    if not pool:
        return None, suggestions

    best = sorted(pool, key=score, reverse=True)[0]
    return best, suggestions


