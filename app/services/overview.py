"""
Overview composition: Free Cash Flow + Buffett-style KPIs.

Source: Spec_Overview_Tab_FCF_and_Valuation_KPIs.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import FundamentalsSnapshot, InstrumentDatasetRefresh


FRESH_TTL = timedelta(hours=24)


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s in ("", "None", "null", "NA", "N/A"):
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def _is_fresh(ts: Optional[datetime], now: datetime) -> bool:
    return bool(ts) and (now - ts) < FRESH_TTL


def _get_refresh_row(db: Session, instrument_id: int, dataset_type: str) -> InstrumentDatasetRefresh:
    row = (
        db.query(InstrumentDatasetRefresh)
        .filter(
            InstrumentDatasetRefresh.instrument_id == instrument_id,
            InstrumentDatasetRefresh.dataset_type == dataset_type,
        )
        .first()
    )
    if row:
        return row
    row = InstrumentDatasetRefresh(instrument_id=instrument_id, dataset_type=dataset_type)
    db.add(row)
    db.commit()
    return row


def upsert_fundamentals_from_alpha_vantage_payload(
    db: Session,
    instrument_id: int,
    statement_type: str,
    payload: Dict[str, Any],
    fetched_at: Optional[str],
) -> Tuple[int, int]:
    """
    Persist annual + quarterly reports into FundamentalsSnapshot.
    Returns (inserted, skipped).
    """
    inserted = 0
    skipped = 0

    def _handle(freq: str, key: str):
        nonlocal inserted, skipped
        reports = payload.get(key)
        if not isinstance(reports, list):
            return
        for r in reports:
            if not isinstance(r, dict):
                continue
            d_str = r.get("fiscalDateEnding")
            try:
                period_end = date.fromisoformat(d_str) if d_str else None
            except Exception:
                period_end = None
            if not period_end:
                continue

            exists = (
                db.query(FundamentalsSnapshot)
                .filter(
                    FundamentalsSnapshot.instrument_id == instrument_id,
                    FundamentalsSnapshot.statement_type == statement_type,
                    FundamentalsSnapshot.frequency == freq,
                    FundamentalsSnapshot.period_end == period_end,
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            db.add(
                FundamentalsSnapshot(
                    instrument_id=instrument_id,
                    statement_type=statement_type,
                    frequency=freq,
                    period_end=period_end,
                    provider="alpha_vantage",
                    payload=r,
                    source_metadata={"endpoint": statement_type.upper(), "fetched_at": fetched_at},
                )
            )
            inserted += 1

    _handle("annual", "annualReports")
    _handle("quarterly", "quarterlyReports")
    db.commit()
    return inserted, skipped


def load_fundamentals_snapshots(
    db: Session, instrument_id: int, statement_type: str, frequency: str, limit: int
) -> List[FundamentalsSnapshot]:
    return (
        db.query(FundamentalsSnapshot)
        .filter(
            FundamentalsSnapshot.instrument_id == instrument_id,
            FundamentalsSnapshot.statement_type == statement_type,
            FundamentalsSnapshot.frequency == frequency,
        )
        .order_by(FundamentalsSnapshot.period_end.desc(), FundamentalsSnapshot.fetched_at.desc())
        .limit(limit)
        .all()
    )


@dataclass(frozen=True)
class FcfPoint:
    period_end: date
    fcf: Optional[float]
    revenue: Optional[float]
    fcf_margin: Optional[float]


@dataclass(frozen=True)
class KpiPoint:
    period_end: date
    roe: Optional[float]
    net_margin: Optional[float]
    operating_margin: Optional[float]
    fcf_margin: Optional[float]
    debt_to_equity: Optional[float]


def compute_fcf_series(
    cash_flows: List[FundamentalsSnapshot],
    incomes: List[FundamentalsSnapshot],
) -> List[FcfPoint]:
    """
    Compute FCF series aligned by period_end.
    """
    inc_by = {s.period_end: s for s in incomes}
    out: List[FcfPoint] = []
    for cf in sorted(cash_flows, key=lambda s: s.period_end):
        p = cf.payload if isinstance(cf.payload, dict) else {}
        ocf = _to_float(p.get("operatingCashflow"))
        capex = _to_float(p.get("capitalExpenditures"))
        fcf = None
        if ocf is not None and capex is not None:
            fcf = ocf - capex
        rev = None
        inc = inc_by.get(cf.period_end)
        if inc and isinstance(inc.payload, dict):
            rev = _to_float(inc.payload.get("totalRevenue"))
        fcf_margin = (fcf / rev) if (fcf is not None and rev not in (None, 0)) else None
        out.append(FcfPoint(period_end=cf.period_end, fcf=fcf, revenue=rev, fcf_margin=fcf_margin))
    return out


def compute_kpis(
    incomes: List[FundamentalsSnapshot],
    balances: List[FundamentalsSnapshot],
    fcf_points: List[FcfPoint],
) -> List[KpiPoint]:
    inc_by = {s.period_end: s for s in incomes}
    bs_by = {s.period_end: s for s in balances}
    fcf_by = {p.period_end: p for p in fcf_points}

    # sort by period end ascending for ROE avg equity
    period_ends = sorted(set(list(inc_by.keys()) + list(bs_by.keys())))
    out: List[KpiPoint] = []
    prev_equity = None
    for pe in period_ends:
        inc = inc_by.get(pe)
        bs = bs_by.get(pe)
        if not inc or not bs or not isinstance(inc.payload, dict) or not isinstance(bs.payload, dict):
            continue
        rev = _to_float(inc.payload.get("totalRevenue"))
        net_income = _to_float(inc.payload.get("netIncome"))
        op_income = _to_float(inc.payload.get("operatingIncome"))

        equity = _to_float(bs.payload.get("totalShareholderEquity"))
        liabilities = _to_float(bs.payload.get("totalLiabilities"))

        avg_equity = None
        if equity is not None and prev_equity is not None:
            avg_equity = (equity + prev_equity) / 2.0
        prev_equity = equity if equity is not None else prev_equity

        roe = (net_income / avg_equity) if (net_income is not None and avg_equity not in (None, 0)) else None
        net_margin = (net_income / rev) if (net_income is not None and rev not in (None, 0)) else None
        operating_margin = (op_income / rev) if (op_income is not None and rev not in (None, 0)) else None

        fcfp = fcf_by.get(pe)
        fcf_margin = fcfp.fcf_margin if fcfp else None

        debt_to_equity = (liabilities / equity) if (liabilities is not None and equity not in (None, 0)) else None

        out.append(
            KpiPoint(
                period_end=pe,
                roe=roe,
                net_margin=net_margin,
                operating_margin=operating_margin,
                fcf_margin=fcf_margin,
                debt_to_equity=debt_to_equity,
            )
        )
    return out


def refresh_fundamentals_if_needed(
    db: Session,
    instrument_id: int,
    frequency: str,
    now: datetime,
    fetch_fn,
) -> Dict[str, Any]:
    """
    frequency: quarterly|annual
    fetch_fn: () -> dict { cash_flow, income_statement, balance_sheet } each with {payload,fetched_at}
    """
    dataset_type = f"fundamentals_{frequency}"
    rr = _get_refresh_row(db, instrument_id, dataset_type)
    if _is_fresh(rr.last_refresh_at, now) and rr.last_status == "success":
        return {"fresh": True, "last_refresh_at": rr.last_refresh_at, "last_status": rr.last_status, "last_error": rr.last_error}

    try:
        resp = fetch_fn()
        for st_key, st_type in [
            ("cash_flow", "cash_flow"),
            ("income_statement", "income_statement"),
            ("balance_sheet", "balance_sheet"),
        ]:
            obj = resp.get(st_key) or {}
            payload = obj.get("payload") if isinstance(obj, dict) else None
            fetched_at = obj.get("fetched_at") if isinstance(obj, dict) else None
            if isinstance(payload, dict):
                upsert_fundamentals_from_alpha_vantage_payload(db, instrument_id, st_type, payload, fetched_at)
        rr.last_refresh_at = now
        rr.last_status = "success"
        rr.last_error = None
        db.commit()
        return {"fresh": False, "last_refresh_at": rr.last_refresh_at, "last_status": rr.last_status, "last_error": rr.last_error}
    except Exception as e:
        rr.last_status = "failed"
        rr.last_error = str(e)
        db.commit()
        return {"fresh": False, "last_refresh_at": rr.last_refresh_at, "last_status": rr.last_status, "last_error": rr.last_error}


def refresh_fundamentals_bundle(
    db: Session,
    instrument_id: int,
    now: datetime,
    fetch_fn,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Alpha Vantage statement endpoints return both quarterly and annual in the same payload.
    To avoid duplicate provider calls, refresh quarterly+annual together.
    Returns (quarterly_meta, annual_meta).
    """
    q_rr = _get_refresh_row(db, instrument_id, "fundamentals_quarterly")
    a_rr = _get_refresh_row(db, instrument_id, "fundamentals_annual")

    if _is_fresh(q_rr.last_refresh_at, now) and q_rr.last_status == "success" and _is_fresh(a_rr.last_refresh_at, now) and a_rr.last_status == "success":
        meta_q = {"fresh": True, "last_refresh_at": q_rr.last_refresh_at, "last_status": q_rr.last_status, "last_error": q_rr.last_error}
        meta_a = {"fresh": True, "last_refresh_at": a_rr.last_refresh_at, "last_status": a_rr.last_status, "last_error": a_rr.last_error}
        return meta_q, meta_a

    try:
        resp = fetch_fn()
        for st_key, st_type in [
            ("cash_flow", "cash_flow"),
            ("income_statement", "income_statement"),
            ("balance_sheet", "balance_sheet"),
        ]:
            obj = resp.get(st_key) or {}
            payload = obj.get("payload") if isinstance(obj, dict) else None
            fetched_at = obj.get("fetched_at") if isinstance(obj, dict) else None
            if isinstance(payload, dict):
                upsert_fundamentals_from_alpha_vantage_payload(db, instrument_id, st_type, payload, fetched_at)
        # One fetch updates both “datasets”
        for rr in (q_rr, a_rr):
            rr.last_refresh_at = now
            rr.last_status = "success"
            rr.last_error = None
        db.commit()
        meta_q = {"fresh": False, "last_refresh_at": q_rr.last_refresh_at, "last_status": q_rr.last_status, "last_error": q_rr.last_error}
        meta_a = {"fresh": False, "last_refresh_at": a_rr.last_refresh_at, "last_status": a_rr.last_status, "last_error": a_rr.last_error}
        return meta_q, meta_a
    except Exception as e:
        for rr in (q_rr, a_rr):
            rr.last_status = "failed"
            rr.last_error = str(e)
        db.commit()
        meta_q = {"fresh": False, "last_refresh_at": q_rr.last_refresh_at, "last_status": q_rr.last_status, "last_error": q_rr.last_error}
        meta_a = {"fresh": False, "last_refresh_at": a_rr.last_refresh_at, "last_status": a_rr.last_status, "last_error": a_rr.last_error}
        return meta_q, meta_a


