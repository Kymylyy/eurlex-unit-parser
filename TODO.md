# TODO

This file tracks planned engineering work that is intentionally not implemented yet.

## P1: Amendment aggregation and relation extraction

- Status: Proposed
- Priority: High
- Last updated: 2026-02-16

### Problem statement

`Unit.is_amendment_text` currently marks local parser context but does not produce
an aggregate, document-level map of which external acts are amended and how those
relations should be surfaced for downstream graph tooling.

Relevant code paths:

- `src/eurlex_unit_parser/parser/oj.py` (amending article detection heuristics)
- `src/eurlex_unit_parser/parser/enrichment.py` (`amendment_articles` metadata)
- `src/eurlex_unit_parser/parser/citations.py` (citations currently skipped in amendment text units)

### Target outcome

Provide a deterministic aggregate amendment layer that captures amended target acts
at document level, beyond boolean `is_amendment_text`, while preserving current parse quality.

### Scope

- Define amendment-relation representation in parser output/API.
- Detect and aggregate amended target acts for amendment-heavy articles.
- Keep unit-level `is_amendment_text` as low-level signal, but add higher-level resolved view.
- Add regression coverage for amendment relation extraction.

### Non-goals

- Full legal-effect interpretation beyond explicit amendment language.
- Redesigning the full citation engine in one step.

### Acceptance criteria

- Amended target acts are available in deterministic aggregate output.
- Existing parser and coverage regressions remain green.
- New regression tests cover:
  - positive amendment aggregation cases,
  - no false positives on non-amending articles,
  - stable output for benchmark documents.

### Implementation checklist

- [ ] Define schema/API fields for aggregated amendment relations.
- [ ] Implement extraction and aggregation logic.
- [ ] Add regression tests for aggregation and false-positive guards.
- [ ] Validate with `ruff`, `mypy`, `pytest`, and batch coverage.
- [ ] Document behavior in `README.md` and `CHANGELOG.md` once implemented.

## P2: First-class footnote handling

- Status: Proposed
- Priority: High
- Last updated: 2026-02-10

### Problem statement

The parser currently removes footnote anchors/superscripts during text extraction and, in some paths (notably amending articles), skips note paragraphs entirely. As a result, footnotes are not represented as explicit units in JSON output.

Relevant code paths:

- `src/eurlex_unit_parser/text_utils.py` (`remove_note_tags`)
- `src/eurlex_unit_parser/parser/oj.py` (handling of `p.oj-note`)
- `src/eurlex_unit_parser/parser/consolidated.py` (note cleanup in consolidated flow)

### Target outcome

Footnotes should be captured as structured data instead of being only stripped, while keeping current parsing quality gates intact (`gone`, `phantom`, hierarchy, ordering).

### Scope

- Define an explicit footnote representation in output (schema + placement rules).
- Extract footnote bodies where available in OJ and consolidated HTML.
- Preserve linkage between in-text footnote references and extracted footnotes when source HTML allows it.
- Ensure non-footnote text extraction behavior remains unchanged.

### Non-goals

- Rewriting the full parser architecture.
- Introducing format-specific behavior that cannot be validated with tests.

### Acceptance criteria

- Footnotes are available in parser output in a deterministic structure.
- Existing regression tests continue to pass.
- New regression tests cover:
  - footnote extraction in standard OJ articles,
  - footnote handling in amending articles,
  - no leakage of citation-only footnotes into amendment text units.
- Coverage metrics do not regress on benchmark corpus.

### Implementation checklist

- [ ] Finalize output schema for footnotes (and backward-compatibility policy).
- [ ] Implement extraction/linking logic.
- [ ] Add/extend regression tests.
- [ ] Validate with `ruff`, `mypy`, `pytest`, and batch coverage.
- [ ] Document behavior in `README.md` and `CHANGELOG.md` once implemented.

## P3: Citation extraction v0.2 expansion

- Status: Implemented
- Priority: Medium
- Last updated: 2026-02-10

### Delivery summary

Citation extraction has been expanded to v0.2 with deterministic matcher ordering and
regression coverage. Implemented additions include:

- Internal subparagraph references (`first/second/... subparagraph`).
- Internal structural references (`Chapter`, `Section`, `Title`, `Annex`).
- Treaty references (`TFEU`, `TEU`, Charter, Protocol).
- Decision-format external references (including framework decisions).
- Connective phrase metadata (`Citation.connective_phrase`).
- v0.1 gap fixes for external point-first preservation and article labels (`Article 6a(1)`).

### Scope (implemented)

- Internal subparagraph references (`first/second/third/... subparagraph`).
- Internal structural references (`Chapter`, `Section`, `Title`, `Annex`).
- Treaty references (`TFEU`, `TEU`, long-form treaty mentions, Protocol).
- Connective phrase tagging as auxiliary citation context.

### Non-goals

- Rewriting parser architecture.
- Mixing Polish citation extraction into this repository scope.
- `eu_case` extraction (`Case C-...`) remains out of scope.

### Acceptance criteria

- [x] New citation types/patterns are covered by deterministic tests.
- [x] No overlap regression with v0.1 patterns.
- [x] Existing parser/enrichment tests remain green.
- [x] `README.md` and `CHANGELOG.md` document each added pattern family.

### Implementation checklist

- [x] Added new regex matcher families with explicit ordering and overlap guards.
- [x] Extended citation model with additive optional v0.2 fields.
- [x] Added focused regression tests for each new pattern family.
- [x] Validated with `ruff`, `mypy`, and `pytest`.
