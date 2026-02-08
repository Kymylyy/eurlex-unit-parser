# EUR-Lex Parser

Parser for EU Official Journal (EUR-Lex) HTML documents.
It converts ELI-style legislation pages into a flat JSON list of legal units
(recitals, articles, paragraphs, points, subpoints, annex items).

## Status

- Language: Python 3.10+
- License: MIT
- Validation corpus: 52 EUR-Lex documents (`data/eurlex_links.jsonl`)
- Latest benchmark target: `mirror` oracle, forced reparse

Current benchmark result on this corpus:

- `52 / 52 PASS`
- `gone = 0` (no text loss)
- `phantom = 0` (no hallucinated text)
- `hierarchy_ok = true`
- `ordering_ok = true`

## Requirements

- Python 3.10+
- Core dependencies: `lxml`, `beautifulsoup4`
- Optional downloader dependency: `playwright`

Install core dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Optional (for remote downloading):

```bash
python3 -m pip install playwright
playwright install chromium
```

## Quick Start

### 1. Parse a single HTML file

```bash
python3 parse_eu.py --input downloads/eur-lex/32022R2554.html
```

Default outputs:

- `out/json/<name>.json`
- `out/validation/<name>_validation.json`

### 2. Run coverage test for a single document

```bash
python3 test_coverage.py \
  --input downloads/eur-lex/32022R2554.html \
  --json out/json/32022R2554.json \
  --oracle mirror
```

### 3. Run full batch benchmark (reproducible)

```bash
python3 run_batch.py --force-reparse --oracle mirror
```

Reports are generated into:

- `reports/eurlex_coverage_success.jsonl`
- `reports/eurlex_coverage_failures.jsonl`

## Output Format

Each JSON output is a flat array of units.

Canonical example file in this repository:

- `examples/DORA.json` (Regulation (EU) 2022/2554, DORA)

Example:

```json
{
  "id": "art-5.par-1.pt-a",
  "type": "point",
  "ref": "(a)",
  "text": "processed lawfully, fairly and in a transparent manner...",
  "parent_id": "art-5.par-1",
  "article_number": "5",
  "paragraph_number": "1",
  "point_label": "a"
}
```

## Quality Gates

The project uses two coverage perspectives:

- `text recall`: checks whether source text was preserved (`gone == 0`)
- `strict coverage`: checks type-accurate matching (e.g. point vs subparagraph)

Batch pass criteria currently used by `run_batch.py`:

- `gone == 0`
- `phantom == 0`
- `hierarchy_ok == true`
- `ordering_ok == true`
- non-vacuous parse

## Repository Layout

```text
.
├── data/                     # benchmark links
├── downloads/                # downloaded HTML corpus (gitignored)
├── out/                      # parser outputs (gitignored)
├── examples/                 # committed sample output (DORA)
├── reports/                  # batch reports (JSONL gitignored)
├── parse_eu.py               # parser
├── test_coverage.py          # coverage oracle + validators
├── run_batch.py              # corpus benchmark runner
├── tests/                    # regression tests
└── download_eurlex.py        # downloader helper
```

## Known Scope and Limitations

- Focus is EUR-Lex ELI HTML structures used in the benchmark corpus.
- EUR-Lex markup can evolve; new edge cases may require parser updates.
- This project does not redistribute legal texts by itself.

## Security and Responsible Use

If you find a security issue, see `SECURITY.md`.

## Contributing

See `CONTRIBUTING.md` for development workflow and PR rules.

## Changelog

See `CHANGELOG.md`.

## License

MIT. See `LICENSE`.
