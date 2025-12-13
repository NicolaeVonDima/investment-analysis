"""
Evidence builder service.

Transforms computed metrics into structured "evidence factors" that are:
- rules-based
- traceable back to metric names
- non-predictive (no forecasts)
"""

from __future__ import annotations

from typing import Any, Dict, List


class EvidenceBuilder:
    """
    Build simple evidence factors from computed metrics.

    This is intentionally conservative; it stores structured summaries and flags,
    not investment advice or predictions.
    """

    def build(self, metrics: List[Dict[str, Any]], market_data: Dict[str, Any]) -> Dict[str, Any]:
        metric_by_name = {m.get("name"): m for m in metrics if isinstance(m, dict)}

        factors: List[Dict[str, Any]] = []

        def add_factor(name: str, category: str, metric_refs: List[str], rationale: str, score: float | None = None):
            factors.append(
                {
                    "name": name,
                    "category": category,
                    "metric_refs": metric_refs,
                    "rationale": rationale,
                    "score": score,
                }
            )

        # Valuation flags (purely descriptive)
        pe = _metric_value(metric_by_name.get("pe_ratio"))
        if pe is not None:
            add_factor(
                name="pe_ratio_observation",
                category="valuation",
                metric_refs=["pe_ratio"],
                rationale=f"P/E ratio observed at {pe:.2f} (as computed).",
                score=None,
            )

        ptb = _metric_value(metric_by_name.get("price_to_book"))
        if ptb is not None:
            add_factor(
                name="price_to_book_observation",
                category="valuation",
                metric_refs=["price_to_book"],
                rationale=f"Price-to-book observed at {ptb:.2f} (as computed).",
                score=None,
            )

        div = _metric_value(metric_by_name.get("dividend_yield"))
        if div is not None:
            add_factor(
                name="dividend_yield_observation",
                category="shareholder_returns",
                metric_refs=["dividend_yield"],
                rationale=f"Dividend yield observed at {div:.2f}% (as computed).",
                score=None,
            )

        # Data integrity factor: whether we got a current price
        current_price = market_data.get("current_price")
        add_factor(
            name="data_integrity",
            category="data_quality",
            metric_refs=[],
            rationale="Current price present in snapshot." if current_price is not None else "Current price missing in snapshot.",
            score=1.0 if current_price is not None else 0.0,
        )

        return {
            "version": "1.0.0",
            "factors": factors,
        }


def _metric_value(metric: Dict[str, Any] | None) -> float | None:
    if not metric:
        return None
    value_obj = metric.get("value") or {}
    val = value_obj.get("value")
    try:
        return float(val)
    except Exception:
        return None


