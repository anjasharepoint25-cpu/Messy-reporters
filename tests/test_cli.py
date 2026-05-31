from pathlib import Path

from messy_reporter.cli import main


def test_cli_generates_json_report(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    destination = tmp_path / "report.json"
    source.write_text(" Name ,Score\n Ada , 99\n", encoding="utf-8")

    exit_code = main([str(source), str(destination)])

    assert exit_code == 0
    assert destination.exists()
    assert '"name": "Ada"' in destination.read_text(encoding="utf-8")
