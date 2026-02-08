# Reports

This directory is used for generated benchmark outputs.

Generated files (gitignored):

- `eurlex_coverage_success.jsonl`
- `eurlex_coverage_failures.jsonl`

To regenerate:

```bash
python3 run_batch.py --force-reparse --oracle mirror
```
