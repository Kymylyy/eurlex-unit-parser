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
- Architecture: modular package (`src/eurlex_unit_parser`) with legacy wrappers preserved

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

### Option B: legacy script mode

```bash
python3 -m pip install -r requirements.txt
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
python3 convert_links_csv.py --input data/eurlex_test_links.csv --output data/eurlex_test_links.jsonl
```

- Downloader:

```bash
eurlex-download "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689" EMIR3
```

### Legacy CLI (still supported)

- `python3 parse_eu.py ...`
- `python3 test_coverage.py ...`
- `python3 run_batch.py ...`
- `python3 convert_links_csv.py ...`
- `python3 download_eurlex.py ...`

## Public API

### New package imports

```python
from eurlex_unit_parser import Citation, EUParser, Unit, ValidationReport
```

### Legacy imports (still supported)

```python
from parse_eu import EUParser
from parse_eu import remove_note_tags, normalize_text, strip_leading_label, is_list_table, get_cell_text
```

## JSON Contract

Parser output (`eurlex-parse`) is a JSON object:

- `document_metadata`: document-level summary and aggregate counters.
- `units`: flat array of parsed units in document order.

Validation output (`--validation`) is a separate JSON object described by `ValidationReport`.

Each `unit` includes a `citations` list (possibly empty) populated during enrichment.
Structural index fields include `paragraph_index` and `subparagraph_index` (both optional, 1-based when present).
Citation extraction supports v0.2 patterns and optional metadata fields:
`article_label`, `point_range`, `paragraph_range`, `subparagraph_ordinal`, `chapter`,
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
| `article`, `paragraph`, `point` | Parsed structural targets when detected. |
| `article_range` | Inclusive `(start, end)` article range for references like `Articles X to Y`. |
| `target_node_id` | Resolved internal unit id only when present in the current document tree; otherwise `null`. |
| `act_type`, `act_number`, `celex` | External act metadata for `eu_legislation` citations. |

Breaking change: legacy root-list JSON is no longer supported by coverage/batch tools.

Citation note: a single phrase may intentionally emit multiple citation objects when it references multiple targets (for example `Articles 13 and 14`).

Canonical example in repo:

- `examples/DORA.json` (Regulation (EU) 2022/2554, DORA)

Example parser output:

```json
{
  "document_metadata": {
    "title": "REGULATION (EU) 2022/2554 ...",
    "total_units": 888,
    "total_articles": 64,
    "total_paragraphs": 267,
    "total_points": 385,
    "total_definitions": 65,
    "has_annexes": false,
    "amendment_articles": ["59", "60", "61", "62", "63"]
  },
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

## Quality Gates

Batch pass criteria used by `eurlex-batch` / `run_batch.py`:

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
│   └── cli/                      # CLI entrypoints
├── parse_eu.py                   # legacy wrapper + re-exports
├── test_coverage.py              # legacy wrapper + re-exports
├── run_batch.py                  # legacy wrapper + re-exports
├── convert_links_csv.py          # CSV -> JSONL links converter wrapper
├── download_eurlex.py            # legacy wrapper + re-exports
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
