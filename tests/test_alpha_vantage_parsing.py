from datetime import date

from app.services.alpha_vantage_client import parse_global_quote_price


def test_parse_global_quote_price_happy_path():
    payload = {
        "provider": "alpha_vantage",
        "endpoint": "GLOBAL_QUOTE",
        "symbol": "ADBE",
        "fetched_at": "2025-12-13T00:00:00Z",
        "payload": {
            "Global Quote": {
                "01. symbol": "ADBE",
                "05. price": "612.34",
                "07. latest trading day": "2025-12-12",
            }
        },
    }
    out = parse_global_quote_price(payload)
    assert out["price"] == 612.34
    assert out["as_of_date"] == date(2025, 12, 12)


def test_parse_global_quote_price_missing_fields():
    out = parse_global_quote_price({"payload": {}})
    assert out["price"] is None
    assert out["as_of_date"] is None


