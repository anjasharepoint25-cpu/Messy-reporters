"""Core data-cleaning and report-generation logic."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

SUPPORTED_INPUT_SUFFIXES = frozenset({".csv", ".xlsx", ".xlsm"})


class MessyReporterError(Exception):
    """Base exception for all package-specific errors."""


class UnsupportedFileTypeError(MessyReporterError):
    """Raised when an input file type is not supported."""


class UnsupportedReportFormatError(MessyReporterError):
    """Raised when an output report format is not supported."""


class DataReadError(MessyReporterError):
    """Raised when input data cannot be read."""


class DataCleaningError(MessyReporterError):
    """Raised when input data cannot be cleaned."""


class DataWriteError(MessyReporterError):
    """Raised when a report cannot be written to disk."""


class ReportFormat(str, Enum):
    """Supported report output formats."""

    JSON = "json"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class CleaningOptions:
    """Options controlling tabular data cleanup.

    Attributes:
        trim_whitespace: Whether to trim whitespace from string cells.
        drop_empty_rows: Whether to remove rows where every value is missing.
        drop_empty_columns: Whether to remove columns where every value is missing.
        normalize_column_names: Whether to convert column names to snake_case.
        missing_values: String values that should be treated as missing.
    """

    trim_whitespace: bool = True
    drop_empty_rows: bool = True
    drop_empty_columns: bool = True
    normalize_column_names: bool = True
    missing_values: tuple[str, ...] = (
        "",
        "NA",
        "N/A",
        "n/a",
        "NULL",
        "null",
        "None",
        "none",
        "-",
    )


@dataclass(frozen=True, slots=True)
class CleanReport:
    """Structured report generated from cleaned tabular data.

    Attributes:
        source_path: Original source file path.
        rows: Number of cleaned rows.
        columns: Cleaned column names.
        records: Cleaned row records.
    """

    source_path: Path
    rows: int
    columns: tuple[str, ...]
    records: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the report.

        Returns:
            Dictionary containing report metadata and records.
        """
        return {
            "source_path": str(self.source_path),
            "rows": self.rows,
            "columns": list(self.columns),
            "records": [dict(record) for record in self.records],
        }


def load_tabular_file(path: str | Path, *, sheet_name: str | int = 0) -> pd.DataFrame:
    """Load a CSV or Excel file into a pandas DataFrame.

    Args:
        path: Path to the input CSV, XLSX, or XLSM file.
        sheet_name: Excel sheet name or zero-based sheet index.

    Returns:
        Loaded pandas DataFrame.

    Raises:
        UnsupportedFileTypeError: If the file suffix is unsupported.
        DataReadError: If the file cannot be read.
    """
    file_path = Path(path).expanduser()

    if not file_path.exists():
        raise DataReadError(f"Input file does not exist: {file_path}")

    if not file_path.is_file():
        raise DataReadError(f"Input path is not a file: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_INPUT_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_INPUT_SUFFIXES))
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Supported types: {supported}"
        )

    try:
        logger.info("Loading input file: %s", file_path)

        if suffix == ".csv":
            return pd.read_csv(file_path)

        return pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")

    except PermissionError as exc:
        logger.exception("Permission denied while reading %s", file_path)
        raise DataReadError(f"Permission denied while reading: {file_path}") from exc
    except pd.errors.EmptyDataError as exc:
        logger.exception("Input file is empty: %s", file_path)
        raise DataReadError(f"Input file is empty: {file_path}") from exc
    except pd.errors.ParserError as exc:
        logger.exception("Unable to parse input file: %s", file_path)
        raise DataReadError(f"Unable to parse input file: {file_path}") from exc
    except OSError as exc:
        logger.exception("OS error while reading %s", file_path)
        raise DataReadError(f"Unable to read input file: {file_path}") from exc


def clean_dataframe(
    dataframe: pd.DataFrame,
    options: CleaningOptions | None = None,
) -> pd.DataFrame:
    """Clean a raw pandas DataFrame.

    Args:
        dataframe: Raw DataFrame to clean.
        options: Optional cleaning configuration.

    Returns:
        Cleaned DataFrame with normalized columns and JSON-safe missing values.

    Raises:
        DataCleaningError: If cleaning fails.
    """
    cleaning_options = options or CleaningOptions()

    try:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        cleaned = dataframe.copy()

        if cleaning_options.trim_whitespace:
            cleaned = cleaned.map(_strip_cell)

        if cleaning_options.missing_values:
            cleaned = cleaned.replace(list(cleaning_options.missing_values), pd.NA)

        if cleaning_options.drop_empty_rows:
            cleaned = cleaned.dropna(how="all")

        if cleaning_options.drop_empty_columns:
            cleaned = cleaned.dropna(axis="columns", how="all")

        if cleaning_options.normalize_column_names:
            normalized_columns = [
                normalize_column_name(column) for column in cleaned.columns
            ]
            cleaned.columns = deduplicate_column_names(normalized_columns)

        cleaned = cleaned.astype(object).where(pd.notna(cleaned), None)
        return cleaned.reset_index(drop=True)

    except (AttributeError, TypeError, ValueError) as exc:
        logger.exception("Failed to clean dataframe")
        raise DataCleaningError("Failed to clean dataframe") from exc


def generate_report(
    path: str | Path,
    *,
    options: CleaningOptions | None = None,
    sheet_name: str | int = 0,
) -> CleanReport:
    """Generate a clean report from a CSV or Excel source file.

    Args:
        path: Path to the input file.
        options: Optional cleaning configuration.
        sheet_name: Excel sheet name or zero-based sheet index.

    Returns:
        CleanReport containing cleaned metadata and records.

    Raises:
        MessyReporterError: If reading or cleaning fails.
    """
    file_path = Path(path).expanduser()

    raw_dataframe = load_tabular_file(file_path, sheet_name=sheet_name)
    cleaned_dataframe = clean_dataframe(raw_dataframe, options)

    records = tuple(_dataframe_to_records(cleaned_dataframe))
    report = CleanReport(
        source_path=file_path.resolve(),
        rows=len(records),
        columns=tuple(str(column) for column in cleaned_dataframe.columns),
        records=records,
    )

    logger.info(
        "Generated report from %s with %d rows and %d columns",
        file_path,
        report.rows,
        len(report.columns),
    )
    return report


def render_report(report: CleanReport, output_format: ReportFormat | str) -> str:
    """Render a CleanReport as JSON or Markdown.

    Args:
        report: Report to render.
        output_format: Desired output format.

    Returns:
        Rendered report content.

    Raises:
        UnsupportedReportFormatError: If the format is unsupported.
    """
    report_format = coerce_report_format(output_format)

    if report_format is ReportFormat.JSON:
        return json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    if report_format is ReportFormat.MARKDOWN:
        return _render_markdown(report)

    raise UnsupportedReportFormatError(f"Unsupported report format: {output_format}")


def save_report(
    report: CleanReport,
    output_path: str | Path,
    output_format: ReportFormat | str | None = None,
) -> Path:
    """Write a rendered report to disk.

    Args:
        report: Report to write.
        output_path: Destination file path.
        output_format: Optional explicit output format. If omitted, inferred from
            suffix.

    Returns:
        Path to the written report.

    Raises:
        UnsupportedReportFormatError: If the output format cannot be inferred.
        DataWriteError: If the report cannot be written.
    """
    destination = Path(output_path).expanduser()
    report_format = (
        coerce_report_format(output_format)
        if output_format is not None
        else infer_report_format(destination)
    )
    rendered = render_report(report, report_format)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
        logger.info("Saved %s report to %s", report_format.value, destination)
        return destination

    except PermissionError as exc:
        logger.exception("Permission denied while writing %s", destination)
        raise DataWriteError(f"Unable to write report: {destination}") from exc
    except OSError as exc:
        logger.exception("OS error while writing %s", destination)
        raise DataWriteError(f"Unable to write report: {destination}") from exc


def infer_report_format(path: str | Path) -> ReportFormat:
    """Infer report format from a file suffix.

    Args:
        path: Output path whose suffix should be inspected.

    Returns:
        Inferred ReportFormat.

    Raises:
        UnsupportedReportFormatError: If the suffix is unsupported.
    """
    suffix = Path(path).suffix.lower()

    if suffix == ".json":
        return ReportFormat.JSON

    if suffix in {".md", ".markdown"}:
        return ReportFormat.MARKDOWN

    raise UnsupportedReportFormatError(
        "Could not infer report format. Use .json, .md, or .markdown."
    )


def coerce_report_format(output_format: ReportFormat | str) -> ReportFormat:
    """Convert a string or enum value into a ReportFormat.

    Args:
        output_format: Format value to coerce.

    Returns:
        Matching ReportFormat enum value.

    Raises:
        UnsupportedReportFormatError: If the value is unsupported.
    """
    if isinstance(output_format, ReportFormat):
        return output_format

    try:
        return ReportFormat(str(output_format).lower())
    except ValueError as exc:
        raise UnsupportedReportFormatError(
            f"Unsupported report format: {output_format}"
        ) from exc


def normalize_column_name(name: object) -> str:
    """Normalize a column name into snake_case.

    Args:
        name: Original column name.

    Returns:
        Normalized snake_case column name.
    """
    raw_name = "" if name is None else str(name)
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", raw_name.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    if not normalized:
        normalized = "column"

    if normalized[0].isdigit():
        normalized = f"column_{normalized}"

    return normalized


def deduplicate_column_names(names: list[str]) -> list[str]:
    """Ensure column names are unique while preserving order.

    Args:
        names: Column names to deduplicate.

    Returns:
        Unique column names.
    """
    used: set[str] = set()
    counts: dict[str, int] = {}
    deduplicated: list[str] = []

    for name in names:
        base_name = name or "column"
        candidate = base_name
        index = counts.get(base_name, 1)

        while candidate in used:
            index += 1
            candidate = f"{base_name}_{index}"

        counts[base_name] = index
        used.add(candidate)
        deduplicated.append(candidate)

    return deduplicated


def _strip_cell(value: Any) -> Any:
    """Strip whitespace from string cells.

    Args:
        value: Cell value.

    Returns:
        Trimmed string for string values, otherwise the original value.
    """
    if isinstance(value, str):
        return value.strip()
    return value


def _dataframe_to_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame into JSON-compatible row records.

    Args:
        dataframe: Cleaned DataFrame.

    Returns:
        List of JSON-compatible dictionaries.
    """
    raw_records = dataframe.to_dict(orient="records")
    return [
        {str(key): _to_json_compatible(value) for key, value in record.items()}
        for record in raw_records
    ]


def _to_json_compatible(value: Any) -> Any:
    """Convert pandas and Python values into JSON-compatible values.

    Args:
        value: Value to convert.

    Returns:
        JSON-compatible value.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return value.item()
        except (AttributeError, TypeError, ValueError):
            logger.debug("Unable to convert scalar value with item(): %r", value)

    return value


def _render_markdown(report: CleanReport) -> str:
    """Render a report as Markdown.

    Args:
        report: Report to render.

    Returns:
        Markdown string.
    """
    lines = [
        "# Clean Data Report",
        "",
        f"- Source: `{report.source_path}`",
        f"- Rows: `{report.rows}`",
        f"- Columns: `{len(report.columns)}`",
        "",
    ]

    if not report.records:
        lines.append("No records found.")
        return "\n".join(lines)

    lines.extend(_render_markdown_table(report.records, report.columns))
    return "\n".join(lines)


def _render_markdown_table(
    records: tuple[dict[str, Any], ...],
    columns: tuple[str, ...],
) -> list[str]:
    """Render records as a Markdown table.

    Args:
        records: Row records.
        columns: Column names.

    Returns:
        Markdown table lines.
    """
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"

    rows = [
        "| "
        + " | ".join(_format_markdown_cell(record.get(column)) for column in columns)
        + " |"
        for record in records
    ]

    return [header, separator, *rows]


def _format_markdown_cell(value: Any) -> str:
    """Format a value for safe use inside a Markdown table cell.

    Args:
        value: Cell value.

    Returns:
        Escaped Markdown cell value.
    """
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)

    return text.replace("|", "\\|").replace("\n", "<br>")
