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
    PriceSeriesResponse,
    PricePoint,
    OverviewResponse,
    OverviewDatasetStatus,
    OverviewFcfPoint,
    OverviewKpiPoint,
)
from app.services.portfolio_analytics import recompute_portfolio_dashboard
from app.services.browse_lite import is_fresh, parse_daily_adjusted_latest, parse_time_series_daily_closes
from app.services.overview import (
    compute_fcf_series,
    compute_kpis,
    load_fundamentals_snapshots,
    refresh_fundamentals_bundle,
)
from app.services.ticker_resolution import (
    SYMBOL_SEARCH_TTL,
    choose_best_match,
    normalize_query,
    parse_symbol_search_matches,
    valid_ticker_format,
)

logger = logging.getLogger("app.ticker_resolution")

app = FastAPI(
    title="Investment Analysis Platform",
    description="Rules-based investment memorandum generator",
    version="1.0.0"
)

# CORS (frontend dev server runs on a different origin)
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
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
        staleness_hours = (now - refresh.last_refresh_at).total_seconds() / 3600.0 if refresh.last_refresh_at else None
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
        staleness_hours = (now - refresh.last_refresh_at).total_seconds() / 3600.0 if refresh.last_refresh_at else None
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

            staleness_hours = (now - refresh.last_refresh_at).total_seconds() / 3600.0 if refresh.last_refresh_at else None
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
    staleness_hours = (now - refresh.last_refresh_at).total_seconds() / 3600.0 if refresh.last_refresh_at else None
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

    client = AlphaVantageClient()

    def fetch_all():
        return {
            "cash_flow": client.get_cash_flow(inst.canonical_symbol),
            "income_statement": client.get_income_statement(inst.canonical_symbol),
            "balance_sheet": client.get_balance_sheet(inst.canonical_symbol),
        }

    q_meta, a_meta = refresh_fundamentals_bundle(db, inst.id, now, fetch_all)

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
