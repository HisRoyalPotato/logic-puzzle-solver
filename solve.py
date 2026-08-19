def propagate_until_stable(grid, constraints):
    """Repeatedly propagate every constraint against `grid` until a full
    pass eliminates nothing further (a fixed point). Mutates `grid` in place.
    Raises Contradiction (from possibilities.py) if a position runs out of
    candidates along the way."""
    changed = True
    while changed:
        changed = False
        for constraint in constraints:
            if constraint.propagate(grid):
                changed = True
