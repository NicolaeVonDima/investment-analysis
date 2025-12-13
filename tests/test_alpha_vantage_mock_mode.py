import os


def test_alpha_vantage_mock_mode_symbol_search_no_api_key(monkeypatch):
    monkeypatch.setenv("ALPHAVANTAGE_MOCK", "1")
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    from app.services.alpha_vantage_client import AlphaVantageClient

    client = AlphaVantageClient()
    out = client.symbol_search("AAPL")
    payload = out.get("payload")
    assert isinstance(payload, dict)
    matches = payload.get("bestMatches")
    assert isinstance(matches, list)
    assert matches and matches[0].get("1. symbol") == "AAPL"


