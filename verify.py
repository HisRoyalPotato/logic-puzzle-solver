"""The last line of defence: check a finished answer against every clue.

Propagation should never produce a wrong answer — the brute-force cross-check
says it doesn't — but "should never" resting on the correctness of the code
that produced the answer is not much of a guarantee. This re-reads the
finished grid and checks it directly, so a bug in the solving loop cannot
quietly ship a wrong answer.

Reuses each clue's own definition of what it means (RelativePosition.allows
and the operator table), so it catches orchestration bugs — a clue that never
ran, a botched grid copy, a misread answer — rather than a misunderstanding
baked into the clue itself.
"""
from constraints import _OPERATORS, AbsolutePosition, And, Or, RelativePosition
from deduction import StepKind
from possibilities import Contradiction, PossibilityGrid


class VerificationFailed(Exception):
    """A finished answer breaks one of its own clues. Always a bug in the
    solver, never a fact about the puzzle — so it raises rather than becoming
    a Status the caller has to remember to check."""


def verify(puzzle, constraints, assignment):
    """Check `assignment` really is a legal answer. Returns a list of
    complaints; an empty list means it holds up. Checks two things: that the
    answer is shaped like a solution at all, and that every clue is satisfied."""
    complaints = _check_shape(puzzle, assignment)

    # A misshapen answer makes clue-checking meaningless, so stop here.
    if complaints:
        return complaints

    for constraint in constraints:
        if not holds(constraint, assignment):
            complaints.append(f"clue not satisfied: {constraint}")

    return complaints


def _check_shape(puzzle, assignment):
    """Every category must place every value exactly once, one per position.
    Catches a half-finished or duplicated answer before any clue is consulted."""
    complaints = []

    for category, values in puzzle.categories.items():
        placed = []
        for position in puzzle.positions:
            if (category, position) not in assignment:
                complaints.append(f"nothing assigned for '{category}' at position {position}")
            else:
                placed.append(assignment[(category, position)])

        # Same length and same contents means it's a permutation of the values.
        if sorted(placed) != sorted(values):
            complaints.append(
                f"category '{category}' does not use each value exactly once: {placed}"
            )

    return complaints


def holds(constraint, assignment):
    """True if `constraint` is satisfied by a finished assignment."""
    if isinstance(constraint, AbsolutePosition):
        compare = _OPERATORS[constraint.operator]
        return compare(_position_of(assignment, constraint.category_value), constraint.position)

    if isinstance(constraint, RelativePosition):
        # allows() is the clue's own pair test, the same one propagation uses.
        return constraint.allows(
            _position_of(assignment, constraint.a),
            _position_of(assignment, constraint.b),
        )

    if isinstance(constraint, And):
        return all(holds(child, assignment) for child in constraint.constraints)

    if isinstance(constraint, Or):
        return any(holds(child, assignment) for child in constraint.constraints)

    raise TypeError(f"unknown constraint type: {type(constraint).__name__}")


def _position_of(assignment, category_value):
    """Which position holds this (category, value). Raises if it was never
    placed — the shape check runs first, so that shouldn't happen."""
    category, value = category_value
    for (assigned_category, position), assigned_value in assignment.items():
        if assigned_category == category and assigned_value == value:
            return position
    raise KeyError(f"'{value}' was never placed in category '{category}'")


def verify_trace(puzzle, steps, finished):
    """Check the trace is an honest account of what the solver actually did.

    Replays the recorded steps on a fresh grid and confirms they land on the
    same grid the solver produced. Returns a list of complaints; empty means it
    holds up.

    Same reasoning as verify() itself: the trace claims to be a proof, and a
    proof nobody checks is only a claim. This catches a step recorded against
    the wrong cell, a step that was lost, and a step recorded twice — none of
    which verify() can see, because they leave the final answer untouched.

    Only top-level steps are replayed. Anything nested happened inside a
    pretend world that was thrown away, so it never touched the real grid.
    """
    complaints = []
    replay = PossibilityGrid(puzzle)

    for step in steps:
        if step.kind is not StepKind.ELIMINATE:
            continue
        try:
            removed = replay.eliminate(step.category, step.position, step.value)
        except Contradiction:
            # Expected on an impossible puzzle: the trace ends at the collision.
            break
        if not removed:
            complaints.append(
                f"trace says it removed '{step.value}' from '{step.category}' at "
                f"position {step.position}, but it was already gone"
            )

    for category in puzzle.categories:
        for position in puzzle.positions:
            expected = finished.candidates(category, position)
            replayed = replay.candidates(category, position)
            if replayed != expected:
                complaints.append(
                    f"replaying the trace leaves '{category}' at position {position} as "
                    f"{sorted(replayed)}, but the solver ended with {sorted(expected)}"
                )

    return complaints
