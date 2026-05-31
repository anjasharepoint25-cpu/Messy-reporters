# Contributing

Thanks for your interest in contributing to Messy Reporter.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
pip install -e .
```

## Quality Checks

Before opening a pull request, run:

```bash
pytest
ruff check .
mypy src
```

## Pull Requests

- Keep changes focused and documented.
- Add or update tests for behavior changes.
- Prefer small pull requests over broad rewrites.
- Use clear commit messages.

## Reporting Bugs

Please include:

- The command or code you ran.
- The input file type and a minimal sample, if possible.
- The full error message and traceback.
- Your Python version and operating system.
