from dataclasses import dataclass
from enum import Enum

from constraints import validate_constraints
from deduction import Rule, SubProof, group_steps, relevant
from possibilities import Contradiction, PossibilityGrid
from rules import apply_all_rules
from verify import VerificationFailed, verify, verify_trace


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

    # The deduction chain, grouped so neighbouring steps that share a reason
    # read as one thought. Present for ALL THREE outcomes: a user whose puzzle
    # is impossible needs the explanation most of all.
    trace: list | None = None


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
            trace=_checked_trace(puzzle, possibilities),
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
            trace=_checked_trace(puzzle, possibilities),
        )

    # Last line of defence. A wrong answer here is a solver bug, not a fact
    # about the puzzle, so it blows up loudly instead of being reported.
    complaints = verify(puzzle, constraints, assignment)
    if complaints:
        raise VerificationFailed(
            "solver produced an answer that breaks its own clues: " + "; ".join(complaints)
        )

    return Solution(
        status=Status.SOLVED,
        possibilities=possibilities,
        assignment=assignment,
        trace=_checked_trace(puzzle, possibilities),
    )


def _checked_trace(puzzle, possibilities):
    """The deduction chain, proved honest and then grouped for reading.

    Every outcome goes through here, not just SOLVED. A trace is a claim about
    what the solver did, and a claim nobody checks is worth little — the same
    reasoning that produced verify(). Replaying it catches a step recorded
    against the wrong cell, a lost step and a duplicated one, none of which
    show up in the final answer.
    """
    complaints = verify_trace(puzzle, possibilities.steps, possibilities)
    if complaints:
        raise VerificationFailed(
            "solver produced a trace that does not match what it did: " + "; ".join(complaints)
        )

    # Grouping is a logical judgement about which steps belong together, so it
    # happens here rather than being left to the AI that words them later.
    return group_steps(possibilities.steps)


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

                refutation = _refute_assumption(possibilities, constraints,
                                                category, position, value)
                if refutation is None:
                    continue  # It survived, which proves nothing. Throw it away.

                if possibilities.eliminate(category, position, value,
                                           because=Rule.SHAVING):
                    changed = True
                    # Hang the proof on the step it justifies, so a reader can
                    # check the refutation instead of taking it on faith.
                    possibilities.killed_by(category, position, value).children = [refutation]

    return changed


def _refute_assumption(possibilities, constraints, category, position, value):
    """Try pinning `value` at (category, position) and see if the puzzle breaks.

    Returns a SubProof if assuming it led to a contradiction — that is a proof
    the value was never possible. Returns None if the assumption survived,
    which proves nothing at all (other candidates might survive too), so the
    whole trial is discarded. Runs on a throwaway copy, so the real grid is
    untouched either way.
    """
    trial = possibilities.copy()

    # The "suppose..." line the refutation argues against. Recorded first so it
    # reads as an assumption rather than as a deduction.
    assumption = trial.record_suppose(category, position, value)

    # Pin it by clearing every other candidate from that spot.
    for other_value in trial.candidates(category, position):
        if other_value != value:
            trial.eliminate(category, position, other_value,
                            because=Rule.ASSUMPTION, leaning_on=[assumption])

    try:
        propagate_until_stable(trial, constraints)
    except Contradiction as dead_end:
        # Keep only the chain that actually reached the contradiction. A trial
        # does plenty of work along the way that never bore on the result.
        return SubProof(
            steps=relevant(trial.steps, [dead_end.step]),
            refuted=True,
            about=assumption,
        )

    return None
