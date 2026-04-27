import json
import shutil
from pathlib import Path

import pytest

from scripts import backfill_nav

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def backfill_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backfill"
    d.mkdir()
    shutil.copy(FIXTURES / "sample_flex_2022.xml", d / "2022.xml")
    shutil.copy(FIXTURES / "sample_flex_2023.xml", d / "2023.xml")
    return d


def test_merge_xml_dir_sorts_and_dedupes(backfill_dir: Path):
    nav, cashflows = backfill_nav.merge_xml_dir(backfill_dir)
    dates = [r["date"] for r in nav]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))  # no duplicates
    # 2022-12-30 appears in both files; later (2023.xml) wins → total = 111000
    boundary = next(r for r in nav if r["date"] == "2022-12-30")
    assert boundary["total"] == 111000


def test_merge_xml_dir_full_range(backfill_dir: Path):
    nav, _ = backfill_nav.merge_xml_dir(backfill_dir)
    assert nav[0]["date"] == "2022-01-04"
    assert nav[-1]["date"] == "2023-12-29"
    assert len(nav) == 5  # 3 + 3 - 1 dup


def test_main_writes_reanchored_pct(backfill_dir: Path, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = backfill_nav.main([str(backfill_dir)])
    assert rc == 0

    pct = json.loads((tmp_path / "data" / "nav_history_pct.json").read_text(encoding="utf-8"))
    assert pct[0]["date"] == "2022-01-04"
    assert pct[0]["return_pct"] == 0.0  # re-anchor invariant
    # No cashflows in fixtures, so TWR equals raw NAV ratio:
    # 100000 -> 110000 (+10%) -> 111000 (+0.91%) -> 120000 (+8.11%) -> 130000 (+8.33%)
    # cumulative = 1.10 * 1.00909 * 1.0811 * 1.0833 ≈ 1.30  -> +30.0%
    assert pct[-1]["date"] == "2023-12-29"
    assert round(pct[-1]["return_pct"], 1) == 30.0

    dollars = json.loads((tmp_path / "data" / "nav_history.json").read_text(encoding="utf-8"))
    assert len(dollars) == len(pct)


def test_main_errors_on_empty_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        backfill_nav.main([str(empty)])


def test_skips_leading_zero_balance_days(tmp_path: Path):
    """Pre-funding rows (total=0) at the start of history must be dropped to
    avoid a divide-by-zero when re-anchoring the pct series."""
    d = tmp_path / "backfill"
    d.mkdir()
    (d / "early.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
<EquitySummaryInBase>
<EquitySummaryByReportDateInBase reportDate="2022-01-03" total="0" totalLong="0" totalShort="0" />
<EquitySummaryByReportDateInBase reportDate="2022-01-04" total="0" totalLong="0" totalShort="0" />
<EquitySummaryByReportDateInBase reportDate="2022-01-05" total="50000" totalLong="50000" totalShort="0" />
<EquitySummaryByReportDateInBase reportDate="2022-01-06" total="55000" totalLong="55000" totalShort="0" />
</EquitySummaryInBase>
</FlexStatement></FlexStatements></FlexQueryResponse>""",
        encoding="utf-8",
    )
    nav, _ = backfill_nav.merge_xml_dir(d)
    assert nav[0]["date"] == "2022-01-05"
    assert nav[0]["total"] == 50000
    assert len(nav) == 2


def test_merge_dedupes_cashflows_across_files(tmp_path: Path):
    """Same deposit event appearing in two overlapping queries must only
    count once — otherwise the TWR math double-subtracts the contribution."""
    d = tmp_path / "backfill"
    d.mkdir()
    body_template = """<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
<EquitySummaryInBase>
<EquitySummaryByReportDateInBase reportDate="2024-06-01" total="100000" totalLong="100000" totalShort="0" />
<EquitySummaryByReportDateInBase reportDate="2024-06-02" total="105000" totalLong="105000" totalShort="0" />
</EquitySummaryInBase>
<CashTransactions>
<CashTransaction reportDate="2024-06-02" amount="5000" type="Deposits/Withdrawals" />
</CashTransactions>
</FlexStatement></FlexStatements></FlexQueryResponse>"""
    (d / "a.xml").write_text(body_template, encoding="utf-8")
    (d / "b.xml").write_text(body_template, encoding="utf-8")  # same event, different file
    _, cashflows = backfill_nav.merge_xml_dir(d)
    assert len(cashflows) == 1
    assert cashflows[0]["amount"] == 5000


def test_main_uses_twr_when_cashflows_present(tmp_path: Path, monkeypatch):
    """End-to-end: deposit on day 2 must NOT show up as performance."""
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "backfill"
    d.mkdir()
    (d / "x.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse><FlexStatements><FlexStatement>
<EquitySummaryInBase>
<EquitySummaryByReportDateInBase reportDate="2024-01-02" total="100000" totalLong="100000" totalShort="0" />
<EquitySummaryByReportDateInBase reportDate="2024-01-03" total="150000" totalLong="150000" totalShort="0" />
<EquitySummaryByReportDateInBase reportDate="2024-01-04" total="165000" totalLong="165000" totalShort="0" />
</EquitySummaryInBase>
<CashTransactions>
<CashTransaction reportDate="2024-01-03" amount="50000" type="Deposits/Withdrawals" />
</CashTransactions>
</FlexStatement></FlexStatements></FlexQueryResponse>""",
        encoding="utf-8",
    )
    rc = backfill_nav.main([str(d)])
    assert rc == 0
    pct = json.loads((tmp_path / "data" / "nav_history_pct.json").read_text(encoding="utf-8"))
    assert pct[1]["return_pct"] == 0.0    # deposit isolated
    assert pct[2]["return_pct"] == 10.0   # real 10% gain on $150k
