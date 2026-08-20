from abc import ABC, abstractmethod
from dataclasses import dataclass
import operator as op


# Maps the operator strings constraints use onto Python's comparison functions.
_OPERATORS = {
    "==": op.eq,
    "!=": op.ne,
    "<": op.lt,
    ">": op.gt,
}


def _validate_operator(operator):
    """Raise ValueError if `operator` isn't one of the supported comparisons."""
    if operator not in _OPERATORS:
        raise ValueError(f"unsupported operator '{operator}', expected one of {sorted(_OPERATORS)}")


class Constraint(ABC):
    """A clue. Knows how to rule candidates out of a PossibilityGrid."""

    @abstractmethod
    def propagate(self, possibilities):
        """Rule out candidates this clue proves impossible.
        Returns True if anything was actually eliminated."""


@dataclass
class AbsolutePosition(Constraint):
    """(category, value) compared to a literal position, e.g. Norwegian in house 1."""

    category_value: tuple
    operator: str
    position: int

    def __post_init__(self):
        _validate_operator(self.operator)

    def propagate(self, possibilities):
        category, value = self.category_value
        puzzle = possibilities.puzzle
        changed = False

        if self.operator == "==":
            # Pinned here, so it can't be anywhere else — and nothing else can
            # be here, since a category maps one-to-one onto positions.
            for position in puzzle.positions:
                if position != self.position and possibilities.eliminate(category, position, value):
                    changed = True
            for other_value in puzzle.categories[category]:
                if other_value != value and possibilities.eliminate(category, self.position, other_value):
                    changed = True

        elif self.operator == "!=":
            if possibilities.eliminate(category, self.position, value):
                changed = True

        elif self.operator == "<":
            # Must sit below self.position, so rule it out at or above.
            for position in puzzle.positions:
                if position >= self.position and possibilities.eliminate(category, position, value):
                    changed = True

        elif self.operator == ">":
            for position in puzzle.positions:
                if position <= self.position and possibilities.eliminate(category, position, value):
                    changed = True

        return changed


@dataclass
class RelativePosition(Constraint):
    """position(a) + offset {operator} position(b), e.g. green immediately left of white."""

    a: tuple
    b: tuple
    operator: str
    offset: int = 0

    def __post_init__(self):
        _validate_operator(self.operator)

    def propagate(self, possibilities):
        # Not built yet. Needs arc consistency: drop any candidate position for
        # `a` that no candidate position of `b` can satisfy, then the reverse.
        return False


@dataclass
class And(Constraint):
    """Holds only if every child holds, so every child may eliminate freely."""

    constraints: list

    def propagate(self, possibilities):
        # No short-circuiting — each child may rule out different candidates.
        changed = False
        for constraint in self.constraints:
            if constraint.propagate(possibilities):
                changed = True
        return changed


@dataclass
class Or(Constraint):
    """Holds if at least one child holds."""

    constraints: list

    def propagate(self, possibilities):
        # Not built yet. A candidate is only impossible if it's impossible in
        # every branch, which needs trial elimination per branch then an
        # intersection of the results.
        return False


def validate_constraints(puzzle, constraint):
    """Check that every (category, value) `constraint` references actually
    exists in `puzzle`. Raises ValueError on the first bad reference found."""
    if isinstance(constraint, AbsolutePosition):
        _check_value_exists(puzzle, *constraint.category_value)
    elif isinstance(constraint, RelativePosition):
        _check_value_exists(puzzle, *constraint.a)
        _check_value_exists(puzzle, *constraint.b)
    elif isinstance(constraint, (And, Or)):
        for child in constraint.constraints:
            validate_constraints(puzzle, child)
    else:
        raise TypeError(f"unknown constraint type: {type(constraint).__name__}")


def _check_value_exists(puzzle, category, value):
    """Raise ValueError if `value` isn't a legal value for `category` in `puzzle`."""
    if category not in puzzle.categories:
        raise ValueError(f"'{category}' is not a category in this puzzle")
    if value not in puzzle.categories[category]:
        raise ValueError(f"'{value}' is not a valid value for category '{category}'")
