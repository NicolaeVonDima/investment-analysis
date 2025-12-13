from datetime import datetime, timedelta, timezone, date

from app.services.browse_lite import is_fresh, parse_daily_adjusted_latest, parse_time_series_daily_closes
from app.services.ticker_resolution import choose_best_match, normalize_query, valid_ticker_format


def test_is_fresh_true_within_24h():
    now = datetime(2025, 12, 13, 12, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    last = now - timedelta(hours=23, minutes=59)
    assert is_fresh(last, now) is True


def test_is_fresh_false_at_24h_or_more():
    now = datetime(2025, 12, 13, 12, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    last = now - timedelta(hours=24)
    assert is_fresh(last, now) is False


def test_parse_daily_adjusted_latest_extracts_latest_close_and_change_pct():
    payload = {
        "Time Series (Daily)": {
            "2025-12-12": {"4. close": "110.0"},
            "2025-12-11": {"4. close": "100.0"},
        }
    }
    out = parse_daily_adjusted_latest(payload)
    assert out is not None
    assert out.as_of_date == date(2025, 12, 12)
    assert out.close == 110.0
    assert abs(out.change_pct - 0.10) < 1e-9


def test_valid_ticker_format_and_normalize():
    assert normalize_query(" goog ") == "GOOG"
    assert valid_ticker_format("AAPL") is True
    assert valid_ticker_format("BRK.B") is True
    assert valid_ticker_format("RDS-A") is True
    assert valid_ticker_format("AAPL!") is False
    assert valid_ticker_format("") is False


def test_choose_best_match_prefers_exact_symbol():
    query = "AAPL"
    matches = [
        {"1. symbol": "AAP", "4. region": "United States", "9. matchScore": "0.90"},
        {"1. symbol": "AAPL", "4. region": "United States", "9. matchScore": "0.10"},
    ]
    best, suggestions = choose_best_match(query, matches)
    assert best is not None
    assert (best.get("1. symbol") or "").upper() == "AAPL"
    assert "AAPL" in suggestions


def test_parse_time_series_daily_closes_returns_ascending_series():
    payload = {
        "Time Series (Daily)": {
            "2025-12-12": {"4. close": "100.0"},
            "2025-12-11": {"4. close": "90.0"},
        }
    }
    out = parse_time_series_daily_closes(payload, limit=10)
    assert out[0][0].isoformat() == "2025-12-11"
    assert out[0][1] == 90.0
    assert out[-1][0].isoformat() == "2025-12-12"
    assert out[-1][1] == 100.0


