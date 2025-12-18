"""
SEC 10-K / 10-Q ingestion and parse orchestration (V0).

Implements the functional spec from:
SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf

Responsibilities:
- CIK resolution for a ticker
- Filings discovery and deterministic selection
- Download and register RAW_FILING artifacts on local filesystem
- Create PARSE_FILING jobs for new/changed artifacts
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import (
    Instrument,
    SecArtifact,
    SecArtifactKind,
    SecParseJob,
    SecParseJobStatus,
)
from app.services.sec_edgar_client import SecEdgarClient, SecEdgarError


@dataclass
class SecIngestionConfig:
    enabled: bool
    lookback_10k: int
    lookback_10q: int
    include_amendments: bool
    storage_base_path: str
    parser_version: str
    parse_max_attempts: int


def load_config() -> SecIngestionConfig:
    enabled = os.getenv("SEC_INTEGRATION_ENABLED", "1") not in ("0", "false", "False")
    lookback_10k = int(os.getenv("SEC_10K_LOOKBACK", "2") or "2")
    lookback_10q = int(os.getenv("SEC_10Q_LOOKBACK", "8") or "8")
    include_amendments = os.getenv("SEC_INCLUDE_AMENDMENTS", "0") in ("1", "true", "True")
    storage_base_path = os.getenv("SEC_STORAGE_BASE_PATH", "./sec_filings").rstrip("/")
    parser_version = os.getenv("SEC_PARSER_VERSION", "v0")
    parse_max_attempts = int(os.getenv("SEC_PARSE_MAX_ATTEMPTS", "3") or "3")
    return SecIngestionConfig(
        enabled=enabled,
        lookback_10k=lookback_10k,
        lookback_10q=lookback_10q,
        include_amendments=include_amendments,
        storage_base_path=storage_base_path,
        parser_version=parser_version,
        parse_max_attempts=parse_max_attempts,
    )


def _ensure_instrument_with_cik(db: Session, ticker: str, cik: str) -> Instrument:
    """
    Attach resolved CIK to the canonical Instrument.

    Creates the instrument when missing.
    """
    sym = ticker.upper().strip()
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == sym).first()
    if not inst:
        inst = Instrument(canonical_symbol=sym, cik=cik)
        db.add(inst)
        db.commit()
        db.refresh(inst)
        return inst

    if inst.cik != cik:
        inst.cik = cik
        db.commit()
    return inst


def resolve_cik_for_ticker(db: Session, ticker: str, client: Optional[SecEdgarClient] = None) -> str:
    """
    Resolve CIK for a ticker, reusing Instrument.cik when present.

    Raises SecEdgarError when resolution fails.
    """
    sym = ticker.upper().strip()
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == sym).first()
    if inst and inst.cik:
        return inst.cik

    client = client or SecEdgarClient()
    cik = client.resolve_cik(sym)
    if not cik:
        raise SecEdgarError(f"Unable to resolve CIK for ticker {sym}")

    _ensure_instrument_with_cik(db, sym, cik)
    return cik


def _parse_date_safe(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _eligible_form(form: str, include_amendments: bool) -> bool:
    f = (form or "").upper().strip()
    base = {"10-K", "10-Q"}
    if f in base:
        return True
    if include_amendments and f in {"10-K/A", "10-Q/A"}:
        return True
    return False


def select_filings(
    submissions: Dict[str, Any],
    lookback_10k: int,
    lookback_10q: int,
    include_amendments: bool,
) -> List[Dict[str, Any]]:
    """
    Deterministically select the most recent N 10-K and M 10-Q filings.

    Returns a list of dicts with:
    - form
    - filing_date
    - accession_number
    - primary_document
    - report_date (optional)
    """
    filings_recent = (submissions.get("filings") or {}).get("recent") or {}
    forms = filings_recent.get("form") or []
    filing_dates = filings_recent.get("filingDate") or []
    accessions = filings_recent.get("accessionNumber") or []
    primary_docs = filings_recent.get("primaryDocument") or []
    report_dates = filings_recent.get("reportDate") or []

    n = min(len(forms), len(filing_dates), len(accessions), len(primary_docs))

    rows: List[Dict[str, Any]] = []
    for i in range(n):
        form = forms[i]
        if not _eligible_form(form, include_amendments):
            continue
        filing_date = _parse_date_safe(filing_dates[i])
        if not filing_date:
            continue
        rows.append(
            {
                "form": form,
                "filing_date": filing_date,
                "accession_number": accessions[i],
                "primary_document": primary_docs[i],
                "report_date": _parse_date_safe(report_dates[i]) if i < len(report_dates) else None,
            }
        )

    # Sort by filing_date desc, then accession_number desc for determinism
    rows.sort(key=lambda r: (r["filing_date"], r["accession_number"]), reverse=True)

    ks: List[Dict[str, Any]] = []
    qs: List[Dict[str, Any]] = []
    for r in rows:
        form = (r["form"] or "").upper().strip()
        if form.startswith("10-K"):
            if len(ks) < lookback_10k:
                ks.append(r)
        elif form.startswith("10-Q"):
            if len(qs) < lookback_10q:
                qs.append(r)

    # Preserve global ordering by filing_date desc across combined list
    combined = ks + qs
    combined.sort(key=lambda r: (r["filing_date"], r["accession_number"]), reverse=True)
    return combined


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _artifact_storage_path(config: SecIngestionConfig, cik: str, accession_number: str, file_name: str) -> str:
    base = config.storage_base_path
    acc_no_dashed = accession_number.replace("/", "_")
    return os.path.join(base, cik, acc_no_dashed, file_name)


def register_raw_artifact(
    db: Session,
    config: SecIngestionConfig,
    instrument: Optional[Instrument],
    cik: str,
    ticker: Optional[str],
    filing: Dict[str, Any],
    content_bytes: bytes,
    content_hash: str,
) -> Tuple[SecArtifact, bool]:
    """
    Upsert RAW_FILING artifact for a given filing.

    Returns (artifact, created_bool).
    """
    accession_number = filing["accession_number"]
    form_type = filing["form"]
    filing_date: date = filing["filing_date"]
    period_end: Optional[date] = filing.get("report_date")
    primary_document = filing["primary_document"]

    storage_path = _artifact_storage_path(config, cik, accession_number, primary_document)
    _ensure_dir(os.path.dirname(storage_path))
    with open(storage_path, "wb") as f:
        f.write(content_bytes)

    # Try to find existing RAW_FILING artifact
    existing = (
        db.query(SecArtifact)
        .filter(
            SecArtifact.cik == cik,
            SecArtifact.accession_number == accession_number,
            SecArtifact.artifact_kind == SecArtifactKind.RAW_FILING,
        )
        .first()
    )
    if existing:
        # If content hash changed, update pointer + hash.
        # Also refresh storage path if it changed (e.g., base path updated).
        if existing.content_hash != content_hash or existing.storage_path != storage_path:
            existing.storage_backend = "local_fs"
            existing.storage_path = storage_path
            existing.file_name = primary_document
            existing.content_hash = content_hash
            existing.filing_date = filing_date
            existing.period_end = period_end
            existing.form_type = form_type
            existing.ticker = ticker
            existing.instrument_id = instrument.id if instrument else None
            db.commit()
            return existing, False
        return existing, False

    art = SecArtifact(
        source="SEC_EDGAR",
        ticker=ticker,
        instrument_id=instrument.id if instrument else None,
        cik=cik,
        accession_number=accession_number,
        form_type=form_type,
        filing_date=filing_date,
        period_end=period_end,
        artifact_kind=SecArtifactKind.RAW_FILING,
        storage_backend="local_fs",
        storage_path=storage_path,
        file_name=primary_document,
        content_hash=content_hash,
    )
    db.add(art)
    try:
        db.commit()
        db.refresh(art)
    except IntegrityError:
        db.rollback()
        art = (
            db.query(SecArtifact)
            .filter(
                SecArtifact.cik == cik,
                SecArtifact.accession_number == accession_number,
                SecArtifact.artifact_kind == SecArtifactKind.RAW_FILING,
            )
            .first()
        )
    return art, True


def create_parse_job_if_needed(
    db: Session,
    config: SecIngestionConfig,
    artifact: SecArtifact,
) -> Optional[SecParseJob]:
    """
    Create a PARSE_FILING job when none exists for (artifact_id, parser_version).
    """
    if artifact.artifact_kind != SecArtifactKind.RAW_FILING:
        return None

    parser_version = config.parser_version
    idem_key = f"parse:{artifact.id}:{parser_version}"
    existing = db.query(SecParseJob).filter(SecParseJob.idempotency_key == idem_key).first()
    if existing:
        return None

    job = SecParseJob(
        job_type="PARSE_FILING",
        artifact_id=artifact.id,
        status=SecParseJobStatus.QUEUED,
        attempt_count=0,
        max_attempts=config.parse_max_attempts,
        idempotency_key=idem_key,
    )
    db.add(job)
    try:
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        job = db.query(SecParseJob).filter(SecParseJob.idempotency_key == idem_key).first()
    return job


def ingest_sec_filings_for_ticker(
    db: Session,
    ticker: str,
    client: Optional[SecEdgarClient] = None,
) -> Dict[str, Any]:
    """
    Main orchestration for SEC ingestion for a given ticker.

    Steps:
    - Resolve CIK
    - Fetch submissions index
    - Deterministically select most recent N 10-K and M 10-Q
    - Download and register RAW_FILING artifacts
    - Create PARSE_FILING jobs for new artifacts
    """
    config = load_config()
    if not config.enabled:
        raise SecEdgarError("SEC integration is disabled via SEC_INTEGRATION_ENABLED")

    client = client or SecEdgarClient()
    sym = ticker.upper().strip()

    cik = resolve_cik_for_ticker(db, sym, client=client)
    submissions = client.get_company_submissions(cik)

    selected = select_filings(
        submissions,
        lookback_10k=config.lookback_10k,
        lookback_10q=config.lookback_10q,
        include_amendments=config.include_amendments,
    )

    inst = db.query(Instrument).filter(Instrument.canonical_symbol == sym).first()
    if not inst:
        inst = _ensure_instrument_with_cik(db, sym, cik)

    artifacts: List[int] = []
    jobs: List[int] = []
    created_raw = 0
    created_jobs = 0

    for filing in selected:
        content_bytes, _, content_hash = client.download_primary_document(
            cik_padded=cik,
            accession_number=filing["accession_number"],
            primary_document=filing["primary_document"],
        )
        art, is_new = register_raw_artifact(
            db=db,
            config=config,
            instrument=inst,
            cik=cik,
            ticker=sym,
            filing=filing,
            content_bytes=content_bytes,
            content_hash=content_hash,
        )
        artifacts.append(art.id)
        if is_new:
            created_raw += 1
        job = create_parse_job_if_needed(db, config, art)
        if job:
            jobs.append(job.id)
            created_jobs += 1

    return {
        "ticker": sym,
        "cik": cik,
        "selected_count": len(selected),
        "artifact_ids": artifacts,
        "parse_job_ids": jobs,
        "created_raw_count": created_raw,
        "created_parse_job_count": created_jobs,
        "run_at": datetime.utcnow().isoformat(),
    }

