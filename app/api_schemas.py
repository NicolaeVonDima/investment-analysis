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


