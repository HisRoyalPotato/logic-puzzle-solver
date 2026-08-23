from possibilities import Contradiction


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

        # These two aren't clues — they're facts about how the puzzle works,
        # so they run every pass no matter what the clues say.
        if apply_value_used_once(possibilities):
            changed = True
        if apply_value_must_be_somewhere(possibilities):
            changed = True


def apply_value_used_once(possibilities):
    """Puzzle rule: a value fills exactly one position. So once a position is
    down to a single value, no other position in that category can hold it.
    Returns True if anything was eliminated."""
    puzzle = possibilities.puzzle
    changed = False

    for category in puzzle.categories:
        for position in puzzle.positions:
            if not possibilities.is_forced(category, position):
                continue

            value = possibilities.forced_value(category, position)
            for other_position in puzzle.positions:
                if other_position == position:
                    continue
                if possibilities.eliminate(category, other_position, value):
                    changed = True

    return changed


def apply_value_must_be_somewhere(possibilities):
    """Puzzle rule: every value fills some position. So if only one position
    still allows a value, that position must hold it, and everything else
    there can go. Returns True if anything was eliminated. Raises
    Contradiction if a value has no position left at all."""
    puzzle = possibilities.puzzle
    changed = False

    for category, values in puzzle.categories.items():
        for value in values:
            open_positions = possibilities.positions_for(category, value)

            # A position running empty is caught by eliminate(); this is the
            # mirror case, where a value has nowhere left to go.
            if not open_positions:
                raise Contradiction(
                    f"no position remains for '{value}' in category '{category}'"
                )

            if len(open_positions) == 1:
                only_position = open_positions[0]
                for other_value in values:
                    if other_value == value:
                        continue
                    if possibilities.eliminate(category, only_position, other_value):
                        changed = True

    return changed
