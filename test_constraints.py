import pytest

from constraints import (
    AbsolutePosition,
    And,
    Or,
    RelativePosition,
    validate_constraints,
)
from possibilities import PossibilityGrid
from puzzle import Puzzle


# Shared 4-position, single-category puzzle.
def make_puzzle():
    return Puzzle({"color": ["red", "green", "blue", "yellow"]}, 4)


def make_grid():
    return PossibilityGrid(make_puzzle())


# "==" pins the value to one spot and clears every other value from that spot.
def test_absolute_equals_pins_value_and_clears_the_position():
    grid = make_grid()

    changed = AbsolutePosition(("color", "green"), "==", 2).propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "green") == [2]
    assert grid.candidates("color", 2) == {"green"}


# "!=" removes exactly one candidate and leaves the rest alone.
def test_absolute_not_equals_removes_only_that_candidate():
    grid = make_grid()

    changed = AbsolutePosition(("color", "red"), "!=", 1).propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "red") == [2, 3, 4]
    # Nothing else at position 1 was touched.
    assert grid.candidates("color", 1) == {"green", "blue", "yellow"}


# "<" is strict: the value is ruled out at the named position and above.
def test_absolute_less_than_rules_out_that_position_and_above():
    grid = make_grid()

    changed = AbsolutePosition(("color", "red"), "<", 3).propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "red") == [1, 2]


def test_absolute_greater_than_rules_out_that_position_and_below():
    grid = make_grid()

    changed = AbsolutePosition(("color", "red"), ">", 2).propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "red") == [3, 4]


# Running the same clue twice must report "nothing changed" the second time,
# otherwise the solver loop would never reach a fixed point.
def test_absolute_propagate_is_idempotent():
    grid = make_grid()
    constraint = AbsolutePosition(("color", "green"), "==", 2)

    assert constraint.propagate(grid) is True
    assert constraint.propagate(grid) is False


# Bad operators are caught at construction, not deep inside propagation.
def test_unsupported_operator_rejected_at_construction():
    with pytest.raises(ValueError, match="unsupported operator"):
        AbsolutePosition(("color", "red"), "<=", 2)

    with pytest.raises(ValueError, match="unsupported operator"):
        RelativePosition(("color", "red"), ("color", "green"), "~", 1)


# Documents the current stub. Delete/replace this once arc consistency lands.
def test_relative_position_is_not_implemented_yet():
    grid = make_grid()

    changed = RelativePosition(("color", "green"), ("color", "blue"), "==", 1).propagate(grid)

    assert changed is False
    assert grid.candidates("color", 1) == {"red", "green", "blue", "yellow"}


# And runs every child, so eliminations from all of them land.
def test_and_propagates_all_children():
    grid = make_grid()

    changed = And([
        AbsolutePosition(("color", "red"), "!=", 1),
        AbsolutePosition(("color", "green"), "!=", 2),
    ]).propagate(grid)

    assert changed is True
    assert not grid.is_candidate("color", 1, "red")
    assert not grid.is_candidate("color", 2, "green")


def test_and_reports_no_change_once_children_are_settled():
    grid = make_grid()
    constraint = And([AbsolutePosition(("color", "red"), "!=", 1)])

    assert constraint.propagate(grid) is True
    assert constraint.propagate(grid) is False


# Documents the current stub. Or needs speculation, which isn't built yet.
def test_or_is_not_implemented_yet():
    grid = make_grid()

    changed = Or([AbsolutePosition(("color", "red"), "==", 1)]).propagate(grid)

    assert changed is False
    assert grid.candidates("color", 1) == {"red", "green", "blue", "yellow"}


# validate_constraints guards the boundary where AI-written constraints arrive.
def test_validate_accepts_a_well_formed_constraint():
    validate_constraints(make_puzzle(), AbsolutePosition(("color", "red"), "==", 1))


def test_validate_rejects_unknown_category():
    with pytest.raises(ValueError, match="not a category"):
        validate_constraints(make_puzzle(), AbsolutePosition(("drink", "tea"), "==", 1))


def test_validate_rejects_unknown_value():
    with pytest.raises(ValueError, match="not a valid value"):
        validate_constraints(make_puzzle(), AbsolutePosition(("color", "purple"), "==", 1))


# Both sides of a relative clue get checked.
def test_validate_checks_both_ends_of_relative_position():
    constraint = RelativePosition(("color", "red"), ("color", "purple"), "==", 1)

    with pytest.raises(ValueError, match="not a valid value"):
        validate_constraints(make_puzzle(), constraint)


def test_validate_recurses_into_combinators():
    nested = And([Or([AbsolutePosition(("color", "purple"), "==", 1)])])

    with pytest.raises(ValueError, match="not a valid value"):
        validate_constraints(make_puzzle(), nested)


def test_validate_rejects_unknown_constraint_type():
    with pytest.raises(TypeError, match="unknown constraint type"):
        validate_constraints(make_puzzle(), object())
