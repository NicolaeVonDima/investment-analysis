"""
Data fetching service for market data.
Uses yfinance as the initial data provider, designed to be replaceable.
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class DataFetcher:
    """Fetches market data for a given ticker."""
    
    def __init__(self, provider: str = "yfinance"):
        """
        Initialize data fetcher.
        
        Args:
            provider: Data provider name (currently only 'yfinance' supported)
        """
        self.provider = provider
    
    def fetch_ticker_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary containing market data, financials, and company info
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get historical data (1 year)
            hist = stock.history(period="1y")
            
            # Get financial statements
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            cashflow = stock.cashflow
            
            # Get quarterly data
            quarterly_financials = stock.quarterly_financials
            quarterly_balance_sheet = stock.quarterly_balance_sheet
            quarterly_cashflow = stock.quarterly_cashflow
            
            # Extract key metrics
            current_price = hist['Close'].iloc[-1] if not hist.empty else None
            price_52w_high = hist['High'].max() if not hist.empty else None
            price_52w_low = hist['Low'].min() if not hist.empty else None
            
            return {
                "ticker": ticker,
                "company_info": {
                    "ticker": ticker,
                    "name": info.get("longName") or info.get("shortName", ticker),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "exchange": info.get("exchange"),
                },
                "current_price": float(current_price) if current_price else None,
                "price_52w_high": float(price_52w_high) if price_52w_high else None,
                "price_52w_low": float(price_52w_low) if price_52w_low else None,
                "historical_data": hist.to_dict('records') if not hist.empty else [],
                "financials": financials.to_dict() if not financials.empty else {},
                "balance_sheet": balance_sheet.to_dict() if not balance_sheet.empty else {},
                "cashflow": cashflow.to_dict() if not cashflow.empty else {},
                "quarterly_financials": quarterly_financials.to_dict() if not quarterly_financials.empty else {},
                "quarterly_balance_sheet": quarterly_balance_sheet.to_dict() if not quarterly_balance_sheet.empty else {},
                "quarterly_cashflow": quarterly_cashflow.to_dict() if not quarterly_cashflow.empty else {},
                "info": info,
                "period_end": datetime.now().date().isoformat(),
                "fetched_at": datetime.utcnow().isoformat(),
                "provider": self.provider
            }
        except Exception as e:
            print(f"Error fetching data for {ticker}: {str(e)}")
            return None

