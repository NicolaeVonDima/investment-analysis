"""
Narrative generation service with strict guardrails.
All claims must reference computed metrics - no invented numbers.
"""

import os
import json
from typing import List, Dict, Any
from datetime import datetime
from app.schemas import NarrativeSection, FinancialMetric


class NarrativeGenerator:
    """Generates narrative sections with traceable claims."""
    
    def __init__(self, ruleset_version: str = "latest", prompt_version: str = "1.0.0"):
        """
        Initialize narrative generator.
        
        Args:
            ruleset_version: Version of ruleset to use
            prompt_version: Version of prompt template
        """
        self.ruleset_version = ruleset_version
        self.prompt_version = prompt_version
        self.prompts = self._load_prompts()
    
    def _load_prompts(self) -> Dict[str, Any]:
        """Load prompt templates."""
        prompts_path = os.path.join(os.getcwd(), "templates", "prompts.json")
        
        if os.path.exists(prompts_path):
            with open(prompts_path, 'r') as f:
                return json.load(f)
        else:
            return self._get_default_prompts()
    
    def _get_default_prompts(self) -> Dict[str, Any]:
        """Return default prompt templates."""
        return {
            "version": "1.0.0",
            "sections": [
                {
                    "title": "Company Overview",
                    "template": "Generate a brief overview of {company_name} ({ticker}), focusing on factual information from the data."
                },
                {
                    "title": "Financial Analysis",
                    "template": "Analyze the financial metrics, referencing specific computed values. Do not invent any numbers."
                },
                {
                    "title": "Valuation Assessment",
                    "template": "Assess valuation based on computed metrics. All numbers must come from the provided metrics."
                }
            ]
        }
    
    def generate_narrative(
        self,
        metrics: List[FinancialMetric],
        market_data: Dict[str, Any],
        ticker: str
    ) -> List[NarrativeSection]:
        """
        Generate narrative sections with strict guardrails.
        
        Args:
            metrics: List of computed metrics
            market_data: Market data dictionary
            ticker: Stock ticker symbol
            
        Returns:
            List of NarrativeSection objects
        """
        narrative = []
        generated_at = datetime.utcnow().isoformat()
        company_name = market_data.get("company_info", {}).get("name", ticker)
        
        # Create metric lookup
        metric_dict = {m.name: m for m in metrics}
        
        # Generate each section
        for section_def in self.prompts.get("sections", []):
            # Determine which metrics support this section
            supporting_metrics = self._get_supporting_metrics(section_def.get("title", ""), metrics)
            
            # Generate content (simplified - in production, use LLM with strict constraints)
            content = self._generate_section_content(
                section_def,
                metric_dict,
                market_data,
                company_name,
                ticker
            )
            
            section = NarrativeSection(
                title=section_def.get("title", "Untitled"),
                content=content,
                supporting_metrics=[m.name for m in supporting_metrics],
                generated_at=generated_at,
                prompt_version=self.prompt_version
            )
            narrative.append(section)
        
        return narrative
    
    def _get_supporting_metrics(self, section_title: str, metrics: List[FinancialMetric]) -> List[FinancialMetric]:
        """Determine which metrics support a given section."""
        title_lower = section_title.lower()
        
        if "valuation" in title_lower:
            return [m for m in metrics if m.category == "valuation"]
        elif "financial" in title_lower or "profitability" in title_lower:
            return [m for m in metrics if m.category in ["profitability", "financial"]]
        elif "growth" in title_lower:
            return [m for m in metrics if m.category == "growth"]
        else:
            # Return all metrics for overview sections
            return metrics[:3]  # Limit to first 3 for overview
    
    def _generate_section_content(
        self,
        section_def: Dict[str, Any],
        metric_dict: Dict[str, FinancialMetric],
        market_data: Dict[str, Any],
        company_name: str,
        ticker: str
    ) -> str:
        """
        Generate content for a section.
        
        This is a simplified template-based approach. In production,
        you'd use an LLM with strict constraints to ensure no invented numbers.
        """
        title = section_def.get("title", "")
        template = section_def.get("template", "")
        
        # Simple template-based generation
        if "Overview" in title:
            sector = market_data.get("company_info", {}).get("sector", "Unknown")
            industry = market_data.get("company_info", {}).get("industry", "Unknown")
            return f"{company_name} ({ticker}) operates in the {sector} sector, specifically in {industry}. " \
                   f"The company's current market price is ${market_data.get('current_price', 0):.2f}."
        
        elif "Financial" in title:
            # Reference actual metrics
            content = "Financial analysis based on computed metrics:\n\n"
            for metric_name, metric in list(metric_dict.items())[:5]:  # Limit to 5 metrics
                content += f"- {metric.description}: {metric.value.value:.2f} {metric.value.unit}\n"
            return content
        
        elif "Valuation" in title:
            # Reference valuation metrics
            valuation_metrics = [m for m in metric_dict.values() if m.category == "valuation"]
            if valuation_metrics:
                content = "Valuation assessment:\n\n"
                for metric in valuation_metrics[:3]:
                    content += f"- {metric.description}: {metric.value.value:.2f} {metric.value.unit}\n"
                return content
            else:
                return "Valuation metrics not available."
        
        else:
            return template.format(company_name=company_name, ticker=ticker)

