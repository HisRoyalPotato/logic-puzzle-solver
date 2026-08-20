def propagate_until_stable(possibilities, constraints):
    """Repeatedly propagate every constraint against `possibilities` until a
    full pass eliminates nothing further (a fixed point). Mutates it in place.
    Raises Contradiction (from possibilities.py) if a position runs out of
    candidates along the way."""
    changed = True
    while changed:
        changed = False
        for constraint in constraints:
            if constraint.propagate(possibilities):
                changed = True
