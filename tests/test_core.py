from pathlib import Path

import pandas as pd
import pytest

from messy_reporter.core import (
    CleanReport,
    DataWriteError,
    ReportFormat,
    clean_dataframe,
    generate_report,
    render_report,
    save_report,
)


def test_generate_report_from_messy_csv_happy_path(tmp_path: Path) -> None:
    source = tmp_path / "customers.csv"
    source.write_text(
        " First Name ,Age, Notes \n"
        " Alice ,34, paid \n"
        " Bob , ,NA\n",
        encoding="utf-8",
    )

    report = generate_report(source)

    assert report.rows == 2
    assert report.columns == ("first_name", "age", "notes")
    assert report.records[0] == {
        "first_name": "Alice",
        "age": "34",
        "notes": "paid",
    }
    assert report.records[1]["first_name"] == "Bob"
    assert report.records[1]["age"] is None
    assert report.records[1]["notes"] is None


def test_clean_dataframe_handles_duplicate_columns_and_empty_columns() -> None:
    dataframe = pd.DataFrame(
        [
            [" Ada ", "Lovelace", None],
            [" Grace ", "Hopper", None],
        ],
        columns=[" Full Name ", "Full-Name", "###"],
    )

    cleaned = clean_dataframe(dataframe)

    assert list(cleaned.columns) == ["full_name", "full_name_2"]
    assert cleaned.to_dict(orient="records") == [
        {"full_name": "Ada", "full_name_2": "Lovelace"},
        {"full_name": "Grace", "full_name_2": "Hopper"},
    ]


def test_render_markdown_handles_empty_report(tmp_path: Path) -> None:
    report = CleanReport(
        source_path=tmp_path / "empty.csv",
        rows=0,
        columns=(),
        records=(),
    )

    rendered = render_report(report, ReportFormat.MARKDOWN)

    assert "# Clean Data Report" in rendered
    assert "No records found." in rendered


def test_save_report_wraps_permission_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = CleanReport(
        source_path=tmp_path / "input.csv",
        rows=1,
        columns=("name",),
        records=({"name": "Alice"},),
    )

    def raise_permission_error(
        self: Path,
        data: str,
        encoding: str | None = None,
    ) -> int:
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(Path, "write_text", raise_permission_error)

    with pytest.raises(DataWriteError, match="Unable to write report"):
        save_report(report, tmp_path / "report.json", ReportFormat.JSON)
