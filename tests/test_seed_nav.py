import json
from pathlib import Path
from scripts.seed_nav import parse_statement_csv, main


def test_extracts_nav_rows_from_csv():
    csv_text = Path("tests/fixtures/sample_statement.csv").read_text(encoding="utf-8")
    ledger = parse_statement_csv(csv_text)
    assert len(ledger) == 3
    assert ledger[0] == {
        "date": "2023-04-18",
        "total": 250000.00,
        "total_long": 250000.00,
        "total_short": 0.00,
    }
    assert ledger[-1]["total_short"] == -4700.00


def test_main_writes_nav_history(tmp_path, monkeypatch):
    csv_path = tmp_path / "stmt.csv"
    csv_path.write_text(Path("tests/fixtures/sample_statement.csv").read_text(encoding="utf-8"))
    out_path = tmp_path / "nav_history.json"
    main([str(csv_path), str(out_path)])
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written[0]["date"] == "2023-04-18"
    assert len(written) == 3
