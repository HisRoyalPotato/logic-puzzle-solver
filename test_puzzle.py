import pytest

from puzzle import Puzzle


# A puzzle built with legal arguments exposes its categories and positions.
def test_valid_puzzle_has_expected_shape():
    puzzle = Puzzle({"color": ["red", "green"], "drink": ["tea", "milk"]}, 2)

    assert puzzle.num_positions == 2
    assert puzzle.categories["color"] == ["red", "green"]
    assert puzzle.categories["drink"] == ["tea", "milk"]


# Positions are 1-indexed so they read like puzzle clues ("house 1").
def test_positions_are_one_indexed():
    puzzle = Puzzle({"color": ["red", "green", "blue"]}, 3)

    assert puzzle.positions == [1, 2, 3]


# Puzzle copies the caller's lists, so later edits outside can't corrupt it.
def test_puzzle_copies_caller_categories():
    categories = {"color": ["red", "green"]}
    puzzle = Puzzle(categories, 2)

    categories["color"].append("blue")

    assert puzzle.categories["color"] == ["red", "green"]


def test_rejects_zero_positions():
    with pytest.raises(ValueError, match="at least 1"):
        Puzzle({"color": ["red"]}, 0)


def test_rejects_empty_categories():
    with pytest.raises(ValueError, match="at least one category"):
        Puzzle({}, 3)


# Every category must supply exactly one value per position.
def test_rejects_category_with_wrong_number_of_values():
    with pytest.raises(ValueError, match="expected 3"):
        Puzzle({"color": ["red", "green"]}, 3)


def test_rejects_duplicate_values_within_a_category():
    with pytest.raises(ValueError, match="duplicate"):
        Puzzle({"color": ["red", "red"]}, 2)
