# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- Regression tests for difficult amending-document cases.
- Split coverage metrics (`gone` vs `misclassified`) in coverage outputs.
- Packaging metadata via `pyproject.toml` with installable console scripts:
  `eurlex-parse`, `eurlex-coverage`, `eurlex-batch`, `eurlex-download`.
- Modular package layout under `src/eurlex_unit_parser` for parser, coverage, batch, download, and CLI.
- Compatibility tests for legacy root wrappers and imports.
- Inline regression tests for modular parser behavior (OJ, consolidated, amending, annex).

### Changed
- Improved amending article parsing path to preserve structure and point extraction.
- Improved list-table detection fallback heuristic.
- Batch reporting updated to use machine-readable metrics.
- Legacy root scripts (`parse_eu.py`, `test_coverage.py`, `run_batch.py`, `download_eurlex.py`)
  now act as thin wrappers with backward-compatible re-exports.
