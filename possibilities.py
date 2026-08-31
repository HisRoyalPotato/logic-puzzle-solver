from deduction import Step, StepKind


class Contradiction(Exception):
    """Raised when the puzzle turns out to be impossible.

    Carries the CONTRADICTION step that recorded it, so a caller refuting an
    assumption has the last line of its sub-proof to hand rather than having to
    go hunting for it.
    """

    def __init__(self, message, step=None):
        super().__init__(message)
        self.step = step


class PossibilityGrid:
    """Tracks, per (category, position), the set of values not yet ruled out —
    and, as it goes, why each value was ruled out.

    The trace lives here rather than in a separate object passed around because
    `eliminate` is the only way to cross anything off. Recording at that single
    door means a deduction physically cannot happen unnoticed; a separate
    tracker would rely on every caller remembering to pass it.
    """

    def __init__(self, puzzle):
        # Kept so constraints can ask "what positions/values exist" during propagation.
        self.puzzle = puzzle

        # Every position starts able to be any legal value for its category.
        self._candidates = {}
        for category, values in puzzle.categories.items():
            for position in puzzle.positions:
                self._candidates[(category, position)] = set(values)

        # What this grid did, in order. A trial grid keeps its own, which is
        # what makes a sub-proof a sub-proof.
        self.steps = []

        # (category, position, value) -> the Step that killed it. Lets a later
        # deduction cite what it depended on by looking them up, instead of
        # every rule hand-tracking its own bookkeeping.
        self._killed_by = {}

    def copy(self):
        """A separate grid holding the same candidates. Eliminating on one
        never affects the other — Or and shaving use this to try something for
        real without committing to it. The puzzle is shared, not copied: it
        never changes, so both grids can safely read the same one."""
        clone = PossibilityGrid(self.puzzle)
        for key, values in self._candidates.items():
            # set(values) builds a NEW set. Assigning `values` directly would
            # leave both grids pointing at one shared set.
            clone._candidates[key] = set(values)

        # `steps` deliberately stays EMPTY: a copy is a new pretend world, and
        # it needs its own blank sub-list. That is what makes the trace come
        # out as a tree without anyone managing indentation by hand.
        #
        # `_killed_by` is the opposite — inherited, because a step inside the
        # pretence may need to cite something that died before the pretending
        # started. dict() makes it a NEW map holding the same Steps, so the
        # trial can add its own without disturbing the parent.
        clone._killed_by = dict(self._killed_by)
        return clone

    def candidates(self, category, position):
        """Copy of the current possible values for (category, position)."""
        return set(self._candidates[(category, position)])

    def is_candidate(self, category, position, value):
        """True if `value` is still possible at (category, position)."""
        return value in self._candidates[(category, position)]

    def killed_by(self, category, position, value):
        """The Step that ruled this candidate out, or None if it is still alive.
        This is the lookup that lets a deduction cite its evidence."""
        return self._killed_by.get((category, position, value))

    def positions_for(self, category, value):
        """The positions where `value` is still possible — the mirror image of
        candidates(). Returns a fresh list, so callers can safely eliminate
        while looping over it."""
        open_positions = []
        for position in self.puzzle.positions:
            if value in self._candidates[(category, position)]:
                open_positions.append(position)
        return open_positions

    def eliminate(self, category, position, value, because=None, leaning_on=()):
        """Rule out `value` at (category, position), recording why.

        No-op if already ruled out. Returns True if a candidate was actually
        removed, False if it was already gone — callers use this to detect
        whether anything changed. Nothing is recorded for a no-op, which is
        what keeps hundreds of pointless re-checks out of the trace.

        `because` is the clue or Rule responsible; `leaning_on` is the earlier
        Steps whose facts this one read.
        """
        remaining = self._candidates[(category, position)]
        if value not in remaining:
            return False

        remaining.discard(value)

        step = Step(
            kind=StepKind.ELIMINATE,
            category=category,
            position=position,
            value=value,
            because=because,
            leaning_on=list(leaning_on),
        )
        self.steps.append(step)
        self._killed_by[(category, position, value)] = step

        if not remaining:
            # The removal really did happen, so it is recorded above BEFORE
            # this blows up — that step is the last line of the sub-proof.
            self.record_contradiction(
                f"no values remain for '{category}' at position {position}",
                category=category,
                position=position,
                because=because,
                leaning_on=self._killers_in_cell(category, position),
            )

        # Down to one, so the cell is now decided. Recording that as its own
        # step is what lets the trace land on "so it must be X" instead of only
        # ever saying "not this, not that".
        if len(remaining) == 1:
            survivor = next(iter(remaining))
            self.steps.append(Step(
                kind=StepKind.CONCLUDE,
                category=category,
                position=position,
                value=survivor,
                leaning_on=self._killers_in_cell(category, position, skip=survivor),
            ))

        return True

    def record_suppose(self, category, position, value):
        """Note an assumption at the top of a trial's trace. Not a deduction —
        it is the "suppose..." line a refutation argues against."""
        step = Step(kind=StepKind.SUPPOSE, category=category, position=position,
                    value=value)
        self.steps.append(step)
        return step

    def record_contradiction(self, message, category=None, position=None, value=None,
                             because=None, leaning_on=(), children=()):
        """Record that the puzzle broke, then raise. Every sub-proof ends here,
        so the step goes into the trace before the exception unwinds."""
        step = Step(
            kind=StepKind.CONTRADICTION,
            category=category,
            position=position,
            value=value,
            because=because,
            leaning_on=list(leaning_on),
            children=list(children),
        )
        self.steps.append(step)
        raise Contradiction(message, step=step)

    def _killers_in_cell(self, category, position, skip=None):
        """The Steps that killed the other values at (category, position).
        This is the evidence behind "that cell is decided", and behind "that
        cell ran dry"."""
        found = []
        for candidate in self.puzzle.categories[category]:
            if candidate == skip:
                continue
            step = self._killed_by.get((category, position, candidate))
            if step is not None:
                found.append(step)
        return found

    def is_forced(self, category, position):
        """True if exactly one candidate remains for (category, position)."""
        return len(self._candidates[(category, position)]) == 1

    def forced_value(self, category, position):
        """The single remaining candidate. Raises if not yet forced."""
        remaining = self._candidates[(category, position)]
        if len(remaining) != 1:
            raise ValueError(f"'{category}' at position {position} is not yet forced: {remaining}")
        return next(iter(remaining))
