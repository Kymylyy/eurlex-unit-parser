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
ruff check .
mypy src/eurlex_unit_parser
pytest -q
```

For benchmark-impacting parser changes, also run:

```bash
eurlex-batch --force-reparse --oracle mirror
```

## Canonical Example Refresh

When changing parser behavior, extraction/enrichment logic, output schema, or docs
that describe parser output, refresh the canonical example JSON before opening a PR:

```bash
eurlex-parse --input downloads/eur-lex/32022R2554.html --out examples/DORA.json
```

If `eurlex-parse` is not available on `PATH`, use:

```bash
PYTHONPATH=src python3 -m eurlex_unit_parser.cli.parse --input downloads/eur-lex/32022R2554.html --out examples/DORA.json
```

## Pull Request Rules

- Keep diffs focused and surgical.
- Add or update tests for behavior changes.
- Refresh `examples/DORA.json` whenever parser/output behavior changes.
- Do not commit generated `downloads/` or `out/` artifacts.
- Do not commit machine-specific absolute paths.
- Update `README.md` and `CHANGELOG.md` when user-facing behavior changes.

## Commit Style

Use Conventional Commits where possible, for example:

- `refactor: split parser into modular flows`
- `test: add package public API coverage`
- `build: add pyproject and package scripts`
