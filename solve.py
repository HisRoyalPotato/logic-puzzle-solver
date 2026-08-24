from rules import apply_all_rules


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
