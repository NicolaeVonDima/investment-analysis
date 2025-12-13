from datetime import date

from app.services.fundamentals_series import compute_fundamentals_series


class _Snap:
    def __init__(self, period_end: date, payload: dict):
        self.period_end = period_end
        self.payload = payload


def test_compute_fundamentals_series_values_and_sign_conventions():
    q1 = date(2025, 9, 30)
    q2 = date(2025, 6, 30)

    cash = [
        _Snap(
            q2,
            {
                "operatingCashflow": "100",
                "capitalExpenditures": "-20",
                "dividendsPaid": "-5",
                "paymentsForRepurchaseOfCommonStock": "-7",
                "stockBasedCompensation": "3",
            },
        ),
        _Snap(
            q1,
            {
                "operatingCashflow": "120",
                "capitalExpenditures": "-30",
                "dividendsPaid": "-6",
                "paymentsForRepurchaseOfCommonStock": "-8",
                "stockBasedCompensation": "4",
            },
        ),
    ]
    income = [
        _Snap(q2, {"netIncome": "40"}),
        _Snap(q1, {"netIncome": "48"}),
    ]
    balance = [
        _Snap(q2, {"shortTermDebt": "10", "longTermDebt": "90"}),
        _Snap(q1, {"shortTermDebt": "12", "longTermDebt": "88"}),
    ]

    bundle = compute_fundamentals_series(
        cash_flows=cash,
        incomes=income,
        balances=balance,
        requested=["fcf", "sbc", "netIncome", "debt", "dividends", "buybacks"],
    )

    assert bundle.unavailable == []
    assert bundle.as_of == q1

    # FCF = OCF - CapEx (CapEx is negative in AV strings)
    fcf = dict(bundle.series["fcf"])
    assert fcf[q2] == 120.0
    assert fcf[q1] == 150.0

    # Dividends/Buybacks are absolute "spent" amounts
    div = dict(bundle.series["dividends"])
    bb = dict(bundle.series["buybacks"])
    assert div[q2] == 5.0 and div[q1] == 6.0
    assert bb[q2] == 7.0 and bb[q1] == 8.0

    sbc = dict(bundle.series["sbc"])
    assert sbc[q2] == 3.0 and sbc[q1] == 4.0

    ni = dict(bundle.series["netIncome"])
    assert ni[q2] == 40.0 and ni[q1] == 48.0

    debt = dict(bundle.series["debt"])
    assert debt[q2] == 100.0
    assert debt[q1] == 100.0


def test_series_marked_unavailable_when_all_none():
    q1 = date(2025, 9, 30)
    cash = [_Snap(q1, {"operatingCashflow": "10", "capitalExpenditures": "-1"})]
    income = [_Snap(q1, {"netIncome": "2"})]
    balance = [_Snap(q1, {"shortTermDebt": "1", "longTermDebt": "9"})]

    # Request sbc but don't provide any sbc fields -> should be unavailable + omitted
    bundle = compute_fundamentals_series(
        cash_flows=cash,
        incomes=income,
        balances=balance,
        requested=["fcf", "sbc"],
    )
    assert "sbc" in bundle.unavailable
    assert "sbc" not in bundle.series
    assert "fcf" in bundle.series


