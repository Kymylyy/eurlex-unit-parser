"""Validation mixin for parser output integrity."""


class ValidationMixin:
    """Mixin with post-parse integrity checks."""

    def _validate(self) -> None:
        all_ids = {u.id for u in self.units}
        for unit in self.units:
            if unit.parent_id and unit.parent_id not in all_ids:
                self.validation.orphans.append({"id": unit.id, "parent_id": unit.parent_id})

        recital_nums = sorted(
            [
                int(u.recital_number)
                for u in self.units
                if u.type == "recital" and u.recital_number and u.recital_number.isdigit()
            ]
        )
        if recital_nums:
            expected = set(range(1, max(recital_nums) + 1))
            actual = set(recital_nums)
            gaps = expected - actual
            if gaps:
                self.validation.sequence_gaps.append({"type": "recital", "missing": sorted(gaps)})
