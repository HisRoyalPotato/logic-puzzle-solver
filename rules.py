"""The two facts that are true of every puzzle, no matter what the clues say.

These are not clues, so they live apart from constraints.py. Both solve.py and
constraints.py (for Or's trial branches) import from here. Nothing in this file
imports either of them, so the imports only ever point one way.
"""
from deduction import Rule


def apply_all_rules(possibilities):
    """Run both puzzle rules once. Returns True if anything was eliminated."""
    changed = False
    if apply_value_used_once(possibilities):
        changed = True
    if apply_value_must_be_somewhere(possibilities):
        changed = True
    return changed


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

            # What made this cell forced: the steps that killed everything
            # else in it. That is the evidence behind every removal below.
            evidence = _killers(
                possibilities,
                [(category, position, other) for other in puzzle.categories[category]
                 if other != value],
            )

            for other_position in puzzle.positions:
                if other_position == position:
                    continue
                if possibilities.eliminate(category, other_position, value,
                                           because=Rule.VALUE_USED_ONCE,
                                           leaning_on=evidence):
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
                possibilities.record_contradiction(
                    f"no position remains for '{value}' in category '{category}'",
                    category=category,
                    value=value,
                    because=Rule.VALUE_MUST_BE_SOMEWHERE,
                    # Every position lost it, and those losses are the proof.
                    leaning_on=_killers(
                        possibilities,
                        [(category, p, value) for p in puzzle.positions],
                    ),
                )

            if len(open_positions) == 1:
                only_position = open_positions[0]

                # The mirror of the rule above: there, the evidence was other
                # VALUES dying in one cell; here it is this value dying at
                # every other POSITION.
                evidence = _killers(
                    possibilities,
                    [(category, p, value) for p in puzzle.positions if p != only_position],
                )

                for other_value in values:
                    if other_value == value:
                        continue
                    if possibilities.eliminate(category, only_position, other_value,
                                               because=Rule.VALUE_MUST_BE_SOMEWHERE,
                                               leaning_on=evidence):
                        changed = True

    return changed


def _killers(possibilities, candidates):
    """Look up the Steps that killed each of `candidates`, skipping any still
    alive. Dependencies are looked up, never hand-tracked — the grid already
    knows who killed what."""
    found = []
    for category, position, value in candidates:
        step = possibilities.killed_by(category, position, value)
        if step is not None:
            found.append(step)
    return found
