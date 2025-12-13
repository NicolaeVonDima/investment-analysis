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
)
from app.services.data_fetcher import DataFetcher
from app.services.metric_computer import MetricComputer
from app.services.narrative_generator import NarrativeGenerator
from app.services.pdf_generator import PDFGenerator
from app.services.evidence_builder import EvidenceBuilder
from app.schemas import InvestmentMemorandum, CompanyInfo
from datetime import datetime, date
import json
import os
import traceback
import yfinance as yf
from sqlalchemy.exc import IntegrityError
import time


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

