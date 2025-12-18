"""
SEC fundamentals extraction, change detection, and alerting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    SecArtifact,
    SecArtifactKind,
    SecFundamentalsAlert,
    SecFundamentalsChange,
    SecFundamentalsFact,
    SecFundamentalsSnapshot,
)


@dataclass
class ExtractedFact:
    metric_key: str
    metric_label: str
    value_num: Optional[float]
    value_raw: str
    unit: str
    period: Optional[str]
    context_snippet: Optional[str]
    confidence: float


_METRIC_PATTERNS: Dict[str, Dict[str, Any]] = {
    "revenue": {
        "label": "Revenue",
        "unit": "USD",
        "patterns": [
            r"(total\s+revenue|net\s+revenue|revenues?)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
    "net_income": {
        "label": "Net income",
        "unit": "USD",
        "patterns": [
            r"(net\s+income|net\s+loss)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
    "operating_income": {
        "label": "Operating income",
        "unit": "USD",
        "patterns": [
            r"(operating\s+income|operating\s+loss)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
    "gross_margin_pct": {
        "label": "Gross margin",
        "unit": "PERCENT",
        "patterns": [
            r"(gross\s+margin)\s*(?:of|was|:)?\s*([0-9]{1,3}(?:\.[0-9]+)?)\s*%",
        ],
    },
    "eps_diluted": {
        "label": "Diluted EPS",
        "unit": "USD",
        "patterns": [
            r"(diluted\s+earnings\s+per\s+share|diluted\s+eps)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)",
        ],
    },
    "total_assets": {
        "label": "Total assets",
        "unit": "USD",
        "patterns": [
            r"(total\s+assets)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
    "total_liabilities": {
        "label": "Total liabilities",
        "unit": "USD",
        "patterns": [
            r"(total\s+liabilities)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
    "cash_and_equivalents": {
        "label": "Cash and cash equivalents",
        "unit": "USD",
        "patterns": [
            r"(cash\s+and\s+cash\s+equivalents)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
    "total_debt": {
        "label": "Total debt",
        "unit": "USD",
        "patterns": [
            r"(total\s+debt|long-term\s+debt)\s*(?:were|was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
    "operating_cash_flow": {
        "label": "Operating cash flow",
        "unit": "USD",
        "patterns": [
            r"(net\s+cash\s+provided\s+by\s+operating\s+activities)\s*(?:was|:)?\s*\$?\s*([0-9][0-9,\.]*)\s*(million|billion|thousand)?",
        ],
    },
}

_RISK_PATTERNS: Dict[str, Dict[str, Any]] = {
    "risk_going_concern": {
        "label": "Going concern risk",
        "pattern": r"substantial\s+doubt.*going\s+concern|going\s+concern",
    },
    "risk_material_weakness": {
        "label": "Material weakness",
        "pattern": r"material\s+weakness",
    },
    "risk_restatement": {
        "label": "Restatement",
        "pattern": r"restatement",
    },
    "risk_investigation": {
        "label": "Investigation risk",
        "pattern": r"sec\s+investigation|subpoena|investigation",
    },
}

_DEFAULT_ALERT_RULES: List[Dict[str, Any]] = [
    {
        "id": "revenue_down_10pct",
        "metric_key": "revenue",
        "direction": "down",
        "threshold_pct": -0.10,
        "severity": "high",
        "message": "Revenue down more than 10% vs prior period.",
    },
    {
        "id": "net_income_down_15pct",
        "metric_key": "net_income",
        "direction": "down",
        "threshold_pct": -0.15,
        "severity": "high",
        "message": "Net income down more than 15% vs prior period.",
    },
    {
        "id": "gross_margin_down_200bps",
        "metric_key": "gross_margin_pct",
        "direction": "down",
        "threshold_abs": -2.0,
        "severity": "medium",
        "message": "Gross margin down more than 200 bps.",
    },
    {
        "id": "debt_up_20pct",
        "metric_key": "total_debt",
        "direction": "up",
        "threshold_pct": 0.20,
        "severity": "medium",
        "message": "Total debt up more than 20% vs prior period.",
    },
    {
        "id": "operating_cf_down_20pct",
        "metric_key": "operating_cash_flow",
        "direction": "down",
        "threshold_pct": -0.20,
        "severity": "medium",
        "message": "Operating cash flow down more than 20% vs prior period.",
    },
    {
        "id": "risk_going_concern",
        "metric_key": "risk_going_concern",
        "direction": "present",
        "severity": "high",
        "message": "Going concern risk disclosed.",
    },
    {
        "id": "risk_material_weakness",
        "metric_key": "risk_material_weakness",
        "direction": "present",
        "severity": "high",
        "message": "Material weakness disclosed.",
    },
]


def _load_alert_rules() -> List[Dict[str, Any]]:
    ruleset_dir = os.path.join(os.getcwd(), "rulesets")
    if not os.path.exists(ruleset_dir):
        return _DEFAULT_ALERT_RULES

    versions = [f for f in os.listdir(ruleset_dir) if f.endswith(".json")]
    if not versions:
        return _DEFAULT_ALERT_RULES

    versions.sort(reverse=True)
    path = os.path.join(ruleset_dir, versions[0])
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("sec_alert_rules") or []
        if not rules:
            return _DEFAULT_ALERT_RULES
        return rules
    except Exception:
        return _DEFAULT_ALERT_RULES


def _parse_numeric(value: str) -> Optional[float]:
    if value is None:
        return None
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _apply_scale(value: Optional[float], scale_word: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if not scale_word:
        return value
    scale_map = {
        "thousand": 1_000.0,
        "million": 1_000_000.0,
        "billion": 1_000_000_000.0,
    }
    return value * scale_map.get(scale_word.lower(), 1.0)


def _detect_period(window: str) -> Optional[str]:
    window_lower = window.lower()
    if "three months ended" in window_lower or "quarter ended" in window_lower:
        return "quarter"
    if "six months ended" in window_lower:
        return "six_months"
    if "nine months ended" in window_lower:
        return "nine_months"
    if "twelve months ended" in window_lower or "year ended" in window_lower or "fiscal year" in window_lower:
        return "year"
    return None


def _snippet(text: str, start: int, end: int, radius: int = 120) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip()


def extract_fundamentals_from_text(text: str) -> List[ExtractedFact]:
    facts: List[ExtractedFact] = []
    normalized = text or ""

    for metric_key, spec in _METRIC_PATTERNS.items():
        label = spec["label"]
        unit = spec["unit"]
        for pattern in spec["patterns"]:
            for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                full = match.group(0)
                head = match.group(1).lower() if match.lastindex and match.lastindex >= 1 else ""
                raw_value = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
                scale_word = match.group(3) if match.lastindex and match.lastindex >= 3 else None
                is_loss = "loss" in head

                value = _parse_numeric(raw_value)
                value = _apply_scale(value, scale_word)
                if value is not None and is_loss:
                    value = -abs(value)

                period = _detect_period(normalized[max(0, match.start() - 160): match.end() + 160])
                snippet = _snippet(normalized, match.start(), match.end())
                confidence = 0.65 if scale_word or "$" in full else 0.55

                facts.append(
                    ExtractedFact(
                        metric_key=metric_key,
                        metric_label=label,
                        value_num=value,
                        value_raw=full[:240],
                        unit=unit,
                        period=period,
                        context_snippet=snippet[:320],
                        confidence=confidence,
                    )
                )

    for risk_key, spec in _RISK_PATTERNS.items():
        pattern = spec["pattern"]
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        snippet = _snippet(normalized, match.start(), match.end())
        facts.append(
            ExtractedFact(
                metric_key=risk_key,
                metric_label=spec["label"],
                value_num=1.0,
                value_raw=match.group(0)[:240],
                unit="FLAG",
                period=None,
                context_snippet=snippet[:320],
                confidence=0.7,
            )
        )

    return facts


def _select_best_facts(facts: Iterable[ExtractedFact]) -> List[ExtractedFact]:
    best: Dict[Tuple[str, Optional[str]], ExtractedFact] = {}
    for fact in facts:
        key = (fact.metric_key, fact.period)
        current = best.get(key)
        if not current:
            best[key] = fact
            continue
        if fact.value_num is None:
            continue
        if current.value_num is None or abs(fact.value_num) > abs(current.value_num or 0):
            best[key] = fact
    return list(best.values())


def _read_artifact_text(artifact: SecArtifact) -> str:
    path = artifact.storage_path
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def process_parsed_sec_artifact(db: Session, parsed_artifact_id: int) -> Dict[str, Any]:
    artifact = db.query(SecArtifact).filter(SecArtifact.id == parsed_artifact_id).first()
    if not artifact:
        return {"status": "not_found", "artifact_id": parsed_artifact_id}
    if artifact.artifact_kind != SecArtifactKind.PARSED_TEXT:
        return {"status": "skipped", "artifact_id": parsed_artifact_id, "reason": "not_parsed_text"}

    existing = db.query(SecFundamentalsSnapshot).filter(SecFundamentalsSnapshot.artifact_id == artifact.id).first()
    if existing:
        return {"status": "skipped", "artifact_id": parsed_artifact_id, "snapshot_id": existing.id}

    text = _read_artifact_text(artifact)
    raw_facts = extract_fundamentals_from_text(text)
    facts = _select_best_facts(raw_facts)

    snapshot = SecFundamentalsSnapshot(
        instrument_id=artifact.instrument_id,
        ticker=artifact.ticker,
        cik=artifact.cik,
        artifact_id=artifact.id,
        form_type=artifact.form_type,
        filing_date=artifact.filing_date,
        period_end=artifact.period_end,
        parser_version=artifact.parser_version,
        extracted_at=datetime.utcnow(),
        payload={
            "fact_count": len(facts),
            "metric_keys": sorted({f.metric_key for f in facts}),
        },
        source_metadata={"artifact_id": artifact.id, "storage_path": artifact.storage_path},
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    for fact in facts:
        db.add(
            SecFundamentalsFact(
                snapshot_id=snapshot.id,
                metric_key=fact.metric_key,
                metric_label=fact.metric_label,
                value_num=fact.value_num,
                value_raw=fact.value_raw,
                unit=fact.unit,
                period=fact.period,
                context_snippet=fact.context_snippet,
                confidence=fact.confidence,
            )
        )
    db.commit()

    changes = compute_changes_and_alerts(db, snapshot)
    return {
        "status": "completed",
        "artifact_id": parsed_artifact_id,
        "snapshot_id": snapshot.id,
        "fact_count": len(facts),
        "change_count": changes.get("change_count", 0),
        "alert_count": changes.get("alert_count", 0),
    }


def _latest_prior_snapshot(db: Session, snapshot: SecFundamentalsSnapshot) -> Optional[SecFundamentalsSnapshot]:
    if not snapshot.instrument_id:
        return None
    query = (
        db.query(SecFundamentalsSnapshot)
        .filter(
            SecFundamentalsSnapshot.instrument_id == snapshot.instrument_id,
            SecFundamentalsSnapshot.form_type == snapshot.form_type,
        )
        .order_by(SecFundamentalsSnapshot.period_end.desc(), SecFundamentalsSnapshot.filing_date.desc())
    )
    prior = query.filter(SecFundamentalsSnapshot.id != snapshot.id).first()
    return prior


def _facts_by_key(db: Session, snapshot_id: int) -> Dict[Tuple[str, Optional[str]], SecFundamentalsFact]:
    facts = db.query(SecFundamentalsFact).filter(SecFundamentalsFact.snapshot_id == snapshot_id).all()
    return {(f.metric_key, f.period): f for f in facts}


def _evaluate_alert_rules(
    change: SecFundamentalsChange, rules: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    for rule in rules:
        if rule.get("metric_key") != change.metric_key:
            continue
        direction = rule.get("direction")
        threshold_pct = rule.get("threshold_pct")
        threshold_abs = rule.get("threshold_abs")
        trigger_value = rule.get("trigger_on_value")

        matched = False
        if direction == "present":
            matched = change.curr_value is not None and trigger_value in (None, change.curr_value)
        elif threshold_pct is not None and change.delta_pct is not None:
            if direction == "down" and change.delta_pct <= float(threshold_pct):
                matched = True
            if direction == "up" and change.delta_pct >= float(threshold_pct):
                matched = True
        elif threshold_abs is not None and change.delta is not None:
            if direction == "down" and change.delta <= float(threshold_abs):
                matched = True
            if direction == "up" and change.delta >= float(threshold_abs):
                matched = True

        if matched:
            alerts.append(
                {
                    "alert_type": rule.get("id") or change.metric_key,
                    "severity": rule.get("severity", "medium"),
                    "message": rule.get("message") or f"{change.metric_label} changed materially.",
                    "rule_id": rule.get("id"),
                }
            )
    return alerts


def compute_changes_and_alerts(db: Session, snapshot: SecFundamentalsSnapshot) -> Dict[str, int]:
    existing_changes = (
        db.query(SecFundamentalsChange)
        .filter(SecFundamentalsChange.curr_snapshot_id == snapshot.id)
        .count()
    )
    if existing_changes:
        return {"change_count": existing_changes, "alert_count": 0}

    prior = _latest_prior_snapshot(db, snapshot)
    if not prior:
        return {"change_count": 0, "alert_count": 0}

    current_facts = _facts_by_key(db, snapshot.id)
    prior_facts = _facts_by_key(db, prior.id)
    rules = _load_alert_rules()

    change_count = 0
    alert_count = 0

    for key, curr_fact in current_facts.items():
        prior_fact = prior_facts.get(key)
        if not prior_fact:
            continue

        prev_value = prior_fact.value_num
        curr_value = curr_fact.value_num
        if prev_value is None or curr_value is None:
            continue

        delta = curr_value - prev_value
        delta_pct = None
        if prev_value != 0:
            delta_pct = delta / prev_value

        change = SecFundamentalsChange(
            instrument_id=snapshot.instrument_id,
            ticker=snapshot.ticker,
            metric_key=curr_fact.metric_key,
            metric_label=curr_fact.metric_label,
            prev_value=prev_value,
            curr_value=curr_value,
            delta=delta,
            delta_pct=delta_pct,
            unit=curr_fact.unit,
            period=curr_fact.period,
            prev_snapshot_id=prior.id,
            curr_snapshot_id=snapshot.id,
            detected_at=datetime.utcnow(),
            severity="info",
            context_snippet=curr_fact.context_snippet,
        )
        db.add(change)
        db.commit()
        db.refresh(change)

        alerts = _evaluate_alert_rules(change, rules)
        if alerts:
            severity_rank = {"high": 3, "medium": 2, "low": 1, "info": 0}
            best = max(alerts, key=lambda a: severity_rank.get(a.get("severity", "info"), 0))
            change.severity = best.get("severity", "info")
            change.rule_id = best.get("rule_id")
            db.commit()

        change_count += 1

        for alert in alerts:
            db.add(
                SecFundamentalsAlert(
                    instrument_id=snapshot.instrument_id,
                    ticker=snapshot.ticker,
                    alert_type=alert.get("alert_type"),
                    severity=alert.get("severity", "medium"),
                    status="open",
                    message=alert.get("message"),
                    rule_id=alert.get("rule_id"),
                    change_id=change.id,
                    curr_snapshot_id=snapshot.id,
                    evidence={"context_snippet": curr_fact.context_snippet},
                    triggered_at=datetime.utcnow(),
                )
            )
            alert_count += 1

    db.commit()
    return {"change_count": change_count, "alert_count": alert_count}
