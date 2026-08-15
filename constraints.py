from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
import operator as op


class TriState(Enum):
    """Result of checking a constraint against an assignment that may be incomplete."""
    SATISFIED = auto()
    VIOLATED = auto()
    UNDETERMINED = auto()


# Maps the operator strings constraints use onto Python's comparison functions.
_OPERATORS = {
    "==": op.eq,
    "!=": op.ne,
    "<": op.lt,
    ">": op.gt,
}


class Constraint(ABC):
    """Something that can be checked against an Assignment."""

    @abstractmethod
    def check(self, assignment):
        """Return a TriState: does this constraint hold given what's assigned so far?"""


@dataclass
class AbsolutePosition(Constraint):
    """(category, value) compared to a literal position, e.g. Norwegian in house 1."""

    category_value: tuple
    operator: str
    position: int

    def check(self, assignment):
        category, value = self.category_value
        actual_position = assignment.try_position_of(category, value)
        if actual_position is None:
            return TriState.UNDETERMINED

        holds = _OPERATORS[self.operator](actual_position, self.position)
        return TriState.SATISFIED if holds else TriState.VIOLATED


@dataclass
class RelativePosition(Constraint):
    """position(a) + offset {operator} position(b), e.g. green immediately left of white."""

    a: tuple
    b: tuple
    operator: str
    offset: int = 0

    def check(self, assignment):
        a_category, a_value = self.a
        b_category, b_value = self.b
        a_position = assignment.try_position_of(a_category, a_value)
        b_position = assignment.try_position_of(b_category, b_value)
        if a_position is None or b_position is None:
            return TriState.UNDETERMINED

        holds = _OPERATORS[self.operator](a_position + self.offset, b_position)
        return TriState.SATISFIED if holds else TriState.VIOLATED


@dataclass
class And(Constraint):
    """Holds only if every child constraint holds."""

    constraints: list

    def check(self, assignment):
        saw_undetermined = False
        for c in self.constraints:
            result = c.check(assignment)
            if result == TriState.VIOLATED:
                return TriState.VIOLATED
            if result == TriState.UNDETERMINED:
                saw_undetermined = True
        return TriState.UNDETERMINED if saw_undetermined else TriState.SATISFIED


@dataclass
class Or(Constraint):
    """Holds if at least one child constraint holds."""

    constraints: list

    def check(self, assignment):
        saw_undetermined = False
        for c in self.constraints:
            result = c.check(assignment)
            if result == TriState.SATISFIED:
                return TriState.SATISFIED
            if result == TriState.UNDETERMINED:
                saw_undetermined = True
        return TriState.UNDETERMINED if saw_undetermined else TriState.VIOLATED


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
