"""
Database models for investment analysis platform.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Enum as SQLEnum,
    Text,
    ForeignKey,
    Float,
    JSON,
    Index,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class AnalysisStatus(enum.Enum):
    """Status of an analysis request."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRequest(Base):
    """Model for analysis requests."""
    __tablename__ = "analysis_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    ruleset_version = Column(String(50), nullable=True)
    status = Column(SQLEnum(AnalysisStatus), nullable=False, default=AnalysisStatus.PENDING)
    
    # Output paths
    json_output_path = Column(String(500), nullable=True)
    pdf_output_path = Column(String(500), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<AnalysisRequest(id={self.id}, ticker={self.ticker}, status={self.status.value})>"


# ---------------------------------------------------------------------------
# Snapshot layer (immutable, time-versioned artifacts)
# ---------------------------------------------------------------------------


class DataSnapshot(Base):
    """
    Immutable market/fundamental data snapshot by ticker and snapshot_date.

    Stores the raw provider payload and enough metadata to reproduce the fetch.
    """

    __tablename__ = "data_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)  # "as-of" date for this snapshot

    provider = Column(String(50), nullable=False, default="yfinance")
    provider_version = Column(String(50), nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Raw payload from provider (EOD prices, fundamentals, company info, etc.)
    payload = Column(JSON, nullable=False)
    source_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    metrics_snapshots = relationship("MetricsSnapshot", back_populates="data_snapshot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_data_snapshots_ticker_date_fetched", "ticker", "snapshot_date", "fetched_at"),
    )


class MetricsSnapshot(Base):
    """Immutable derived metrics snapshot, computed from a DataSnapshot and a ruleset."""

    __tablename__ = "metrics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    data_snapshot_id = Column(Integer, ForeignKey("data_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)

    ruleset_version = Column(String(50), nullable=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Stored as JSON to preserve exact computed values/units/metadata.
    metrics = Column(JSON, nullable=False)  # List[FinancialMetric] (as dicts)
    summary = Column(JSON, nullable=True)
    computation_steps = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    data_snapshot = relationship("DataSnapshot", back_populates="metrics_snapshots")
    evidence_snapshots = relationship(
        "EvidenceSnapshot", back_populates="metrics_snapshot", cascade="all, delete-orphan"
    )


class EvidenceSnapshot(Base):
    """
    Immutable evidence snapshot derived from MetricsSnapshot.

    Evidence factors are structured, traceable interpretations (not predictions).
    """

    __tablename__ = "evidence_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    metrics_snapshot_id = Column(
        Integer, ForeignKey("metrics_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )

    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Arbitrary structured evidence factors (JSON).
    evidence = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    metrics_snapshot = relationship("MetricsSnapshot", back_populates="evidence_snapshots")
    memo_snapshots = relationship("MemoSnapshot", back_populates="evidence_snapshot", cascade="all, delete-orphan")


class MemoSnapshot(Base):
    """
    Immutable memo snapshot (JSON + optional PDF path).

    This is the canonical analysis artifact for a ticker+snapshot_date+ruleset+prompt.
    """

    __tablename__ = "memo_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    evidence_snapshot_id = Column(
        Integer, ForeignKey("evidence_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Optional linkage back to job tracking (keeps AnalysisRequest schema unchanged).
    analysis_request_id = Column(Integer, ForeignKey("analysis_requests.id", ondelete="SET NULL"), nullable=True)

    prompt_version = Column(String(50), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    memorandum = Column(JSON, nullable=False)  # InvestmentMemorandum dict
    json_output_path = Column(String(500), nullable=True)
    pdf_output_path = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    evidence_snapshot = relationship("EvidenceSnapshot", back_populates="memo_snapshots")
    analysis_request = relationship("AnalysisRequest")

    __table_args__ = (
        Index("ix_memo_snapshots_req_generated", "analysis_request_id", "generated_at"),
    )


# ---------------------------------------------------------------------------
# Portfolio layer
# ---------------------------------------------------------------------------


class Portfolio(Base):
    """A portfolio groups positions that reference existing analysis snapshots."""

    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Strategy/config metadata (allocation rules, cadence, etc.)
    strategy = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    positions = relationship("Position", back_populates="portfolio", cascade="all, delete-orphan")
    analytics_snapshots = relationship(
        "PortfolioAnalyticsSnapshot", back_populates="portfolio", cascade="all, delete-orphan"
    )


class Position(Base):
    """A portfolio position referencing a memo snapshot (analysis artifact)."""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)

    ticker = Column(String(10), nullable=False, index=True)

    # Reference to analysis artifact
    memo_snapshot_id = Column(Integer, ForeignKey("memo_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Optional position sizing fields (either weight or shares based)
    weight = Column(Float, nullable=True)  # 0..1
    shares = Column(Float, nullable=True)
    cost_basis = Column(Float, nullable=True)

    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    portfolio = relationship("Portfolio", back_populates="positions")
    memo_snapshot = relationship("MemoSnapshot")

    __table_args__ = (
        Index("ix_positions_portfolio_ticker", "portfolio_id", "ticker"),
    )


class PortfolioAnalyticsSnapshot(Base):
    """Immutable portfolio analytics snapshot derived from constituent positions/memos."""

    __tablename__ = "portfolio_analytics_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)

    as_of_date = Column(Date, nullable=False, index=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Structured dashboard output (allocations, aggregates, drift, etc.)
    dashboard = Column(JSON, nullable=False)

    # Traceability of constituents used
    constituent_memo_snapshot_ids = Column(JSON, nullable=False)  # List[int]

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    portfolio = relationship("Portfolio", back_populates="analytics_snapshots")


# ---------------------------------------------------------------------------
# Watchlists with global ticker refresh (shared snapshots across users)
# ---------------------------------------------------------------------------


class RefreshJobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RefreshJobItemStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Watchlist(Base):
    """User-owned watchlist container. Data is global; users own the lists."""

    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship("WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_watchlists_user_active", "user_id", "is_active"),
    )


class WatchlistItem(Base):
    """Ticker membership within a Watchlist."""

    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    watchlist = relationship("Watchlist", back_populates="items")

    __table_args__ = (
        UniqueConstraint("watchlist_id", "ticker", name="ux_watchlist_items_watchlist_ticker"),
        Index("ix_watchlist_items_watchlist", "watchlist_id"),
    )


class RefreshJob(Base):
    """Daily refresh job over the union of active watchlists."""

    __tablename__ = "refresh_jobs"

    id = Column(Integer, primary_key=True, index=True)
    as_of_date = Column(Date, nullable=False, index=True)
    status = Column(SQLEnum(RefreshJobStatus), nullable=False, default=RefreshJobStatus.PENDING)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Auditable, structured stats / metadata (counts, durations, config, etc.)
    stats = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items = relationship("RefreshJobItem", back_populates="refresh_job", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("as_of_date", name="ux_refresh_jobs_as_of_date"),
    )


class RefreshJobItem(Base):
    """Per-ticker refresh attempt status for a given RefreshJob."""

    __tablename__ = "refresh_job_items"

    id = Column(Integer, primary_key=True, index=True)
    refresh_job_id = Column(Integer, ForeignKey("refresh_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    status = Column(SQLEnum(RefreshJobItemStatus), nullable=False, default=RefreshJobItemStatus.PENDING)

    attempts = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    # Link to global DataSnapshot for traceability (nullable when failed/skipped).
    data_snapshot_id = Column(Integer, ForeignKey("data_snapshots.id", ondelete="SET NULL"), nullable=True, index=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    refresh_job = relationship("RefreshJob", back_populates="items")
    data_snapshot = relationship("DataSnapshot")

    __table_args__ = (
        UniqueConstraint("refresh_job_id", "ticker", name="ux_refresh_job_items_job_ticker"),
        Index("ix_refresh_job_items_job", "refresh_job_id"),
    )


# ---------------------------------------------------------------------------
# Instruments + provider-normalized market data (Alpha Vantage MVP)
# ---------------------------------------------------------------------------


class ProviderRefreshJobStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Instrument(Base):
    """Canonical instrument (one per unique company/security)."""

    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    canonical_symbol = Column(String(32), nullable=False, index=True, unique=True)

    # Identity fields (populated from provider overview / cached identity)
    name = Column(String(255), nullable=True)
    exchange = Column(String(64), nullable=True)
    sector = Column(String(128), nullable=True)
    industry = Column(String(128), nullable=True)
    currency = Column(String(16), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    symbol_maps = relationship("ProviderSymbolMap", back_populates="instrument", cascade="all, delete-orphan")
    prices = relationship("PriceEOD", back_populates="instrument", cascade="all, delete-orphan")
    fundamentals = relationship("FundamentalsSnapshot", back_populates="instrument", cascade="all, delete-orphan")


class ProviderSymbolMap(Base):
    """Maps provider-specific symbols/aliases to canonical Instrument."""

    __tablename__ = "provider_symbol_map"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(64), nullable=False, index=True)
    provider_symbol = Column(String(32), nullable=False, index=True)

    instrument_id = Column(Integer, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    is_primary = Column(Boolean, nullable=False, default=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    instrument = relationship("Instrument", back_populates="symbol_maps")

    __table_args__ = (
        UniqueConstraint("provider", "provider_symbol", name="ux_provider_symbol_map_provider_symbol"),
        Index("ix_provider_symbol_map_provider_instrument", "provider", "instrument_id"),
    )


class ProviderSymbolSearchCache(Base):
    """
    Cache provider symbol search results to reduce calls (24h TTL enforced in code).
    """

    __tablename__ = "provider_symbol_search_cache"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(64), nullable=False, index=True, default="alpha_vantage")
    query = Column(String(64), nullable=False, index=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    payload = Column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "query", name="ux_provider_symbol_search_cache_provider_query"),
        Index("ix_provider_symbol_search_cache_provider_fetched", "provider", "fetched_at"),
    )


class PriceEOD(Base):
    """Immutable EOD price row (daily) per instrument."""

    __tablename__ = "price_eod"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    as_of_date = Column(Date, nullable=False, index=True)

    close = Column(Float, nullable=True)
    adjusted_close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)

    provider = Column(String(64), nullable=False, default="alpha_vantage")
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    source_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    instrument = relationship("Instrument", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("instrument_id", "as_of_date", name="ux_price_eod_instrument_date"),
        Index("ix_price_eod_instrument_date_fetched", "instrument_id", "as_of_date", "fetched_at"),
    )


class FundamentalsSnapshot(Base):
    """Immutable fundamentals snapshot per instrument/period."""

    __tablename__ = "fundamentals_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)

    statement_type = Column(String(64), nullable=False, index=True)  # overview|income_statement|balance_sheet|cash_flow
    frequency = Column(String(16), nullable=False, default="annual", index=True)  # annual|quarterly
    period_end = Column(Date, nullable=False, index=True)

    provider = Column(String(64), nullable=False, default="alpha_vantage")
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    source_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    instrument = relationship("Instrument", back_populates="fundamentals")

    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "statement_type",
            "frequency",
            "period_end",
            name="ux_fundamentals_snapshot_key",
        ),
        Index("ix_fundamentals_snapshot_instrument_period", "instrument_id", "statement_type", "period_end"),
    )


class ProviderRefreshJob(Base):
    """
    Tracks provider work for idempotency, retry, and audit.

    Uses a unique `request_key` so repeated calls can be de-duplicated safely.
    """

    __tablename__ = "provider_refresh_jobs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(64), nullable=False, index=True, default="alpha_vantage")
    job_type = Column(String(32), nullable=False, index=True)  # lite|backfill

    instrument_id = Column(Integer, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=True, index=True)
    as_of_date = Column(Date, nullable=True, index=True)

    request_key = Column(String(255), nullable=False, unique=True, index=True)
    status = Column(SQLEnum(ProviderRefreshJobStatus), nullable=False, default=ProviderRefreshJobStatus.PENDING)

    attempts = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    stats = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    instrument = relationship("Instrument")


class InstrumentRefresh(Base):
    """
    Per-instrument refresh state for UI-lite browse caching.

    This is global (not per user) and tracks the most recent successful refresh time.
    """

    __tablename__ = "instrument_refresh"

    instrument_id = Column(
        Integer, ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    last_refresh_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_status = Column(String(32), nullable=True)  # success|failed
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    instrument = relationship("Instrument")


class InstrumentDatasetRefresh(Base):
    """
    Per-instrument, per-dataset refresh state to enforce 24h DB-first caching for composed views.
    """

    __tablename__ = "instrument_dataset_refresh"

    instrument_id = Column(
        Integer, ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    dataset_type = Column(String(64), primary_key=True, index=True)  # fundamentals_quarterly|fundamentals_annual|...

    last_refresh_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_status = Column(String(32), nullable=True)  # success|failed
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    instrument = relationship("Instrument")

