from datetime import date

from app.services.overview import compute_fcf_series, compute_kpis


class _Snap:
    def __init__(self, period_end: date, payload: dict):
        self.period_end = period_end
        self.payload = payload


def test_compute_fcf_series_and_kpis_basic():
    # Quarterly snapshots
    q1 = date(2025, 9, 30)
    q2 = date(2025, 6, 30)

    cash = [
        _Snap(q2, {"operatingCashflow": "100", "capitalExpenditures": "-20"}),
        _Snap(q1, {"operatingCashflow": "120", "capitalExpenditures": "-30"}),
    ]
    income = [
        _Snap(q2, {"totalRevenue": "200", "netIncome": "40", "operatingIncome": "60"}),
        _Snap(q1, {"totalRevenue": "240", "netIncome": "48", "operatingIncome": "72"}),
    ]
    balance = [
        _Snap(q2, {"totalShareholderEquity": "400", "totalLiabilities": "800"}),
        _Snap(q1, {"totalShareholderEquity": "500", "totalLiabilities": "900"}),
    ]

    fcf = compute_fcf_series(cash, income)
    assert len(fcf) == 2
    assert fcf[-1].period_end == q1
    assert fcf[-1].fcf == 150.0  # 120 - (-30)
    assert abs(fcf[-1].fcf_margin - (150.0 / 240.0)) < 1e-9

    kpis = compute_kpis(income, balance, fcf)
    # ROE uses avg equity, so only second period has ROE
    assert len(kpis) == 2
    assert kpis[0].period_end == q2
    assert kpis[0].roe is None
    assert abs(kpis[1].roe - (48.0 / ((400.0 + 500.0) / 2.0))) < 1e-9
    assert abs(kpis[1].net_margin - (48.0 / 240.0)) < 1e-9
    assert abs(kpis[1].operating_margin - (72.0 / 240.0)) < 1e-9
    assert abs(kpis[1].debt_to_equity - (900.0 / 500.0)) < 1e-9


