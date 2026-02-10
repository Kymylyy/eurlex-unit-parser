# EUR-Lex Unit Parser

Parser for EU Official Journal (EUR-Lex) HTML documents.
It converts ELI-style legislation pages into structured JSON with document metadata and legal units
(document titles, recitals, articles, paragraphs, points, subpoints, annex items).

## Status

- Language: Python 3.10+
- License: MIT
- Validation corpus: 52 EUR-Lex documents (`data/eurlex_links.jsonl`)
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

- Downloader:

```bash
eurlex-download "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689" EMIR3
```

### Legacy CLI (still supported)

- `python3 parse_eu.py ...`
- `python3 test_coverage.py ...`
- `python3 run_batch.py ...`
- `python3 download_eurlex.py ...`

## Public API

### New package imports

```python
from eurlex_unit_parser import EUParser, Unit, ValidationReport
```

### Legacy imports (still supported)

```python
from parse_eu import EUParser
from parse_eu import remove_note_tags, normalize_text, strip_leading_label, is_list_table, get_cell_text
```

## Output Format

Each JSON output is an object:

- `document_metadata`: document-level summary metadata
- `units`: flat array of parsed units

Breaking change: legacy root-list JSON is no longer supported by coverage/batch tools.

Canonical example in repo:

- `examples/DORA.json` (Regulation (EU) 2022/2554, DORA)

Example:

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
      "id": "art-5.par-1.pt-a",
      "type": "point",
      "ref": "(a)",
      "text": "processed lawfully, fairly and in a transparent manner...",
      "parent_id": "art-5.par-1",
      "article_number": "5",
      "paragraph_number": "1",
      "point_label": "a",
      "target_path": "Art. 5(1)(a)",
      "article_heading": "Definitions",
      "children_count": 0,
      "is_leaf": true,
      "is_stem": false,
      "word_count": 10,
      "char_count": 61
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
