class Puzzle:
    """The shape of a puzzle: categories, their legal values, and how many
    positions exist. Purely descriptive — no constraints, no solving."""

    def __init__(self, categories, num_positions):
        # Copy so mutating this Puzzle doesn't affect the caller's dict.
        self.categories = {}
        for name, values in categories.items():
            self.categories[name] = list(values)

        self.num_positions = num_positions
        self._validate()

        # 1-indexed to match how puzzle clues refer to positions ("house 1").
        self.positions = list(range(1, self.num_positions + 1))

    def _validate(self):
        """A legal puzzle: at least one position, at least one category, every
        category has exactly num_positions values, and no repeats in a category."""
        if self.num_positions < 1:
            raise ValueError("num_positions must be at least 1")
        if not self.categories:
            raise ValueError("puzzle must have at least one category")

        for name, values in self.categories.items():
            if len(values) != self.num_positions:
                raise ValueError(
                    f"category '{name}' has {len(values)} values, expected {self.num_positions}"
                )
            if len(set(values)) != len(values):
                raise ValueError(f"category '{name}' has duplicate values: {values}")
