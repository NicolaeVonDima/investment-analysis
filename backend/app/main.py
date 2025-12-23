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
from app.models import PortfolioModel, ScenarioModel
from app.schemas import (
    PortfolioCreate,
    PortfolioResponse,
    ScenarioCreate,
    ScenarioResponse,
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
            overperform_strategy = getattr(portfolio_data, 'overperformStrategy', None) or getattr(portfolio_data, 'overperform_strategy', None)
            
            if portfolio:
                # Update existing
                portfolio.name = portfolio_data.name
                portfolio.color = portfolio_data.color
                portfolio.capital = portfolio_data.capital
                portfolio.goal = portfolio_data.goal
                portfolio.risk_label = risk_label
                portfolio.horizon = horizon
                portfolio.overperform_strategy = overperform_strategy
                portfolio.allocation = portfolio_data.allocation
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
                    overperform_strategy=overperform_strategy,
                    allocation=portfolio_data.allocation,
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
            tax_on_sale_proceeds = getattr(scenario_data, 'taxOnSaleProceeds', None) or getattr(scenario_data, 'tax_on_sale_proceeds', None)
            tax_on_dividends = getattr(scenario_data, 'taxOnDividends', None) or getattr(scenario_data, 'tax_on_dividends', None)
            
            if scenario:
                # Update existing
                scenario.name = scenario_data.name
                scenario.inflation = scenario_data.inflation
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
                    tax_on_sale_proceeds=tax_on_sale_proceeds,
                    tax_on_dividends=tax_on_dividends,
                    asset_returns=asset_returns,
                    trim_rules=trim_rules,
                    fidelis_cap=fidelis_cap,
                    is_default=(data.default_scenario_id == scenario_data.name)
                )
                db.add(scenario)
        
        db.commit()
        return {"status": "success", "message": "Data saved successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving data: {str(e)}")


@app.get("/api/data/load", response_model=LoadDataResponse)
async def load_data(db: Session = Depends(get_db)):
    """Load all portfolios and scenarios."""
    try:
        portfolios = db.query(PortfolioModel).all()
        scenarios = db.query(ScenarioModel).all()
        
        default_scenario = db.query(ScenarioModel).filter(
            ScenarioModel.is_default == True
        ).first()
        
        return LoadDataResponse(
            portfolios=[PortfolioResponse(
                id=p.id,
                name=p.name,
                color=p.color,
                capital=p.capital,
                goal=getattr(p, 'goal', None),
                riskLabel=getattr(p, 'risk_label', None),
                horizon=getattr(p, 'horizon', None),
                overperformStrategy=getattr(p, 'overperform_strategy', None),
                allocation=p.allocation,
                rules=p.rules,
                strategy=getattr(p, 'strategy', None),
                created_at=p.created_at,
                updated_at=p.updated_at
            ) for p in portfolios],
            scenarios=[ScenarioResponse(
                name=s.name,
                inflation=s.inflation,
                taxOnSaleProceeds=getattr(s, 'tax_on_sale_proceeds', None),
                taxOnDividends=getattr(s, 'tax_on_dividends', None),
                assetReturns=s.asset_returns,
                trimRules=s.trim_rules,
                fidelisCap=s.fidelis_cap,
                is_default=s.is_default,
                created_at=s.created_at,
                updated_at=s.updated_at
            ) for s in scenarios],
            default_scenario_id=default_scenario.name if default_scenario else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading data: {str(e)}")


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

