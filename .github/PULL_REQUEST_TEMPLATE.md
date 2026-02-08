## Summary

- What changed?
- Why?

## Validation

- [ ] `python3 -m py_compile parse_eu.py test_coverage.py run_batch.py`
- [ ] `python3 -m pytest -q`
- [ ] Benchmark impact reviewed (if parser logic changed)

## Checklist

- [ ] No machine-specific absolute paths added
- [ ] No generated artifacts from `downloads/` or `out/` committed
- [ ] Docs updated (`README.md` / `CHANGELOG.md`) if behavior changed
