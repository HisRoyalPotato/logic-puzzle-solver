class Contradiction(Exception):
    """Raised when eliminating a candidate would leave a position with no possible values."""


class PossibilityGrid:
    """Tracks, per (category, position), the set of values not yet ruled out."""

    def __init__(self, puzzle):
        # Every position starts able to be any legal value for its category.
        self._candidates = {}
        for category, values in puzzle.categories.items():
            for position in puzzle.positions:
                self._candidates[(category, position)] = set(values)

    def candidates(self, category, position):
        """Copy of the current possible values for (category, position)."""
        return set(self._candidates[(category, position)])

    def eliminate(self, category, position, value):
        """Rule out `value` at (category, position). No-op if already ruled out."""
        remaining = self._candidates[(category, position)]
        if value not in remaining:
            return

        remaining.discard(value)
        if not remaining:
            raise Contradiction(f"no values remain for '{category}' at position {position}")

    def is_forced(self, category, position):
        """True if exactly one candidate remains for (category, position)."""
        return len(self._candidates[(category, position)]) == 1

    def forced_value(self, category, position):
        """The single remaining candidate. Raises if not yet forced."""
        remaining = self._candidates[(category, position)]
        if len(remaining) != 1:
            raise ValueError(f"'{category}' at position {position} is not yet forced: {remaining}")
        return next(iter(remaining))
