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


def _has_legal_partner(position, partner_positions, pair_is_legal):
    """True if at least one of `partner_positions` forms a legal pair with
    `position`. One surviving partner is enough to keep the position alive."""
    for partner_position in partner_positions:
        if pair_is_legal(position, partner_position):
            return True
    return False


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

    def allows(self, position_a, position_b):
        """True if this pair of positions would satisfy the clue."""
        compare = _OPERATORS[self.operator]
        return compare(position_a + self.offset, position_b)

    def propagate(self, possibilities):
        """Arc consistency, both directions: a position survives only if the
        other side has at least one surviving position it can pair with."""
        changed = False

        # Prune `a` first, then prune `b` against the already-narrowed `a`,
        # so a single pass squeezes out as much as it can.
        if self._prune(possibilities, self.a, self.b, self.allows):
            changed = True
        if self._prune(possibilities, self.b, self.a, lambda pb, pa: self.allows(pa, pb)):
            changed = True

        return changed

    def _prune(self, possibilities, target, partner, pair_is_legal):
        """Eliminate every position for `target` that no remaining position of
        `partner` can legally pair with. `pair_is_legal` takes the positions in
        (target, partner) order. Returns True if anything was eliminated."""
        target_category, target_value = target
        partner_category, partner_value = partner

        # Snapshot both sides up front — positions_for returns a fresh list,
        # so eliminating below can't disturb what we're looping over.
        partner_positions = possibilities.positions_for(partner_category, partner_value)
        target_positions = possibilities.positions_for(target_category, target_value)

        changed = False
        for target_position in target_positions:
            if _has_legal_partner(target_position, partner_positions, pair_is_legal):
                continue
            if possibilities.eliminate(target_category, target_position, target_value):
                changed = True

        return changed


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
