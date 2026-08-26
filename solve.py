from dataclasses import dataclass
from enum import Enum

from constraints import validate_constraints
from possibilities import Contradiction, PossibilityGrid
from rules import apply_all_rules


class Status(Enum):
    """How a solve attempt ended. An Enum is a fixed menu of allowed values:
    Status.SOLVEDD is an instant crash, where the string "solvedd" would just
    quietly never match anything."""

    SOLVED = "solved"          # every position pinned to exactly one value
    UNSOLVABLE = "unsolvable"  # the clues contradict each other
    INCOMPLETE = "incomplete"  # ran out of deductions with choices still open


@dataclass
class Solution:
    """What solve() hands back. Always returned — never an exception — so a
    caller (the web layer, later) can just read `status` and react."""

    status: Status
    possibilities: PossibilityGrid
    assignment: dict | None = None  # (category, position) -> value, only when SOLVED
    reason: str | None = None       # plain-language why, when not SOLVED


def solve(puzzle, constraints):
    """Public front door. Solves `puzzle` under `constraints` and always
    returns a Solution saying what happened.

    A Contradiction means the clues fight each other, so no solution exists —
    that becomes UNSOLVABLE rather than escaping as an exception.

    Clues naming things the puzzle never defined still RAISE InvalidConstraint,
    on purpose. That is a different failure: the AI mistranslated, so nothing
    is known about whether the puzzle has an answer. Callers should retry the
    translation, not tell the user their puzzle is impossible."""
    validate_constraints(puzzle, constraints)

    possibilities = PossibilityGrid(puzzle)

    try:
        deduce_until_stable(possibilities, constraints)
    except Contradiction as contradiction:
        # The grid is left mid-deduction on purpose — it shows how far we got
        # before the clues collided.
        return Solution(
            status=Status.UNSOLVABLE,
            possibilities=possibilities,
            reason=f"no solution: {contradiction}",
        )

    assignment = _read_assignment(possibilities)
    if assignment is None:
        return Solution(
            status=Status.INCOMPLETE,
            possibilities=possibilities,
            reason=(
                "ran out of deductions with choices still open: this puzzle "
                "either has more than one solution, or needs guessing to "
                "finish and the solver only deduces"
            ),
        )

    return Solution(
        status=Status.SOLVED,
        possibilities=possibilities,
        assignment=assignment,
    )


def _read_assignment(possibilities):
    """The finished answer as (category, position) -> value, or None if any
    position still has more than one candidate. Deciding SOLVED vs INCOMPLETE
    is the same question as "did every cell come out forced?", so one pass
    answers both."""
    puzzle = possibilities.puzzle
    assignment = {}

    for category in puzzle.categories:
        for position in puzzle.positions:
            if not possibilities.is_forced(category, position):
                return None
            assignment[(category, position)] = possibilities.forced_value(category, position)

    return assignment


def propagate_until_stable(possibilities, constraints):
    """Settle the grid as far as the clues and puzzle rules allow. Mutates
    `possibilities` in place. Raises Contradiction if the puzzle is impossible.

    Runs in two phases: the cheap clues alone first, then everything together.
    Order can't change the final answer — the loop only stops when nothing at
    all is left to eliminate — but it changes the cost. Or copies the whole
    grid once per branch, so letting the cheap clues narrow things down first
    means Or's branches are smaller and die sooner. It also makes the deduction
    chain read the way a person solves: easy clues first, guesswork last."""
    definite = [c for c in constraints if not c.is_speculative()]
    speculative = [c for c in constraints if c.is_speculative()]

    _run_until_stable(possibilities, definite)

    # Phase 2 re-runs the definite clues too: once an Or eliminates something,
    # the cheap clues usually have more to say about it.
    if speculative:
        _run_until_stable(possibilities, constraints)


def _run_until_stable(possibilities, constraints):
    """Apply every clue and both puzzle rules over and over until a full pass
    eliminates nothing further (a fixed point)."""
    changed = True
    while changed:
        changed = False

        for constraint in constraints:
            if constraint.propagate(possibilities):
                changed = True

        # The rules aren't clues — they're facts about how the puzzle works,
        # so they run every pass no matter what the clues say.
        if apply_all_rules(possibilities):
            changed = True


def deduce_until_stable(possibilities, constraints):
    """Everything the solver knows how to deduce, run to a fixed point: plain
    propagation first, then shaving, alternating until neither finds anything.

    Kept separate from propagate_until_stable on purpose. Shaving runs
    propagate_until_stable on its trial grids, so if shaving lived inside that
    function it would call itself forever. Splitting them also keeps shaving
    exactly one level deep: a trial never shaves inside a trial, so every
    refutation stays a short chain a person can follow."""
    while True:
        propagate_until_stable(possibilities, constraints)

        # Only pay for shaving once the cheap deductions are exhausted.
        if not shave(possibilities, constraints):
            return


def shave(possibilities, constraints):
    """Proof by contradiction, one candidate at a time: assume a candidate is
    true, propagate, and if the puzzle explodes then that candidate was never
    possible — so cross it off. Returns True if anything was eliminated.

    Only ever REFUTES. A trial that survives proves nothing (other candidates
    might survive too), so it is thrown away. That refusal is what keeps every
    conclusion a proof rather than a guess."""
    puzzle = possibilities.puzzle
    changed = False

    for category in puzzle.categories:
        for position in puzzle.positions:
            # candidates() hands back a copy, so refuting below can't disturb
            # what we're looping over.
            for value in possibilities.candidates(category, position):
                if possibilities.is_forced(category, position):
                    break  # Down to one value; nothing left here to test.

                # An earlier refutation this round may have already killed it.
                if not possibilities.is_candidate(category, position, value):
                    continue

                if _survives_assumption(possibilities, constraints, category, position, value):
                    continue

                if possibilities.eliminate(category, position, value):
                    changed = True

    return changed


def _survives_assumption(possibilities, constraints, category, position, value):
    """True if pinning `value` at (category, position) leaves a workable
    puzzle. False means assuming it broke the puzzle, which proves it
    impossible. Runs on a throwaway copy, so the real grid is untouched
    either way."""
    trial = possibilities.copy()

    # Pin the assumption by clearing every other candidate from that spot.
    for other_value in trial.candidates(category, position):
        if other_value != value:
            trial.eliminate(category, position, other_value)

    try:
        propagate_until_stable(trial, constraints)
    except Contradiction:
        return False

    return True
