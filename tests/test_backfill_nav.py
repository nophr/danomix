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
    merged = backfill_nav.merge_xml_dir(backfill_dir)
    dates = [r["date"] for r in merged]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))  # no duplicates
    # 2022-12-30 appears in both files; later (2023.xml) wins → total = 111000
    boundary = next(r for r in merged if r["date"] == "2022-12-30")
    assert boundary["total"] == 111000


def test_merge_xml_dir_full_range(backfill_dir: Path):
    merged = backfill_nav.merge_xml_dir(backfill_dir)
    assert merged[0]["date"] == "2022-01-04"
    assert merged[-1]["date"] == "2023-12-29"
    assert len(merged) == 5  # 3 + 3 - 1 dup


def test_main_writes_reanchored_pct(backfill_dir: Path, tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = backfill_nav.main([str(backfill_dir)])
    assert rc == 0

    pct = json.loads((tmp_path / "data" / "nav_history_pct.json").read_text(encoding="utf-8"))
    assert pct[0]["date"] == "2022-01-04"
    assert pct[0]["return_pct"] == 0.0  # re-anchor invariant
    # 130000 / 100000 = 1.30 → +30.0%
    assert pct[-1]["date"] == "2023-12-29"
    assert pct[-1]["return_pct"] == 30.0

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
    merged = backfill_nav.merge_xml_dir(d)
    assert merged[0]["date"] == "2022-01-05"
    assert merged[0]["total"] == 50000
    assert len(merged) == 2
