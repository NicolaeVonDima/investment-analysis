"""
Database models for investment analysis platform.
"""

from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Text
from sqlalchemy.sql import func
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

