"""
Database models for portfolios and scenarios.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from app.database import Base


class PortfolioModel(Base):
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False)
    capital = Column(Float, nullable=False)
    goal = Column(String, nullable=True)
    risk_label = Column(String, nullable=True)  # e.g., "Risk: Medium"
    horizon = Column(String, nullable=True)  # e.g., "2026 - 2029"
    overperform_strategy = Column(JSON, nullable=True)  # {title, content: []}
    allocation = Column(JSON, nullable=False)  # {vwce, tvbetetf, ernx, wqdv, fidelis}
    rules = Column(JSON, nullable=False)  # {tvbetetfConditional}
    strategy = Column(JSON, nullable=True)  # {overperformanceStrategy, overperformanceThreshold}
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ScenarioModel(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    inflation = Column(Float, nullable=False)
    growth_cushion = Column(Float, nullable=True, default=0.02)  # Real growth cushion (e.g., 0.02 = 2%)
    tax_on_sale_proceeds = Column(Float, nullable=True)  # Tax rate on capital gains (e.g., 0.10 = 10%)
    tax_on_dividends = Column(Float, nullable=True)  # Tax rate on dividends/yield (e.g., 0.05 = 5%)
    asset_returns = Column(JSON, nullable=False)  # {vwce, tvbetetf, ernx, ernxYield, wqdv, wqdvYield, fidelis}
    trim_rules = Column(JSON, nullable=False)  # {vwce: {enabled, threshold}, ...}
    fidelis_cap = Column(Float, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

