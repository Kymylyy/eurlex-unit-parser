# Contributing

Thanks for contributing.

## Development Setup

1. Create a virtual environment.
2. Install dev dependencies:

```bash
python3 -m pip install -e .[dev]
```

Optional downloader support:

```bash
python3 -m pip install -e .[download]
playwright install chromium
```

## Basic Validation Before PR

Run these checks locally:

```bash
python3 -m py_compile parse_eu.py test_coverage.py run_batch.py download_eurlex.py
ruff check .
mypy src/eurlex_unit_parser
pytest -q
```

For benchmark-impacting parser changes, also run:

```bash
eurlex-batch --force-reparse --oracle mirror
```

Legacy equivalent remains supported:

```bash
python3 run_batch.py --force-reparse --oracle mirror
```

## Pull Request Rules

- Keep diffs focused and surgical.
- Add or update tests for behavior changes.
- Do not commit generated `downloads/` or `out/` artifacts.
- Do not commit machine-specific absolute paths.
- Update `README.md` and `CHANGELOG.md` when user-facing behavior changes.

## Commit Style

Use Conventional Commits where possible, for example:

- `refactor: split parser into modular flows`
- `test: add legacy wrapper compatibility coverage`
- `build: add pyproject and package scripts`
