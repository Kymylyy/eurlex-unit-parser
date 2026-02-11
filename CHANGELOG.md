# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- Formal JSON Schema artifacts (Draft 2020-12):
  - `schemas/eurlex-output.schema.json` for parser output payloads,
  - `schemas/eurlex-validation.schema.json` for validation report payloads.
- Schema generator CLI (`scripts/generate_json_schemas.py`) with deterministic output and `--check` mode.
- Schema synchronization regression tests:
  - `tests/test_json_schema_sync.py` (artifact drift guard),
  - `tests/test_json_schema_contract.py` (schema contract validation).
- Citation extraction enrichment (`Unit.citations`) for v0.1 EU reference patterns
  (internal references and EU legislation references).
- `Citation` model exported in package and legacy wrapper APIs.
- Citation extraction regression tests (`tests/test_citations.py`).
- Regression tests for difficult amending-document cases.
- Split coverage metrics (`gone` vs `misclassified`) in coverage outputs.
- Packaging metadata via `pyproject.toml` with installable console scripts:
  `eurlex-parse`, `eurlex-coverage`, `eurlex-batch`, `eurlex-download`.
- Modular package layout under `src/eurlex_unit_parser` for parser, coverage, batch, download, and CLI.
- Compatibility tests for legacy root wrappers and imports.
- Inline regression tests for modular parser behavior (OJ, consolidated, amending, annex).
- Post-parse enrichment metadata on `Unit` (`target_path`, `article_heading`, `children_count`,
  `is_leaf`, `is_stem`, `word_count`, `char_count`).
- New `DocumentMetadata` model computed from parsed units.
- Enrichment regression tests covering structural and document-level metadata.
- CSV -> JSONL converter for candidate EUR-Lex link sets (`convert_links_csv.py` and
  `src/eurlex_unit_parser/batch/links_convert.py`).
- Batch runner support for processing custom corpora in windows:
  `--links-file`, `--offset`, `--limit`, and per-run snapshots via `--snapshot-tag`.
- Extended corpus files in `data/`:
  `eurlex_test_links.csv` and `eurlex_test_links.jsonl` (70 links).
- Parser/coverage regressions fixed for specific annex heading spacing and OJ recital table extraction,
  validated on the extended 70-link corpus.

### Changed
- Parser enrichment pipeline now runs citation extraction and includes `citations` in JSON output.
- Improved amending article parsing path to preserve structure and point extraction.
- Improved list-table detection fallback heuristic.
- Batch reporting updated to use machine-readable metrics.
- Legacy root scripts (`parse_eu.py`, `test_coverage.py`, `run_batch.py`, `download_eurlex.py`)
  now act as thin wrappers with backward-compatible re-exports.
- `eurlex-parse` JSON output migrated from root list to JSON v2 object:
  `{"document_metadata": ..., "units": [...]}`.
- Coverage tooling now requires JSON v2 input (`units` root key).
