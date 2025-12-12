"""
Main FastAPI application for investment analysis platform.
Handles user input, orchestration, and document delivery.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import os
from datetime import datetime

from app.database import get_db, init_db
from app.models import AnalysisRequest, AnalysisStatus
from app.worker.tasks import process_analysis_task

app = FastAPI(
    title="Investment Analysis Platform",
    description="Rules-based investment memorandum generator",
    version="1.0.0"
)


class TickerRequest(BaseModel):
    """Request model for stock ticker analysis."""
    ticker: str = Field(..., description="Stock ticker symbol", min_length=1, max_length=10)
    ruleset_version: Optional[str] = Field(None, description="Version of ruleset to use (defaults to latest)")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "investment-analysis-platform",
        "version": "1.0.0"
    }


@app.post("/api/analyze", status_code=202)
async def analyze_ticker(request: TickerRequest):
    """
    Submit a stock ticker for analysis.
    Returns a job ID that can be used to check status and retrieve results.
    """
    ticker = request.ticker.upper().strip()
    
    # Validate ticker format (basic validation)
    if not ticker.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker format")
    
    # Create analysis request record
    db = next(get_db())
    analysis_request = AnalysisRequest(
        ticker=ticker,
        ruleset_version=request.ruleset_version,
        status=AnalysisStatus.PENDING,
        created_at=datetime.utcnow()
    )
    db.add(analysis_request)
    db.commit()
    db.refresh(analysis_request)
    
    # Queue background task
    process_analysis_task.delay(analysis_request.id)
    
    return {
        "job_id": analysis_request.id,
        "ticker": ticker,
        "status": "pending",
        "message": "Analysis queued for processing"
    }


@app.get("/api/status/{job_id}")
async def get_status(job_id: int):
    """Get the status of an analysis job."""
    db = next(get_db())
    analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == job_id).first()
    
    if not analysis_request:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": analysis_request.id,
        "ticker": analysis_request.ticker,
        "status": analysis_request.status.value,
        "created_at": analysis_request.created_at.isoformat(),
        "completed_at": analysis_request.completed_at.isoformat() if analysis_request.completed_at else None,
        "error": analysis_request.error_message
    }


@app.get("/api/result/{job_id}/json")
async def get_json_result(job_id: int):
    """Retrieve the JSON result of a completed analysis."""
    db = next(get_db())
    analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == job_id).first()
    
    if not analysis_request:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if analysis_request.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not completed. Current status: {analysis_request.status.value}"
        )
    
    if not analysis_request.json_output_path:
        raise HTTPException(status_code=404, detail="JSON result not found")
    
    import json
    with open(analysis_request.json_output_path, 'r') as f:
        result = json.load(f)
    
    return JSONResponse(content=result)


@app.get("/api/result/{job_id}/pdf")
async def get_pdf_result(job_id: int):
    """Retrieve the PDF result of a completed analysis."""
    db = next(get_db())
    analysis_request = db.query(AnalysisRequest).filter(AnalysisRequest.id == job_id).first()
    
    if not analysis_request:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if analysis_request.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not completed. Current status: {analysis_request.status.value}"
        )
    
    if not analysis_request.pdf_output_path:
        raise HTTPException(status_code=404, detail="PDF result not found")
    
    if not os.path.exists(analysis_request.pdf_output_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    
    return FileResponse(
        analysis_request.pdf_output_path,
        media_type="application/pdf",
        filename=f"investment_memorandum_{analysis_request.ticker}_{job_id}.pdf"
    )


@app.get("/api/jobs")
async def list_jobs(limit: int = 20, offset: int = 0):
    """List recent analysis jobs."""
    db = next(get_db())
    jobs = db.query(AnalysisRequest).order_by(AnalysisRequest.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "jobs": [
            {
                "job_id": job.id,
                "ticker": job.ticker,
                "status": job.status.value,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
            for job in jobs
        ],
        "limit": limit,
        "offset": offset
    }

