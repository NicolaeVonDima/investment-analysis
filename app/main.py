"""
Main FastAPI application for investment analysis platform.
Handles user input, orchestration, and document delivery.
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import os
from datetime import datetime, timedelta
from datetime import date as date_type
import zlib
import time
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import (
    AnalysisRequest,
    AnalysisStatus,
    DataSnapshot,
    MemoSnapshot,
    EvidenceSnapshot,
    MetricsSnapshot,
    Portfolio,
    Position,
    PortfolioAnalyticsSnapshot,
    Watchlist,
    WatchlistItem,
    RefreshJob,
    Instrument,
    ProviderSymbolMap,
    ProviderSymbolSearchCache,
    PriceEOD,
    InstrumentRefresh,
    InstrumentDatasetRefresh,
    InvestmentThesis,
    SecArtifact,
    SecArtifactKind,
    SecParseJob,
    SecParseJobStatus,
    SecFundamentalsSnapshot,
    SecFundamentalsFact,
    SecFundamentalsChange,
    SecFundamentalsAlert,
)
from app.worker.tasks import process_analysis_task
from app.api_schemas import (
    CreatePortfolioRequest,
    PortfolioResponse,
    AddPositionRequest,
    PositionResponse,
    DataSnapshotResponse,
    MemoSnapshotResponse,
    PortfolioDashboardResponse,
    CreateWatchlistRequest,
    WatchlistResponse,
    AddWatchlistItemRequest,
    WatchlistItemResponse,
    WatchlistStatusResponse,
    RefreshStatusResponse,
    ResolveInstrumentRequest,
    InstrumentResponse,
    ResolveInstrumentSuccessResponse,
    ResolveInstrumentErrorResponse,
    LiteSnapshotResponse,
    BackfillEnqueueResponse,
    BrowseLiteResponse,
    CreateInvestmentThesisRequest,
    InvestmentThesisResponse,
    PriceSeriesResponse,
    PricePoint,
    OverviewResponse,
    OverviewDatasetStatus,
    OverviewFcfPoint,
    OverviewKpiPoint,
    FundamentalsSeriesResponse,
    FundamentalsSeriesPoint,
    CreateInvestmentThesisRequest,
    InvestmentThesisResponse,
    SecIngestResponse,
    SecFilingListResponse,
    SecFilingSummary,
    SecFundamentalsSummaryResponse,
    SecFundamentalsSnapshotSummary,
    SecFundamentalsFactSummary,
    SecFundamentalsChangeSummary,
    SecFundamentalsAlertSummary,
    SecFundamentalsAlertsResponse,
    SecFundamentalsPerspectiveResponse,
    SecFundamentalsPerspectivesResponse,
)
from app.services.portfolio_analytics import recompute_portfolio_dashboard
from app.services.browse_lite import is_fresh, parse_daily_adjusted_latest, parse_time_series_daily_closes
from app.services.overview import (
    compute_fcf_series,
    compute_kpis,
    load_fundamentals_snapshots,
    refresh_fundamentals_bundle,
)
from app.services.fundamentals_series import ALLOWED_SERIES, compute_fundamentals_series
from app.services.ticker_resolution import (
    SYMBOL_SEARCH_TTL,
    choose_best_match,
    normalize_query,
    parse_symbol_search_matches,
    valid_ticker_format,
)
from app.services.sec_ingestion import ingest_sec_filings_for_ticker, resolve_cik_for_ticker

logger = logging.getLogger("app.ticker_resolution")

app = FastAPI(
    title="Investment Analysis Platform",
    description="Rules-based investment memorandum generator",
    version="1.0.0"
)

# CORS (frontend dev server runs on a different origin)
# For local development, it is safe and much simpler to allow all origins.
# If you need to lock this down later, set CORS_ALLOW_ORIGINS explicitly.
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS")
if _cors_origins_env:
    if _cors_origins_env.strip() == "*":
        _cors_origins = ["*"]
    else:
        _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
else:
    # Default to permissive "*" in dev to avoid confusing silent CORS issues.
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TickerRequest(BaseModel):
    """Request model for stock ticker analysis."""
    ticker: str = Field(..., description="Stock ticker symbol", min_length=1, max_length=10)
    ruleset_version: Optional[str] = Field(None, description="Version of ruleset to use (defaults to latest)")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    # Seed initial instruments (best-effort)
    gen = None
    try:
        gen = get_db()
        db = next(gen)
        _seed_instruments(db)
    except Exception:
        pass
    finally:
        # Ensure `get_db()` generator finalizer runs and session is closed.
        if gen is not None:
            try:
                gen.close()
            except Exception:
                pass


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "investment-analysis-platform",
        "version": "1.0.0"
    }


def _get_user_id(x_user_id: Optional[str]) -> str:
    """Simple user identity shim (until proper auth is added)."""
    uid = (x_user_id or "").strip()
    return uid or "demo"


def _watchlist_limits():
    max_watchlists = int(os.getenv("MAX_WATCHLISTS_PER_USER", "10"))
    max_tickers = os.getenv("MAX_TICKERS_PER_WATCHLIST")
    max_tickers_int = int(max_tickers) if max_tickers and max_tickers.strip() else None
    return max_watchlists, max_tickers_int


def _get_or_create_default_watchlist(db, user_id: str) -> Watchlist:
    wl = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user_id, Watchlist.name == "Default")
        .order_by(Watchlist.id.asc())
        .first()
    )
    if wl:
        return wl
    wl = Watchlist(user_id=user_id, name="Default", is_active=True)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


def _seed_instruments(db):
    """
    MVP seed per provider spec:
    - ADBE
    - GOOGL (alias GOOG)
    """

    def ensure(symbol: str, aliases: list[str]):
        sym = symbol.upper().strip()
        inst = db.query(Instrument).filter(Instrument.canonical_symbol == sym).first()
        if not inst:
            inst = Instrument(canonical_symbol=sym)
            db.add(inst)
            db.commit()
            db.refresh(inst)

        for a in [sym, *aliases]:
            ps = a.upper().strip()
            existing = (
                db.query(ProviderSymbolMap)
                .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.provider_symbol == ps)
                .first()
            )
            if not existing:
                db.add(
                    ProviderSymbolMap(
                        provider="alpha_vantage",
                        provider_symbol=ps,
                        instrument_id=inst.id,
                        is_primary=(ps == sym),
                    )
                )
        db.commit()

    ensure("ADBE", [])
    ensure("GOOGL", ["GOOG"])


@app.post("/api/analyze", status_code=202)
async def analyze_ticker(request: TickerRequest, db: Session = Depends(get_db)):
    """
    Submit a stock ticker for analysis.
    Returns a job ID that can be used to check status and retrieve results.
    """
    ticker = request.ticker.upper().strip()
    
    # Validate ticker format (basic validation)
    if not ticker.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")
    
    # Create analysis request record
    analysis_request = AnalysisRequest(
        ticker=ticker,
        ruleset_version=request.ruleset_version,
        status=AnalysisStatus.PENDING,
        created_at=datetime.utcnow()
    )
    db.add(analysis_request)
    db.commit()
    db.refresh(analysis_request)
    
    # Queue background task
    process_analysis_task.delay(analysis_request.id)
    
    return {
        "job_id": analysis_request.id,
        "ticker": ticker,
        "status": "pending",
        "message": "Analysis queued for processing"
    }


@app.get("/api/status/{job_id}")
async def get_status(job_id: int, db: Session = Depends(get_db)):
    """Get the status of an analysis job."""
    analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == job_id).first()
    
    if not analysis_request:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": analysis_request.id,
        "ticker": analysis_request.ticker,
        "status": analysis_request.status.value,
        "created_at": analysis_request.created_at.isoformat(),
        "completed_at": analysis_request.completed_at.isoformat() if analysis_request.completed_at else None,
        "error": analysis_request.error_message
    }


@app.get("/api/result/{job_id}/json")
async def get_json_result(job_id: int, db: Session = Depends(get_db)):
    """Retrieve the JSON result of a completed analysis."""
    analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == job_id).first()
    
    if not analysis_request:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if analysis_request.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not completed. Current status: {analysis_request.status.value}"
        )
    
    if not analysis_request.json_output_path:
        raise HTTPException(status_code=404, detail="JSON result not found")
    
    import json
    with open(analysis_request.json_output_path, 'r') as f:
        result = json.load(f)
    
    return JSONResponse(content=result)


@app.get("/api/result/{job_id}/pdf")
async def get_pdf_result(job_id: int, db: Session = Depends(get_db)):
    """Retrieve the PDF result of a completed analysis."""
    analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == job_id).first()
    
    if not analysis_request:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if analysis_request.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not completed. Current status: {analysis_request.status.value}"
        )
    
    if not analysis_request.pdf_output_path:
        raise HTTPException(status_code=404, detail="PDF result not found")
    
    if not os.path.exists(analysis_request.pdf_output_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    return FileResponse(
        analysis_request.pdf_output_path,
        media_type="application/pdf",
        filename=f"investment_memorandum_{analysis_request.ticker}_{job_id}.pdf"
    )


@app.get("/api/jobs")
async def list_jobs(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """List recent analysis jobs."""
    jobs = db.query(AnalysisRequest).order_by(AnalysisRequest.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "jobs": [
            {
                "job_id": job.id,
                "ticker": job.ticker,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
            for job in jobs
        ],
        "limit": limit,
        "offset": offset
    }


# ---------------------------------------------------------------------------
# Snapshot browsing endpoints (immutable artifacts)
# ---------------------------------------------------------------------------


@app.get("/api/snapshots/data/{ticker}")
async def list_data_snapshots(ticker: str, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """List data snapshots for a ticker (most recent first)."""
    t = ticker.upper().strip()
    snaps = (
        db.query(DataSnapshot)
        .filter(DataSnapshot.ticker == t)
        .order_by(DataSnapshot.fetched_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "ticker": t,
        "snapshots": [
            DataSnapshotResponse(
                id=s.id,
                ticker=s.ticker,
                snapshot_date=s.snapshot_date,
                provider=s.provider,
                provider_version=s.provider_version,
                fetched_at=s.fetched_at.isoformat() if s.fetched_at else None,
            ).model_dump()
            for s in snaps
        ],
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/snapshots/memos/{ticker}")
async def list_memo_snapshots(ticker: str, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    """List memo snapshots (analysis artifacts) for a ticker (most recent first)."""
    t = ticker.upper().strip()

    rows = (
        db.query(MemoSnapshot, DataSnapshot, MetricsSnapshot)
        .join(EvidenceSnapshot, MemoSnapshot.evidence_snapshot_id == EvidenceSnapshot.id)
        .join(MetricsSnapshot, EvidenceSnapshot.metrics_snapshot_id == MetricsSnapshot.id)
        .join(DataSnapshot, MetricsSnapshot.data_snapshot_id == DataSnapshot.id)
        .filter(DataSnapshot.ticker == t)
        .order_by(MemoSnapshot.generated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "ticker": t,
        "memos": [
            MemoSnapshotResponse(
                id=m.id,
                ticker=t,
                snapshot_date=ds.snapshot_date,
                ruleset_version=ms.ruleset_version,
                prompt_version=m.prompt_version,
                generated_at=m.generated_at.isoformat() if m.generated_at else None,
            ).model_dump()
            for (m, ds, ms) in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/memo/{memo_id}/json")
async def get_memo_json(memo_id: int, db: Session = Depends(get_db)):
    """Retrieve stored memo snapshot JSON (immutable analysis artifact)."""
    memo = db.query(MemoSnapshot).filter(MemoSnapshot.id == memo_id).first()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo snapshot not found")
    return JSONResponse(content=memo.memorandum)


@app.get("/api/memo/{memo_id}/pdf")
async def get_memo_pdf(memo_id: int, db: Session = Depends(get_db)):
    """Retrieve stored memo snapshot PDF by memo snapshot id."""
    memo = db.query(MemoSnapshot).filter(MemoSnapshot.id == memo_id).first()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo snapshot not found")
    if not memo.pdf_output_path:
        raise HTTPException(status_code=404, detail="PDF not available for this memo snapshot")
    if not os.path.exists(memo.pdf_output_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    filename = f"investment_memorandum_{memo_id}.pdf"
    if isinstance(memo.memorandum, dict) and memo.memorandum.get("ticker"):
        filename = f"investment_memorandum_{memo.memorandum.get('ticker')}_{memo_id}.pdf"
    return FileResponse(memo.pdf_output_path, media_type="application/pdf", filename=filename)


# ---------------------------------------------------------------------------
# Portfolio endpoints
# ---------------------------------------------------------------------------


@app.post("/api/portfolios", response_model=PortfolioResponse)
async def create_portfolio(request: CreatePortfolioRequest, db: Session = Depends(get_db)):
    p = Portfolio(name=request.name, description=request.description, strategy=request.strategy)
    db.add(p)
    db.commit()
    db.refresh(p)
    return PortfolioResponse(id=p.id, name=p.name, description=p.description, strategy=p.strategy)


@app.get("/api/portfolios", response_model=list[PortfolioResponse])
async def list_portfolios(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    ps = db.query(Portfolio).order_by(Portfolio.created_at.desc()).offset(offset).limit(limit).all()
    return [PortfolioResponse(id=p.id, name=p.name, description=p.description, strategy=p.strategy) for p in ps]


@app.get("/api/portfolios/{portfolio_id}")
async def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    positions = db.query(Position).filter(Position.portfolio_id == portfolio_id).order_by(Position.id.asc()).all()
    return {
        "portfolio": PortfolioResponse(id=p.id, name=p.name, description=p.description, strategy=p.strategy).model_dump(),
        "positions": [
            PositionResponse(
                id=pos.id,
                portfolio_id=pos.portfolio_id,
                ticker=pos.ticker,
                memo_snapshot_id=pos.memo_snapshot_id,
                weight=pos.weight,
                shares=pos.shares,
                cost_basis=pos.cost_basis,
            ).model_dump()
            for pos in positions
        ],
    }


@app.post("/api/portfolios/{portfolio_id}/positions", response_model=PositionResponse)
async def add_position(portfolio_id: int, request: AddPositionRequest, db: Session = Depends(get_db)):
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    memo = db.query(MemoSnapshot).filter(MemoSnapshot.id == request.memo_snapshot_id).first()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo snapshot not found")

    memo_ticker = None
    if isinstance(memo.memorandum, dict):
        memo_ticker = (memo.memorandum.get("ticker") or "").upper() or None

    if request.ticker and memo_ticker and request.ticker.upper() != memo_ticker:
        raise HTTPException(status_code=400, detail="ticker does not match memo snapshot ticker")

    ticker = (request.ticker or memo_ticker or "UNKNOWN").upper()

    pos = Position(
        portfolio_id=portfolio_id,
        ticker=ticker,
        memo_snapshot_id=request.memo_snapshot_id,
        weight=request.weight,
        shares=request.shares,
        cost_basis=request.cost_basis,
    )
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return PositionResponse(
        id=pos.id,
        portfolio_id=pos.portfolio_id,
        ticker=pos.ticker,
        memo_snapshot_id=pos.memo_snapshot_id,
        weight=pos.weight,
        shares=pos.shares,
        cost_basis=pos.cost_basis,
    )


@app.post("/api/portfolios/{portfolio_id}/recalculate", response_model=PortfolioDashboardResponse)
async def recalculate_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    try:
        snap = recompute_portfolio_dashboard(db, portfolio_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PortfolioDashboardResponse(
        portfolio_id=snap.portfolio_id,
        as_of_date=snap.as_of_date,
        generated_at=snap.generated_at.isoformat() if snap.generated_at else datetime.utcnow().isoformat(),
        dashboard=snap.dashboard,
        constituent_memo_snapshot_ids=snap.constituent_memo_snapshot_ids or [],
    )


@app.get("/api/portfolios/{portfolio_id}/dashboard", response_model=PortfolioDashboardResponse)
async def get_portfolio_dashboard(portfolio_id: int, db: Session = Depends(get_db)):
    snap = (
        db.query(PortfolioAnalyticsSnapshot)
        .filter(PortfolioAnalyticsSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioAnalyticsSnapshot.generated_at.desc())
        .first()
    )
    if not snap:
        # compute on-demand if none exists
        try:
            snap = recompute_portfolio_dashboard(db, portfolio_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return PortfolioDashboardResponse(
        portfolio_id=snap.portfolio_id,
        as_of_date=snap.as_of_date,
        generated_at=snap.generated_at.isoformat() if snap.generated_at else datetime.utcnow().isoformat(),
        dashboard=snap.dashboard,
        constituent_memo_snapshot_ids=snap.constituent_memo_snapshot_ids or [],
    )


# ---------------------------------------------------------------------------
# Watchlists APIs
# ---------------------------------------------------------------------------


@app.get("/api/admin/watchlists/config")
async def get_watchlist_config():
    max_watchlists, max_tickers = _watchlist_limits()
    return {
        "max_watchlists_per_user": max_watchlists,
        "max_tickers_per_watchlist": max_tickers,
        "refresh_hour_utc": int(os.getenv("WATCHLIST_REFRESH_HOUR", "2")),
        "refresh_minute_utc": int(os.getenv("WATCHLIST_REFRESH_MINUTE", "0")),
    }


# ---------------------------------------------------------------------------
# Instruments + composable fetch endpoints (Alpha Vantage MVP)
# ---------------------------------------------------------------------------


@app.post("/api/instruments/resolve", response_model=ResolveInstrumentSuccessResponse)
async def resolve_instrument(request: ResolveInstrumentRequest, db: Session = Depends(get_db)):
    """
    Resolve an input symbol to a canonical instrument.
    Prefer DB/provider maps; otherwise use provider SYMBOL_SEARCH.
    Must NOT create instruments for invalid or not-found tickers.
    """
    raw = request.query or request.symbol or ""
    q = normalize_query(raw)
    t0 = time.perf_counter()
    provider_calls = 0
    if not q:
        logger.info("resolve", extra={"query": raw, "outcome": "invalid_format", "provider_calls": 0, "latency_ms": int((time.perf_counter() - t0) * 1000)})
        raise HTTPException(
            status_code=422,
            detail=ResolveInstrumentErrorResponse(
                error_code="INVALID_FORMAT", message="Ticker is required"
            ).model_dump(),
        )
    if not valid_ticker_format(q):
        logger.info("resolve", extra={"query": q, "outcome": "invalid_format", "provider_calls": 0, "latency_ms": int((time.perf_counter() - t0) * 1000)})
        raise HTTPException(
            status_code=422,
            detail=ResolveInstrumentErrorResponse(
                error_code="INVALID_FORMAT", message="Invalid ticker format"
            ).model_dump(),
        )

    # (1) DB exact match
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == q).first()
    if inst:
        # best-effort provider symbol
        primary = (
            db.query(ProviderSymbolMap)
            .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.instrument_id == inst.id)
            .order_by(ProviderSymbolMap.is_primary.desc(), ProviderSymbolMap.id.asc())
            .first()
        )
        logger.info(
            "resolve",
            extra={
                "query": q,
                "outcome": "success",
                "source": "db",
                "provider_calls": 0,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
        return ResolveInstrumentSuccessResponse(
            instrument_id=inst.id,
            ticker=inst.canonical_symbol,
            provider_symbol=(primary.provider_symbol if primary else inst.canonical_symbol),
            name=inst.name,
            exchange=inst.exchange,
            currency=inst.currency,
            resolution_source="db",
        )

    # (2) alias/provider map
    mapping = (
        db.query(ProviderSymbolMap)
        .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.provider_symbol == q)
        .first()
    )
    if mapping:
        inst = db.query(Instrument).filter(Instrument.id == mapping.instrument_id).first()
        if not inst:
            logger.info(
                "resolve",
                extra={
                    "query": q,
                    "outcome": "not_found",
                    "source": "alias",
                    "provider_calls": 0,
                    "latency_ms": int((time.perf_counter() - t0) * 1000),
                },
            )
            raise HTTPException(
                status_code=404,
                detail=ResolveInstrumentErrorResponse(
                    error_code="TICKER_NOT_FOUND", message="Ticker not found"
                ).model_dump(),
            )
        logger.info(
            "resolve",
            extra={
                "query": q,
                "outcome": "success",
                "source": "alias",
                "provider_calls": 0,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
        return ResolveInstrumentSuccessResponse(
            instrument_id=inst.id,
            ticker=inst.canonical_symbol,
            provider_symbol=mapping.provider_symbol,
            name=inst.name,
            exchange=inst.exchange,
            currency=inst.currency,
            resolution_source="alias",
        )

    # (3) provider symbol search with 24h cache
    now = datetime.utcnow()
    cache = (
        db.query(ProviderSymbolSearchCache)
        .filter(ProviderSymbolSearchCache.provider == "alpha_vantage", ProviderSymbolSearchCache.query == q)
        .first()
    )
    payload = None
    if cache and cache.fetched_at and (now - cache.fetched_at) < SYMBOL_SEARCH_TTL:
        payload = cache.payload
    else:
        from app.services.alpha_vantage_client import AlphaVantageClient

        try:
            client = AlphaVantageClient()
            provider_calls = 1
            resp = client.symbol_search(q)
            payload = resp.get("payload") if isinstance(resp, dict) else None
            if not isinstance(payload, dict):
                raise ValueError("Unexpected provider response")

            if cache:
                cache.payload = payload
                cache.fetched_at = now
            else:
                cache = ProviderSymbolSearchCache(provider="alpha_vantage", query=q, payload=payload)
                db.add(cache)
            db.commit()
        except Exception as e:
            logger.warning(
                "resolve",
                extra={
                    "query": q,
                    "outcome": "provider_error",
                    "provider_calls": provider_calls,
                    "latency_ms": int((time.perf_counter() - t0) * 1000),
                },
            )
            raise HTTPException(
                status_code=502,
                detail=ResolveInstrumentErrorResponse(
                    error_code="PROVIDER_ERROR", message=str(e)
                ).model_dump(),
            )

    matches = parse_symbol_search_matches(payload or {})
    best, suggestions = choose_best_match(q, matches)
    if not best:
        logger.info(
            "resolve",
            extra={
                "query": q,
                "outcome": "not_found",
                "source": "provider",
                "provider_calls": provider_calls,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
        raise HTTPException(
            status_code=404,
            detail=ResolveInstrumentErrorResponse(
                error_code="TICKER_NOT_FOUND", message="Ticker not found", suggestions=suggestions
            ).model_dump(),
        )

    best_symbol = (best.get("1. symbol") or "").upper().strip()
    best_name = best.get("2. name")
    best_region = best.get("4. region")
    best_currency = best.get("8. currency")

    if not best_symbol:
        logger.info(
            "resolve",
            extra={
                "query": q,
                "outcome": "not_found",
                "source": "provider",
                "provider_calls": provider_calls,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
            },
        )
        raise HTTPException(
            status_code=404,
            detail=ResolveInstrumentErrorResponse(
                error_code="TICKER_NOT_FOUND", message="Ticker not found", suggestions=suggestions
            ).model_dump(),
        )

    # Upsert instrument after successful provider resolution.
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == best_symbol).first()
    if not inst:
        inst = Instrument(canonical_symbol=best_symbol, name=best_name, exchange=best_region, currency=best_currency)
        db.add(inst)
        db.commit()
        db.refresh(inst)
    else:
        inst.name = inst.name or best_name
        inst.exchange = inst.exchange or best_region
        inst.currency = inst.currency or best_currency
        db.commit()

    # Upsert provider symbol mapping for best symbol
    def upsert_map(sym: str, is_primary: bool):
        row = (
            db.query(ProviderSymbolMap)
            .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.provider_symbol == sym)
            .first()
        )
        if row:
            row.instrument_id = inst.id
            row.is_primary = row.is_primary or is_primary
            row.last_verified_at = now
            db.commit()
            return row
        row = ProviderSymbolMap(
            provider="alpha_vantage",
            provider_symbol=sym,
            instrument_id=inst.id,
            is_primary=is_primary,
            last_verified_at=now,
        )
        db.add(row)
        db.commit()
        return row

    best_map = upsert_map(best_symbol, True)
    if q != best_symbol:
        upsert_map(q, False)

    return ResolveInstrumentSuccessResponse(
        instrument_id=inst.id,
        ticker=inst.canonical_symbol,
        provider_symbol=best_map.provider_symbol,
        name=inst.name,
        exchange=inst.exchange,
        currency=inst.currency,
        resolution_source="provider",
    )


def _advisory_lock_id_from_ticker(ticker: str) -> int:
    # Deterministic 32-bit hash promoted to signed 64-bit.
    return int(zlib.crc32(ticker.encode("utf-8")) & 0x7FFFFFFF)


def _maybe_acquire_ticker_lock(db, ticker: str):
    """
    Acquire a per-ticker lock for Postgres using pg_advisory_xact_lock.
    No-op for non-Postgres engines.
    """
    try:
        bind = db.get_bind()
        if getattr(bind.dialect, "name", "") != "postgresql":
            return
        lock_id = _advisory_lock_id_from_ticker(ticker)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
    except Exception:
        # Best-effort; uniqueness constraints still prevent duplicates.
        return


@app.get("/api/instruments/{ticker}/browse-lite", response_model=BrowseLiteResponse)
async def browse_lite(ticker: str, db: Session = Depends(get_db)):
    """
    24h cache:
    - If last_refresh_at < 24h: serve DB only.
    - Else: refresh from Alpha Vantage, persist, update last_refresh_at, and return updated snapshot.
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    # Resolve instrument; must NOT create instrument rows for unknown tickers.
    mapping = (
        db.query(ProviderSymbolMap)
        .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.provider_symbol == t)
        .first()
    )
    inst = None
    if mapping:
        inst = db.query(Instrument).filter(Instrument.id == mapping.instrument_id).first()
    if not inst:
        inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Ticker not found")

    now = datetime.utcnow()
    refresh = db.query(InstrumentRefresh).filter(InstrumentRefresh.instrument_id == inst.id).first()
    if not refresh:
        refresh = InstrumentRefresh(instrument_id=inst.id, last_refresh_at=None, last_status=None, last_error=None)
        db.add(refresh)
        db.commit()
        db.refresh(refresh)

    latest = (
        db.query(PriceEOD)
        .filter(PriceEOD.instrument_id == inst.id)
        .order_by(PriceEOD.as_of_date.desc(), PriceEOD.fetched_at.desc())
        .first()
    )

    if is_fresh(refresh.last_refresh_at, now) and latest:
        last_ref = refresh.last_refresh_at
        if last_ref is not None and last_ref.tzinfo is not None:
            last_ref = last_ref.replace(tzinfo=None)
        staleness_hours = (now - last_ref).total_seconds() / 3600.0 if last_ref else None
        return BrowseLiteResponse(
            ticker=inst.canonical_symbol,
            instrument_id=inst.id,
            name=inst.name,
            currency=inst.currency,
            exchange=inst.exchange,
            as_of_date=latest.as_of_date if latest else None,
            close=latest.close if latest else None,
            change_pct=None,
            source="db",
            last_refresh_at=refresh.last_refresh_at.isoformat() if refresh.last_refresh_at else None,
            staleness_hours=staleness_hours,
            stale=False,
            last_status=refresh.last_status,
            last_error=refresh.last_error,
        )

    # stale/missing -> refresh synchronously, protected by per-ticker lock
    _maybe_acquire_ticker_lock(db, inst.canonical_symbol)
    db.refresh(refresh)
    latest = (
        db.query(PriceEOD)
        .filter(PriceEOD.instrument_id == inst.id)
        .order_by(PriceEOD.as_of_date.desc(), PriceEOD.fetched_at.desc())
        .first()
    )
    if is_fresh(refresh.last_refresh_at, now) and latest:
        last_ref = refresh.last_refresh_at
        if last_ref is not None and last_ref.tzinfo is not None:
            last_ref = last_ref.replace(tzinfo=None)
        staleness_hours = (now - last_ref).total_seconds() / 3600.0 if last_ref else None
        return BrowseLiteResponse(
            ticker=inst.canonical_symbol,
            instrument_id=inst.id,
            name=inst.name,
            currency=inst.currency,
            exchange=inst.exchange,
            as_of_date=latest.as_of_date,
            close=latest.close,
            change_pct=None,
            source="db",
            last_refresh_at=refresh.last_refresh_at.isoformat() if refresh.last_refresh_at else None,
            staleness_hours=staleness_hours,
            stale=False,
            last_status=refresh.last_status,
            last_error=refresh.last_error,
        )

    # Provider refresh with retries/backoff
    from app.services.alpha_vantage_client import AlphaVantageClient

    client = AlphaVantageClient()
    # Keep browse-lite responsive and avoid burning provider credits:
    # one attempt per request; caller can retry later and DB cache will absorb repeated hits.
    attempts = 1
    last_exc = None
    for i in range(attempts):
        try:
            # TIME_SERIES_DAILY_ADJUSTED is premium on some keys; use TIME_SERIES_DAILY for browse-lite.
            daily = client.get_time_series_daily_compact(inst.canonical_symbol)
            payload = daily.get("payload") if isinstance(daily, dict) else None
            if not isinstance(payload, dict):
                raise ValueError("Unexpected provider payload")
            parsed = parse_daily_adjusted_latest(payload)
            if not parsed:
                raise ValueError("Unable to parse latest daily price")

            # insert (idempotent via unique constraint)
            existing = (
                db.query(PriceEOD)
                .filter(PriceEOD.instrument_id == inst.id, PriceEOD.as_of_date == parsed.as_of_date)
                .first()
            )
            if not existing:
                db.add(
                    PriceEOD(
                        instrument_id=inst.id,
                        as_of_date=parsed.as_of_date,
                        close=parsed.close,
                        adjusted_close=None,
                        volume=None,
                        provider="alpha_vantage",
                        source_metadata={"endpoint": "TIME_SERIES_DAILY", "fetched_at": daily.get("fetched_at")},
                    )
                )
                db.commit()
            refresh.last_refresh_at = now
            refresh.last_status = "success"
            refresh.last_error = None
            db.commit()

            last_ref = refresh.last_refresh_at
            if last_ref is not None and last_ref.tzinfo is not None:
                last_ref = last_ref.replace(tzinfo=None)
            staleness_hours = (now - last_ref).total_seconds() / 3600.0 if last_ref else None
            return BrowseLiteResponse(
                ticker=inst.canonical_symbol,
                instrument_id=inst.id,
                name=inst.name,
                currency=inst.currency,
                exchange=inst.exchange,
                as_of_date=parsed.as_of_date,
                close=parsed.close,
                change_pct=parsed.change_pct,
                source="alpha_vantage",
                last_refresh_at=refresh.last_refresh_at.isoformat() if refresh.last_refresh_at else None,
                staleness_hours=staleness_hours,
                stale=False,
                last_status=refresh.last_status,
                last_error=refresh.last_error,
            )
        except Exception as e:
            last_exc = e
            # If key is missing, do not retry.
            if "ALPHAVANTAGE_API_KEY is not set" in str(e):
                break
            # If provider is throttling / returning informational errors, don't retry.
            if isinstance(e, RuntimeError):
                break

    # Provider failure: return stale DB if available
    refresh.last_status = "failed"
    refresh.last_error = str(last_exc) if last_exc else "provider_refresh_failed"
    db.commit()
    latest = (
        db.query(PriceEOD)
        .filter(PriceEOD.instrument_id == inst.id)
        .order_by(PriceEOD.as_of_date.desc(), PriceEOD.fetched_at.desc())
        .first()
    )
    last_ref = refresh.last_refresh_at
    if last_ref is not None and last_ref.tzinfo is not None:
        last_ref = last_ref.replace(tzinfo=None)
    staleness_hours = (now - last_ref).total_seconds() / 3600.0 if last_ref else None
    return BrowseLiteResponse(
        ticker=inst.canonical_symbol,
        instrument_id=inst.id,
        name=inst.name,
        currency=inst.currency,
        exchange=inst.exchange,
        as_of_date=latest.as_of_date if latest else None,
        close=latest.close if latest else None,
        change_pct=None,
        source="db" if latest else "alpha_vantage",
        last_refresh_at=refresh.last_refresh_at.isoformat() if refresh.last_refresh_at else None,
        staleness_hours=staleness_hours,
        stale=True,
        last_status=refresh.last_status,
        last_error=refresh.last_error,
    )


@app.get("/api/instruments/{ticker}/prices", response_model=PriceSeriesResponse)
async def get_price_series(ticker: str, limit: int = 260, db: Session = Depends(get_db)):
    """
    Return a daily close series for charting.
    - Prefer DB `price_eod` rows.
    - If missing / stale, fetch TIME_SERIES_DAILY (compact) once and upsert missing rows (append-only).
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    mapping = (
        db.query(ProviderSymbolMap)
        .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.provider_symbol == t)
        .first()
    )
    inst = None
    if mapping:
        inst = db.query(Instrument).filter(Instrument.id == mapping.instrument_id).first()
    if not inst:
        inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Ticker not found")

    lim = max(5, min(int(limit or 260), 800))
    rows = (
        db.query(PriceEOD)
        .filter(PriceEOD.instrument_id == inst.id)
        .order_by(PriceEOD.as_of_date.desc(), PriceEOD.fetched_at.desc())
        .limit(lim)
        .all()
    )
    latest_date = rows[0].as_of_date if rows else None
    today = datetime.utcnow().date()

    should_refresh = (not rows) or (latest_date is not None and latest_date < today)
    if should_refresh:
        from app.services.alpha_vantage_client import AlphaVantageClient

        try:
            client = AlphaVantageClient()
            daily = client.get_time_series_daily_compact(inst.canonical_symbol)
            payload = daily.get("payload") if isinstance(daily, dict) else None
            if not isinstance(payload, dict):
                raise ValueError("Unexpected provider payload")

            # Use provider series for response (even if DB has a conflicting row),
            # to avoid stale/corrupted dev DB values masking correct upstream data.
            series = parse_time_series_daily_closes(payload, limit=lim)
            fetched_at = daily.get("fetched_at")

            # Upsert missing days (append-only; uniqueness protects duplicates)
            for d, close in series:
                exists = (
                    db.query(PriceEOD)
                    .filter(PriceEOD.instrument_id == inst.id, PriceEOD.as_of_date == d)
                    .first()
                )
                if exists:
                    continue
                db.add(
                    PriceEOD(
                        instrument_id=inst.id,
                        as_of_date=d,
                        close=close,
                        adjusted_close=None,
                        volume=None,
                        provider="alpha_vantage",
                        source_metadata={"endpoint": "TIME_SERIES_DAILY", "fetched_at": fetched_at},
                    )
                )
            db.commit()

            # Return provider series directly (ascending)
            return PriceSeriesResponse(
                ticker=inst.canonical_symbol,
                instrument_id=inst.id,
                points=[PricePoint(as_of_date=d, close=close) for d, close in series],
            )
        except Exception:
            db.rollback()

    # Re-read series for response (ascending)
    rows = (
        db.query(PriceEOD)
        .filter(PriceEOD.instrument_id == inst.id)
        .order_by(PriceEOD.as_of_date.desc(), PriceEOD.fetched_at.desc())
        .limit(lim)
        .all()
    )
    # Collapse duplicates by date keeping newest fetched_at, then sort ascending
    by_date = {}
    for r in rows:
        if r.as_of_date not in by_date:
            by_date[r.as_of_date] = r
    points = [PricePoint(as_of_date=d, close=by_date[d].close) for d in sorted(by_date.keys())]

    return PriceSeriesResponse(ticker=inst.canonical_symbol, instrument_id=inst.id, points=points)


@app.get("/api/instruments/{ticker}/overview", response_model=OverviewResponse)
async def get_overview(ticker: str, db: Session = Depends(get_db)):
    """
    Overview composition: price + FCF + KPI panels.
    Applies 24h DB-first caching per dataset type.
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    mapping = (
        db.query(ProviderSymbolMap)
        .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.provider_symbol == t)
        .first()
    )
    inst = None
    if mapping:
        inst = db.query(Instrument).filter(Instrument.id == mapping.instrument_id).first()
    if not inst:
        inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Ticker not found")

    now = datetime.utcnow()

    # Price: use existing price_eod latest (populated via browse-lite/prices); do not force provider call here.
    latest_price = (
        db.query(PriceEOD)
        .filter(PriceEOD.instrument_id == inst.id)
        .order_by(PriceEOD.as_of_date.desc(), PriceEOD.fetched_at.desc())
        .first()
    )
    as_of_date = latest_price.as_of_date if latest_price else None
    close = latest_price.close if latest_price else None

    # Fundamentals refresh (quarterly + annual)
    from app.services.alpha_vantage_client import AlphaVantageClient

    # Default meta in case provider calls fail; we still want a 200 with error info,
    # not a silent 500.
    q_meta: dict[str, Any] = {"last_status": "failed", "last_error": None, "last_refresh_at": None}
    a_meta: dict[str, Any] = {"last_status": "failed", "last_error": None, "last_refresh_at": None}

    try:
        client = AlphaVantageClient()

        def fetch_all():
            return {
                "cash_flow": client.get_cash_flow(inst.canonical_symbol),
                "income_statement": client.get_income_statement(inst.canonical_symbol),
                "balance_sheet": client.get_balance_sheet(inst.canonical_symbol),
            }

        q_meta, a_meta = refresh_fundamentals_bundle(db, inst.id, now, fetch_all)
    except Exception as e:
        # Preserve any existing snapshots; just mark meta as failed.
        msg = str(e)
        q_meta = {**q_meta, "last_error": msg}
        a_meta = {**a_meta, "last_error": msg}

    # Load snapshots
    q_cf = load_fundamentals_snapshots(db, inst.id, "cash_flow", "quarterly", limit=12)
    q_is = load_fundamentals_snapshots(db, inst.id, "income_statement", "quarterly", limit=12)
    q_bs = load_fundamentals_snapshots(db, inst.id, "balance_sheet", "quarterly", limit=12)

    a_cf = load_fundamentals_snapshots(db, inst.id, "cash_flow", "annual", limit=10)
    a_is = load_fundamentals_snapshots(db, inst.id, "income_statement", "annual", limit=10)
    a_bs = load_fundamentals_snapshots(db, inst.id, "balance_sheet", "annual", limit=10)

    q_fcf = compute_fcf_series(q_cf, q_is)
    a_fcf = compute_fcf_series(a_cf, a_is)

    q_kpis = compute_kpis(q_is, q_bs, q_fcf)
    a_kpis = compute_kpis(a_is, a_bs, a_fcf)

    def ds_status(dataset_type: str, meta: dict) -> OverviewDatasetStatus:
        last_refresh_at = meta.get("last_refresh_at")
        last_refresh_str = last_refresh_at.isoformat() if last_refresh_at else None
        stale = not (meta.get("last_status") == "success" and meta.get("last_refresh_at") and (now - meta.get("last_refresh_at")) < timedelta(hours=24))
        return OverviewDatasetStatus(
            dataset_type=dataset_type,
            last_refresh_at=last_refresh_str,
            last_status=meta.get("last_status"),
            last_error=meta.get("last_error"),
            stale=stale,
        )

    return OverviewResponse(
        ticker=inst.canonical_symbol,
        instrument_id=inst.id,
        as_of_date=as_of_date,
        close=close,
        fcf_quarterly=[OverviewFcfPoint(period_end=p.period_end, fcf=p.fcf, revenue=p.revenue, fcf_margin=p.fcf_margin) for p in q_fcf],
        fcf_annual=[OverviewFcfPoint(period_end=p.period_end, fcf=p.fcf, revenue=p.revenue, fcf_margin=p.fcf_margin) for p in a_fcf],
        kpis_quarterly=[
            OverviewKpiPoint(
                period_end=p.period_end,
                roe=p.roe,
                net_margin=p.net_margin,
                operating_margin=p.operating_margin,
                fcf_margin=p.fcf_margin,
                debt_to_equity=p.debt_to_equity,
            )
            for p in q_kpis
        ],
        kpis_annual=[
            OverviewKpiPoint(
                period_end=p.period_end,
                roe=p.roe,
                net_margin=p.net_margin,
                operating_margin=p.operating_margin,
                fcf_margin=p.fcf_margin,
                debt_to_equity=p.debt_to_equity,
            )
            for p in a_kpis
        ],
        datasets=[ds_status("fundamentals_quarterly", q_meta), ds_status("fundamentals_annual", a_meta)],
    )


@app.get("/api/instruments/{ticker}/fundamentals/series", response_model=FundamentalsSeriesResponse)
async def get_fundamentals_series(
    ticker: str,
    period: str = "quarterly",
    series: str = "fcf",
    db: Session = Depends(get_db),
):
    """
    Return aligned fundamentals series for overlay charting.
    - period: quarterly|annual
    - series: comma-separated list, e.g. fcf,sbc,netIncome,debt,dividends,buybacks
    Uses 24h DB-first caching via InstrumentDatasetRefresh (fundamentals_quarterly/fundamentals_annual).
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    p = (period or "").strip().lower()
    if p not in ("quarterly", "annual"):
        raise HTTPException(status_code=422, detail="period must be quarterly or annual")

    requested = [s.strip() for s in (series or "").split(",") if s.strip()]
    requested = [s for s in requested if s in ALLOWED_SERIES]
    if not requested:
        raise HTTPException(status_code=422, detail="No valid series requested")

    mapping = (
        db.query(ProviderSymbolMap)
        .filter(ProviderSymbolMap.provider == "alpha_vantage", ProviderSymbolMap.provider_symbol == t)
        .first()
    )
    inst = None
    if mapping:
        inst = db.query(Instrument).filter(Instrument.id == mapping.instrument_id).first()
    if not inst:
        inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Ticker not found")

    now = datetime.utcnow()

    from app.services.alpha_vantage_client import AlphaVantageClient

    try:
        client = AlphaVantageClient()

        def fetch_all():
            return {
                "cash_flow": client.get_cash_flow(inst.canonical_symbol),
                "income_statement": client.get_income_statement(inst.canonical_symbol),
                "balance_sheet": client.get_balance_sheet(inst.canonical_symbol),
            }

        # Refresh both quarterly and annual together to avoid duplicate provider calls.
        refresh_fundamentals_bundle(db, inst.id, now, fetch_all)
    except Exception:
        # Best-effort: fall back to whatever fundamentals snapshots already exist.
        pass

    # Load snapshots for requested period
    freq = "quarterly" if p == "quarterly" else "annual"
    lim = 12 if freq == "quarterly" else 10
    cf = load_fundamentals_snapshots(db, inst.id, "cash_flow", freq, limit=lim)
    inc = load_fundamentals_snapshots(db, inst.id, "income_statement", freq, limit=lim)
    bs = load_fundamentals_snapshots(db, inst.id, "balance_sheet", freq, limit=lim)

    bundle = compute_fundamentals_series(cash_flows=cf, incomes=inc, balances=bs, requested=requested)

    # Use instrument currency if present (Alpha Vantage statements do not always carry it).
    currency = inst.currency

    out_series = {
        k: [FundamentalsSeriesPoint(period_end=d, value=v) for (d, v) in pts]
        for k, pts in bundle.series.items()
    }
    return FundamentalsSeriesResponse(
        ticker=inst.canonical_symbol,
        instrument_id=inst.id,
        period=p,
        currency=currency,
        as_of=bundle.as_of,
        series=out_series,
        unavailable=bundle.unavailable,
    )


@app.get("/api/instruments/{instrument_id}/snapshot/latest-lite", response_model=LiteSnapshotResponse)
async def get_latest_lite_snapshot(instrument_id: int, db: Session = Depends(get_db)):
    """
    Serve from DB if present; otherwise return last known snapshot with stale=true and
    best-effort queue a provider refresh job.
    """
    inst = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found")

    today = datetime.utcnow().date()
    latest = (
        db.query(PriceEOD)
        .filter(PriceEOD.instrument_id == inst.id)
        .order_by(PriceEOD.as_of_date.desc(), PriceEOD.fetched_at.desc())
        .first()
    )
    stale = (latest is None) or (latest.as_of_date < today)
    refresh_queued = False

    if stale:
        try:
            from app.worker.tasks import refresh_instrument_lite

            refresh_instrument_lite.delay(inst.id)
            refresh_queued = True
        except Exception:
            refresh_queued = False

    return LiteSnapshotResponse(
        instrument=InstrumentResponse(
            id=inst.id,
            canonical_symbol=inst.canonical_symbol,
            name=inst.name,
            exchange=inst.exchange,
            sector=inst.sector,
            industry=inst.industry,
            currency=inst.currency,
        ),
        as_of_date=latest.as_of_date if latest else None,
        price=(latest.adjusted_close or latest.close) if latest else None,
        currency=inst.currency,
        stale=stale,
        refresh_queued=refresh_queued,
        provider=latest.provider if latest else None,
        fetched_at=latest.fetched_at.isoformat() if latest and latest.fetched_at else None,
    )


@app.post("/api/instruments/{instrument_id}/backfill", response_model=BackfillEnqueueResponse, status_code=202)
async def enqueue_instrument_backfill(instrument_id: int, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found")

    request_key = f"alpha_vantage:backfill:{inst.id}:5y"
    try:
        from app.worker.tasks import backfill_instrument_data

        backfill_instrument_data.delay(inst.id)
    except Exception:
        pass

    return BackfillEnqueueResponse(instrument_id=inst.id, status="queued", request_key=request_key, job_id=None)


# ---------------------------------------------------------------------------
# SEC EDGAR ingestion / parse (10-K / 10-Q)
# ---------------------------------------------------------------------------


@app.post("/api/sec/{ticker}/ingest", response_model=SecIngestResponse)
async def sec_ingest_filings(ticker: str, db: Session = Depends(get_db)):
    """
    Trigger SEC 10-K / 10-Q ingestion for a single ticker.

    This endpoint runs ingestion synchronously (V0) and:
    - resolves CIK,
    - discovers eligible filings,
    - downloads primary documents and registers RAW_FILING artifacts,
    - creates PARSE_FILING jobs for new artifacts.
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    try:
        result = ingest_sec_filings_for_ticker(db, t)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Enqueue any queued parse jobs for this ticker (best-effort).
    try:
        from app.worker.tasks import sec_parse_filing_task

        queued_jobs = (
            db.query(SecParseJob)
            .join(SecArtifact, SecParseJob.artifact_id == SecArtifact.id)
            .filter(
                SecArtifact.ticker == t,
                SecParseJob.status.in_([SecParseJobStatus.QUEUED, SecParseJobStatus.FAILED]),
            )
            .all()
        )
        for job in queued_jobs:
            try:
                sec_parse_filing_task.delay(job.id)
            except Exception:
                pass
    except Exception:
        pass

    return SecIngestResponse(**result)


@app.get("/api/sec/{ticker}/filings", response_model=SecFilingListResponse)
async def list_sec_filings(ticker: str, db: Session = Depends(get_db)):
    """
    List SEC filing artifacts (raw + parsed) for a ticker, including parse job status.
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        # Attempt lazy CIK resolution + instrument creation
        try:
            cik = resolve_cik_for_ticker(db, t)
            inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
        except Exception:
            raise HTTPException(status_code=404, detail="Instrument/CIK not found for ticker")
    cik = inst.cik
    if not cik:
        try:
            cik = resolve_cik_for_ticker(db, t)
        except Exception:
            raise HTTPException(status_code=404, detail="CIK not found for ticker")

    artifacts = (
        db.query(SecArtifact)
        .filter(SecArtifact.cik == cik)
        .order_by(SecArtifact.filing_date.desc(), SecArtifact.accession_number.desc(), SecArtifact.artifact_kind)
        .all()
    )

    # Preload parse jobs keyed by artifact id
    jobs = (
        db.query(SecParseJob)
        .filter(SecParseJob.artifact_id.in_([a.id for a in artifacts]))
        .all()
        if artifacts
        else []
    )
    by_artifact_id = {j.artifact_id: j for j in jobs}

    summaries: list[SecFilingSummary] = []
    for a in artifacts:
        job = by_artifact_id.get(a.id)
        summaries.append(
            SecFilingSummary(
                artifact_id=a.id,
                accession_number=a.accession_number,
                form_type=a.form_type,
                filing_date=a.filing_date,
                period_end=a.period_end,
                artifact_kind=a.artifact_kind.value if isinstance(a.artifact_kind, SecArtifactKind) else str(a.artifact_kind),
                parser_version=a.parser_version,
                parse_job_status=job.status.value if job and job.status else None,
            )
        )

    return SecFilingListResponse(ticker=t, cik=cik, filings=summaries)


@app.get("/api/sec/artifacts/{artifact_id}/download")
async def download_sec_artifact(artifact_id: int, db: Session = Depends(get_db)):
    """
    Download a SEC artifact file (raw filing or parsed text).
    """
    artifact = db.query(SecArtifact).filter(SecArtifact.id == artifact_id).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Security: verify file exists and is within expected storage path
    if artifact.storage_backend != "local_fs":
        raise HTTPException(status_code=400, detail="Only local filesystem artifacts are supported")

    file_path = artifact.storage_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Determine media type based on file extension
    ext = os.path.splitext(artifact.file_name)[1].lower()
    media_type_map = {
        ".html": "text/html",
        ".htm": "text/html",
        ".txt": "text/plain",
        ".xml": "application/xml",
        ".xbrl": "application/xml",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")

    # Generate download filename: {form_type}_{filing_date}_{accession_number}.{ext}
    safe_form = artifact.form_type.replace("/", "-")
    safe_date = artifact.filing_date.strftime("%Y%m%d") if artifact.filing_date else "unknown"
    safe_acc = artifact.accession_number.replace("/", "-")
    download_filename = f"{safe_form}_{safe_date}_{safe_acc}{ext}"

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=download_filename,
        headers={"Content-Disposition": f'attachment; filename="{download_filename}"'},
    )


@app.get("/api/instruments/{ticker}/sec/fundamentals/summary", response_model=SecFundamentalsSummaryResponse)
async def sec_fundamentals_summary(ticker: str, db: Session = Depends(get_db)):
    """
    Latest SEC fundamentals extraction summary + alerts for a ticker.
    """
    t = ticker.upper().strip()
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        try:
            resolve_cik_for_ticker(db, t)
            inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
        except Exception:
            raise HTTPException(status_code=404, detail="Instrument not found")

    snapshot = (
        db.query(SecFundamentalsSnapshot)
        .filter(SecFundamentalsSnapshot.instrument_id == inst.id)
        .order_by(SecFundamentalsSnapshot.filing_date.desc(), SecFundamentalsSnapshot.extracted_at.desc())
        .first()
    )

    if not snapshot:
        return SecFundamentalsSummaryResponse(
            ticker=t,
            instrument_id=inst.id,
            latest_snapshot=None,
            top_facts=[],
            top_changes=[],
            alerts=[],
        )

    facts = (
        db.query(SecFundamentalsFact)
        .filter(SecFundamentalsFact.snapshot_id == snapshot.id)
        .order_by(SecFundamentalsFact.metric_key.asc())
        .all()
    )
    fact_summaries = [
        SecFundamentalsFactSummary(
            metric_key=f.metric_key,
            metric_label=f.metric_label,
            value=f.value_num,
            unit=f.unit,
            period=f.period,
            context_snippet=f.context_snippet,
        )
        for f in facts[:8]
    ]

    changes = (
        db.query(SecFundamentalsChange)
        .filter(SecFundamentalsChange.curr_snapshot_id == snapshot.id)
        .all()
    )
    severity_rank = {"high": 3, "medium": 2, "low": 1, "info": 0}
    changes_sorted = sorted(
        changes,
        key=lambda c: (
            -severity_rank.get((c.severity or "info").lower(), 0),
            -abs(c.delta_pct or 0),
        ),
    )
    change_summaries = [
        SecFundamentalsChangeSummary(
            metric_key=c.metric_key,
            metric_label=c.metric_label,
            prev_value=c.prev_value,
            curr_value=c.curr_value,
            delta=c.delta,
            delta_pct=c.delta_pct,
            unit=c.unit,
            period=c.period,
            severity=c.severity,
            rule_id=c.rule_id,
        )
        for c in changes_sorted[:6]
    ]

    alerts = (
        db.query(SecFundamentalsAlert)
        .filter(
            SecFundamentalsAlert.instrument_id == inst.id,
            SecFundamentalsAlert.status == "open",
        )
        .order_by(SecFundamentalsAlert.triggered_at.desc())
        .all()
    )
    alert_summaries = [
        SecFundamentalsAlertSummary(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            status=a.status,
            message=a.message,
            triggered_at=a.triggered_at.isoformat(),
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
            evidence=a.evidence,
        )
        for a in alerts[:8]
    ]

    return SecFundamentalsSummaryResponse(
        ticker=t,
        instrument_id=inst.id,
        latest_snapshot=SecFundamentalsSnapshotSummary(
            snapshot_id=snapshot.id,
            form_type=snapshot.form_type,
            filing_date=snapshot.filing_date,
            period_end=snapshot.period_end,
            parser_version=snapshot.parser_version,
            extracted_at=snapshot.extracted_at.isoformat(),
        ),
        top_facts=fact_summaries,
        top_changes=change_summaries,
        alerts=alert_summaries,
    )


def _build_sec_fundamentals_perspective(
    db: Session, inst: Instrument, scope: str, form_types: Optional[list[str]]
) -> SecFundamentalsPerspectiveResponse:
    scope_key = scope
    query = db.query(SecFundamentalsSnapshot).filter(SecFundamentalsSnapshot.instrument_id == inst.id)
    if form_types:
        query = query.filter(SecFundamentalsSnapshot.form_type.in_(form_types))

    snapshot = (
        query.order_by(SecFundamentalsSnapshot.filing_date.desc(), SecFundamentalsSnapshot.extracted_at.desc())
        .first()
    )

    if not snapshot:
        return SecFundamentalsPerspectiveResponse(
            scope=scope_key,
            latest_snapshot=None,
            top_facts=[],
            top_changes=[],
            alerts=[],
        )

    facts = (
        db.query(SecFundamentalsFact)
        .filter(SecFundamentalsFact.snapshot_id == snapshot.id)
        .order_by(SecFundamentalsFact.metric_key.asc())
        .all()
    )
    fact_summaries = [
        SecFundamentalsFactSummary(
            metric_key=f.metric_key,
            metric_label=f.metric_label,
            value=f.value_num,
            unit=f.unit,
            period=f.period,
            context_snippet=f.context_snippet,
        )
        for f in facts[:8]
    ]

    prior = (
        query.filter(SecFundamentalsSnapshot.id != snapshot.id)
        .order_by(SecFundamentalsSnapshot.filing_date.desc(), SecFundamentalsSnapshot.extracted_at.desc())
        .first()
    )

    change_summaries: list[SecFundamentalsChangeSummary] = []
    if prior:
        prior_facts = (
            db.query(SecFundamentalsFact)
            .filter(SecFundamentalsFact.snapshot_id == prior.id)
            .all()
        )
        prior_by_key = {(f.metric_key, f.period): f for f in prior_facts}
        for f in facts:
            key = (f.metric_key, f.period)
            prev = prior_by_key.get(key)
            if not prev or f.value_num is None or prev.value_num is None:
                continue
            delta = f.value_num - prev.value_num
            delta_pct = delta / prev.value_num if prev.value_num != 0 else None
            change_summaries.append(
                SecFundamentalsChangeSummary(
                    metric_key=f.metric_key,
                    metric_label=f.metric_label,
                    prev_value=prev.value_num,
                    curr_value=f.value_num,
                    delta=delta,
                    delta_pct=delta_pct,
                    unit=f.unit,
                    period=f.period,
                    severity=None,
                    rule_id=None,
                )
            )
        change_summaries.sort(key=lambda c: -abs(c.delta_pct or 0))
        change_summaries = change_summaries[:6]

    alerts = (
        db.query(SecFundamentalsAlert)
        .filter(
            SecFundamentalsAlert.instrument_id == inst.id,
            SecFundamentalsAlert.curr_snapshot_id == snapshot.id,
            SecFundamentalsAlert.status == "open",
        )
        .order_by(SecFundamentalsAlert.triggered_at.desc())
        .all()
    )
    alert_summaries = [
        SecFundamentalsAlertSummary(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            status=a.status,
            message=a.message,
            triggered_at=a.triggered_at.isoformat(),
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
            evidence=a.evidence,
        )
        for a in alerts[:8]
    ]

    return SecFundamentalsPerspectiveResponse(
        scope=scope_key,
        latest_snapshot=SecFundamentalsSnapshotSummary(
            snapshot_id=snapshot.id,
            form_type=snapshot.form_type,
            filing_date=snapshot.filing_date,
            period_end=snapshot.period_end,
            parser_version=snapshot.parser_version,
            extracted_at=snapshot.extracted_at.isoformat(),
        ),
        top_facts=fact_summaries,
        top_changes=change_summaries,
        alerts=alert_summaries,
    )


@app.get("/api/instruments/{ticker}/sec/fundamentals/perspectives", response_model=SecFundamentalsPerspectivesResponse)
async def sec_fundamentals_perspectives(ticker: str, db: Session = Depends(get_db)):
    """
    Aggregated, 10-K, and 10-Q SEC fundamentals perspectives for a ticker.
    """
    t = ticker.upper().strip()
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        try:
            resolve_cik_for_ticker(db, t)
            inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
        except Exception:
            raise HTTPException(status_code=404, detail="Instrument not found")

    aggregate = _build_sec_fundamentals_perspective(db, inst, "aggregate", None)
    ten_k = _build_sec_fundamentals_perspective(db, inst, "10k", ["10-K", "10-K/A"])
    ten_q = _build_sec_fundamentals_perspective(db, inst, "10q", ["10-Q", "10-Q/A"])

    return SecFundamentalsPerspectivesResponse(
        ticker=t,
        instrument_id=inst.id,
        aggregate=aggregate,
        ten_k=ten_k,
        ten_q=ten_q,
    )


@app.get("/api/instruments/{ticker}/sec/fundamentals/alerts", response_model=SecFundamentalsAlertsResponse)
async def list_sec_fundamentals_alerts(
    ticker: str,
    status: Optional[str] = None,
    limit: int = 25,
    db: Session = Depends(get_db),
):
    """
    List SEC fundamentals alerts for a ticker.
    """
    t = ticker.upper().strip()
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        try:
            resolve_cik_for_ticker(db, t)
            inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
        except Exception:
            raise HTTPException(status_code=404, detail="Instrument not found")

    query = db.query(SecFundamentalsAlert).filter(SecFundamentalsAlert.instrument_id == inst.id)
    if status and status.lower() != "all":
        query = query.filter(SecFundamentalsAlert.status == status.lower())

    alerts = query.order_by(SecFundamentalsAlert.triggered_at.desc()).limit(min(limit, 100)).all()
    alert_summaries = [
        SecFundamentalsAlertSummary(
            id=a.id,
            alert_type=a.alert_type,
            severity=a.severity,
            status=a.status,
            message=a.message,
            triggered_at=a.triggered_at.isoformat(),
            resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
            evidence=a.evidence,
        )
        for a in alerts
    ]

    return SecFundamentalsAlertsResponse(ticker=t, instrument_id=inst.id, alerts=alert_summaries)


@app.post("/api/sec/{ticker}/fundamentals/reprocess")
async def reprocess_sec_fundamentals(ticker: str, db: Session = Depends(get_db)):
    """
    Reprocess parsed SEC filings to extract fundamentals for a ticker.
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        try:
            resolve_cik_for_ticker(db, t)
            inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
        except Exception:
            raise HTTPException(status_code=404, detail="Instrument not found")

    artifacts = (
        db.query(SecArtifact)
        .filter(
            SecArtifact.instrument_id == inst.id,
            SecArtifact.artifact_kind == SecArtifactKind.PARSED_TEXT,
        )
        .order_by(SecArtifact.filing_date.desc())
        .limit(10)
        .all()
    )
    if not artifacts:
        raise HTTPException(status_code=404, detail="No parsed SEC filings found for ticker")

    enqueued = 0
    for art in artifacts:
        try:
            from app.worker.tasks import sec_extract_fundamentals_task

            sec_extract_fundamentals_task.delay(art.id)
            enqueued += 1
        except Exception:
            pass

    return {"ticker": t, "parsed_artifact_count": len(artifacts), "enqueued": enqueued}


@app.post("/api/sec/{ticker}/parse/requeue")
async def requeue_sec_parse_jobs(ticker: str, db: Session = Depends(get_db)):
    """
    Requeue SEC parse jobs for a ticker (queued/failed/deadletter).
    """
    t = ticker.upper().strip()
    if not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
    if not inst:
        try:
            resolve_cik_for_ticker(db, t)
            inst = db.query(Instrument).filter(Instrument.canonical_symbol == t).first()
        except Exception:
            raise HTTPException(status_code=404, detail="Instrument not found")

    jobs = (
        db.query(SecParseJob)
        .join(SecArtifact, SecParseJob.artifact_id == SecArtifact.id)
        .filter(
            SecArtifact.ticker == t,
            SecParseJob.status.in_(
                [SecParseJobStatus.QUEUED, SecParseJobStatus.FAILED, SecParseJobStatus.DEADLETTER]
            ),
        )
        .all()
    )
    if not jobs:
        return {"ticker": t, "requeued": 0, "status": "no_jobs"}

    requeued = 0
    for job in jobs:
        job.status = SecParseJobStatus.QUEUED
        job.last_error = None
        job.locked_by = None
        job.locked_at = None
        db.add(job)
    db.commit()

    try:
        from app.worker.tasks import sec_parse_filing_task

        for job in jobs:
            try:
                sec_parse_filing_task.delay(job.id)
                requeued += 1
            except Exception:
                pass
    except Exception:
        pass

    return {"ticker": t, "requeued": requeued, "total_jobs": len(jobs)}


@app.get("/api/watchlists", response_model=list[WatchlistResponse])
async def list_watchlists(
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"), db: Session = Depends(get_db)
):
    user_id = _get_user_id(x_user_id)
    rows = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user_id)
        .order_by(Watchlist.created_at.desc())
        .all()
    )
    return [WatchlistResponse(id=w.id, user_id=w.user_id, name=w.name, is_active=w.is_active) for w in rows]


@app.post("/api/watchlists", response_model=WatchlistResponse, status_code=201)
async def create_watchlist(
    request: CreateWatchlistRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user_id = _get_user_id(x_user_id)
    max_watchlists, _ = _watchlist_limits()
    count = db.query(Watchlist).filter(Watchlist.user_id == user_id).count()
    if count >= max_watchlists:
        raise HTTPException(status_code=400, detail="Max watchlists per user exceeded")
    wl = Watchlist(user_id=user_id, name=request.name, is_active=request.is_active)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return WatchlistResponse(id=wl.id, user_id=wl.user_id, name=wl.name, is_active=wl.is_active)


@app.delete("/api/watchlists/{watchlist_id}", status_code=204)
async def delete_watchlist(
    watchlist_id: int,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user_id = _get_user_id(x_user_id)
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    db.delete(wl)
    db.commit()
    return None


@app.get("/api/watchlists/{watchlist_id}/items", response_model=list[WatchlistItemResponse])
async def list_watchlist_items(
    watchlist_id: int,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user_id = _get_user_id(x_user_id)
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    items = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == wl.id).order_by(WatchlistItem.id.asc()).all()
    return [WatchlistItemResponse(id=i.id, watchlist_id=i.watchlist_id, ticker=i.ticker) for i in items]


@app.post("/api/watchlists/{watchlist_id}/items", response_model=WatchlistItemResponse, status_code=201)
async def add_watchlist_item(
    watchlist_id: int,
    request: AddWatchlistItemRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user_id = _get_user_id(x_user_id)
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    _, max_tickers = _watchlist_limits()
    if max_tickers is not None:
        current = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == wl.id).count()
        if current >= max_tickers:
            raise HTTPException(status_code=400, detail="Max tickers per watchlist exceeded")

    ticker = request.ticker.upper().strip()
    if not ticker.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")

    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == wl.id, WatchlistItem.ticker == ticker)
        .first()
    )
    if existing:
        return WatchlistItemResponse(id=existing.id, watchlist_id=existing.watchlist_id, ticker=existing.ticker)

    item = WatchlistItem(watchlist_id=wl.id, ticker=ticker)
    db.add(item)
    db.commit()
    db.refresh(item)
    return WatchlistItemResponse(id=item.id, watchlist_id=item.watchlist_id, ticker=item.ticker)


@app.delete("/api/watchlists/{watchlist_id}/items/{item_id}", status_code=204)
async def delete_watchlist_item(
    watchlist_id: int,
    item_id: int,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user_id = _get_user_id(x_user_id)
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id, WatchlistItem.watchlist_id == wl.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(item)
    db.commit()
    return None


@app.post("/api/watchlists/default/add", response_model=WatchlistItemResponse, status_code=201)
async def add_to_default_watchlist(
    request: AddWatchlistItemRequest,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user_id = _get_user_id(x_user_id)
    wl = _get_or_create_default_watchlist(db, user_id)
    # Reuse existing endpoint logic locally
    ticker = request.ticker.upper().strip()
    existing = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == wl.id, WatchlistItem.ticker == ticker)
        .first()
    )
    if existing:
        return WatchlistItemResponse(id=existing.id, watchlist_id=existing.watchlist_id, ticker=existing.ticker)
    item = WatchlistItem(watchlist_id=wl.id, ticker=ticker)
    db.add(item)
    db.commit()
    db.refresh(item)
    return WatchlistItemResponse(id=item.id, watchlist_id=item.watchlist_id, ticker=item.ticker)


@app.get("/api/watchlists/{watchlist_id}/status", response_model=WatchlistStatusResponse)
async def get_watchlist_status(
    watchlist_id: int,
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user_id = _get_user_id(x_user_id)
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    as_of_date: date_type = datetime.utcnow().date()
    items = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == wl.id).order_by(WatchlistItem.id.asc()).all()

    # Fetch today's job status (if any)
    job = db.query(RefreshJob).filter(RefreshJob.as_of_date == as_of_date).first()
    job_status = job.status.value if job and job.status else None

    out: list[RefreshStatusResponse] = []
    stale_count = 0
    for it in items:
        latest = (
            db.query(DataSnapshot)
            .filter(DataSnapshot.ticker == it.ticker)
            .order_by(DataSnapshot.snapshot_date.desc(), DataSnapshot.fetched_at.desc())
            .first()
        )
        last_date = latest.snapshot_date if latest else None
        stale = (last_date is None) or (last_date < as_of_date)
        if stale:
            stale_count += 1
        out.append(
            RefreshStatusResponse(
                ticker=it.ticker,
                last_snapshot_date=last_date,
                last_fetched_at=latest.fetched_at.isoformat() if latest and latest.fetched_at else None,
                stale=stale,
                last_refresh_job_status=job_status,
            )
        )

    return WatchlistStatusResponse(
        watchlist=WatchlistResponse(id=wl.id, user_id=wl.user_id, name=wl.name, is_active=wl.is_active),
        items=out,
        as_of_date=as_of_date,
        stale_count=stale_count,
    )


@app.post("/api/admin/refresh/watchlists/run", status_code=202)
async def run_watchlist_refresh_now():
    """
    Manual trigger to enqueue the daily refresh task immediately.
    Useful for admins or local dev; the scheduler will also run this daily.
    """
    from app.worker.tasks import refresh_watchlist_universe

    async_result = refresh_watchlist_universe.delay()
    return {"task_id": async_result.id, "status": "queued"}


# ---------------------------------------------------------------------------
# Investment Thesis endpoints
# ---------------------------------------------------------------------------


@app.get("/api/instruments/{ticker}/thesis", response_model=InvestmentThesisResponse)
async def get_investment_thesis(ticker: str, db: Session = Depends(get_db)):
    """Get the investment thesis for a ticker."""
    ticker_upper = ticker.upper().strip()
    
    # Find instrument
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == ticker_upper).first()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instrument not found: {ticker}")
    
    # Get thesis
    thesis = db.query(InvestmentThesis).filter(InvestmentThesis.instrument_id == inst.id).first()
    if not thesis:
        raise HTTPException(status_code=404, detail=f"Investment thesis not found for {ticker}")
    
    return InvestmentThesisResponse(
        id=thesis.id,
        ticker=thesis.ticker,
        title=thesis.title,
        date=thesis.date,
        current_price=thesis.current_price,
        recommendation=thesis.recommendation,
        executive_summary=thesis.executive_summary,
        thesis_content=thesis.thesis_content,
        action_plan=thesis.action_plan,
        conclusion=thesis.conclusion,
        created_at=thesis.created_at.isoformat(),
        updated_at=thesis.updated_at.isoformat(),
    )


@app.post("/api/instruments/{ticker}/thesis", response_model=InvestmentThesisResponse, status_code=201)
async def create_or_update_investment_thesis(
    ticker: str, request: CreateInvestmentThesisRequest, db: Session = Depends(get_db)
):
    """Create or update the investment thesis for a ticker."""
    ticker_upper = ticker.upper().strip()
    
    # Find or create instrument
    inst = db.query(Instrument).filter(Instrument.canonical_symbol == ticker_upper).first()
    if not inst:
        # Create instrument if it doesn't exist
        inst = Instrument(canonical_symbol=ticker_upper)
        db.add(inst)
        db.flush()
    
    # Check if thesis exists
    thesis = db.query(InvestmentThesis).filter(InvestmentThesis.instrument_id == inst.id).first()
    
    if thesis:
        # Update existing
        thesis.title = request.title
        thesis.date = request.date
        thesis.current_price = request.current_price
        thesis.recommendation = request.recommendation
        thesis.executive_summary = request.executive_summary
        thesis.thesis_content = request.thesis_content
        thesis.action_plan = request.action_plan
        thesis.conclusion = request.conclusion
        thesis.updated_at = datetime.utcnow()
    else:
        # Create new
        thesis = InvestmentThesis(
            instrument_id=inst.id,
            ticker=ticker_upper,
            title=request.title,
            date=request.date,
            current_price=request.current_price,
            recommendation=request.recommendation,
            executive_summary=request.executive_summary,
            thesis_content=request.thesis_content,
            action_plan=request.action_plan,
            conclusion=request.conclusion,
        )
        db.add(thesis)
    
    db.commit()
    db.refresh(thesis)
    
    return InvestmentThesisResponse(
        id=thesis.id,
        ticker=thesis.ticker,
        title=thesis.title,
        date=thesis.date,
        current_price=thesis.current_price,
        recommendation=thesis.recommendation,
        executive_summary=thesis.executive_summary,
        thesis_content=thesis.thesis_content,
        action_plan=thesis.action_plan,
        conclusion=thesis.conclusion,
        created_at=thesis.created_at.isoformat(),
        updated_at=thesis.updated_at.isoformat(),
    )
