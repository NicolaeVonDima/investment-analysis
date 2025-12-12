"""
Metric computation service using versioned rulesets.
All metrics must be explicitly defined in rulesets - no ad-hoc calculations.
"""

import os
import json
from typing import List, Dict, Any
from datetime import datetime
from app.schemas import FinancialMetric, MetricValue


class MetricComputer:
    """Computes financial metrics using versioned rulesets."""
    
    def __init__(self, ruleset_version: str = "latest"):
        """
        Initialize metric computer.
        
        Args:
            ruleset_version: Version of ruleset to use
        """
        self.ruleset_version = ruleset_version
        self.ruleset = self._load_ruleset(ruleset_version)
        self.computation_steps = []
    
    def _load_ruleset(self, version: str) -> Dict[str, Any]:
        """Load ruleset from file."""
        if version == "latest":
            # Find latest version
            ruleset_dir = os.path.join(os.getcwd(), "rulesets")
            if not os.path.exists(ruleset_dir):
                # Fallback to default ruleset
                return self._get_default_ruleset()
            
            versions = [f for f in os.listdir(ruleset_dir) if f.endswith('.json')]
            if not versions:
                return self._get_default_ruleset()
            
            version_file = sorted(versions)[-1]
            version = version_file.replace('.json', '')
        
        ruleset_path = os.path.join(os.getcwd(), "rulesets", f"{version}.json")
        
        if os.path.exists(ruleset_path):
            with open(ruleset_path, 'r') as f:
                return json.load(f)
        else:
            return self._get_default_ruleset()
    
    def _get_default_ruleset(self) -> Dict[str, Any]:
        """Return default ruleset if no file exists."""
        return {
            "version": "1.0.0",
            "metrics": [
                {
                    "name": "market_cap",
                    "description": "Market capitalization",
                    "category": "valuation",
                    "formula": "current_price * shares_outstanding",
                    "unit": "USD"
                },
                {
                    "name": "pe_ratio",
                    "description": "Price-to-Earnings ratio",
                    "category": "valuation",
                    "formula": "current_price / earnings_per_share",
                    "unit": "ratio"
                },
                {
                    "name": "price_to_book",
                    "description": "Price-to-Book ratio",
                    "category": "valuation",
                    "unit": "ratio"
                }
            ]
        }
    
    def compute_all_metrics(self, market_data: Dict[str, Any], ticker: str) -> List[FinancialMetric]:
        """
        Compute all metrics defined in the ruleset.
        
        Args:
            market_data: Market data from DataFetcher
            ticker: Stock ticker symbol
            
        Returns:
            List of computed FinancialMetric objects
        """
        metrics = []
        computed_at = datetime.utcnow().isoformat()
        
        for metric_def in self.ruleset.get("metrics", []):
            try:
                value = self._compute_metric(metric_def, market_data)
                
                metric = FinancialMetric(
                    name=metric_def["name"],
                    description=metric_def.get("description", ""),
                    value=MetricValue(
                        value=value,
                        unit=metric_def.get("unit", "USD"),
                        source="computed",
                        computed_at=computed_at,
                        ruleset_version=self.ruleset.get("version", self.ruleset_version)
                    ),
                    category=metric_def.get("category", "general")
                )
                metrics.append(metric)
                
                self.computation_steps.append({
                    "metric": metric_def["name"],
                    "value": value,
                    "computed_at": computed_at
                })
            except Exception as e:
                # Log error but continue with other metrics
                print(f"Error computing metric {metric_def.get('name')}: {str(e)}")
                self.computation_steps.append({
                    "metric": metric_def.get("name"),
                    "error": str(e)
                })
        
        return metrics
    
    def _compute_metric(self, metric_def: Dict[str, Any], market_data: Dict[str, Any]) -> float:
        """
        Compute a single metric based on its definition.
        
        This is a simplified implementation. In production, you'd want
        a more robust formula evaluator.
        """
        name = metric_def["name"]
        
        # Extract common values
        current_price = market_data.get("current_price", 0)
        info = market_data.get("info", {})
        
        # Simple metric computation logic
        if name == "market_cap":
            shares_outstanding = info.get("sharesOutstanding", 0)
            return current_price * shares_outstanding if shares_outstanding else 0
        
        elif name == "pe_ratio":
            trailing_pe = info.get("trailingPE")
            forward_pe = info.get("forwardPE")
            return trailing_pe or forward_pe or 0
        
        elif name == "price_to_book":
            return info.get("priceToBook", 0)
        
        elif name == "dividend_yield":
            return info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0
        
        elif name == "profit_margin":
            profit_margin = info.get("profitMargins", 0)
            return profit_margin * 100 if profit_margin else 0
        
        elif name == "revenue_growth":
            revenue_growth = info.get("revenueGrowth", 0)
            return revenue_growth * 100 if revenue_growth else 0
        
        else:
            # Try to get from info directly
            return info.get(name, 0)
    
    def generate_summary(self, metrics: List[FinancialMetric]) -> Dict[str, Any]:
        """Generate summary from computed metrics."""
        summary_metrics = {}
        for metric in metrics:
            if metric.category in ["valuation", "profitability"]:
                summary_metrics[metric.name] = metric.value.value
        
        return {
            "key_metrics": summary_metrics,
            "total_metrics_computed": len(metrics),
            "categories": list(set(m.category for m in metrics))
        }
    
    def get_computation_steps(self) -> List[Dict[str, Any]]:
        """Get audit trail of computation steps."""
        return self.computation_steps

