"""
API request/response schemas for the snapshot + portfolio layers.

These are separate from `app/schemas.py`, which defines the memorandum JSON schema.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreatePortfolioRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    strategy: Optional[Dict[str, Any]] = None


class PortfolioResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    strategy: Optional[Dict[str, Any]]


class AddPositionRequest(BaseModel):
    memo_snapshot_id: int = Field(..., description="Existing memo snapshot to reference (immutable analysis artifact)")
    ticker: Optional[str] = Field(None, description="Optional; validated against memo snapshot ticker when provided")
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    shares: Optional[float] = Field(None, ge=0.0)
    cost_basis: Optional[float] = Field(None, ge=0.0)


class PositionResponse(BaseModel):
    id: int
    portfolio_id: int
    ticker: str
    memo_snapshot_id: int
    weight: Optional[float]
    shares: Optional[float]
    cost_basis: Optional[float]


class DataSnapshotResponse(BaseModel):
    id: int
    ticker: str
    snapshot_date: date
    provider: str
    provider_version: Optional[str]
    fetched_at: str


class MemoSnapshotResponse(BaseModel):
    id: int
    ticker: str
    snapshot_date: Optional[date] = None
    ruleset_version: Optional[str] = None
    prompt_version: Optional[str] = None
    generated_at: str


class PortfolioDashboardResponse(BaseModel):
    portfolio_id: int
    as_of_date: date
    generated_at: str
    dashboard: Dict[str, Any]
    constituent_memo_snapshot_ids: List[int]


# ---------------------------------------------------------------------------
# Watchlists + global refresh
# ---------------------------------------------------------------------------


class CreateWatchlistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    is_active: bool = True


class WatchlistResponse(BaseModel):
    id: int
    user_id: str
    name: str
    is_active: bool


class AddWatchlistItemRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)


class WatchlistItemResponse(BaseModel):
    id: int
    watchlist_id: int
    ticker: str


class RefreshStatusResponse(BaseModel):
    ticker: str
    last_snapshot_date: Optional[date] = None
    last_fetched_at: Optional[str] = None
    stale: bool
    last_refresh_job_status: Optional[str] = None


class WatchlistStatusResponse(BaseModel):
    watchlist: WatchlistResponse
    items: List[RefreshStatusResponse]
    as_of_date: date
    stale_count: int


# ---------------------------------------------------------------------------
# Instruments + Alpha Vantage composable fetch
# ---------------------------------------------------------------------------


class ResolveInstrumentRequest(BaseModel):
    # Accept either `symbol` (current clients) or `query` (spec v1.3.0).
    symbol: Optional[str] = Field(None, min_length=1, max_length=32)
    query: Optional[str] = Field(None, min_length=1, max_length=32)


class ResolveInstrumentSuccessResponse(BaseModel):
    instrument_id: int
    ticker: str
    provider_symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    resolution_source: str  # db|alias|provider


class ResolveInstrumentErrorResponse(BaseModel):
    error_code: str  # INVALID_FORMAT|TICKER_NOT_FOUND|PROVIDER_ERROR
    message: str
    suggestions: Optional[list[str]] = None


class InstrumentResponse(BaseModel):
    id: int
    canonical_symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: Optional[str] = None


class LiteSnapshotResponse(BaseModel):
    instrument: InstrumentResponse
    as_of_date: Optional[date] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    stale: bool
    refresh_queued: bool = False
    provider: Optional[str] = None
    fetched_at: Optional[str] = None


class BackfillEnqueueResponse(BaseModel):
    instrument_id: int
    status: str
    request_key: str
    job_id: Optional[int] = None


class BrowseLiteResponse(BaseModel):
    ticker: str
    instrument_id: int
    name: Optional[str] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None

    as_of_date: Optional[date] = None
    close: Optional[float] = None
    change_pct: Optional[float] = None

    source: str  # db|alpha_vantage
    last_refresh_at: Optional[str] = None
    staleness_hours: Optional[float] = None
    stale: bool

    last_status: Optional[str] = None
    last_error: Optional[str] = None


class PricePoint(BaseModel):
    as_of_date: date
    close: Optional[float] = None


class PriceSeriesResponse(BaseModel):
    ticker: str
    instrument_id: int
    points: List[PricePoint]


class OverviewFcfPoint(BaseModel):
    period_end: date
    fcf: Optional[float] = None
    revenue: Optional[float] = None
    fcf_margin: Optional[float] = None


class OverviewKpiPoint(BaseModel):
    period_end: date
    roe: Optional[float] = None
    net_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    fcf_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None


class OverviewDatasetStatus(BaseModel):
    dataset_type: str
    last_refresh_at: Optional[str] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    stale: bool


class OverviewResponse(BaseModel):
    ticker: str
    instrument_id: int
    as_of_date: Optional[date] = None
    close: Optional[float] = None

    fcf_quarterly: List[OverviewFcfPoint] = []
    fcf_annual: List[OverviewFcfPoint] = []

    kpis_quarterly: List[OverviewKpiPoint] = []
    kpis_annual: List[OverviewKpiPoint] = []

    datasets: List[OverviewDatasetStatus] = []


# ---------------------------------------------------------------------------
# Fundamentals multi-series (chart overlays)
# ---------------------------------------------------------------------------


class FundamentalsSeriesPoint(BaseModel):
    period_end: date
    value: Optional[float] = None


class FundamentalsSeriesResponse(BaseModel):
    ticker: str
    instrument_id: int
    period: str  # quarterly|annual
    currency: Optional[str] = None
    as_of: Optional[date] = None
    series: Dict[str, List[FundamentalsSeriesPoint]] = {}
    unavailable: List[str] = []


# ---------------------------------------------------------------------------
# Investment Thesis
# ---------------------------------------------------------------------------


class CreateInvestmentThesisRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    date: date
    current_price: Optional[float] = None
    recommendation: str = Field(..., min_length=1, max_length=50)
    executive_summary: str = Field(..., min_length=1)
    thesis_content: str = Field(..., min_length=1)
    action_plan: Optional[str] = None
    conclusion: Optional[str] = None


class InvestmentThesisResponse(BaseModel):
    id: int
    ticker: str
    title: str
    date: date
    current_price: Optional[float]
    recommendation: str
    executive_summary: str
    thesis_content: str
    action_plan: Optional[str]
    conclusion: Optional[str]
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# SEC EDGAR ingestion / parse (10-K / 10-Q)
# ---------------------------------------------------------------------------


class SecIngestResponse(BaseModel):
    ticker: str
    cik: str
    selected_count: int
    artifact_ids: List[int]
    parse_job_ids: List[int]
    created_raw_count: int
    created_parse_job_count: int
    run_at: str


class SecFilingSummary(BaseModel):
    artifact_id: int
    accession_number: str
    form_type: str
    filing_date: date
    period_end: Optional[date] = None
    artifact_kind: str  # RAW_FILING|PARSED_TEXT
    parser_version: Optional[str] = None
    parse_job_status: Optional[str] = None  # queued|running|done|failed|deadletter


class SecFilingListResponse(BaseModel):
    ticker: str
    cik: str
    filings: List[SecFilingSummary]


