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
    horizon: Optional[str] = Field(None, alias="horizon")
    selectedStrategy: Optional[str] = Field(None, alias="selected_strategy")
    overperformStrategy: Optional[Dict[str, Any]] = Field(None, alias="overperform_strategy")
    allocation: Dict[str, float]
    # memberAllocations removed - we now use per-member portfolios instead
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
    inflation: float  # International inflation
    romanianInflation: Optional[float] = Field(0.08, alias="romanian_inflation")  # Romanian inflation (default 8%)
    growthCushion: Optional[float] = Field(0.02, alias="growth_cushion")
    taxOnSaleProceeds: Optional[float] = Field(None, alias="tax_on_sale_proceeds")
    taxOnDividends: Optional[float] = Field(None, alias="tax_on_dividends")
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


class FamilyMemberBase(BaseModel):
    id: str
    name: str
    amount: float
    displayOrder: Optional[int] = Field(0, alias="display_order")
    
    model_config = ConfigDict(populate_by_name=True)


class FamilyMemberCreate(FamilyMemberBase):
    pass


class FamilyMemberResponse(FamilyMemberBase):
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SaveDataRequest(BaseModel):
    portfolios: list[PortfolioBase]
    scenarios: list[ScenarioBase]
    familyMembers: Optional[list[FamilyMemberBase]] = Field(None, alias="family_members")
    default_scenario_id: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)


class LoadDataResponse(BaseModel):
    portfolios: list[PortfolioResponse]
    scenarios: list[ScenarioResponse]
    familyMembers: Optional[list[FamilyMemberResponse]] = Field(None, alias="family_members")
    default_scenario_id: Optional[str] = None
    
    model_config = ConfigDict(populate_by_name=True)


# Authentication Schemas
class UserRegister(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    subscription_tier: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None
    is_primary_account: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

