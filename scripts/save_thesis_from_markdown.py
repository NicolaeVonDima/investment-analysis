#!/usr/bin/env python3
"""
Script to save investment thesis from markdown file to database via API.
Usage: python scripts/save_thesis_from_markdown.py <markdown_file> <ticker>
"""

import sys
import re
import requests
from datetime import datetime, date
from pathlib import Path

API_URL = "http://localhost:8000/api"


def parse_markdown_thesis(md_file: str) -> dict:
    """Parse markdown file and extract thesis components."""
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract title (first line after #)
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "Investment Memorandum"
    
    # Extract date
    date_match = re.search(r'\*\*Date:\*\* (.+)', content)
    thesis_date_str = date_match.group(1).strip() if date_match else datetime.now().strftime("%B %d, %Y")
    # Try to parse date
    try:
        thesis_date = datetime.strptime(thesis_date_str, "%B %d, %Y").date()
    except:
        thesis_date = date.today()
    
    # Extract current price
    price_match = re.search(r'\*\*Current Price:\*\* \$?([\d.]+)', content)
    current_price = float(price_match.group(1)) if price_match else None
    
    # Extract recommendation
    rec_match = re.search(r'\*\*Recommendation:\*\* (.+)', content)
    recommendation = rec_match.group(1).strip() if rec_match else "HOLD"
    
    # Extract executive summary (between ## Executive Summary and next ##)
    exec_match = re.search(r'## Executive Summary\n\n(.+?)(?=\n## |$)', content, re.DOTALL)
    executive_summary = exec_match.group(1).strip() if exec_match else ""
    
    # Extract investment thesis content (between ## Investment Thesis and ## Action Plan or ## Conclusion)
    thesis_match = re.search(r'## Investment Thesis[^\n]*\n\n(.+?)(?=\n## (?:Action Plan|Conclusion)|$)', content, re.DOTALL)
    thesis_content = thesis_match.group(1).strip() if thesis_match else ""
    
    # Extract action plan (between ## Action Plan and ## Conclusion or end)
    action_match = re.search(r'## Action Plan\n\n(.+?)(?=\n## Conclusion|$)', content, re.DOTALL)
    action_plan = action_match.group(1).strip() if action_match else None
    
    # Extract conclusion (after ## Conclusion)
    conclusion_match = re.search(r'## Conclusion\n\n(.+?)(?=\n---|$)', content, re.DOTALL)
    conclusion = conclusion_match.group(1).strip() if conclusion_match else None
    
    return {
        "title": title,
        "date": thesis_date.isoformat(),
        "current_price": current_price,
        "recommendation": recommendation,
        "executive_summary": executive_summary,
        "thesis_content": thesis_content,
        "action_plan": action_plan,
        "conclusion": conclusion,
    }


def save_thesis(ticker: str, thesis_data: dict):
    """Save thesis to database via API."""
    url = f"{API_URL}/instruments/{ticker}/thesis"
    
    response = requests.post(url, json=thesis_data)
    
    if response.status_code in (200, 201):
        print(f"✓ Successfully saved investment thesis for {ticker}")
        print(f"  Title: {thesis_data['title']}")
        print(f"  Date: {thesis_data['date']}")
        print(f"  Recommendation: {thesis_data['recommendation']}")
        return True
    else:
        print(f"✗ Failed to save thesis: {response.status_code}")
        print(f"  Error: {response.text}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/save_thesis_from_markdown.py <markdown_file> <ticker>")
        sys.exit(1)
    
    md_file = sys.argv[1]
    ticker = sys.argv[2].upper()
    
    if not Path(md_file).exists():
        print(f"Error: File not found: {md_file}")
        sys.exit(1)
    
    print(f"Parsing markdown file: {md_file}")
    thesis_data = parse_markdown_thesis(md_file)
    
    print(f"\nSaving thesis for {ticker}...")
    success = save_thesis(ticker, thesis_data)
    
    sys.exit(0 if success else 1)

