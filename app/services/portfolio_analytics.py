"""
Portfolio analytics computation.

Computes dashboard-style aggregates from portfolio positions that reference memo snapshots.
All output is derived from stored snapshots (immutable artifacts).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as date_type, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    Portfolio,
    Position,
    MemoSnapshot,
    EvidenceSnapshot,
    MetricsSnapshot,
    DataSnapshot,
    PortfolioAnalyticsSnapshot,
)


KEY_METRICS = [
    "pe_ratio",
    "price_to_book",
    "dividend_yield",
    "profit_margin",
    "revenue_growth",
    "market_cap",
]


def recompute_portfolio_dashboard(db: Session, portfolio_id: int, as_of_date: Optional[date_type] = None) -> PortfolioAnalyticsSnapshot:
    portfolio = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise ValueError("Portfolio not found")

    positions: List[Position] = (
        db.query(Position).filter(Position.portfolio_id == portfolio_id).order_by(Position.id.asc()).all()
    )

    memo_ids = [p.memo_snapshot_id for p in positions]
    memos: List[MemoSnapshot] = db.query(MemoSnapshot).filter(MemoSnapshot.id.in_(memo_ids)).all() if memo_ids else []
    memo_by_id = {m.id: m for m in memos}

    weights = _resolve_weights(positions)

    allocation_by_ticker: Dict[str, float] = defaultdict(float)
    allocation_by_sector: Dict[str, float] = defaultdict(float)

    # Aggregates by metric name (weighted)
    metric_weighted_sum: Dict[str, float] = defaultdict(float)
    metric_weighted_w: Dict[str, float] = defaultdict(float)

    constituents: List[int] = []

    for pos, w in zip(positions, weights):
        memo = memo_by_id.get(pos.memo_snapshot_id)
        if not memo:
            continue
        memorandum = memo.memorandum or {}
        ticker = (memorandum.get("ticker") or pos.ticker or "").upper()
        if not ticker:
            ticker = pos.ticker.upper()
        sector = (memorandum.get("company") or {}).get("sector") or "Unknown"

        allocation_by_ticker[ticker] += w
        allocation_by_sector[sector] += w
        constituents.append(memo.id)

        metrics_list = memorandum.get("metrics") or []
        metric_map = _metric_map(metrics_list)
        for name in KEY_METRICS:
            val = _metric_value(metric_map.get(name))
            if val is None:
                continue
            metric_weighted_sum[name] += val * w
            metric_weighted_w[name] += w

    valuation_aggregates = {
        name: (metric_weighted_sum[name] / metric_weighted_w[name]) if metric_weighted_w[name] else None
        for name in KEY_METRICS
    }

    concentration = _concentration_risk(allocation_by_ticker)

    thesis_drift = _thesis_drift(db, portfolio_id)

    dashboard: Dict[str, Any] = {
        "allocation": {
            "by_ticker": dict(sorted(allocation_by_ticker.items(), key=lambda kv: kv[1], reverse=True)),
            "by_sector": dict(sorted(allocation_by_sector.items(), key=lambda kv: kv[1], reverse=True)),
        },
        "aggregates": {
            "key_metrics_weighted_avg": valuation_aggregates,
        },
        "risk": concentration,
        "thesis_drift": thesis_drift,
        "meta": {
            "position_count": len(positions),
            "constituent_memo_snapshot_ids": constituents,
        },
    }

    snap = PortfolioAnalyticsSnapshot(
        portfolio_id=portfolio_id,
        as_of_date=as_of_date or datetime.utcnow().date(),
        dashboard=dashboard,
        constituent_memo_snapshot_ids=constituents,
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


def _resolve_weights(positions: List[Position]) -> List[float]:
    if not positions:
        return []
    provided = [p.weight for p in positions]
    if all(w is not None for w in provided):
        total = float(sum(provided)) or 1.0
        return [float(w) / total for w in provided]  # normalize
    # Equal weight fallback
    eq = 1.0 / len(positions)
    return [eq for _ in positions]


def _metric_map(metrics_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for m in metrics_list:
        if not isinstance(m, dict):
            continue
        name = m.get("name")
        if name:
            out[name] = m
    return out


def _metric_value(metric: Optional[Dict[str, Any]]) -> Optional[float]:
    if not metric:
        return None
    v = (metric.get("value") or {}).get("value")
    try:
        return float(v)
    except Exception:
        return None


def _concentration_risk(allocation_by_ticker: Dict[str, float]) -> Dict[str, Any]:
    items = sorted(allocation_by_ticker.items(), key=lambda kv: kv[1], reverse=True)
    top = items[:5]
    hhi = sum((w ** 2) for _, w in items) if items else 0.0
    return {
        "top_positions": [{"ticker": t, "weight": w} for t, w in top],
        "hhi": hhi,
    }


def _thesis_drift(db: Session, portfolio_id: int) -> Dict[str, Any]:
    """
    Simple drift: for each ticker in the portfolio, compare the latest two memo snapshots
    and compute delta for KEY_METRICS.
    """
    positions: List[Position] = db.query(Position).filter(Position.portfolio_id == portfolio_id).all()
    tickers: List[str] = []

    # Derive tickers from the memo chain (authoritative) to avoid relying on Position.ticker.
    for p in positions:
        memo = db.query(MemoSnapshot).filter(MemoSnapshot.id == p.memo_snapshot_id).first()
        if memo and isinstance(memo.memorandum, dict):
            t = (memo.memorandum.get("ticker") or "").upper()
            if t:
                tickers.append(t)
    tickers = sorted(set(tickers))

    drift_items: List[Dict[str, Any]] = []

    for t in tickers:
        # Find latest two memos for ticker via snapshot chain
        q = (
            db.query(MemoSnapshot, DataSnapshot)
            .join(EvidenceSnapshot, MemoSnapshot.evidence_snapshot_id == EvidenceSnapshot.id)
            .join(MetricsSnapshot, EvidenceSnapshot.metrics_snapshot_id == MetricsSnapshot.id)
            .join(DataSnapshot, MetricsSnapshot.data_snapshot_id == DataSnapshot.id)
            .filter(DataSnapshot.ticker == t)
            .order_by(MemoSnapshot.generated_at.desc())
            .limit(2)
        )
        rows: List[Tuple[MemoSnapshot, DataSnapshot]] = q.all()
        if len(rows) < 2:
            continue

        (m0, ds0), (m1, ds1) = rows[0], rows[1]  # m0 newer, m1 older
        mm0 = m0.memorandum or {}
        mm1 = m1.memorandum or {}
        map0 = _metric_map(mm0.get("metrics") or [])
        map1 = _metric_map(mm1.get("metrics") or [])

        deltas: Dict[str, Any] = {}
        for name in KEY_METRICS:
            v0 = _metric_value(map0.get(name))
            v1 = _metric_value(map1.get(name))
            if v0 is None or v1 is None:
                continue
            deltas[name] = v0 - v1

        drift_items.append(
            {
                "ticker": t,
                "newer": {
                    "memo_snapshot_id": m0.id,
                    "snapshot_date": ds0.snapshot_date.isoformat(),
                    "generated_at": m0.generated_at.isoformat() if m0.generated_at else None,
                },
                "older": {
                    "memo_snapshot_id": m1.id,
                    "snapshot_date": ds1.snapshot_date.isoformat(),
                    "generated_at": m1.generated_at.isoformat() if m1.generated_at else None,
                },
                "metric_deltas": deltas,
            }
        )

    return {"items": drift_items, "metric_names": KEY_METRICS}


