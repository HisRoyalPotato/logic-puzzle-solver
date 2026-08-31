import pytest

from constraints import AbsolutePosition, And, Or, RelativePosition
from deduction import Rule, StepKind
from possibilities import Contradiction, PossibilityGrid
from puzzle import Puzzle
from rules import apply_value_must_be_somewhere, apply_value_used_once
from solve import Status, propagate_until_stable, solve
from test_zebra import zebra_clues, zebra_puzzle
from verify import VerificationFailed, verify_trace


def color_grid(num_positions=3):
    values = ["red", "green", "blue", "yellow", "white"][:num_positions]
    return PossibilityGrid(Puzzle({"color": values}, num_positions))


def kinds(steps):
    return [step.kind for step in steps]


# Every wrong candidate dies exactly once, and 25 cells x 4 wrong values is
# 100 — the most removals a 5x5 puzzle can possibly need.
def test_zebra_records_one_step_per_removal():
    result = solve(zebra_puzzle(), zebra_clues())
    steps = result.possibilities.steps

    assert sum(1 for s in steps if s.kind is StepKind.ELIMINATE) == 100
    assert sum(1 for s in steps if s.kind is StepKind.CONCLUDE) == 25


# Re-checking a candidate that is already gone is not a deduction, so it must
# leave no trace. This is what keeps hundreds of no-op calls out of the chain.
def test_a_repeated_elimination_records_nothing():
    grid = color_grid()

    assert grid.eliminate("color", 1, "red") is True
    assert len(grid.steps) == 1

    assert grid.eliminate("color", 1, "red") is False
    assert len(grid.steps) == 1


# A copy is a new pretend world: it starts with a blank sub-list, which is what
# makes the trace come out as a tree.
def test_a_copy_starts_its_own_empty_trace():
    grid = color_grid()
    grid.eliminate("color", 1, "red")

    trial = grid.copy()

    assert trial.steps == []
    assert grid.steps != []


# ...but it inherits who-killed-what, so a step inside the pretence can still
# cite something that died before the pretending started.
def test_a_copy_inherits_what_was_already_killed():
    grid = color_grid()
    grid.eliminate("color", 1, "red")

    trial = grid.copy()

    assert trial.killed_by("color", 1, "red") is grid.killed_by("color", 1, "red")

    # Its own kills must not leak back into the parent.
    trial.eliminate("color", 2, "red")
    assert grid.killed_by("color", 2, "red") is None


# Landing on "so it must be X" is what makes a chain readable; without it the
# trace only ever says "not this, not that".
def test_the_last_removal_in_a_cell_records_a_conclusion():
    grid = color_grid()

    grid.eliminate("color", 1, "red")
    grid.eliminate("color", 1, "green")

    assert kinds(grid.steps) == [StepKind.ELIMINATE, StepKind.ELIMINATE, StepKind.CONCLUDE]
    assert grid.steps[-1].value == "blue"


# The removal really happened, so it is recorded before the blow-up. That step
# is the last line of the sub-proof.
def test_a_cell_running_dry_is_recorded_before_it_raises():
    grid = color_grid()
    grid.eliminate("color", 1, "red")
    grid.eliminate("color", 1, "green")

    with pytest.raises(Contradiction):
        grid.eliminate("color", 1, "blue")

    assert kinds(grid.steps)[-2:] == [StepKind.ELIMINATE, StepKind.CONTRADICTION]


# An AbsolutePosition reads no grid state at all — only the clue and some
# arithmetic — so its steps are the roots the whole chain traces back to.
def test_absolute_position_steps_are_roots():
    grid = color_grid()
    clue = AbsolutePosition(("color", "red"), "==", 1)

    clue.propagate(grid)

    step = grid.killed_by("color", 2, "red")
    assert step.because is clue
    assert step.leaning_on == []


# A relative clue kills a candidate because every partner position that could
# have paired with it is already gone. Those deaths are the evidence.
def test_relative_position_cites_the_partner_it_lost():
    puzzle = Puzzle({"color": ["red", "green", "blue"], "pet": ["cat", "dog", "fish"]}, 3)
    grid = PossibilityGrid(puzzle)

    # Cat must sit immediately left of red, so killing red's homes kills cat's.
    killed_red_2 = grid.eliminate("color", 2, "red")
    assert killed_red_2

    clue = RelativePosition(("pet", "cat"), ("color", "red"), "==", 1)
    clue.propagate(grid)

    # Cat at 1 needed red at 2, which is gone.
    step = grid.killed_by("pet", 1, "cat")
    assert step is not None
    assert grid.killed_by("color", 2, "red") in step.leaning_on


# "Used once" fires because a cell is pinned, and a cell is pinned because
# every other value in it died. Those are the steps it leans on.
def test_value_used_once_cites_the_rest_of_the_cell():
    grid = color_grid()
    grid.eliminate("color", 1, "red")
    grid.eliminate("color", 1, "green")   # position 1 is now forced to blue

    apply_value_used_once(grid)

    step = grid.killed_by("color", 2, "blue")
    assert step.because is Rule.VALUE_USED_ONCE
    assert grid.killed_by("color", 1, "red") in step.leaning_on
    assert grid.killed_by("color", 1, "green") in step.leaning_on


# The mirror rule leans on the mirror evidence: the same value dying at every
# other position, rather than other values dying in the same cell.
def test_value_must_be_somewhere_cites_the_other_positions():
    grid = color_grid()
    grid.eliminate("color", 2, "red")
    grid.eliminate("color", 3, "red")     # red can only live at position 1 now

    apply_value_must_be_somewhere(grid)

    step = grid.killed_by("color", 1, "green")
    assert step.because is Rule.VALUE_MUST_BE_SOMEWHERE
    assert grid.killed_by("color", 2, "red") in step.leaning_on
    assert grid.killed_by("color", 3, "red") in step.leaning_on


# Shaving's whole claim is "assuming this broke the puzzle", so the refutation
# has to travel with it — otherwise the reader is asked to take it on faith.
def test_shaving_carries_the_refutation_that_justifies_it():
    result = solve(zebra_puzzle(), zebra_clues())

    step = result.possibilities.killed_by("nation", 2, "Japanese")
    assert step.because is Rule.SHAVING

    proof = step.children[0]
    assert proof.refuted is True
    assert proof.steps[0].kind is StepKind.SUPPOSE
    assert proof.steps[-1].kind is StepKind.CONTRADICTION

    # The exact chain the test suite already documents: assuming the Japanese
    # is in house 2 leaves Parliaments with nowhere to go.
    assert proof.steps[-1].value == "Parliaments"


# Unlike shaving, an Or's SURVIVING branches are load-bearing: "it died under A
# and it died under B" is the whole argument, so both chains are kept.
def test_or_keeps_a_sub_proof_for_every_surviving_branch():
    grid = color_grid()
    clue = Or([AbsolutePosition(("color", "red"), "==", 1),
               AbsolutePosition(("color", "red"), "==", 2)])

    propagate_until_stable(grid, [clue])

    step = grid.killed_by("color", 3, "red")
    assert len(step.children) == 2
    assert [proof.refuted for proof in step.children] == [False, False]


# A branch that dies keeps its refutation too, alongside the survivors'.
def test_or_keeps_refuted_and_surviving_branches_together():
    grid = color_grid()
    impossible = And([AbsolutePosition(("color", "green"), "==", 1),
                      AbsolutePosition(("color", "red"), "==", 1)])
    clue = Or([AbsolutePosition(("color", "red"), "==", 1), impossible])

    propagate_until_stable(grid, [clue])

    step = grid.killed_by("color", 2, "red")
    assert sorted(proof.refuted for proof in step.children) == [False, True]


# The user whose puzzle is broken needs the explanation most, so every outcome
# carries one.
def test_all_three_outcomes_carry_a_trace():
    puzzle = Puzzle({"color": ["red", "green", "blue"]}, 3)

    solved = solve(puzzle, [AbsolutePosition(("color", "red"), "==", 1),
                            AbsolutePosition(("color", "green"), "==", 2)])
    impossible = solve(puzzle, [AbsolutePosition(("color", "red"), "==", 1),
                                AbsolutePosition(("color", "red"), "==", 2)])
    stuck = solve(puzzle, [AbsolutePosition(("color", "red"), "==", 1)])

    assert solved.status is Status.SOLVED and solved.trace
    assert impossible.status is Status.UNSOLVABLE and impossible.trace
    assert stuck.status is Status.INCOMPLETE and stuck.trace


# An impossible puzzle's trace ends where the clues collided.
def test_an_impossible_puzzle_traces_to_its_contradiction():
    puzzle = Puzzle({"color": ["red", "green", "blue"]}, 3)

    result = solve(puzzle, [AbsolutePosition(("color", "red"), "==", 1),
                            AbsolutePosition(("color", "red"), "==", 2)])

    assert result.trace[-1].kind is StepKind.CONTRADICTION


# Replaying a real trace must land on the grid the solver actually ended with.
def test_a_real_trace_replays_to_the_same_grid():
    puzzle = zebra_puzzle()
    result = solve(puzzle, zebra_clues())

    assert verify_trace(puzzle, result.possibilities.steps, result.possibilities) == []


# The point of the checker: a trace that does not match what the solver did
# gets caught, even though the answer itself is still correct.
def test_a_corrupted_trace_is_rejected():
    puzzle = Puzzle({"color": ["red", "green", "blue"]}, 3)
    result = solve(puzzle, [AbsolutePosition(("color", "red"), "==", 1),
                            AbsolutePosition(("color", "green"), "==", 2)])

    # Rewrite one step to blame the wrong cell.
    for step in result.possibilities.steps:
        if step.kind is StepKind.ELIMINATE:
            step.position = 1 if step.position != 1 else 2
            break

    assert verify_trace(puzzle, result.possibilities.steps, result.possibilities) != []


# And solve() refuses to hand over an answer whose trace does not hold up.
def test_solve_raises_when_the_trace_does_not_replay(monkeypatch):
    import solve as solve_module

    def broken(puzzle, steps, finished):
        return ["pretend the trace is wrong"]

    monkeypatch.setattr(solve_module, "verify_trace", broken)

    with pytest.raises(VerificationFailed):
        solve(Puzzle({"color": ["red", "green", "blue"]}, 3),
              [AbsolutePosition(("color", "red"), "==", 1),
               AbsolutePosition(("color", "green"), "==", 2)])
