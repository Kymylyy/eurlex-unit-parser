# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- Citation extraction v0.2 expansion:
  - internal point ranges (`points (a) to (d)`),
  - subparagraph references,
  - chapter/section/title references,
  - annex references,
  - treaty references (`TFEU`, `TEU`, Charter, Protocol),
  - connective phrase annotation metadata.
- Expanded `Citation` schema fields for v0.2 metadata:
  `article_label`, `point_range`, `paragraph_range`, `subparagraph_ordinal`,
  `chapter`, `section`, `title_ref`, `annex`, `annex_part`, `treaty_code`,
  `connective_phrase`.
- Regression coverage for v0.1 gaps:
  - external point-first citations preserving `point`,
  - internal `Article 6a(1)` detection and `art-6a...` node mapping.
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
- Citation matcher ordering now prioritizes external point-first references before
  article-first to avoid losing leading `point (...)` segments.
- Internal article parsing now preserves alphanumeric labels (e.g. `6a`) via
  `Citation.article_label` while keeping `Citation.article` for compatibility.
- Parser enrichment pipeline now runs citation extraction and includes `citations` in JSON output.
- Improved amending article parsing path to preserve structure and point extraction.
- Improved list-table detection fallback heuristic.
- Batch reporting updated to use machine-readable metrics.
- Legacy root scripts (`parse_eu.py`, `test_coverage.py`, `run_batch.py`, `download_eurlex.py`)
  now act as thin wrappers with backward-compatible re-exports.
- `eurlex-parse` JSON output migrated from root list to JSON v2 object:
  `{"document_metadata": ..., "units": [...]}`.
- Coverage tooling now requires JSON v2 input (`units` root key).
