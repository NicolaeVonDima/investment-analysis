from datetime import date

from app.worker import tasks


def test_years_ago_safe_handles_feb_29():
    d = date(2024, 2, 29)
    out = tasks._years_ago_safe(d, 5)
    assert out == date(2019, 2, 28)


