"""
Celery tasks for investment analysis processing.
"""

from app.worker.main import celery_app
from app.database import SessionLocal
from app.models import (
    AnalysisRequest,
    AnalysisStatus,
    DataSnapshot,
    MetricsSnapshot,
    EvidenceSnapshot,
    MemoSnapshot,
    Watchlist,
    WatchlistItem,
    RefreshJob,
    RefreshJobItem,
    RefreshJobStatus,
    RefreshJobItemStatus,
    Instrument,
    ProviderSymbolMap,
    PriceEOD,
    FundamentalsSnapshot,
    ProviderRefreshJob,
    ProviderRefreshJobStatus,
    SecArtifact,
    SecArtifactKind,
    SecParseJob,
    SecParseJobStatus,
)
from app.services.data_fetcher import DataFetcher
from app.services.metric_computer import MetricComputer
from app.services.narrative_generator import NarrativeGenerator
from app.services.pdf_generator import PDFGenerator
from app.services.evidence_builder import EvidenceBuilder
from app.services.alpha_vantage_client import AlphaVantageClient, parse_global_quote_price
from app.schemas import InvestmentMemorandum, CompanyInfo
from datetime import datetime, date
import json
import os
import traceback
import yfinance as yf
from sqlalchemy.exc import IntegrityError
import time
import uuid
from typing import Optional

from app.services.sec_ingestion import ingest_sec_filings_for_ticker, load_config


def _years_ago_safe(d: date, years: int) -> date:
    """
    Subtract whole years while handling leap-day transitions (e.g., Feb 29 -> Feb 28).
    """
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


def _normalize_html_to_text(raw: str) -> str:
    """
    Best-effort HTML/iXBRL to plain text normalization.

    V0: strip tags and collapse whitespace. This is intentionally simple
    and deterministic; richer parsing/sectioning can be added in later versions.
    """
    import re

    # Remove script/style blocks
    no_scripts = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", raw)
    # Strip all tags
    no_tags = re.sub(r"(?s)<[^>]+>", " ", no_scripts)
    # Collapse whitespace
    normalized = re.sub(r"\\s+", " ", no_tags).strip()
    return normalized


@celery_app.task(bind=True, name="process_analysis")
def process_analysis_task(self, request_id: int):
    """
    Main task for processing an investment analysis.
    
    Steps:
    1. Fetch market data
    2. Compute metrics using ruleset
    3. Generate narrative with guardrails
    4. Validate against schema
    5. Generate PDF
    6. Save results
    """
    db = SessionLocal()
    
    try:
        # Get analysis request
        analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == request_id).first()
        if not analysis_request:
            raise ValueError(f"Analysis request {request_id} not found")
        
        # Update status to processing
        analysis_request.status = AnalysisStatus.PROCESSING
        db.commit()
        
        # Determine ruleset version
        ruleset_version = analysis_request.ruleset_version or "latest"
        
        # Step 1: Fetch data (raw snapshot payload)
        self.update_state(state="PROGRESS", meta={"step": "fetching_data", "progress": 10})
        data_fetcher = DataFetcher()
        market_data = data_fetcher.fetch_ticker_data(analysis_request.ticker)
        
        if not market_data:
            raise ValueError(f"Failed to fetch data for ticker {analysis_request.ticker}")

        # Persist (or reuse) global immutable DataSnapshot for today's as-of date.
        # This enables "at most one snapshot per ticker per day" globally.
        as_of_date = datetime.utcnow().date()
        data_snapshot = (
            db.query(DataSnapshot)
            .filter(DataSnapshot.ticker == analysis_request.ticker, DataSnapshot.snapshot_date == as_of_date)
            .order_by(DataSnapshot.fetched_at.desc())
            .first()
        )
        if not data_snapshot:
            data_snapshot = DataSnapshot(
                ticker=analysis_request.ticker,
                snapshot_date=as_of_date,
                provider=market_data.get("provider", "yfinance"),
                provider_version=getattr(yf, "__version__", None),
                payload=market_data,
                source_metadata={
                    "provider": market_data.get("provider", "yfinance"),
                    "provider_version": getattr(yf, "__version__", None),
                    "fetched_at": market_data.get("fetched_at"),
                },
            )
            db.add(data_snapshot)
            try:
                db.commit()
                db.refresh(data_snapshot)
            except IntegrityError:
                db.rollback()
                data_snapshot = (
                    db.query(DataSnapshot)
                    .filter(DataSnapshot.ticker == analysis_request.ticker, DataSnapshot.snapshot_date == as_of_date)
                    .order_by(DataSnapshot.fetched_at.desc())
                    .first()
                )
        
        # Step 2: Compute metrics
        self.update_state(state="PROGRESS", meta={"step": "computing_metrics", "progress": 30})
        metric_computer = MetricComputer(ruleset_version=ruleset_version)
        metrics = metric_computer.compute_all_metrics(market_data, analysis_request.ticker)

        metrics_payload = [m.dict() if hasattr(m, "dict") else m for m in metrics]

        metrics_snapshot = MetricsSnapshot(
            data_snapshot_id=data_snapshot.id,
            ruleset_version=ruleset_version,
            metrics=metrics_payload,
            summary=metric_computer.generate_summary(metrics),
            computation_steps=metric_computer.get_computation_steps(),
        )
        db.add(metrics_snapshot)
        db.commit()
        db.refresh(metrics_snapshot)
        
        # Step 3: Generate narrative
        self.update_state(state="PROGRESS", meta={"step": "generating_narrative", "progress": 60})
        narrative_generator = NarrativeGenerator(ruleset_version=ruleset_version)
        narrative = narrative_generator.generate_narrative(metrics, market_data, analysis_request.ticker)

        # Evidence snapshot (structured factors, traceable to metrics)
        evidence_builder = EvidenceBuilder()
        evidence_payload = evidence_builder.build(metrics_payload, market_data)
        evidence_snapshot = EvidenceSnapshot(metrics_snapshot_id=metrics_snapshot.id, evidence=evidence_payload)
        db.add(evidence_snapshot)
        db.commit()
        db.refresh(evidence_snapshot)
        
        # Step 4: Build memorandum
        self.update_state(state="PROGRESS", meta={"step": "building_memorandum", "progress": 80})
        
        # Create CompanyInfo from market data
        company_info_dict = market_data.get("company_info", {})
        company_info = CompanyInfo(
            ticker=company_info_dict.get("ticker", analysis_request.ticker),
            name=company_info_dict.get("name", analysis_request.ticker),
            sector=company_info_dict.get("sector"),
            industry=company_info_dict.get("industry"),
            exchange=company_info_dict.get("exchange")
        )
        
        memorandum = InvestmentMemorandum(
            version="1.0.0",
            generated_at=datetime.utcnow().isoformat(),
            ticker=analysis_request.ticker,
            ruleset_version=ruleset_version,
            company=company_info,
            analysis_date=datetime.utcnow().date().isoformat(),
            data_period_end=market_data.get("period_end", datetime.utcnow().date().isoformat()),
            metrics=metrics,
            narrative=narrative,
            summary=metric_computer.generate_summary(metrics),
            audit_trail={
                "data_source": "yfinance",
                "data_fetched_at": datetime.utcnow().isoformat(),
                "ruleset_version": ruleset_version,
                "computation_steps": metric_computer.get_computation_steps(),
                "snapshot_ids": {
                    "data_snapshot_id": data_snapshot.id,
                    "metrics_snapshot_id": metrics_snapshot.id,
                    "evidence_snapshot_id": evidence_snapshot.id,
                },
                "provider_version": getattr(yf, "__version__", None),
            }
        )
        
        # Validate schema
        memorandum_dict = memorandum.dict()
        
        # Step 5: Save JSON
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        
        json_path = os.path.join(output_dir, f"memorandum_{analysis_request.ticker}_{request_id}.json")
        with open(json_path, 'w') as f:
            json.dump(memorandum_dict, f, indent=2)
        
        analysis_request.json_output_path = json_path
        
        # Step 6: Generate PDF
        self.update_state(state="PROGRESS", meta={"step": "generating_pdf", "progress": 90})
        pdf_generator = PDFGenerator()
        pdf_path = os.path.join(output_dir, f"memorandum_{analysis_request.ticker}_{request_id}.pdf")
        pdf_generator.generate_pdf(memorandum_dict, pdf_path)
        
        analysis_request.pdf_output_path = pdf_path

        # Persist immutable MemoSnapshot (canonical analysis artifact)
        memo_snapshot = MemoSnapshot(
            evidence_snapshot_id=evidence_snapshot.id,
            analysis_request_id=analysis_request.id,
            prompt_version=getattr(narrative_generator, "prompt_version", None),
            memorandum=memorandum_dict,
            json_output_path=json_path,
            pdf_output_path=pdf_path,
        )
        db.add(memo_snapshot)
        
        # Update status to completed
        analysis_request.status = AnalysisStatus.COMPLETED
        analysis_request.completed_at = datetime.utcnow()
        db.commit()
        
        return {
            "status": "completed",
            "request_id": request_id,
            "json_path": json_path,
            "pdf_path": pdf_path
        }
        
    except Exception as e:
        # Update status to failed
        if 'analysis_request' in locals():
            analysis_request.status = AnalysisStatus.FAILED
            analysis_request.error_message = str(e) + "\n" + traceback.format_exc()
            db.commit()
        
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True, name="sec_ingest_filings_for_ticker")
def sec_ingest_filings_for_ticker_task(self, ticker: str):
    """
    Celery task wrapper for SEC 10-K / 10-Q ingestion for a single ticker.

    This task is idempotent at the artifact/job level:
    - RAW_FILING artifacts are unique per (cik, accession_number, artifact_kind)
    - PARSE_FILING jobs are unique per (artifact_id, parser_version)
    """
    db = SessionLocal()
    try:
        result = ingest_sec_filings_for_ticker(db, ticker)
        # Enqueue parse jobs best-effort
        from app.worker.tasks import sec_parse_filing_task  # local import to avoid circulars

        for job_id in result.get("parse_job_ids", []):
            try:
                sec_parse_filing_task.delay(job_id)
            except Exception:
                # Best-effort; job remains queued for future manual processing
                pass
        return result
    finally:
        db.close()


@celery_app.task(bind=True, name="sec_parse_filing", max_retries=3)
def sec_parse_filing_task(self, parse_job_id: int):
    """
    Process a single PARSE_FILING job:
    - lock job
    - load raw SEC filing from local storage
    - normalize to plain text
    - persist PARSED_TEXT artifact
    - mark job done / failed / deadletter
    """
    db = SessionLocal()
    config = load_config()
    worker_id = f"sec-parser-{uuid.uuid4()}"

    try:
        job: Optional[SecParseJob] = db.query(SecParseJob).filter(SecParseJob.id == parse_job_id).first()
        if not job:
            return {"status": "not_found", "parse_job_id": parse_job_id}

        if job.status in (SecParseJobStatus.DONE, SecParseJobStatus.DEADLETTER):
            return {"status": "skipped", "parse_job_id": parse_job_id, "state": job.status.value}

        # Acquire a simple DB-level lock via locked_by/locked_at
        now = datetime.utcnow()
        if job.locked_by and job.locked_at:
            # Another worker is processing; skip
            return {"status": "locked", "parse_job_id": parse_job_id, "locked_by": job.locked_by}

        job.locked_by = worker_id
        job.locked_at = now
        job.status = SecParseJobStatus.RUNNING
        job.attempt_count = (job.attempt_count or 0) + 1
        job.last_error = None
        db.commit()

        artifact: Optional[SecArtifact] = (
            db.query(SecArtifact).filter(SecArtifact.id == job.artifact_id).first()
        )
        if not artifact:
            job.status = SecParseJobStatus.DEADLETTER
            job.last_error = "Artifact not found"
            db.commit()
            return {"status": "deadletter", "parse_job_id": parse_job_id}

        if artifact.artifact_kind != SecArtifactKind.RAW_FILING:
            job.status = SecParseJobStatus.DEADLETTER
            job.last_error = "Artifact is not RAW_FILING"
            db.commit()
            return {"status": "deadletter", "parse_job_id": parse_job_id}

        # Idempotent check: if a PARSED_TEXT artifact already exists for this raw+parser_version, skip.
        existing_parsed = (
            db.query(SecArtifact)
            .filter(
                SecArtifact.parent_artifact_id == artifact.id,
                SecArtifact.artifact_kind == SecArtifactKind.PARSED_TEXT,
                SecArtifact.parser_version == config.parser_version,
            )
            .first()
        )
        if existing_parsed:
            job.status = SecParseJobStatus.DONE
            db.commit()
            return {
                "status": "completed",
                "parse_job_id": parse_job_id,
                "artifact_id": artifact.id,
                "parsed_artifact_id": existing_parsed.id,
            }

        # Load raw file from local storage
        if artifact.storage_backend != "local_fs":
            raise RuntimeError(f"Unsupported storage_backend for SEC artifact: {artifact.storage_backend}")

        path = artifact.storage_path
        if not os.path.isabs(path):
            # Resolve relative to current working directory
            path = os.path.join(os.getcwd(), path)

        with open(path, "rb") as f:
            raw_bytes = f.read()

        try:
            raw_text = raw_bytes.decode("utf-8", errors="ignore")
        except Exception:
            raw_text = raw_bytes.decode("latin-1", errors="ignore")

        normalized_text = _normalize_html_to_text(raw_text)

        # Persist parsed text as a sibling .txt file
        base_dir = os.path.dirname(artifact.storage_path)
        file_stem = os.path.splitext(os.path.basename(artifact.storage_path))[0]
        parsed_name = f"{file_stem}.txt"
        parsed_path = os.path.join(base_dir, parsed_name)
        os.makedirs(base_dir, exist_ok=True)
        with open(parsed_path, "w", encoding="utf-8") as f:
            f.write(normalized_text)

        parsed_artifact = SecArtifact(
            source=artifact.source,
            ticker=artifact.ticker,
            instrument_id=artifact.instrument_id,
            cik=artifact.cik,
            accession_number=artifact.accession_number,
            form_type=artifact.form_type,
            filing_date=artifact.filing_date,
            period_end=artifact.period_end,
            artifact_kind=SecArtifactKind.PARSED_TEXT,
            parent_artifact_id=artifact.id,
            storage_backend="local_fs",
            storage_path=parsed_path,
            file_name=parsed_name,
            content_hash=None,
            parser_version=config.parser_version,
            parse_warnings=None,
        )
        db.add(parsed_artifact)
        db.commit()
        db.refresh(parsed_artifact)

        job.status = SecParseJobStatus.DONE
        db.commit()

        return {
            "status": "completed",
            "parse_job_id": parse_job_id,
            "artifact_id": artifact.id,
            "parsed_artifact_id": parsed_artifact.id,
        }
    except Exception as e:
        # Update job error state and decide between FAILED vs DEADLETTER
        job = db.query(SecParseJob).filter(SecParseJob.id == parse_job_id).first()
        if job:
            job.last_error = str(e)
            if job.attempt_count >= (job.max_attempts or 3):
                job.status = SecParseJobStatus.DEADLETTER
            else:
                job.status = SecParseJobStatus.FAILED
            db.commit()

        # Use Celery retry for transient failures while respecting max_attempts
        if isinstance(e, RuntimeError) and job and job.status == SecParseJobStatus.FAILED:
            try:
                countdown = 2 ** max(0, job.attempt_count - 1)
                raise self.retry(exc=e, countdown=countdown)
            except self.MaxRetriesExceededError:
                # Mark as deadletter if Celery exhausted retries
                if job:
                    job.status = SecParseJobStatus.DEADLETTER
                    db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="refresh_watchlist_universe")
def refresh_watchlist_universe(self):
    """
    Daily refresh job:
    - Refresh universe = union of tickers across all active watchlists.
    - Guarantees "once per ticker per day" via DB uniqueness on (ticker, snapshot_date).
    - Records an auditable RefreshJob + per-ticker RefreshJobItem statuses.
    """
    db = SessionLocal()
    as_of_date = datetime.utcnow().date()
    started_at = datetime.utcnow()

    try:
        # Create or reuse the day job (idempotent by unique constraint on as_of_date)
        job = db.query(RefreshJob).filter(RefreshJob.as_of_date == as_of_date).first()
        if not job:
            job = RefreshJob(as_of_date=as_of_date, status=RefreshJobStatus.PENDING)
            db.add(job)
            try:
                db.commit()
                db.refresh(job)
            except IntegrityError:
                db.rollback()
                job = db.query(RefreshJob).filter(RefreshJob.as_of_date == as_of_date).first()

        job.status = RefreshJobStatus.RUNNING
        job.started_at = started_at
        db.commit()

        # Universe = union of active watchlist tickers
        rows = (
            db.query(WatchlistItem.ticker)
            .join(Watchlist, WatchlistItem.watchlist_id == Watchlist.id)
            .filter(Watchlist.is_active.is_(True))
            .distinct()
            .all()
        )
        tickers = sorted({(r[0] or "").upper().strip() for r in rows if r and r[0]})

        data_fetcher = DataFetcher()
        max_attempts = int(os.getenv("REFRESH_MAX_ATTEMPTS", "3"))
        base_backoff = float(os.getenv("REFRESH_RETRY_BACKOFF_SECONDS", "1.0"))
        total = len(tickers)
        ok = 0
        failed = 0
        skipped = 0

        for idx, ticker in enumerate(tickers):
            # Progress update (best-effort)
            try:
                self.update_state(
                    state="PROGRESS",
                    meta={"step": "refreshing", "ticker": ticker, "index": idx + 1, "total": total},
                )
            except Exception:
                pass

            item = (
                db.query(RefreshJobItem)
                .filter(RefreshJobItem.refresh_job_id == job.id, RefreshJobItem.ticker == ticker)
                .first()
            )
            if not item:
                item = RefreshJobItem(refresh_job_id=job.id, ticker=ticker, status=RefreshJobItemStatus.PENDING)
                db.add(item)
                try:
                    db.commit()
                    db.refresh(item)
                except IntegrityError:
                    db.rollback()
                    item = (
                        db.query(RefreshJobItem)
                        .filter(RefreshJobItem.refresh_job_id == job.id, RefreshJobItem.ticker == ticker)
                        .first()
                    )

            # If snapshot already exists for today, we mark as skipped (work already done globally).
            existing = (
                db.query(DataSnapshot)
                .filter(DataSnapshot.ticker == ticker, DataSnapshot.snapshot_date == as_of_date)
                .order_by(DataSnapshot.fetched_at.desc())
                .first()
            )
            if existing:
                item.status = RefreshJobItemStatus.SKIPPED
                item.data_snapshot_id = existing.id
                item.completed_at = datetime.utcnow()
                db.commit()
                skipped += 1
                continue

            # Fetch and persist snapshot
            item.status = RefreshJobItemStatus.RUNNING
            item.started_at = datetime.utcnow()
            item.attempts = (item.attempts or 0) + 1
            item.error_message = None
            db.commit()

            try:
                market_data = None
                last_err = None
                for attempt in range(1, max_attempts + 1):
                    market_data = data_fetcher.fetch_ticker_data(ticker)
                    if market_data:
                        break
                    last_err = f"Failed to fetch data for ticker {ticker}"
                    # Exponential backoff between attempts
                    if attempt < max_attempts:
                        time.sleep(base_backoff * (2 ** (attempt - 1)))

                if not market_data:
                    raise ValueError(last_err or f"Failed to fetch data for ticker {ticker}")

                snap = DataSnapshot(
                    ticker=ticker,
                    snapshot_date=as_of_date,
                    provider=market_data.get("provider", "yfinance"),
                    provider_version=getattr(yf, "__version__", None),
                    payload=market_data,
                    source_metadata={
                        "provider": market_data.get("provider", "yfinance"),
                        "provider_version": getattr(yf, "__version__", None),
                        "fetched_at": market_data.get("fetched_at"),
                    },
                )
                db.add(snap)
                try:
                    db.commit()
                    db.refresh(snap)
                except IntegrityError:
                    db.rollback()
                    # Another worker/job inserted first; reuse it.
                    snap = (
                        db.query(DataSnapshot)
                        .filter(DataSnapshot.ticker == ticker, DataSnapshot.snapshot_date == as_of_date)
                        .order_by(DataSnapshot.fetched_at.desc())
                        .first()
                    )

                item.status = RefreshJobItemStatus.COMPLETED
                item.data_snapshot_id = snap.id if snap else None
                item.completed_at = datetime.utcnow()
                db.commit()
                ok += 1

            except Exception as e:
                item.status = RefreshJobItemStatus.FAILED
                item.error_message = str(e)
                item.completed_at = datetime.utcnow()
                db.commit()
                failed += 1

        job.status = RefreshJobStatus.COMPLETED if failed == 0 else RefreshJobStatus.FAILED
        job.completed_at = datetime.utcnow()
        job.stats = {
            "as_of_date": as_of_date.isoformat(),
            "total": total,
            "completed": ok,
            "failed": failed,
            "skipped": skipped,
        }
        db.commit()

        return {"job_id": job.id, **(job.stats or {})}

    except Exception as e:
        # Mark job failed (best-effort)
        try:
            job = db.query(RefreshJob).filter(RefreshJob.as_of_date == as_of_date).first()
            if job:
                job.status = RefreshJobStatus.FAILED
                job.error_message = str(e) + "\n" + traceback.format_exc()
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="refresh_instrument_lite", rate_limit="5/m")
def refresh_instrument_lite(self, instrument_id: int):
    """
    Lite refresh:
    - fetch company overview + latest quote from Alpha Vantage
    - update Instrument identity fields (best-effort)
    - insert today's PriceEOD (idempotent via unique constraint)
    - record ProviderRefreshJob for audit/idempotency
    """
    db = SessionLocal()
    today = datetime.utcnow().date()
    request_key = f"alpha_vantage:lite:{instrument_id}:{today.isoformat()}"

    try:
        inst = db.query(Instrument).filter(Instrument.id == instrument_id).first()
        if not inst:
            raise ValueError("Instrument not found")

        job = db.query(ProviderRefreshJob).filter(ProviderRefreshJob.request_key == request_key).first()
        if not job:
            job = ProviderRefreshJob(
                provider="alpha_vantage",
                job_type="lite",
                instrument_id=inst.id,
                as_of_date=today,
                request_key=request_key,
                status=ProviderRefreshJobStatus.PENDING,
            )
            db.add(job)
            try:
                db.commit()
                db.refresh(job)
            except IntegrityError:
                db.rollback()
                job = db.query(ProviderRefreshJob).filter(ProviderRefreshJob.request_key == request_key).first()

        if job and job.status == ProviderRefreshJobStatus.COMPLETED:
            return {"status": "skipped", "request_key": request_key}

        job.status = ProviderRefreshJobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.attempts = (job.attempts or 0) + 1
        job.error_message = None
        db.commit()

        # Resolve provider symbol (prefer primary mapping)
        mapping = (
            db.query(ProviderSymbolMap)
            .filter(
                ProviderSymbolMap.provider == "alpha_vantage",
                ProviderSymbolMap.instrument_id == inst.id,
            )
            .order_by(ProviderSymbolMap.is_primary.desc(), ProviderSymbolMap.id.asc())
            .first()
        )
        symbol = mapping.provider_symbol if mapping else inst.canonical_symbol

        client = AlphaVantageClient()
        overview = client.get_company_overview(symbol)
        quote = client.get_global_quote(symbol)
        parsed = parse_global_quote_price(quote)

        # Update identity (best-effort, do not invent)
        ov = overview.get("payload") if isinstance(overview, dict) else None
        if isinstance(ov, dict):
            inst.name = ov.get("Name") or inst.name
            inst.exchange = ov.get("Exchange") or inst.exchange
            inst.sector = ov.get("Sector") or inst.sector
            inst.industry = ov.get("Industry") or inst.industry
            inst.currency = ov.get("Currency") or inst.currency
            db.commit()

        price = parsed.get("price")
        as_of = parsed.get("as_of_date") or today

        # Insert or reuse today's price
        existing = (
            db.query(PriceEOD)
            .filter(PriceEOD.instrument_id == inst.id, PriceEOD.as_of_date == as_of)
            .order_by(PriceEOD.fetched_at.desc())
            .first()
        )
        if not existing:
            row = PriceEOD(
                instrument_id=inst.id,
                as_of_date=as_of,
                close=price,
                adjusted_close=price,
                volume=None,
                provider="alpha_vantage",
                source_metadata={
                    "overview": {"endpoint": "OVERVIEW", "fetched_at": overview.get("fetched_at")},
                    "quote": {"endpoint": "GLOBAL_QUOTE", "fetched_at": quote.get("fetched_at")},
                },
            )
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()

        job.status = ProviderRefreshJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.stats = {"symbol": symbol, "as_of_date": as_of.isoformat(), "price": price}
        db.commit()
        return {"status": "completed", "request_key": request_key}

    except Exception as e:
        try:
            job = db.query(ProviderRefreshJob).filter(ProviderRefreshJob.request_key == request_key).first()
            if job:
                job.status = ProviderRefreshJobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="backfill_instrument_data", rate_limit="5/m")
def backfill_instrument_data(self, instrument_id: int):
    """
    Heavy backfill:
    - fetch TIME_SERIES_DAILY (full) and store >=5y daily rows in price_eod
    - fetch fundamentals statements and store immutable snapshots
    - idempotent via uniqueness constraints + ProviderRefreshJob request_key
    """
    db = SessionLocal()
    request_key = f"alpha_vantage:backfill:{instrument_id}:5y"
    started = datetime.utcnow()

    try:
        inst = db.query(Instrument).filter(Instrument.id == instrument_id).first()
        if not inst:
            raise ValueError("Instrument not found")

        job = db.query(ProviderRefreshJob).filter(ProviderRefreshJob.request_key == request_key).first()
        if not job:
            job = ProviderRefreshJob(
                provider="alpha_vantage",
                job_type="backfill",
                instrument_id=inst.id,
                as_of_date=datetime.utcnow().date(),
                request_key=request_key,
                status=ProviderRefreshJobStatus.PENDING,
            )
            db.add(job)
            try:
                db.commit()
                db.refresh(job)
            except IntegrityError:
                db.rollback()
                job = db.query(ProviderRefreshJob).filter(ProviderRefreshJob.request_key == request_key).first()

        if job and job.status == ProviderRefreshJobStatus.COMPLETED:
            return {"status": "skipped", "request_key": request_key}

        job.status = ProviderRefreshJobStatus.RUNNING
        job.started_at = started
        job.attempts = (job.attempts or 0) + 1
        job.error_message = None
        db.commit()

        mapping = (
            db.query(ProviderSymbolMap)
            .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.instrument_id == inst.id)
            .order_by(ProviderSymbolMap.is_primary.desc(), ProviderSymbolMap.id.asc())
            .first()
        )
        symbol = mapping.provider_symbol if mapping else inst.canonical_symbol

        client = AlphaVantageClient()

        # Prices (TIME_SERIES_DAILY is broadly available; adjusted endpoints may be premium)
        daily = client.get_time_series_daily(symbol)
        payload = daily.get("payload") if isinstance(daily, dict) else None
        ts = payload.get("Time Series (Daily)") if isinstance(payload, dict) else None
        if not isinstance(ts, dict):
            raise ValueError("Unexpected TIME_SERIES_DAILY payload")

        today = datetime.utcnow().date()
        cutoff = _years_ago_safe(today, 5)
        inserted = 0
        skipped = 0

        for d_str, row in ts.items():
            try:
                d = date.fromisoformat(d_str)
            except Exception:
                continue
            if d < cutoff:
                continue
            if not isinstance(row, dict):
                continue
            try:
                close = float(row.get("4. close")) if row.get("4. close") else None
                adj = None
                vol = float(row.get("5. volume")) if row.get("5. volume") else None
            except Exception:
                close, adj, vol = None, None, None

            exists = db.query(PriceEOD).filter(PriceEOD.instrument_id == inst.id, PriceEOD.as_of_date == d).first()
            if exists:
                skipped += 1
                continue
            db.add(
                PriceEOD(
                    instrument_id=inst.id,
                    as_of_date=d,
                    close=close,
                    adjusted_close=adj,
                    volume=vol,
                    provider="alpha_vantage",
                    source_metadata={"endpoint": "TIME_SERIES_DAILY", "fetched_at": daily.get("fetched_at")},
                )
            )
            try:
                db.commit()
                inserted += 1
            except IntegrityError:
                db.rollback()
                skipped += 1

        # Fundamentals snapshots (annual + quarterly)
        def upsert_fund(statement_type: str, freq: str, period_end: date, payload_obj: dict, meta: dict):
            existing = (
                db.query(FundamentalsSnapshot)
                .filter(
                    FundamentalsSnapshot.instrument_id == inst.id,
                    FundamentalsSnapshot.statement_type == statement_type,
                    FundamentalsSnapshot.frequency == freq,
                    FundamentalsSnapshot.period_end == period_end,
                )
                .first()
            )
            if existing:
                return False
            db.add(
                FundamentalsSnapshot(
                    instrument_id=inst.id,
                    statement_type=statement_type,
                    frequency=freq,
                    period_end=period_end,
                    provider="alpha_vantage",
                    payload=payload_obj,
                    source_metadata=meta,
                )
            )
            try:
                db.commit()
                return True
            except IntegrityError:
                db.rollback()
                return False

        # Overview
        overview = client.get_company_overview(symbol)
        ovp = overview.get("payload") if isinstance(overview, dict) else None
        if isinstance(ovp, dict) and ovp.get("Symbol"):
            # Use "LatestQuarter" as a reasonable period_end anchor when present
            latest_q = ovp.get("LatestQuarter")
            try:
                period_end = date.fromisoformat(latest_q) if latest_q else today
            except Exception:
                period_end = today
            upsert_fund("overview", "annual", period_end, ovp, {"endpoint": "OVERVIEW", "fetched_at": overview.get("fetched_at")})

            inst.name = ovp.get("Name") or inst.name
            inst.exchange = ovp.get("Exchange") or inst.exchange
            inst.sector = ovp.get("Sector") or inst.sector
            inst.industry = ovp.get("Industry") or inst.industry
            inst.currency = ovp.get("Currency") or inst.currency
            db.commit()

        # Statements
        income = client.get_income_statement(symbol)
        bal = client.get_balance_sheet(symbol)
        cash = client.get_cash_flow(symbol)

        def store_statement(stmt: dict, statement_type: str):
            p = stmt.get("payload") if isinstance(stmt, dict) else None
            if not isinstance(p, dict):
                return 0
            count = 0
            for freq_key, freq in [("annualReports", "annual"), ("quarterlyReports", "quarterly")]:
                rows = p.get(freq_key)
                if not isinstance(rows, list):
                    continue
                for r in rows:
                    if not isinstance(r, dict):
                        continue
                    try:
                        pe = date.fromisoformat(r.get("fiscalDateEnding")) if r.get("fiscalDateEnding") else None
                    except Exception:
                        pe = None
                    if not pe:
                        continue
                    if upsert_fund(statement_type, freq, pe, r, {"endpoint": stmt.get("endpoint"), "fetched_at": stmt.get("fetched_at")}):
                        count += 1
            return count

        f_income = store_statement(income, "income_statement")
        f_bal = store_statement(bal, "balance_sheet")
        f_cash = store_statement(cash, "cash_flow")

        job.status = ProviderRefreshJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.stats = {
            "symbol": symbol,
            "prices_inserted": inserted,
            "prices_skipped": skipped,
            "fundamentals_inserted": f_income + f_bal + f_cash,
        }
        db.commit()
        return {"status": "completed", "request_key": request_key, **(job.stats or {})}

    except Exception as e:
        try:
            job = db.query(ProviderRefreshJob).filter(ProviderRefreshJob.request_key == request_key).first()
            if job:
                job.status = ProviderRefreshJobStatus.FAILED
                job.error_message = str(e) + "\n" + traceback.format_exc()
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
