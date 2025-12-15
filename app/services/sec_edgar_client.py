"""
SEC EDGAR client (V0) for 10-K / 10-Q ingestion.

Implements:
- CIK resolution via company_tickers.json
- Company submissions fetch
- Primary filing document download

Complies with SEC guidance on automated access:
- User-Agent header with contact info (required)
- Global request rate limiting (default 10 rps)
- Backoff + retry on 429/403/5xx and network errors

References:
- Accessing EDGAR Data: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- Developer Resources: https://www.sec.gov/about/developer-resources
- Rate control limits (10 requests/sec): https://www.sec.gov/filergroup/announcements-old/new-rate-control-limits
- data.sec.gov landing: https://data.sec.gov/
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests


_rate_lock = threading.Lock()
_last_request_ts: float = 0.0


class SecEdgarError(RuntimeError):
    """Domain error for SEC EDGAR operations."""


def _rate_limited_sleep(max_rps: int) -> None:
    """
    Simple per-process rate limiter.

    Ensures at most `max_rps` requests per second by sleeping when needed.
    """
    global _last_request_ts
    if max_rps <= 0:
        return
    min_interval = 1.0 / float(max_rps)
    with _rate_lock:
        now = time.time()
        elapsed = now - _last_request_ts
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
            now = time.time()
        _last_request_ts = now


@dataclass
class SecClientConfig:
    enabled: bool = True
    max_rps: int = 10
    retry_max: int = 3
    user_agent: str = ""


class SecEdgarClient:
    """
    Lightweight client for SEC EDGAR (data.sec.gov).

    V0 uses JSON endpoints:
    - company_tickers.json
    - submissions/CIK##########.json
    and constructs primary document URLs under /Archives/edgar/data/.
    """

    COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_URL_TMPL = "https://data.sec.gov/submissions/CIK{cik}.json"
    ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

    def __init__(self, config: Optional[SecClientConfig] = None) -> None:
        cfg = config or self._from_env()
        if not cfg.user_agent:
            raise SecEdgarError("SEC_EDGAR_USER_AGENT is required for SEC EDGAR access")
        self._config = cfg

    @staticmethod
    def _from_env() -> SecClientConfig:
        enabled = os.getenv("SEC_INTEGRATION_ENABLED", "1") not in ("0", "false", "False")
        max_rps = int(os.getenv("SEC_MAX_REQUEST_RATE", "10") or "10")
        retry_max = int(os.getenv("SEC_RETRY_MAX_ATTEMPTS", "3") or "3")
        user_agent = os.getenv("SEC_EDGAR_USER_AGENT", "").strip()
        return SecClientConfig(enabled=enabled, max_rps=max_rps, retry_max=retry_max, user_agent=user_agent)

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _request_json(self, url: str) -> Dict[str, Any]:
        """GET JSON with rate limiting and retries."""
        headers = {
            "User-Agent": self._config.user_agent,
            "Accept": "application/json",
        }
        last_err: Optional[BaseException] = None
        for attempt in range(1, self._config.retry_max + 1):
            try:
                _rate_limited_sleep(self._config.max_rps)
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code in (429, 403, 500, 502, 503, 504):
                    last_err = SecEdgarError(f"SEC error {resp.status_code}: {resp.text[:200]}")
                elif resp.status_code != 200:
                    raise SecEdgarError(f"Unexpected SEC status {resp.status_code}: {resp.text[:200]}")
                else:
                    return resp.json()
            except (requests.RequestException, ValueError) as e:
                last_err = e

            # Exponential backoff
            if attempt < self._config.retry_max:
                time.sleep(2 ** (attempt - 1))

        raise SecEdgarError(f"Failed to GET {url}: {last_err}")

    def _request_bytes(self, url: str) -> Tuple[bytes, str]:
        """GET raw bytes with rate limiting and retries."""
        headers = {
            "User-Agent": self._config.user_agent,
            "Accept": "*/*",
        }
        last_err: Optional[BaseException] = None
        for attempt in range(1, self._config.retry_max + 1):
            try:
                _rate_limited_sleep(self._config.max_rps)
                resp = requests.get(url, headers=headers, timeout=20)
                if resp.status_code in (429, 403, 500, 502, 503, 504):
                    last_err = SecEdgarError(f"SEC error {resp.status_code}: {resp.text[:200]}")
                elif resp.status_code != 200:
                    raise SecEdgarError(f"Unexpected SEC status {resp.status_code}: {resp.text[:200]}")
                else:
                    ctype = resp.headers.get("Content-Type", "application/octet-stream")
                    return resp.content, ctype
            except (requests.RequestException) as e:
                last_err = e

            if attempt < self._config.retry_max:
                time.sleep(2 ** (attempt - 1))

        raise SecEdgarError(f"Failed to GET bytes {url}: {last_err}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_company_tickers_index(self) -> Dict[str, Any]:
        """
        Fetch company_tickers.json index.

        The JSON is keyed by integer index; each entry contains:
        - cik_str
        - ticker
        - title
        """
        return self._request_json(self.COMPANY_TICKERS_URL)

    def resolve_cik(self, ticker: str) -> Optional[str]:
        """
        Resolve a ticker symbol to a 10-digit padded CIK string.

        Returns None when not found.
        """
        t = (ticker or "").upper().strip()
        if not t:
            return None
        index = self.get_company_tickers_index()
        for _, row in index.items():
            try:
                if not isinstance(row, dict):
                    continue
                if (row.get("ticker") or "").upper().strip() == t:
                    cik_str = str(row.get("cik_str") or "").strip()
                    if not cik_str:
                        continue
                    return cik_str.zfill(10)
            except Exception:
                continue
        return None

    def get_company_submissions(self, cik_padded: str) -> Dict[str, Any]:
        """
        Fetch company submissions index for a given 10-digit padded CIK.
        """
        cik = (cik_padded or "").strip()
        if not cik or len(cik) != 10:
            raise SecEdgarError(f"Invalid padded CIK: {cik_padded!r}")
        url = self.SUBMISSIONS_URL_TMPL.format(cik=cik)
        return self._request_json(url)

    def download_primary_document(
        self, cik_padded: str, accession_number: str, primary_document: str
    ) -> Tuple[bytes, str, str]:
        """
        Download the primary filing document bytes.

        Returns (content_bytes, content_type, sha256_hex).
        """
        cik_str = (cik_padded or "").strip()
        if not cik_str or len(cik_str) != 10:
            raise SecEdgarError(f"Invalid padded CIK: {cik_padded!r}")
        cik_int = str(int(cik_str))  # drop leading zeros for archives path

        acc = (accession_number or "").replace("-", "").strip()
        if not acc:
            raise SecEdgarError("accession_number is required")

        primary = (primary_document or "").strip()
        if not primary:
            raise SecEdgarError("primary_document is required")

        url = f"{self.ARCHIVES_BASE}/{cik_int}/{acc}/{primary}"
        content, ctype = self._request_bytes(url)
        sha = hashlib.sha256(content).hexdigest()
        return content, ctype, sha


