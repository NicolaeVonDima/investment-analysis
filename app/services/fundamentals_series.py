"""
Fundamentals multi-series extraction for overlay charts.

Source: Spec_FCF_MultiKPI_Chart_Toggles_NoTable.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.models import FundamentalsSnapshot
from app.services.overview import _to_float


ALLOWED_SERIES = {"fcf", "sbc", "netIncome", "debt", "dividends", "buybacks"}


@dataclass(frozen=True)
class SeriesBundle:
    currency: Optional[str]
    as_of: Optional[date]
    series: Dict[str, List[Tuple[date, Optional[float]]]]
    unavailable: List[str]


def _first_float(payload: Dict[str, Any], keys: Sequence[str]) -> Optional[float]:
    for k in keys:
        if k in payload:
            v = _to_float(payload.get(k))
            if v is not None:
                return v
    return None


def _abs_if_number(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    try:
        return abs(float(v))
    except Exception:
        return None


def compute_fundamentals_series(
    *,
    cash_flows: Iterable[FundamentalsSnapshot],
    incomes: Iterable[FundamentalsSnapshot],
    balances: Iterable[FundamentalsSnapshot],
    requested: Sequence[str],
) -> SeriesBundle:
    """
    Compute aligned time series for the requested keys.

    Notes:
    - We do not fabricate values.
    - Dividends and buybacks are plotted as absolute "cash spent" amounts.
    """
    req = [s for s in requested if s in ALLOWED_SERIES]
    unavailable: List[str] = []

    cf_by = {s.period_end: (s.payload if isinstance(s.payload, dict) else {}) for s in cash_flows}
    is_by = {s.period_end: (s.payload if isinstance(s.payload, dict) else {}) for s in incomes}
    bs_by = {s.period_end: (s.payload if isinstance(s.payload, dict) else {}) for s in balances}

    # Align to union of known period_end values across statements.
    period_ends = sorted(set(list(cf_by.keys()) + list(is_by.keys()) + list(bs_by.keys())))

    out: Dict[str, List[Tuple[date, Optional[float]]]] = {}

    for key in req:
        out[key] = []

    for pe in period_ends:
        cf = cf_by.get(pe) or {}
        inc = is_by.get(pe) or {}
        bs = bs_by.get(pe) or {}

        if "fcf" in out:
            ocf = _to_float(cf.get("operatingCashflow"))
            capex = _to_float(cf.get("capitalExpenditures"))
            v = (ocf - capex) if (ocf is not None and capex is not None) else None
            out["fcf"].append((pe, v))

        if "sbc" in out:
            v = _first_float(
                cf,
                [
                    "stockBasedCompensation",
                    "stockBasedCompensationExpense",
                    "shareBasedCompensation",
                ],
            )
            out["sbc"].append((pe, v))

        if "netIncome" in out:
            v = _first_float(inc, ["netIncome"])
            out["netIncome"].append((pe, v))

        if "debt" in out:
            total = _first_float(bs, ["totalDebt"])
            if total is None:
                st = _first_float(bs, ["shortTermDebt", "shortLongTermDebtTotal"])
                lt = _first_float(bs, ["longTermDebt", "longTermDebtNoncurrent"])
                if st is not None or lt is not None:
                    total = (st or 0.0) + (lt or 0.0)
            out["debt"].append((pe, total))

        if "dividends" in out:
            v = _first_float(
                cf,
                [
                    "dividendsPaid",
                    "dividendPayout",
                    "cashDividendsPaid",
                ],
            )
            out["dividends"].append((pe, _abs_if_number(v)))

        if "buybacks" in out:
            v = _first_float(
                cf,
                [
                    "paymentsForRepurchaseOfCommonStock",
                    "commonStockRepurchased",
                    "repurchaseOfCommonStock",
                ],
            )
            out["buybacks"].append((pe, _abs_if_number(v)))

    # Mark unavailable if all values are None (or series missing entirely)
    for key in req:
        pts = out.get(key) or []
        if not pts or all(v is None for _, v in pts):
            unavailable.append(key)
            out.pop(key, None)

    as_of = max((d for d in period_ends), default=None)
    return SeriesBundle(currency=None, as_of=as_of, series=out, unavailable=unavailable)


