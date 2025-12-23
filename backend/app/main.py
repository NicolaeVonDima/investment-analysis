"""
FastAPI backend for portfolio simulator.
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import os

from app.database import get_db, init_db
from app.models import PortfolioModel, ScenarioModel, FamilyMemberModel
from app.schemas import (
    PortfolioCreate,
    PortfolioResponse,
    ScenarioCreate,
    ScenarioResponse,
    FamilyMemberCreate,
    FamilyMemberResponse,
    SaveDataRequest,
    LoadDataResponse
)

app = FastAPI(
    title="Portfolio Simulator API",
    description="Backend API for portfolio comparison simulator",
    version="1.0.0"
)

# CORS configuration
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
if _cors_origins_env.strip() == "*":
    _cors_origins = ["*"]
else:
    _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    try:
        init_db()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")


@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Portfolio Simulator API is running"}


@app.post("/api/data/save", response_model=dict)
async def save_data(
    data: SaveDataRequest,
    db: Session = Depends(get_db)
):
    """Save all portfolios and scenarios."""
    try:
        # Save portfolios
        for portfolio_data in data.portfolios:
            portfolio = db.query(PortfolioModel).filter(
                PortfolioModel.id == portfolio_data.id
            ).first()
            
            # Convert camelCase to snake_case for database
            risk_label = getattr(portfolio_data, 'riskLabel', None) or getattr(portfolio_data, 'risk_label', None)
            horizon = getattr(portfolio_data, 'horizon', None)
            selected_strategy = getattr(portfolio_data, 'selectedStrategy', None) or getattr(portfolio_data, 'selected_strategy', None)
            overperform_strategy = getattr(portfolio_data, 'overperformStrategy', None) or getattr(portfolio_data, 'overperform_strategy', None)
            
            if portfolio:
                # Update existing
                portfolio.name = portfolio_data.name
                portfolio.color = portfolio_data.color
                portfolio.capital = portfolio_data.capital
                portfolio.goal = portfolio_data.goal
                portfolio.risk_label = risk_label
                portfolio.horizon = horizon
                portfolio.selected_strategy = selected_strategy
                portfolio.overperform_strategy = overperform_strategy
                portfolio.allocation = portfolio_data.allocation
                # member_allocations removed - we now use per-member portfolios instead
                portfolio.rules = portfolio_data.rules
                portfolio.strategy = portfolio_data.strategy
                # Explicitly update the updated_at timestamp
                portfolio.updated_at = datetime.now(timezone.utc)
            else:
                # Create new
                portfolio = PortfolioModel(
                    id=portfolio_data.id,
                    name=portfolio_data.name,
                    color=portfolio_data.color,
                    capital=portfolio_data.capital,
                    goal=portfolio_data.goal,
                    risk_label=risk_label,
                    horizon=horizon,
                    selected_strategy=selected_strategy,
                    overperform_strategy=overperform_strategy,
                    allocation=portfolio_data.allocation,
                    # member_allocations removed - we now use per-member portfolios instead
                    rules=portfolio_data.rules,
                    strategy=portfolio_data.strategy
                )
                db.add(portfolio)
        
        # Save scenarios
        # First, unset all defaults
        db.query(ScenarioModel).update({ScenarioModel.is_default: False})
        
        for scenario_data in data.scenarios:
            # Use name as ID for scenarios
            scenario_id = scenario_data.name
            scenario = db.query(ScenarioModel).filter(
                ScenarioModel.id == scenario_id
            ).first()
            
            # Convert camelCase to snake_case for database
            asset_returns = scenario_data.assetReturns
            trim_rules = scenario_data.trimRules
            fidelis_cap = scenario_data.fidelisCap
            growth_cushion = getattr(scenario_data, 'growthCushion', None) or getattr(scenario_data, 'growth_cushion', None) or 0.02
            romanian_inflation = getattr(scenario_data, 'romanianInflation', None) or getattr(scenario_data, 'romanian_inflation', None) or 0.08
            tax_on_sale_proceeds = getattr(scenario_data, 'taxOnSaleProceeds', None) or getattr(scenario_data, 'tax_on_sale_proceeds', None)
            tax_on_dividends = getattr(scenario_data, 'taxOnDividends', None) or getattr(scenario_data, 'tax_on_dividends', None)
            
            if scenario:
                # Update existing
                scenario.name = scenario_data.name
                scenario.inflation = scenario_data.inflation
                scenario.romanian_inflation = romanian_inflation
                scenario.growth_cushion = growth_cushion
                scenario.tax_on_sale_proceeds = tax_on_sale_proceeds
                scenario.tax_on_dividends = tax_on_dividends
                scenario.asset_returns = asset_returns
                scenario.trim_rules = trim_rules
                scenario.fidelis_cap = fidelis_cap
                scenario.is_default = (data.default_scenario_id == scenario_data.name)
                # Explicitly update the updated_at timestamp
                scenario.updated_at = datetime.now(timezone.utc)
            else:
                # Create new
                scenario = ScenarioModel(
                    id=scenario_id,
                    name=scenario_data.name,
                    inflation=scenario_data.inflation,
                    romanian_inflation=romanian_inflation,
                    growth_cushion=growth_cushion,
                    tax_on_sale_proceeds=tax_on_sale_proceeds,
                    tax_on_dividends=tax_on_dividends,
                    asset_returns=asset_returns,
                    trim_rules=trim_rules,
                    fidelis_cap=fidelis_cap,
                    is_default=(data.default_scenario_id == scenario_data.name)
                )
                db.add(scenario)
        
        # Save family members
        if data.familyMembers:
            # Get all existing member IDs
            existing_member_ids = {m.id for m in db.query(FamilyMemberModel).all()}
            incoming_member_ids = {m.id for m in data.familyMembers}
            
            # Delete members that are no longer in the incoming data
            members_to_delete = existing_member_ids - incoming_member_ids
            if members_to_delete:
                db.query(FamilyMemberModel).filter(
                    FamilyMemberModel.id.in_(list(members_to_delete))
                ).delete(synchronize_session=False)
            
            # Create or update family members
            for member_data in data.familyMembers:
                member = db.query(FamilyMemberModel).filter(
                    FamilyMemberModel.id == member_data.id
                ).first()
                
                # Pydantic models use attribute access - use displayOrder (camelCase) as defined in schema
                # With populate_by_name=True, we can access as displayOrder
                try:
                    display_order = member_data.displayOrder if member_data.displayOrder is not None else 0
                except AttributeError:
                    # Fallback to snake_case if camelCase doesn't work
                    display_order = getattr(member_data, 'display_order', 0) or 0
                
                if member:
                    # Update existing
                    member.name = member_data.name
                    member.amount = member_data.amount
                    member.display_order = display_order
                    member.updated_at = datetime.now(timezone.utc)
                else:
                    # Create new
                    member = FamilyMemberModel(
                        id=member_data.id,
                        name=member_data.name,
                        amount=member_data.amount,
                        display_order=display_order
                    )
                    db.add(member)
        
        db.commit()
        return {"status": "success", "message": "Data saved successfully"}
    except Exception as e:
        db.rollback()
        import traceback
        error_detail = f"Error saving data: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR in save_data: {error_detail}")  # Print to console for debugging
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/api/data/load", response_model=LoadDataResponse)
async def load_data(db: Session = Depends(get_db)):
    """Load all portfolios and scenarios."""
    try:
        portfolios = db.query(PortfolioModel).all()
        scenarios = db.query(ScenarioModel).all()
        family_members = db.query(FamilyMemberModel).order_by(FamilyMemberModel.display_order, FamilyMemberModel.created_at).all()
        
        default_scenario = db.query(ScenarioModel).filter(
            ScenarioModel.is_default == True
        ).first()
        
        # Convert family members to response format
        family_member_responses = []
        for m in family_members:
            family_member_responses.append(FamilyMemberResponse(
                id=m.id,
                name=m.name,
                amount=m.amount,
                displayOrder=m.display_order if m.display_order is not None else 0,
                created_at=m.created_at,
                updated_at=m.updated_at
            ))
        
        return LoadDataResponse(
            portfolios=[PortfolioResponse(
                id=p.id,
                name=p.name,
                color=p.color,
                capital=p.capital,
                goal=getattr(p, 'goal', None),
                riskLabel=getattr(p, 'risk_label', None),
                horizon=getattr(p, 'horizon', None),
                selectedStrategy=getattr(p, 'selected_strategy', None),
                overperformStrategy=getattr(p, 'overperform_strategy', None),
                allocation=p.allocation,
                # memberAllocations removed - we now use per-member portfolios instead
                rules=p.rules,
                strategy=getattr(p, 'strategy', None),
                created_at=p.created_at,
                updated_at=p.updated_at
            ) for p in portfolios],
            scenarios=[ScenarioResponse(
                name=s.name,
                inflation=s.inflation,
                romanianInflation=getattr(s, 'romanian_inflation', None) or 0.08,
                growthCushion=getattr(s, 'growth_cushion', None) or 0.02,
                taxOnSaleProceeds=getattr(s, 'tax_on_sale_proceeds', None),
                taxOnDividends=getattr(s, 'tax_on_dividends', None),
                assetReturns=s.asset_returns,
                trimRules=s.trim_rules,
                fidelisCap=s.fidelis_cap,
                is_default=s.is_default,
                created_at=s.created_at,
                updated_at=s.updated_at
            ) for s in scenarios],
            familyMembers=family_member_responses if len(family_member_responses) > 0 else None,
            default_scenario_id=default_scenario.name if default_scenario else None
        )
    except Exception as e:
        import traceback
        error_detail = f"Error loading data: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR in load_data: {error_detail}")  # Print to console for debugging
        raise HTTPException(status_code=500, detail=error_detail)


@app.delete("/api/data/clear")
async def clear_data(db: Session = Depends(get_db)):
    """Clear all data (for testing/reset)."""
    try:
        db.query(PortfolioModel).delete()
        db.query(ScenarioModel).delete()
        db.commit()
        return {"status": "success", "message": "All data cleared"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error clearing data: {str(e)}")

