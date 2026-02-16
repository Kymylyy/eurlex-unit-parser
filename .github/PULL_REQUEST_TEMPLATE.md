## Summary

- What changed?
- Why?

## Validation

- [ ] `ruff check .`
- [ ] `mypy src/eurlex_unit_parser`
- [ ] `pytest -q`
- [ ] Benchmark impact reviewed (if parser logic changed)

## Checklist

- [ ] No machine-specific absolute paths added
- [ ] No generated artifacts from `downloads/` or `out/` committed
- [ ] Docs updated (`README.md` / `CHANGELOG.md`) if behavior changed
