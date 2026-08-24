import pytest

from constraints import AbsolutePosition, And, Or, RelativePosition
from possibilities import Contradiction, PossibilityGrid
from puzzle import Puzzle
from rules import apply_value_must_be_somewhere, apply_value_used_once
from solve import propagate_until_stable


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


# The worked example, run through the whole loop: green left of blue, blue
# already known not to be house 3. Arc consistency gives green 1 and blue 2,
# then the puzzle rules hand red the leftover house.
def test_relative_clue_drives_a_full_solve():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    grid.eliminate("color", 3, "blue")

    propagate_until_stable(
        grid, [RelativePosition(("color", "green"), ("color", "blue"), "<")]
    )

    assert solution_for(grid, "color") == {1: "green", 2: "blue", 3: "red"}


# Relative and absolute clues feed each other across categories.
def test_relative_and_absolute_clues_combine():
    grid = make_grid(
        {"color": ["red", "green", "blue"], "drink": ["tea", "milk", "water"]}, 3
    )
    clues = [
        # Green is immediately left of blue.
        RelativePosition(("color", "green"), ("color", "blue"), "==", 1),
        AbsolutePosition(("color", "green"), "!=", 1),
        # Tea is drunk in the blue house.
        RelativePosition(("drink", "tea"), ("color", "blue"), "=="),
        AbsolutePosition(("drink", "milk"), "==", 1),
    ]

    propagate_until_stable(grid, clues)

    assert solution_for(grid, "color") == {1: "red", 2: "green", 3: "blue"}
    assert solution_for(grid, "drink") == {1: "milk", 2: "water", 3: "tea"}


# Nothing can sit left of house 1, so "green left of blue" plus "blue in
# house 1" is impossible. The forward sweep empties green's positions, then
# the reverse sweep finds blue has no partner left and clears house 1 too.
def test_relative_clue_can_force_a_contradiction():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [
        AbsolutePosition(("color", "blue"), "==", 1),
        RelativePosition(("color", "green"), ("color", "blue"), "<"),
    ]

    with pytest.raises(Contradiction, match="no values remain for 'color' at position 1"):
        propagate_until_stable(grid, clues)


# A clue that reaches past the end of the board is impossible. propagate()
# alone can't tell, but the loop's "every value needs a home" rule does.
def test_relative_clue_with_an_impossible_offset_is_caught_by_the_loop():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [RelativePosition(("color", "green"), ("color", "blue"), "==", 5)]

    with pytest.raises(Contradiction):
        propagate_until_stable(grid, clues)


# Known blind spot, recorded on purpose. Arc consistency only compares pairs of
# positions, and "position 1 equals position 1" looks legal to it — it has no
# idea one house can't be two colours. Safe, because being too cautious only
# leaves the puzzle unsolved; it never crosses off a correct answer.
def test_same_category_equals_is_not_detected_as_impossible():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [RelativePosition(("color", "red"), ("color", "blue"), "==", 0)]

    propagate_until_stable(grid, clues)

    assert grid.positions_for("color", "red") == [1, 2, 3]
    assert grid.positions_for("color", "blue") == [1, 2, 3]


# Smallest possible puzzle: the loop must settle instead of spinning forever.
def test_propagation_terminates_on_a_single_position_puzzle():
    grid = make_grid({"color": ["red"]}, 1)

    propagate_until_stable(grid, [])

    assert grid.forced_value("color", 1) == "red"


# Even with the Or listed FIRST, the definite clue must run before it. The spy
# records how narrow red already was the first time the Or was reached.
def test_definite_clues_run_before_speculative_ones():
    width_when_or_first_ran = []

    class SpyOr(Or):
        def propagate(self, possibilities):
            width_when_or_first_ran.append(len(possibilities.positions_for("color", "red")))
            return super().propagate(possibilities)

    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [
        SpyOr([
            AbsolutePosition(("color", "green"), "==", 2),
            AbsolutePosition(("color", "green"), "==", 3),
        ]),
        AbsolutePosition(("color", "red"), "==", 1),
    ]

    propagate_until_stable(grid, clues)

    # Red was already pinned to one house before the Or ever ran.
    assert width_when_or_first_ran[0] == 1


# An And wrapping an Or is expensive too, so it waits for phase two.
def test_and_containing_an_or_counts_as_speculative():
    cheap = And([AbsolutePosition(("color", "red"), "==", 1)])
    costly = And([Or([AbsolutePosition(("color", "red"), "==", 1)])])

    assert cheap.is_speculative() is False
    assert costly.is_speculative() is True
    assert AbsolutePosition(("color", "red"), "==", 1).is_speculative() is False


# Phase order is an optimisation, never a change of answer: the same clues in
# any order must settle on the same grid.
def test_clue_order_does_not_change_the_answer():
    clues = [
        AbsolutePosition(("color", "red"), "==", 1),
        Or([
            AbsolutePosition(("color", "green"), "==", 2),
            AbsolutePosition(("color", "green"), "==", 1),
        ]),
        RelativePosition(("color", "blue"), ("color", "green"), ">"),
    ]

    results = []
    for order in [clues, list(reversed(clues)), [clues[1], clues[0], clues[2]]]:
        grid = make_grid({"color": ["red", "green", "blue"]}, 3)
        propagate_until_stable(grid, order)
        results.append(solution_for(grid, "color"))

    assert results[0] == {1: "red", 2: "green", 3: "blue"}
    assert results[0] == results[1] == results[2]
