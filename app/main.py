"""
Main FastAPI application for investment analysis platform.
Handles user input, orchestration, and document delivery.
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import os
from datetime import datetime
from datetime import date as date_type

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
)
from app.services.portfolio_analytics import recompute_portfolio_dashboard

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


@app.post("/api/analyze", status_code=202)
async def analyze_ticker(request: TickerRequest):
    """
    Submit a stock ticker for analysis.
    Returns a job ID that can be used to check status and retrieve results.
    """
    ticker = request.ticker.upper().strip()
    
    # Validate ticker format (basic validation)
    if not ticker.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")
    
    # Create analysis request record
    db = next(get_db())
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
async def get_status(job_id: int):
    """Get the status of an analysis job."""
    db = next(get_db())
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
async def get_json_result(job_id: int):
    """Retrieve the JSON result of a completed analysis."""
    db = next(get_db())
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
async def get_pdf_result(job_id: int):
    """Retrieve the PDF result of a completed analysis."""
    db = next(get_db())
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
async def list_jobs(limit: int = 20, offset: int = 0):
    """List recent analysis jobs."""
    db = next(get_db())
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
async def list_data_snapshots(ticker: str, limit: int = 20, offset: int = 0):
    """List data snapshots for a ticker (most recent first)."""
    db = next(get_db())
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
async def list_memo_snapshots(ticker: str, limit: int = 20, offset: int = 0):
    """List memo snapshots (analysis artifacts) for a ticker (most recent first)."""
    db = next(get_db())
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
async def get_memo_json(memo_id: int):
    """Retrieve stored memo snapshot JSON (immutable analysis artifact)."""
    db = next(get_db())
    memo = db.query(MemoSnapshot).filter(MemoSnapshot.id == memo_id).first()
    if not memo:
        raise HTTPException(status_code=404, detail="Memo snapshot not found")
    return JSONResponse(content=memo.memorandum)


@app.get("/api/memo/{memo_id}/pdf")
async def get_memo_pdf(memo_id: int):
    """Retrieve stored memo snapshot PDF by memo snapshot id."""
    db = next(get_db())
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
async def create_portfolio(request: CreatePortfolioRequest):
    db = next(get_db())
    p = Portfolio(name=request.name, description=request.description, strategy=request.strategy)
    db.add(p)
    db.commit()
    db.refresh(p)
    return PortfolioResponse(id=p.id, name=p.name, description=p.description, strategy=p.strategy)


@app.get("/api/portfolios", response_model=list[PortfolioResponse])
async def list_portfolios(limit: int = 50, offset: int = 0):
    db = next(get_db())
    ps = db.query(Portfolio).order_by(Portfolio.created_at.desc()).offset(offset).limit(limit).all()
    return [PortfolioResponse(id=p.id, name=p.name, description=p.description, strategy=p.strategy) for p in ps]


@app.get("/api/portfolios/{portfolio_id}")
async def get_portfolio(portfolio_id: int):
    db = next(get_db())
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
async def add_position(portfolio_id: int, request: AddPositionRequest):
    db = next(get_db())
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
async def recalculate_portfolio(portfolio_id: int):
    db = next(get_db())
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
async def get_portfolio_dashboard(portfolio_id: int):
    db = next(get_db())
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


@app.get("/api/watchlists", response_model=list[WatchlistResponse])
async def list_watchlists(x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")):
    db = next(get_db())
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
    request: CreateWatchlistRequest, x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")
):
    db = next(get_db())
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
    watchlist_id: int, x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")
):
    db = next(get_db())
    user_id = _get_user_id(x_user_id)
    wl = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user_id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    db.delete(wl)
    db.commit()
    return None


@app.get("/api/watchlists/{watchlist_id}/items", response_model=list[WatchlistItemResponse])
async def list_watchlist_items(
    watchlist_id: int, x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")
):
    db = next(get_db())
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
):
    db = next(get_db())
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
):
    db = next(get_db())
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
    request: AddWatchlistItemRequest, x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")
):
    db = next(get_db())
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
    watchlist_id: int, x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")
):
    db = next(get_db())
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

