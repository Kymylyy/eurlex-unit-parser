# Data Sets

- `eurlex_links.jsonl`: Core benchmark corpus (52 links), used by default by `eurlex-batch`.
- `eurlex_test_links.csv`: Extended candidate corpus in CSV format (70 links).
- `eurlex_test_links.jsonl`: Extended candidate corpus converted to JSONL for batch runner input.

Fields:

- `url`: EUR-Lex HTML URL
- `celex`: CELEX identifier
- `title`: Human-readable act title
- `category_hint`: Domain/category hint (JSONL)
- `source`: Source tag for provenance (`candidate_csv` in converted extended corpus)
