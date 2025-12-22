"""
Pydantic schemas for API requests and responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class PortfolioBase(BaseModel):
    id: str
    name: str
    color: str
    capital: float
    goal: Optional[str] = None
    riskLabel: Optional[str] = Field(None, alias="risk_label")
    overperformStrategy: Optional[Dict[str, Any]] = Field(None, alias="overperform_strategy")
    allocation: Dict[str, float]
    rules: Dict[str, Any]
    strategy: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(populate_by_name=True)


class PortfolioCreate(PortfolioBase):
    pass


class PortfolioResponse(PortfolioBase):
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ScenarioBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
    
    name: str
    inflation: float
    assetReturns: Dict[str, float] = Field(alias="asset_returns")
    trimRules: Dict[str, Dict[str, Any]] = Field(alias="trim_rules")
    fidelisCap: float = Field(alias="fidelis_cap")
    is_default: bool = False


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioResponse(ScenarioBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class SaveDataRequest(BaseModel):
    portfolios: list[PortfolioBase]
    scenarios: list[ScenarioBase]
    default_scenario_id: Optional[str] = None


class LoadDataResponse(BaseModel):
    portfolios: list[PortfolioResponse]
    scenarios: list[ScenarioResponse]
    default_scenario_id: Optional[str] = None

