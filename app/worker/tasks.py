"""
Celery tasks for investment analysis processing.
"""

from app.worker.main import celery_app
from app.database import SessionLocal
from app.models import AnalysisRequest, AnalysisStatus
from app.services.data_fetcher import DataFetcher
from app.services.metric_computer import MetricComputer
from app.services.narrative_generator import NarrativeGenerator
from app.services.pdf_generator import PDFGenerator
from app.schemas import InvestmentMemorandum, CompanyInfo
from datetime import datetime
import json
import os
import traceback


@celery_app.task(bind=True, name="process_analysis")
def process_analysis_task(self, request_id: int):
    """
    Main task for processing an investment analysis.
    
    Steps:
    1. Fetch market data
    2. Compute metrics using ruleset
    3. Generate narrative with guardrails
    4. Validate against schema
    5. Generate PDF
    6. Save results
    """
    db = SessionLocal()
    
    try:
        # Get analysis request
        analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == request_id).first()
        if not analysis_request:
            raise ValueError(f"Analysis request {request_id} not found")
        
        # Update status to processing
        analysis_request.status = AnalysisStatus.PROCESSING
        db.commit()
        
        # Determine ruleset version
        ruleset_version = analysis_request.ruleset_version or "latest"
        
        # Step 1: Fetch data
        self.update_state(state="PROGRESS", meta={"step": "fetching_data", "progress": 10})
        data_fetcher = DataFetcher()
        market_data = data_fetcher.fetch_ticker_data(analysis_request.ticker)
        
        if not market_data:
            raise ValueError(f"Failed to fetch data for ticker {analysis_request.ticker}")
        
        # Step 2: Compute metrics
        self.update_state(state="PROGRESS", meta={"step": "computing_metrics", "progress": 30})
        metric_computer = MetricComputer(ruleset_version=ruleset_version)
        metrics = metric_computer.compute_all_metrics(market_data, analysis_request.ticker)
        
        # Step 3: Generate narrative
        self.update_state(state="PROGRESS", meta={"step": "generating_narrative", "progress": 60})
        narrative_generator = NarrativeGenerator(ruleset_version=ruleset_version)
        narrative = narrative_generator.generate_narrative(metrics, market_data, analysis_request.ticker)
        
        # Step 4: Build memorandum
        self.update_state(state="PROGRESS", meta={"step": "building_memorandum", "progress": 80})
        
        # Create CompanyInfo from market data
        company_info_dict = market_data.get("company_info", {})
        company_info = CompanyInfo(
            ticker=company_info_dict.get("ticker", analysis_request.ticker),
            name=company_info_dict.get("name", analysis_request.ticker),
            sector=company_info_dict.get("sector"),
            industry=company_info_dict.get("industry"),
            exchange=company_info_dict.get("exchange")
        )
        
        memorandum = InvestmentMemorandum(
            version="1.0.0",
            generated_at=datetime.utcnow().isoformat(),
            ticker=analysis_request.ticker,
            ruleset_version=ruleset_version,
            company=company_info,
            analysis_date=datetime.utcnow().date().isoformat(),
            data_period_end=market_data.get("period_end", datetime.utcnow().date().isoformat()),
            metrics=metrics,
            narrative=narrative,
            summary=metric_computer.generate_summary(metrics),
            audit_trail={
                "data_source": "yfinance",
                "data_fetched_at": datetime.utcnow().isoformat(),
                "ruleset_version": ruleset_version,
                "computation_steps": metric_computer.get_computation_steps()
            }
        )
        
        # Validate schema
        memorandum_dict = memorandum.dict()
        
        # Step 5: Save JSON
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        
        json_path = os.path.join(output_dir, f"memorandum_{analysis_request.ticker}_{request_id}.json")
        with open(json_path, 'w') as f:
            json.dump(memorandum_dict, f, indent=2)
        
        analysis_request.json_output_path = json_path
        
        # Step 6: Generate PDF
        self.update_state(state="PROGRESS", meta={"step": "generating_pdf", "progress": 90})
        pdf_generator = PDFGenerator()
        pdf_path = os.path.join(output_dir, f"memorandum_{analysis_request.ticker}_{request_id}.pdf")
        pdf_generator.generate_pdf(memorandum_dict, pdf_path)
        
        analysis_request.pdf_output_path = pdf_path
        
        # Update status to completed
        analysis_request.status = AnalysisStatus.COMPLETED
        analysis_request.completed_at = datetime.utcnow()
        db.commit()
        
        return {
            "status": "completed",
            "request_id": request_id,
            "json_path": json_path,
            "pdf_path": pdf_path
        }
        
    except Exception as e:
        # Update status to failed
        if 'analysis_request' in locals():
            analysis_request.status = AnalysisStatus.FAILED
            analysis_request.error_message = str(e) + "\n" + traceback.format_exc()
            db.commit()
        
        raise
    
    finally:
        db.close()

