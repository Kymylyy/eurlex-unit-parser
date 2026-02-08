# Contributing

Thanks for contributing.

## Development Setup

1. Create a virtual environment.
2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Basic Validation Before PR

Run these checks locally:

```bash
python3 -m py_compile parse_eu.py test_coverage.py run_batch.py
python3 -m pytest -q
```

For benchmark-impacting parser changes, also run:

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

Prefer clear, imperative commit subjects, for example:

- `Fix amending article point extraction`
- `Split coverage metrics into gone and misclassified`
