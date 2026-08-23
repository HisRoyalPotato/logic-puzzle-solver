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


# "Somewhere to the left": the leftmost spot has nothing to its left to pair
# with, and the rightmost has nothing to its right.
def test_relative_less_than_trims_both_ends():
    grid = make_grid()

    changed = RelativePosition(("color", "green"), ("color", "blue"), "<").propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "green") == [1, 2, 3]
    assert grid.positions_for("color", "blue") == [2, 3, 4]


def test_relative_greater_than_trims_both_ends():
    grid = make_grid()

    changed = RelativePosition(("color", "green"), ("color", "blue"), ">").propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "green") == [2, 3, 4]
    assert grid.positions_for("color", "blue") == [1, 2, 3]


# "Immediately left of" is offset 1 with "==": pos(green) + 1 == pos(blue).
def test_relative_immediately_left_trims_one_spot_from_each_end():
    grid = make_grid()

    changed = RelativePosition(("color", "green"), ("color", "blue"), "==", 1).propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "green") == [1, 2, 3]
    assert grid.positions_for("color", "blue") == [2, 3, 4]


# The user's worked example: green left of blue, blue already down to 1 or 2.
# Blue can't be 1 (nothing is left of house 1), so blue is 2 and green is 1.
def test_relative_narrows_when_the_partner_is_already_narrowed():
    puzzle = Puzzle({"color": ["red", "green", "blue"]}, 3)
    grid = PossibilityGrid(puzzle)
    grid.eliminate("color", 3, "blue")

    RelativePosition(("color", "green"), ("color", "blue"), "<").propagate(grid)

    assert grid.positions_for("color", "green") == [1]
    assert grid.positions_for("color", "blue") == [2]


# A pinned partner leaves only one illegal spot for "!=".
def test_relative_not_equals_only_bites_when_partner_is_pinned():
    grid = make_grid()
    for position in [1, 2, 4]:
        grid.eliminate("color", position, "blue")

    changed = RelativePosition(("color", "green"), ("color", "blue"), "!=").propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "green") == [1, 2, 4]


# Cross-category, offset 0: "the same position as".
def test_relative_equals_links_two_categories():
    puzzle = Puzzle({"person": ["anna", "ben"], "pet": ["cat", "dog"]}, 2)
    grid = PossibilityGrid(puzzle)
    grid.eliminate("person", 1, "anna")

    RelativePosition(("person", "anna"), ("pet", "cat"), "==").propagate(grid)

    assert grid.positions_for("pet", "cat") == [2]


# Once arc consistent, a second pass must report no change so the outer
# fixed-point loop can stop.
def test_relative_propagate_is_idempotent():
    grid = make_grid()
    constraint = RelativePosition(("color", "green"), ("color", "blue"), "==", 1)

    assert constraint.propagate(grid) is True
    assert constraint.propagate(grid) is False


# A negative offset flips the direction: pos(green) - 1 == pos(blue) means
# green sits immediately to the RIGHT of blue.
def test_relative_negative_offset_reverses_the_direction():
    grid = make_grid()

    changed = RelativePosition(("color", "green"), ("color", "blue"), "==", -1).propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "green") == [2, 3, 4]
    assert grid.positions_for("color", "blue") == [1, 2, 3]


# An offset bigger than the board leaves no legal pair at all, so both sides
# lose every position. propagate() itself doesn't raise here — no single spot
# runs out of values — the loop's "every value needs a home" rule catches it.
def test_relative_impossible_offset_empties_both_sides():
    grid = make_grid()

    RelativePosition(("color", "green"), ("color", "blue"), "==", 9).propagate(grid)

    assert grid.positions_for("color", "green") == []
    assert grid.positions_for("color", "blue") == []


# allows() is the yes/no pair test the sweep is built on.
def test_allows_encodes_operator_and_offset():
    immediately_left = RelativePosition(("color", "green"), ("color", "blue"), "==", 1)

    assert immediately_left.allows(1, 2) is True
    assert immediately_left.allows(2, 1) is False
    assert immediately_left.allows(1, 3) is False


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


# Mixed children: the absolute clue runs first and knocks green off house 1,
# and the relative clue immediately feeds on that narrower green inside the
# same pass — so blue loses house 2 as well as house 1.
def test_and_mixes_absolute_and_relative_children():
    grid = make_grid()

    changed = And([
        AbsolutePosition(("color", "green"), "!=", 1),
        RelativePosition(("color", "green"), ("color", "blue"), "==", 1),
    ]).propagate(grid)

    assert changed is True
    assert grid.positions_for("color", "green") == [2, 3]
    assert grid.positions_for("color", "blue") == [3, 4]


# And recurses into nested And, so a bundled group prunes like a flat list.
def test_and_recurses_into_nested_and():
    grid = make_grid()

    And([
        And([
            AbsolutePosition(("color", "green"), "!=", 1),
            RelativePosition(("color", "green"), ("color", "blue"), "==", 1),
        ]),
        AbsolutePosition(("color", "blue"), "!=", 4),
    ]).propagate(grid)

    assert grid.positions_for("color", "green") == [2, 3]
    assert grid.positions_for("color", "blue") == [3]


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
