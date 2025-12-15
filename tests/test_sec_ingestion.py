from datetime import date

from app.services.sec_ingestion import select_filings, _parse_date_safe


def _make_submissions(forms, filing_dates, accessions, primary_docs, report_dates=None):
    return {
        "filings": {
            "recent": {
                "form": forms,
                "filingDate": filing_dates,
                "accessionNumber": accessions,
                "primaryDocument": primary_docs,
                "reportDate": report_dates or [None] * len(forms),
            }
        }
    }


def test_parse_date_safe_handles_iso_and_invalid():
    assert _parse_date_safe("2025-12-15") == date(2025, 12, 15)
    assert _parse_date_safe("") is None
    assert _parse_date_safe(None) is None
    # Non-ISO should not raise
    assert _parse_date_safe("15/12/2025") is None


def test_select_filings_applies_lookback_and_orders_deterministically():
    forms = ["10-K", "10-K", "10-Q", "10-Q", "8-K"]
    filing_dates = [
        "2024-01-31",
        "2023-01-31",
        "2024-03-31",
        "2023-03-31",
        "2024-05-01",
    ]
    accessions = [
        "0000000001-24-000001",
        "0000000001-23-000001",
        "0000000001-24-000002",
        "0000000001-23-000002",
        "0000000001-24-000003",
    ]
    primary_docs = ["k2024.htm", "k2023.htm", "q2024.htm", "q2023.htm", "other.htm"]

    subs = _make_submissions(forms, filing_dates, accessions, primary_docs)

    # N=1 10-K, M=1 10-Q, skip non-10K/10Q
    out = select_filings(subs, lookback_10k=1, lookback_10q=1, include_amendments=False)
    assert len(out) == 2
    # Should contain the most recent K and Q
    forms_out = {r["form"] for r in out}
    assert forms_out == {"10-K", "10-Q"}
    # Overall ordering should be by filing_date desc, then accession desc
    dates = [r["filing_date"] for r in out]
    assert dates == sorted(dates, reverse=True)


def test_select_filings_includes_amendments_when_enabled():
    forms = ["10-K", "10-K/A", "10-Q", "10-Q/A"]
    filing_dates = [
        "2024-01-31",
        "2024-02-15",
        "2024-03-31",
        "2024-04-15",
    ]
    accessions = [
        "0000000001-24-000001",
        "0000000001-24-000002",
        "0000000001-24-000003",
        "0000000001-24-000004",
    ]
    primary_docs = ["k.htm", "k_a.htm", "q.htm", "q_a.htm"]

    subs = _make_submissions(forms, filing_dates, accessions, primary_docs)

    out_no_amend = select_filings(subs, lookback_10k=5, lookback_10q=5, include_amendments=False)
    forms_no_amend = {r["form"] for r in out_no_amend}
    assert "10-K/A" not in forms_no_amend
    assert "10-Q/A" not in forms_no_amend

    out_with_amend = select_filings(subs, lookback_10k=5, lookback_10q=5, include_amendments=True)
    forms_with_amend = {r["form"] for r in out_with_amend}
    assert "10-K/A" in forms_with_amend
    assert "10-Q/A" in forms_with_amend


