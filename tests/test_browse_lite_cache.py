from datetime import datetime, timedelta, timezone, date

from app.services.browse_lite import is_fresh, parse_daily_adjusted_latest


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


