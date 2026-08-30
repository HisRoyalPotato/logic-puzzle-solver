import pytest

from constraints import AbsolutePosition, And, Or, RelativePosition
from puzzle import Puzzle
from solve import Status, solve
from verify import VerificationFailed, holds, verify


def make_puzzle():
    return Puzzle({"color": ["red", "green", "blue"], "pet": ["cat", "dog", "fish"]}, 3)


# red/cat in house 1, green/dog in 2, blue/fish in 3.
def make_answer():
    return {
        ("color", 1): "red", ("color", 2): "green", ("color", 3): "blue",
        ("pet", 1): "cat", ("pet", 2): "dog", ("pet", 3): "fish",
    }


# A correct answer against clues it really satisfies: no complaints.
def test_a_correct_answer_verifies():
    clues = [
        AbsolutePosition(("color", "red"), "==", 1),
        RelativePosition(("pet", "cat"), ("color", "red"), "==", 0),
    ]

    assert verify(make_puzzle(), clues, make_answer()) == []


# The case this whole file exists for: an answer that breaks a clue.
def test_an_answer_breaking_a_clue_is_caught():
    clues = [AbsolutePosition(("color", "red"), "==", 3)]  # red is really in house 1

    complaints = verify(make_puzzle(), clues, make_answer())

    assert len(complaints) == 1
    assert "not satisfied" in complaints[0]


# A half-finished answer is caught before any clue is consulted.
def test_a_missing_position_is_caught():
    answer = make_answer()
    del answer[("color", 3)]

    complaints = verify(make_puzzle(), [], answer)

    assert any("nothing assigned" in c for c in complaints)


# Two houses the same colour is not a legal answer, clues or no clues.
def test_a_duplicated_value_is_caught():
    answer = make_answer()
    answer[("color", 2)] = "red"

    complaints = verify(make_puzzle(), [], answer)

    assert any("exactly once" in c for c in complaints)


# Shape is checked first: a broken answer shouldn't also spew clue failures.
def test_shape_problems_stop_before_clue_checking():
    answer = make_answer()
    answer[("color", 2)] = "red"
    clues = [AbsolutePosition(("color", "green"), "==", 2)]

    complaints = verify(make_puzzle(), clues, answer)

    assert all("not satisfied" not in c for c in complaints)


# Combinators: And needs every child, Or needs only one.
def test_and_needs_every_child_but_or_needs_only_one():
    good = AbsolutePosition(("color", "red"), "==", 1)
    bad = AbsolutePosition(("color", "red"), "==", 3)
    answer = make_answer()

    assert holds(And([good, good]), answer) is True
    assert holds(And([good, bad]), answer) is False
    assert holds(Or([good, bad]), answer) is True


def test_or_fails_when_no_child_holds():
    bad = AbsolutePosition(("color", "red"), "==", 3)

    assert holds(Or([bad, bad]), make_answer()) is False


# Every real solve now runs verification, so this exercises the wiring.
def test_solve_verifies_the_answer_it_returns():
    clues = [
        AbsolutePosition(("color", "red"), "==", 1),
        RelativePosition(("color", "green"), ("color", "blue"), "<", 0),
        # Pets need pinning too, or the puzzle is only half determined.
        RelativePosition(("pet", "cat"), ("color", "red"), "==", 0),
        AbsolutePosition(("pet", "dog"), "==", 2),
    ]

    result = solve(make_puzzle(), clues)

    assert result.status is Status.SOLVED
    assert verify(make_puzzle(), clues, result.assignment) == []


# If the solver ever returned a wrong answer, solve() must blow up rather than
# hand it over. Faking a broken solver proves the alarm is actually wired in.
def test_solve_raises_if_the_answer_is_wrong(monkeypatch):
    import solve as solve_module

    def broken(possibilities):
        return {("color", 1): "green", ("color", 2): "red", ("color", 3): "blue",
                ("pet", 1): "cat", ("pet", 2): "dog", ("pet", 3): "fish"}

    monkeypatch.setattr(solve_module, "_read_assignment", broken)

    with pytest.raises(VerificationFailed):
        solve(make_puzzle(), [AbsolutePosition(("color", "red"), "==", 1)])
