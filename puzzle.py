class Puzzle:
    """The shape of a puzzle: categories, their legal values, and how many
    positions exist. Purely descriptive — no constraints, no solving."""

    def __init__(self, categories):
        # Copy so mutating this Puzzle doesn't affect the caller's dict.
        self.categories = {}
        for name, values in categories.items():
            self.categories[name] = list(values)

        self._validate()

        # Every category has the same length (checked above), so any one works.
        self.size = len(next(iter(self.categories.values())))
        # 1-indexed to match how puzzle clues refer to positions ("house 1").
        self.positions = list(range(1, self.size + 1))

    def _validate(self):
        """A legal puzzle: every category has the same number of values,
        and no value repeats within a category."""
        sizes = set()
        for values in self.categories.values():
            sizes.add(len(values))
        if len(sizes) > 1:
            raise ValueError(
                f"all categories must have the same number of values, got sizes {sizes}"
            )

        for name, values in self.categories.items():
            if len(set(values)) != len(values):
                raise ValueError(f"category '{name}' has duplicate values: {values}")
