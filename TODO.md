# TODO

This file tracks planned engineering work that is intentionally not implemented yet.

## P1: First-class footnote handling

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

## P2: Citation extraction v0.2 expansion

- Status: Proposed
- Priority: Medium
- Last updated: 2026-02-10

### Problem statement

Citation extraction v0.1 intentionally implements only core internal + EU legislation
patterns. High-value legal-reference patterns remain out of scope and should be added
without regressing v0.1 precision.

### Scope (v0.2 targets)

- Internal subparagraph references (`first/second/third subparagraph`).
- Internal structural references (`Chapter`, `Section`, `Annex`).
- Treaty references (`TFEU`, `TEU`, long-form treaty mentions).
- Optional `eu_case` extraction (`Case C-...`) once validated on corpus.
- Optional connective phrase tagging as auxiliary citation context.

### Non-goals

- Rewriting parser architecture.
- Mixing Polish citation extraction into this repository scope.

### Acceptance criteria

- New citation types/patterns are covered by deterministic tests.
- No overlap regression with v0.1 patterns.
- Existing parser/enrichment tests remain green.
- `README.md` and `CHANGELOG.md` document each added pattern family.

### Implementation checklist

- [ ] Add new regex matcher families with explicit ordering and overlap guards.
- [ ] Extend citation model only if required by finalized v0.2 schema.
- [ ] Add focused regression tests for each new pattern family.
- [ ] Validate with `ruff`, `mypy`, `pytest`, and benchmark batch checks.
