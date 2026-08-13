class Assignment:
    """One candidate puzzle solution: raw values per category/position,
    plus a reverse index for fast lookups."""

    def __init__(self, raw):
        # Copy so mutating this Assignment doesn't affect the caller's dict.
        self._raw = {category: dict(positions) for category, positions in raw.items()}

        # Build the reverse index once, scanning _raw a single time.
        self._index = {}
        for category, positions in self._raw.items():
            for position, value in positions.items():
                self._index[(category, value)] = position

    def value_at(self, category, position):
        """What value does `category` have at `position`?"""
        return self._raw[category][position]

    def position_of(self, category, value):
        """Which position has `value` for `category`?"""
        return self._index[(category, value)]

    def set_value(self, category, position, value):
        """Assign a value, keeping _raw and _index in sync."""
        old_value = self._raw[category].get(position)

        # Drop the stale index entry for the value being replaced.
        if old_value is not None and (category, old_value) in self._index:
            del self._index[(category, old_value)]

        self._raw[category][position] = value
        self._index[(category, value)] = position
