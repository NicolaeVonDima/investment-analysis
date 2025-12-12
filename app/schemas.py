"""
JSON schema definitions for investment memorandum.
All outputs must conform to this schema for reproducibility and validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import date


class MetricValue(BaseModel):
    """A computed metric value with metadata."""
    value: float = Field(..., description="The computed metric value")
    unit: str = Field(..., description="Unit of measurement (e.g., 'USD', 'percent', 'ratio')")
    source: str = Field(..., description="Source of the data (e.g., 'yfinance', 'computed')")
    computed_at: str = Field(..., description="ISO timestamp when metric was computed")
    ruleset_version: str = Field(..., description="Version of ruleset used for computation")


class FinancialMetric(BaseModel):
    """A financial metric with its computed value."""
    name: str = Field(..., description="Name of the metric")
    description: str = Field(..., description="Human-readable description")
    value: MetricValue
    category: str = Field(..., description="Category (e.g., 'valuation', 'profitability', 'growth')")


class NarrativeSection(BaseModel):
    """A section of narrative text with traceable claims."""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Narrative content")
    supporting_metrics: List[str] = Field(..., description="List of metric names that support claims in this section")
    generated_at: str = Field(..., description="ISO timestamp when narrative was generated")
    prompt_version: str = Field(..., description="Version of prompt template used")


class CompanyInfo(BaseModel):
    """Basic company information."""
    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    sector: Optional[str] = Field(None, description="Business sector")
    industry: Optional[str] = Field(None, description="Industry")
    exchange: Optional[str] = Field(None, description="Stock exchange")


class InvestmentMemorandum(BaseModel):
    """
    Complete investment memorandum schema.
    All fields must be populated from computed metrics - no invented numbers.
    """
    # Metadata
    version: str = Field("1.0.0", description="Schema version")
    generated_at: str = Field(..., description="ISO timestamp when memorandum was generated")
    ticker: str = Field(..., description="Stock ticker symbol")
    ruleset_version: str = Field(..., description="Version of ruleset used")
    
    # Company information
    company: CompanyInfo
    
    # Analysis period
    analysis_date: str = Field(..., description="Date of analysis (ISO format)")
    data_period_end: str = Field(..., description="End date of data period analyzed (ISO format)")
    
    # Computed metrics
    metrics: List[FinancialMetric] = Field(..., description="All computed financial metrics")
    
    # Narrative sections
    narrative: List[NarrativeSection] = Field(..., description="Narrative sections with traceable claims")
    
    # Summary
    summary: Dict[str, Any] = Field(..., description="Summary section with key findings")
    
    # Audit trail
    audit_trail: Dict[str, Any] = Field(..., description="Audit information including data sources, computation steps")
    
    @validator('metrics')
    def validate_metrics_not_empty(cls, v):
        """Ensure at least one metric is present."""
        if not v:
            raise ValueError("At least one metric must be present")
        return v
    
    @validator('narrative')
    def validate_narrative_claims(cls, v, values):
        """Ensure all narrative claims reference valid metrics."""
        if 'metrics' in values:
            metric_names = {m.name for m in values['metrics']}
            for section in v:
                for claim_metric in section.supporting_metrics:
                    if claim_metric not in metric_names:
                        raise ValueError(f"Narrative references unknown metric: {claim_metric}")
        return v

