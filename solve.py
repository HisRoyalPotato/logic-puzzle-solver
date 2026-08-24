from rules import apply_all_rules


def propagate_until_stable(possibilities, constraints):
    """Repeatedly apply every clue and both puzzle rules against
    `possibilities` until a full pass eliminates nothing further (a fixed
    point). Mutates it in place. Raises Contradiction if the puzzle is
    impossible."""
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
