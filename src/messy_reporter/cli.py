"""Command-line interface for messy-reporter."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from messy_reporter.core import (
    MessyReporterError,
    ReportFormat,
    generate_report,
    save_report,
)

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        Configured argparse parser.
    """
    parser = argparse.ArgumentParser(
        prog="messy-reporter",
        description="Clean messy CSV or Excel files into JSON or Markdown reports.",
    )
    parser.add_argument("input_path", type=Path, help="Path to the CSV or Excel file.")
    parser.add_argument(
        "output_path",
        type=Path,
        help="Path to write the generated .json, .md, or .markdown report.",
    )
    parser.add_argument(
        "--format",
        choices=[report_format.value for report_format in ReportFormat],
        default=None,
        help=(
            "Explicit output format. By default, the format is inferred from "
            "output_path."
        ),
    )
    parser.add_argument(
        "--sheet-name",
        default=0,
        help="Excel sheet name or index. Ignored for CSV files.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable informational logging.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv: Optional command-line arguments. Uses sys.argv when omitted.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    try:
        sheet_name = _parse_sheet_name(args.sheet_name)
        report = generate_report(args.input_path, sheet_name=sheet_name)
        save_report(report, args.output_path, args.format)
        return 0
    except MessyReporterError as exc:
        logger.error("%s", exc)
        return 1


def _parse_sheet_name(value: str | int) -> str | int:
    """Parse a sheet selector into a string or integer.

    Args:
        value: Raw sheet selector from the command line.

    Returns:
        Integer sheet index when numeric, otherwise the original string.
    """
    if isinstance(value, int):
        return value

    try:
        return int(value)
    except ValueError:
        return value


if __name__ == "__main__":
    raise SystemExit(main())
