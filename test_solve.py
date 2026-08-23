import pytest

from constraints import AbsolutePosition
from possibilities import Contradiction, PossibilityGrid
from puzzle import Puzzle
from solve import (
    apply_value_must_be_somewhere,
    apply_value_used_once,
    propagate_until_stable,
)


def make_grid(categories, num_positions):
    return PossibilityGrid(Puzzle(categories, num_positions))


def make_color_grid():
    return make_grid({"color": ["red", "green", "blue", "yellow"]}, 4)


# Reads the finished grid back as {position: value} for one category.
def solution_for(grid, category):
    solved = {}
    for position in grid.puzzle.positions:
        solved[position] = grid.forced_value(category, position)
    return solved


# Rule 1: a position pinned to one value blocks that value everywhere else.
def test_value_used_once_clears_the_value_from_other_positions():
    grid = make_color_grid()
    for value in ["green", "blue", "yellow"]:
        grid.eliminate("color", 1, value)

    changed = apply_value_used_once(grid)

    assert changed is True
    assert grid.positions_for("color", "red") == [1]


def test_value_used_once_does_nothing_when_no_position_is_forced():
    grid = make_color_grid()

    assert apply_value_used_once(grid) is False


# Rule 2: a value with only one home left claims that position outright.
def test_value_must_be_somewhere_claims_the_last_open_position():
    grid = make_color_grid()
    for position in [2, 3, 4]:
        grid.eliminate("color", position, "red")

    changed = apply_value_must_be_somewhere(grid)

    assert changed is True
    assert grid.candidates("color", 1) == {"red"}


def test_value_must_be_somewhere_does_nothing_on_an_open_grid():
    grid = make_color_grid()

    assert apply_value_must_be_somewhere(grid) is False


# The mirror contradiction: eliminate() can't see a value with nowhere to go.
def test_value_must_be_somewhere_raises_when_a_value_has_no_home():
    grid = make_color_grid()
    for position in [1, 2, 3, 4]:
        grid.eliminate("color", position, "red")

    with pytest.raises(Contradiction, match="no position remains for 'red'"):
        apply_value_must_be_somewhere(grid)


# Full solve from partial clues across two categories.
def test_propagation_solves_a_small_puzzle():
    grid = make_grid(
        {"color": ["red", "green", "blue"], "drink": ["tea", "milk", "water"]}, 3
    )
    clues = [
        AbsolutePosition(("color", "red"), "==", 1),
        AbsolutePosition(("color", "green"), "!=", 2),
        AbsolutePosition(("drink", "tea"), "==", 3),
        AbsolutePosition(("drink", "milk"), "!=", 1),
    ]

    propagate_until_stable(grid, clues)

    assert solution_for(grid, "color") == {1: "red", 2: "blue", 3: "green"}
    assert solution_for(grid, "drink") == {1: "water", 2: "milk", 3: "tea"}


# blue and water appear in no clue at all — they fall out of the other
# deductions, which is the whole point of running to a fixed point.
def test_propagation_derives_values_no_clue_mentions():
    grid = make_grid(
        {"color": ["red", "green", "blue"], "drink": ["tea", "milk", "water"]}, 3
    )
    clues = [
        AbsolutePosition(("color", "red"), "==", 1),
        AbsolutePosition(("color", "green"), "!=", 2),
        AbsolutePosition(("drink", "tea"), "==", 3),
        AbsolutePosition(("drink", "milk"), "!=", 1),
    ]

    propagate_until_stable(grid, clues)

    assert grid.forced_value("color", 2) == "blue"
    assert grid.forced_value("drink", 1) == "water"


# Negative test: with nothing to go on, the solver must invent nothing.
def test_propagation_with_no_clues_leaves_everything_open():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)

    propagate_until_stable(grid, [])

    for position in [1, 2, 3]:
        assert grid.candidates("color", position) == {"red", "green", "blue"}


# Two values pinned to the same position empties that position.
def test_propagation_detects_two_values_claiming_one_position():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [
        AbsolutePosition(("color", "red"), "==", 1),
        AbsolutePosition(("color", "green"), "==", 1),
    ]

    with pytest.raises(Contradiction, match="no values remain"):
        propagate_until_stable(grid, clues)


# "before position 1" is impossible, so red ends up with nowhere to live.
def test_propagation_detects_a_value_with_no_possible_position():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [AbsolutePosition(("color", "red"), "<", 1)]

    with pytest.raises(Contradiction, match="no position remains"):
        propagate_until_stable(grid, clues)


# Smallest possible puzzle: the loop must settle instead of spinning forever.
def test_propagation_terminates_on_a_single_position_puzzle():
    grid = make_grid({"color": ["red"]}, 1)

    propagate_until_stable(grid, [])

    assert grid.forced_value("color", 1) == "red"
