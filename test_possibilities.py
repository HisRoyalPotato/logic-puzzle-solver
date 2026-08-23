import pytest

from possibilities import Contradiction, PossibilityGrid
from puzzle import Puzzle


# Shared 3-position puzzle used by most tests in this file.
def make_grid():
    puzzle = Puzzle({"color": ["red", "green", "blue"]}, 3)
    return PossibilityGrid(puzzle)


# Before any deduction, every position can still hold every value.
def test_grid_starts_completely_open():
    grid = make_grid()

    for position in [1, 2, 3]:
        assert grid.candidates("color", position) == {"red", "green", "blue"}


# candidates() hands back a copy, so callers can't reach in and mutate state.
def test_candidates_returns_a_copy():
    grid = make_grid()

    grid.candidates("color", 1).clear()

    assert grid.candidates("color", 1) == {"red", "green", "blue"}


def test_is_candidate_tracks_eliminations():
    grid = make_grid()

    assert grid.is_candidate("color", 1, "red")
    grid.eliminate("color", 1, "red")
    assert not grid.is_candidate("color", 1, "red")


# The True/False return is how the solver loop detects progress.
def test_eliminate_reports_whether_it_changed_anything():
    grid = make_grid()

    assert grid.eliminate("color", 1, "red") is True
    assert grid.eliminate("color", 1, "red") is False


# Emptying a position means the puzzle is broken.
def test_eliminate_raises_when_a_position_runs_out_of_values():
    grid = make_grid()

    grid.eliminate("color", 1, "red")
    grid.eliminate("color", 1, "green")

    with pytest.raises(Contradiction, match="no values remain"):
        grid.eliminate("color", 1, "blue")


def test_is_forced_only_when_one_candidate_remains():
    grid = make_grid()

    assert not grid.is_forced("color", 1)
    grid.eliminate("color", 1, "red")
    assert not grid.is_forced("color", 1)
    grid.eliminate("color", 1, "green")
    assert grid.is_forced("color", 1)
    assert grid.forced_value("color", 1) == "blue"


def test_forced_value_raises_when_still_ambiguous():
    grid = make_grid()

    with pytest.raises(ValueError, match="not yet forced"):
        grid.forced_value("color", 1)


# positions_for is the mirror of candidates: where can this value still go?
def test_positions_for_starts_as_every_position():
    grid = make_grid()

    assert grid.positions_for("color", "red") == [1, 2, 3]


def test_positions_for_shrinks_as_candidates_are_eliminated():
    grid = make_grid()

    grid.eliminate("color", 2, "red")

    assert grid.positions_for("color", "red") == [1, 3]
    # Other values are unaffected.
    assert grid.positions_for("color", "green") == [1, 2, 3]


# Returning a fresh list lets callers eliminate while looping over the result.
def test_positions_for_is_safe_to_loop_while_eliminating():
    grid = make_grid()

    for position in grid.positions_for("color", "red"):
        if position != 1:
            grid.eliminate("color", position, "red")

    assert grid.positions_for("color", "red") == [1]


# An empty list is a legal answer here; the solver rules decide what it means.
def test_positions_for_can_return_empty():
    grid = make_grid()

    for position in [1, 2, 3]:
        grid.eliminate("color", position, "red")

    assert grid.positions_for("color", "red") == []


# A copy starts out matching the original exactly.
def test_copy_starts_identical():
    grid = make_grid()
    grid.eliminate("color", 1, "red")

    clone = grid.copy()

    for position in [1, 2, 3]:
        assert clone.candidates("color", position) == grid.candidates("color", position)


# The whole point of copy(): trying something on the clone leaves the real
# grid untouched. This is what catches a shallow copy.
def test_eliminating_on_the_copy_leaves_the_original_alone():
    grid = make_grid()
    clone = grid.copy()

    clone.eliminate("color", 1, "red")

    assert clone.is_candidate("color", 1, "red") is False
    assert grid.is_candidate("color", 1, "red") is True


# And the other direction, so neither grid can leak into the other.
def test_eliminating_on_the_original_leaves_the_copy_alone():
    grid = make_grid()
    clone = grid.copy()

    grid.eliminate("color", 1, "red")

    assert grid.is_candidate("color", 1, "red") is False
    assert clone.is_candidate("color", 1, "red") is True


# The puzzle is shared on purpose — it never changes, so copying it is waste.
def test_copy_shares_the_puzzle():
    grid = make_grid()

    assert grid.copy().puzzle is grid.puzzle
