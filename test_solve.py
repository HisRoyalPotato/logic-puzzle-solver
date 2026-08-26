import pytest

from constraints import AbsolutePosition, And, InvalidConstraint, Or, RelativePosition
from possibilities import Contradiction, PossibilityGrid
from puzzle import Puzzle
from rules import apply_value_must_be_somewhere, apply_value_used_once
from solve import (
    Solution,
    Status,
    deduce_until_stable,
    propagate_until_stable,
    shave,
    solve,
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


# Was a known blind spot until 2026-08-25. Arc consistency only compares pairs
# of positions, and "house 1 equals house 1" looked legal to it — it had no
# idea one house can't be two colours. allows() now says so outright, so red
# runs out of houses and the puzzle is correctly called impossible.
def test_same_category_equals_is_detected_as_impossible():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [RelativePosition(("color", "red"), ("color", "blue"), "==", 0)]

    with pytest.raises(Contradiction):
        propagate_until_stable(grid, clues)


# The guard must not fire when both sides are the SAME value — "red is where
# red is" is trivially true, and sharing a position is exactly right there.
def test_same_category_same_value_equals_stays_open():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [RelativePosition(("color", "red"), ("color", "red"), "==", 0)]

    propagate_until_stable(grid, clues)

    assert grid.positions_for("color", "red") == [1, 2, 3]


# Offsets are untouched by the guard: red one house left of blue is fine, and
# the pair-equal case it blocks can never come up at a non-zero offset anyway.
def test_same_category_with_offset_still_works():
    grid = make_grid({"color": ["red", "green", "blue"]}, 3)
    clues = [RelativePosition(("color", "red"), ("color", "blue"), "==", 1)]

    propagate_until_stable(grid, clues)

    assert grid.positions_for("color", "red") == [1, 2]
    assert grid.positions_for("color", "blue") == [2, 3]


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


# --- inclusive operators --------------------------------------------------


# "<=" keeps its own position, unlike "<" which rules it out.
def test_absolute_less_than_or_equal_keeps_the_boundary_position():
    grid = make_color_grid()

    AbsolutePosition(("color", "red"), "<=", 2).propagate(grid)

    assert grid.positions_for("color", "red") == [1, 2]


def test_absolute_greater_than_or_equal_keeps_the_boundary_position():
    grid = make_color_grid()

    AbsolutePosition(("color", "red"), ">=", 3).propagate(grid)

    assert grid.positions_for("color", "red") == [3, 4]


# The whole reason to have "<=": the AI can write it without doing off-by-one
# arithmetic. It must land on exactly what the shifted "<" would have done.
def test_inclusive_operator_matches_the_shifted_strict_one():
    inclusive = make_color_grid()
    strict = make_color_grid()

    AbsolutePosition(("color", "red"), "<=", 2).propagate(inclusive)
    AbsolutePosition(("color", "red"), "<", 3).propagate(strict)

    assert inclusive.positions_for("color", "red") == strict.positions_for("color", "red")


# RelativePosition needed no new code — allows() reads the operator out of the
# same dict — so this is the test that proves it.
def test_relative_less_than_or_equal_allows_the_same_position():
    grid = make_color_grid()
    clue = RelativePosition(("color", "red"), ("color", "green"), "<=", 0)

    # Same position is legal for "<=" between DIFFERENT categories...
    assert clue.allows(2, 2) is False  # ...but not within one category.
    assert clue.allows(2, 3) is True


def test_relative_inclusive_across_categories_allows_equal_positions():
    grid = make_grid({"color": ["red", "green"], "pet": ["cat", "dog"]}, 2)
    clue = RelativePosition(("color", "red"), ("pet", "cat"), "<=", 0)

    assert clue.allows(1, 1) is True

    clue.propagate(grid)
    assert grid.positions_for("color", "red") == [1, 2]


# --- solve(): the public front door ---------------------------------------


# A fully determined puzzle comes back SOLVED with a finished assignment.
def test_solve_returns_solved_with_an_assignment():
    puzzle = Puzzle({"color": ["red", "green"]}, 2)
    clues = [AbsolutePosition(("color", "red"), "==", 1)]

    result = solve(puzzle, clues)

    assert result.status is Status.SOLVED
    assert result.assignment == {("color", 1): "red", ("color", 2): "green"}
    assert result.reason is None


# Clues that fight each other must REPORT no solution, not raise.
def test_solve_reports_no_solution_instead_of_raising():
    puzzle = Puzzle({"color": ["red", "green"]}, 2)
    clues = [
        AbsolutePosition(("color", "red"), "==", 1),
        AbsolutePosition(("color", "red"), "==", 2),
    ]

    result = solve(puzzle, clues)

    assert result.status is Status.UNSOLVABLE
    assert result.assignment is None
    assert "no solution" in result.reason


# The same-category fix reaches solve() as a clean UNSOLVABLE too.
def test_solve_reports_no_solution_for_same_category_equals():
    puzzle = Puzzle({"color": ["red", "green", "blue"]}, 3)
    clues = [RelativePosition(("color", "red"), ("color", "blue"), "==", 0)]

    result = solve(puzzle, clues)

    assert result.status is Status.UNSOLVABLE


# No clues at all: nothing is wrong, there just isn't enough to finish.
def test_solve_reports_incomplete_when_deductions_run_out():
    puzzle = Puzzle({"color": ["red", "green"]}, 2)

    result = solve(puzzle, [])

    assert result.status is Status.INCOMPLETE
    assert result.assignment is None
    assert "more than one solution" in result.reason
    # The partial grid still comes back, untouched and fully open.
    assert result.possibilities.candidates("color", 1) == {"red", "green"}


# A clue naming a value the puzzle never defined is a BROKEN clue, not a
# puzzle without an answer — it must raise, never come back as UNSOLVABLE.
# Reporting it as UNSOLVABLE would tell a user with a perfectly good puzzle
# that their puzzle is impossible, when really the AI just misread a word.
def test_solve_raises_on_a_clue_naming_an_unknown_value():
    puzzle = Puzzle({"color": ["red", "green"]}, 2)
    clues = [AbsolutePosition(("color", "purple"), "==", 1)]

    with pytest.raises(InvalidConstraint) as caught:
        solve(puzzle, clues)

    assert caught.value.problems[0].allowed == ["red", "green"]


# --- shaving: proof by contradiction --------------------------------------


# With nothing to contradict, shaving must invent nothing. Assuming a value
# here never breaks anything, so every trial survives and is thrown away.
def test_shave_finds_nothing_on_a_puzzle_with_no_clues():
    grid = make_color_grid()

    assert shave(grid, []) is False
    assert grid.positions_for("color", "red") == [1, 2, 3, 4]


# Nothing left to assume once every cell is down to one value.
def test_shave_returns_false_on_a_finished_puzzle():
    puzzle = Puzzle({"color": ["red", "green"]}, 2)
    grid = PossibilityGrid(puzzle)
    clues = [AbsolutePosition(("color", "red"), "==", 1)]
    propagate_until_stable(grid, clues)

    assert shave(grid, clues) is False


# When shaving has nothing to add, the full toolkit must land exactly where
# plain propagation did — shaving may only ever narrow, never widen.
def test_deduce_matches_propagate_when_shaving_adds_nothing():
    clues = [AbsolutePosition(("color", "red"), "==", 1)]

    propagated = make_color_grid()
    propagate_until_stable(propagated, clues)

    deduced = make_color_grid()
    deduce_until_stable(deduced, clues)

    for position in propagated.puzzle.positions:
        assert deduced.candidates("color", position) == propagated.candidates("color", position)


# Shaving must never cross off a value a real solution needs. Red at house 2
# is perfectly possible here, so no amount of assuming may remove it.
def test_shave_keeps_candidates_that_a_real_solution_uses():
    grid = make_color_grid()
    clues = [AbsolutePosition(("color", "green"), "==", 1)]
    propagate_until_stable(grid, clues)

    shave(grid, clues)

    assert grid.is_candidate("color", 2, "red")
    assert grid.is_candidate("color", 3, "red")
