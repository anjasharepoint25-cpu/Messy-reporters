# Messy Reporter

Messy Reporter is a small Python utility for loading messy CSV or Excel files,
cleaning their structure, and generating clean JSON or Markdown reports.

## Features

- Reads `.csv`, `.xlsx`, and `.xlsm` files.
- Trims whitespace from string cells.
- Drops fully empty rows and columns.
- Normalizes column names to `snake_case`.
- Converts missing values to `null` in JSON output.
- Generates JSON or Markdown reports.
- Provides both a Python API and a command-line interface.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

## Usage

### Python API

```python
from messy_reporter.core import ReportFormat, generate_report, save_report

report = generate_report("data/customers.csv")

save_report(
    report=report,
    output_path="reports/customers.json",
    output_format=ReportFormat.JSON,
)
```

### CLI

```bash
messy-reporter data/customers.csv reports/customers.md
messy-reporter data/customers.xlsx reports/customers.json --sheet-name 0
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
pip install -e .

pytest
ruff check .
mypy src
```

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md)
before opening a pull request.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).
