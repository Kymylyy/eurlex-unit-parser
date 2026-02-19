# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- LSU (Summaries of EU legislation) enrichment support across CLI and API:
  - new summary models `LSUSummary` and `LSUSummarySection`,
  - LSU fetch/parse helpers in `eurlex_unit_parser.summary`,
  - CELEX resolution fallback from source HTML, filename, and consolidated->base CELEX normalization.
- `eurlex-parse` LSU flags:
  - `--no-summary-lsu`,
  - `--summary-lsu-lang`,
  - `--celex`.
- Parser output JSON contract extensions:
  - top-level `summary_lsu`,
  - top-level `summary_lsu_status` (`ok`, `not_found`, `fetch_error`, `celex_missing`, `disabled`).
- LSU regression tests for success, not-found, fetch-error, celex-missing, and consolidated CELEX fallback.
- Formal JSON Schema artifacts (Draft 2020-12):
  - `schemas/eurlex-output.schema.json` for parser output payloads,
  - `schemas/eurlex-validation.schema.json` for validation report payloads.
- Schema generator CLI (`scripts/generate_json_schemas.py`) with deterministic output and `--check` mode.
- Schema synchronization regression tests:
  - `tests/test_json_schema_sync.py` (artifact drift guard),
  - `tests/test_json_schema_contract.py` (schema contract validation).
- Citation extraction v0.2 expansion:
  - internal point ranges (`points (a) to (d)`),
  - subparagraph references,
  - chapter/section/title references,
  - annex references,
  - treaty references (`TFEU`, `TEU`, Charter, Protocol),
  - connective phrase annotation metadata.
- `Citation.act_year` metadata for external EU legislation references.
- Expanded `Citation` schema fields for v0.2 metadata:
  `article_label`, `point_range`, `paragraph_range`, `subparagraph_ordinal`,
  `chapter`, `section`, `title_ref`, `annex`, `annex_part`, `treaty_code`,
  `connective_phrase`.
- `Citation.subparagraph_index` optional metadata (1-based) derived from
  `Citation.subparagraph_ordinal` for explicit subparagraph references.
- Regression coverage for v0.1 gaps:
  - external point-first citations preserving `point`,
  - internal `Article 6a(1)` detection and `art-6a...` node mapping.
- Citation extraction enrichment (`Unit.citations`) for v0.1 EU reference patterns
  (internal references and EU legislation references).
- `Citation` model exported in package APIs.
- Citation extraction regression tests (`tests/test_citations.py`).
- Regression tests for difficult amending-document cases.
- Split coverage metrics (`gone` vs `misclassified`) in coverage outputs.
- Packaging metadata via `pyproject.toml` with installable console scripts:
  `eurlex-parse`, `eurlex-coverage`, `eurlex-batch`, `eurlex-download`.
- Modular package layout under `src/eurlex_unit_parser` for parser, coverage, batch, download, and CLI.
- High-level library facade module (`eurlex_unit_parser.api`) with:
  `parse_html`, `parse_file`, and `download_and_parse`.
- Structured downloader result model `DownloadResult`.
- Inline regression tests for modular parser behavior (OJ, consolidated, amending, annex).
- Post-parse enrichment metadata on `Unit` (`target_path`, `article_heading`, `children_count`,
  `is_leaf`, `is_stem`, `word_count`, `char_count`).
- New `DocumentMetadata` model computed from parsed units.
- Enrichment regression tests covering structural and document-level metadata.
- `Unit.subparagraph_index` optional metadata (1-based) for all parsed `subparagraph` units.
- CSV -> JSONL converter for candidate EUR-Lex link sets
  (`src/eurlex_unit_parser/batch/links_convert.py`).
- Batch runner support for processing custom corpora in windows:
  `--links-file`, `--offset`, `--limit`, and per-run snapshots via `--snapshot-tag`.
- Extended corpus files in `data/`:
  `eurlex_test_links.csv` and `eurlex_test_links.jsonl` (70 links).
- Parser/coverage regressions fixed for specific annex heading spacing and OJ recital table extraction,
  validated on the extended 70-link corpus.

### Changed
- Breaking change: removed legacy root wrappers (`parse_eu.py`, `test_coverage.py`,
  `run_batch.py`, `convert_links_csv.py`, `download_eurlex.py`).
- Breaking change: `download_eurlex(...)` now returns `DownloadResult` instead of `bool`.
- Parser is now state-safe for reuse: `EUParser.parse()` resets runtime state on every call.
- Batch runner subprocess calls now use package module entrypoints (`python -m eurlex_unit_parser.cli.*`).
- Citation matcher ordering now prioritizes external point-first references before
  article-first to avoid losing leading `point (...)` segments.
- Citation extraction now treats explicit `Article(s) ... of Regulation/Directive/Decision`
  references (including enumerations and ranges) and contextual
  `Article(s) ... of that Regulation/Directive/Decision` references as external
  EU legislation citations; multi-article and multi-act mentions are emitted as
  cartesian `article x act` citation sets.
- Internal article enumerations now emit discrete citations; article ranges are limited to explicit `to` ranges.
- Internal article parsing now preserves alphanumeric labels (e.g. `6a`) via
  `Citation.article_label` while keeping `Citation.article` for compatibility.
- Citation resolver now maps standalone internal `points (...)` references to the nearest
  same-clause internal anchor context (e.g. `paragraph 1, points (a) and (b)`) with
  parent-subparagraph fallback for nested point units.
- Citation resolver now reclassifies bare `that Directive/that Regulation/that Decision`
  references to `eu_legislation` when a unique matching antecedent act is present in the same unit.
- Parser enrichment pipeline now runs citation extraction and includes `citations` in JSON output.
- Parser flows now populate `subparagraph_index` wherever `subparagraph` ordering is known
  (including standard OJ subparagraphs, amending paths, and non-list table extraction).
- Improved amending article parsing path to preserve structure and point extraction.
- Improved list-table detection fallback heuristic.
- Batch reporting updated to use machine-readable metrics.
- `eurlex-parse` JSON output migrated from root list to JSON v2 object:
  `{"document_metadata": ..., "units": [...]}`.
- Coverage tooling now requires JSON v2 input (`units` root key).
