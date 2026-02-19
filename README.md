# EUR-Lex Unit Parser

Parser for EU Official Journal (EUR-Lex) HTML documents.
It converts ELI-style legislation pages into structured JSON with document metadata and legal units
(document titles, recitals, articles, paragraphs, points, subpoints, annex items).

## Status

- Language: Python 3.10+
- License: MIT
- Core validation corpus: 52 EUR-Lex documents (`data/eurlex_links.jsonl`)
- Extended validation corpus: 70 EUR-Lex documents (`data/eurlex_test_links.jsonl`, source CSV in `data/eurlex_test_links.csv`)
- Latest extended batch run (2026-02-10): 70/70 PASS (`mirror` oracle, batches of 10)
- Architecture: modular package (`src/eurlex_unit_parser`) with package-first public API

Current benchmark target remains `mirror` oracle with forced reparse.

## Installation

### Option A: package mode (recommended)

```bash
python3 -m pip install -e .
```

With dev tooling:

```bash
python3 -m pip install -e .[dev]
```

If console scripts are not on your `PATH`, run them via module mode:

```bash
PYTHONPATH=src python3 -m eurlex_unit_parser.cli.parse --help
```

Optional downloader dependency:

```bash
python3 -m pip install -e .[download]
playwright install chromium
```

## Usage

### New CLI (package scripts)

- Parse:

```bash
eurlex-parse --input downloads/eur-lex/32022R2554.html
```

- Coverage:

```bash
eurlex-coverage --input downloads/eur-lex/32022R2554.html --json out/json/32022R2554.json --oracle mirror
```

- Batch:

```bash
eurlex-batch --force-reparse --oracle mirror
```

- Batch on custom JSONL and windowing (offset/limit):

```bash
eurlex-batch --links-file data/eurlex_test_links.jsonl --offset 0 --limit 10 --force-reparse --oracle mirror --snapshot-tag batch_01
```

- Convert candidate CSV links to JSONL:

```bash
python3 -m eurlex_unit_parser.batch.links_convert --input data/eurlex_test_links.csv --output data/eurlex_test_links.jsonl
```

- Downloader:

```bash
eurlex-download "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689" EMIR3
```

## Public API

### Package imports

```python
from eurlex_unit_parser import (
    Citation,
    DownloadResult,
    EUParser,
    JobResult,
    LSUSummary,
    LSUSummarySection,
    ParseResult,
    Unit,
    ValidationReport,
    download_and_parse,
    fetch_lsu_summary,
    download_eurlex,
    parse_file,
    parse_html,
)
```

### Library integration API

Use the facade helpers in `eurlex_unit_parser.api` (also exported at package root):

```python
from pathlib import Path
from eurlex_unit_parser import download_and_parse, parse_file

# Parse existing HTML
result = parse_file("downloads/eur-lex/32022R2554.html")
print(result.validation.is_valid(), len(result.units))
print(result.summary_lsu_status, bool(result.summary_lsu))

# Download + parse in one single-document job
job = download_and_parse(
    "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022R2554",
    Path("downloads/eur-lex/32022R2554.html"),
)
if job.download.ok and job.parse:
    print(job.download.bytes_written, len(job.parse.units), job.parse.summary_lsu_status)
else:
    print(job.download.status, job.download.error, job.parse_error)

# Optional: skip LSU fetch when running offline
result_no_lsu = parse_file("downloads/eur-lex/32022R2554.html", with_summary_lsu=False)
print(result_no_lsu.summary_lsu_status)  # disabled
```

`download_eurlex(...)` now returns `DownloadResult` with structured status fields:
`ok`, `status`, `error`, `output_path`, `final_url`, `bytes_written`, `method`.

## How it works

`EUParser` composes focused mixins that split parsing responsibilities while preserving a single `parse()` entrypoint.

- `ParserStateMixin` initializes parser state, detects OJ vs consolidated format, tracks expected/parsed counts, and deduplicates unit ids.
- `OJParserMixin` and `ConsolidatedParserMixin` handle format-specific article/paragraph extraction paths.
- `TablesParserMixin` extracts nested list-table structures (points/subpoints) and non-list table content.
- `AnnexParserMixin` parses annex containers into annex, annex-part, and annex-item units.
- `ValidationMixin` runs post-parse integrity checks for parent-child links and recital sequence gaps.
- `EnrichmentMixin` computes tree metadata (`children_count`, leaf/stem flags), target paths, text stats, and document-level metadata.
- Citation enrichment runs in-order inside `_enrich()`: `CitationExtractorMixin` first, then `CitationResolverMixin` for context-based target resolution.
- `EUParser.parse()` orchestrates the pipeline as: detect/count -> title/recitals -> article flow (OJ or consolidated) -> annexes -> validate -> enrich.
- `EUParser.parse()` resets runtime parser state on every call, so reusing one parser instance does not accumulate units across parses.

## JSON Contract

Parser output (`eurlex-parse`) is a JSON object:

- `document_metadata`: document-level summary and aggregate counters.
- `summary_lsu`: optional LSU summary payload (or `null`).
- `summary_lsu_status`: LSU enrichment status (`ok`, `not_found`, `fetch_error`, `celex_missing`, `disabled`).
- `units`: flat array of parsed units in document order.

Validation output (`--validation`) is a separate JSON object described by `ValidationReport`.

Each `unit` includes a `citations` list (possibly empty) populated during enrichment.
Structural index fields include `paragraph_index` and `subparagraph_index` (both optional, 1-based when present).
Citation extraction supports v0.2 patterns and optional metadata fields:
`article_label`, `point_range`, `paragraph_range`, `subparagraph_ordinal`, `subparagraph_index`, `chapter`,
`section`, `title_ref`, `annex`, `annex_part`, `treaty_code`, `connective_phrase`, `act_year`.

Formal JSON Schema artifacts (Draft 2020-12):

- `schemas/eurlex-output.schema.json`
- `schemas/eurlex-validation.schema.json`

Regenerate artifacts:

```bash
python3 scripts/generate_json_schemas.py
```

Check that committed schemas are synchronized with models:

```bash
python3 scripts/generate_json_schemas.py --check
```

Key `Unit` fields:

| Field | Meaning |
|---|---|
| `id` | Stable hierarchical identifier, e.g. `art-5.par-1.pt-a`. |
| `type` | Structural unit kind (`article`, `paragraph`, `point`, `annex_item`, `nested_N`, etc.). |
| `ref` | Raw source label, e.g. `1.` or `(a)` when available. |
| `text` | Normalized unit text. |
| `parent_id` | Parent unit id or `null` for top-level units. |
| `article_number` / `paragraph_number` | Explicit legal numbering when present. |
| `paragraph_index` | Positional fallback when paragraph has no explicit number. |
| `point_label` / `subpoint_label` / `subsubpoint_label` | Normalized list labels for nested points. |
| `target_path` | Enriched canonical pointer (e.g. `Art. 5(1)(a)`, `Annex I`). |
| `article_heading` | Article heading propagated to descendants during enrichment. |
| `children_count`, `is_leaf`, `is_stem` | Tree structure metadata. |
| `word_count`, `char_count` | Text statistics for downstream processing. |
| `citations` | Extracted citation objects in text order (possibly empty). |

Key `Citation` fields:

| Field | Meaning |
|---|---|
| `raw_text` | Exact citation substring in unit text. |
| `citation_type` | `internal` (within current act) or `eu_legislation` (external EU act). |
| `span_start`, `span_end` | Character offsets of citation in unit text (`start` inclusive, `end` exclusive). |
| `article`, `paragraph`, `point`, `subparagraph_ordinal`, `subparagraph_index` | Parsed structural targets when detected (`subparagraph_index` is 1-based when resolvable). |
| `article_range` | Inclusive `(start, end)` article range for references like `Articles X to Y`. |
| `target_node_id` | Resolved internal unit id only when present in the current document tree; otherwise `null`. |
| `act_type`, `act_number`, `celex` | External act metadata for `eu_legislation` citations. |

Breaking change: legacy root-list JSON is no longer supported by coverage/batch tools.

Citation note: a single phrase may intentionally emit multiple citation objects when it references multiple targets (for example `Articles 13 and 14`).
Resolver note: standalone `points (...)` citations now inherit article/paragraph context from the nearest
preceding internal anchor in the same clause (for example `paragraph 1, points (a) and (b)`), with
subparagraph parent-chain fallback when no anchor exists.
Resolver note: bare `that Directive/that Regulation/that Decision` references are reclassified to
`eu_legislation` when exactly one matching antecedent act of the same type exists earlier in the same unit.

Canonical example in repo:

- `examples/DORA.json` (Regulation (EU) 2022/2554, DORA)

Example parser output:

```json
{
  "document_metadata": {
    "title": "REGULATION (EU) 2022/2554 ...",
    "total_units": 994,
    "total_articles": 64,
    "total_paragraphs": 267,
    "total_points": 385,
    "total_definitions": 65,
    "has_annexes": false,
    "amendment_articles": ["59", "60", "61", "62", "63"]
  },
  "summary_lsu": {
    "celex": "32022R2554",
    "language": "EN",
    "title": "Digital operational resilience for the financial sector",
    "sections": [
      {
        "heading": "SUMMARY OF:",
        "content": "Regulation (EU) 2022/2554 on digital operational resilience for the financial sector"
      }
    ],
    "source_url": "https://eur-lex.europa.eu/legal-content/EN/LSU/?uri=CELEX:32022R2554",
    "canonical_url": "https://eur-lex.europa.eu/EN/legal-content/summary/digital-operational-resilience-for-the-financial-sector.html",
    "last_modified_text": "last update 26.1.2026",
    "last_modified_date": "2026-01-26"
  },
  "summary_lsu_status": "ok",
  "units": [
    {
      "id": "art-5.par-2.subpar-1",
      "type": "subparagraph",
      "ref": null,
      "text": "For the purposes of the first subparagraph, the management body shall:",
      "parent_id": "art-5.par-2",
      "source_id": "",
      "source_file": "downloads/eur-lex/32022R2554.html",
      "article_number": "5",
      "paragraph_number": "2",
      "subparagraph_index": 1,
      "point_label": null,
      "target_path": "Art. 5(2)",
      "article_heading": "Governance and organisation",
      "children_count": 9,
      "is_leaf": false,
      "is_stem": true,
      "word_count": 11,
      "char_count": 70,
      "citations": [
        {
          "raw_text": "the first subparagraph",
          "citation_type": "internal",
          "span_start": 20,
          "span_end": 42,
          "article": 5,
          "article_label": "5",
          "paragraph": 2,
          "point": null,
          "point_range": null,
          "article_range": null,
          "paragraph_range": null,
          "subparagraph_ordinal": "first",
          "subparagraph_index": 1,
          "chapter": null,
          "section": null,
          "title_ref": null,
          "annex": null,
          "annex_part": null,
          "treaty_code": null,
          "connective_phrase": "for the purposes of",
          "target_node_id": "art-5.par-2",
          "act_year": null,
          "act_type": null,
          "act_number": null,
          "celex": null
        }
      ]
    }
  ]
}
```

LSU enrichment controls in `eurlex-parse`:

- default behavior: LSU fetch enabled
- `--no-summary-lsu`: disable LSU fetch (`summary_lsu_status=disabled`)
- `--summary-lsu-lang <LANG>`: override LSU language (default: auto-detect from source HTML, fallback `EN`)
- `--celex <CELEX>`: explicit CELEX override for LSU query

## Quality Gates

Batch pass criteria used by `eurlex-batch`:

- `gone == 0`
- `phantom == 0`
- `hierarchy_ok == true`
- `ordering_ok == true`
- non-vacuous parse

Batch CLI supports:

- `--links-file` for custom JSONL corpus path
- `--offset` and `--limit` for processing in fixed-size batches
- `--snapshot-tag` to persist per-batch report snapshots under `reports/batches/`

## Repository Layout

```text
.
├── data/                         # benchmark links
├── downloads/                    # downloaded HTML corpus (gitignored)
├── out/                          # parser outputs (gitignored)
├── reports/                      # batch reports (JSONL gitignored)
├── src/eurlex_unit_parser/
│   ├── parser/                   # modular parser engine + OJ/consolidated/annex flows
│   ├── coverage/                 # coverage extraction/comparison/report logic
│   ├── batch/                    # batch pipeline
│   ├── download/                 # EUR-Lex downloader
│   ├── api.py                    # high-level single-document library facade
│   └── cli/                      # CLI entrypoints
└── tests/                        # regression + compatibility tests
```

## Security and Responsible Use

If you find a security issue, see `SECURITY.md`.

## Contributing

See `CONTRIBUTING.md` for development workflow and PR rules.

## Changelog

See `CHANGELOG.md`.

## License

MIT. See `LICENSE`.
