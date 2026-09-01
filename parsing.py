"""Turn untrusted clue data into real Constraint objects, or say clearly why not.

This is the AI translation boundary. Everything above it is text a language
model wrote; everything below it is the guaranteed-correct solver. So this file
trusts nothing and guesses nothing.

Two guards sit in a row, each with exactly one job:

    AI data -> clues_from_json -> Constraint objects -> validate_constraints -> solver
                "is this a clue at all?"                "does the puzzle have
                                                         the things it names?"

Deliberately NOT done here: checking that a category or value exists. That needs
the puzzle, and validate_constraints already does it well. Also deliberately not
done: fuzzy matching ("Purple" -> "purple"). Normalising belongs above this line,
where being wrong is recoverable. Below it, a guess would become a confident
wrong answer.

Every problem is collected before raising, so one retry can fix all of the AI's
mistakes at once instead of one retry per mistake.
"""
from dataclasses import dataclass

from constraints import _OPERATORS, AbsolutePosition, And, Or, RelativePosition

# Nesting this deep is already nonsense, and without a cap a runaway structure
# would blow the Python stack — a crash instead of a readable complaint.
_MAX_DEPTH = 10

_PAIR_FIELDS = {"AbsolutePosition": ("category_value",), "RelativePosition": ("a", "b")}


@dataclass
class MalformedClue:
    """One thing wrong with the data. Deliberately pieces, not a sentence: an
    automatic retry needs to read `allowed` and feed it back to the AI, and
    digging that out of prose would be miserable. Same shape as BadReference in
    constraints.py, for the same reason."""

    where: str      # "clue 3", or "clue 3 -> part 2" inside a combined clue
    problem: str    # what is wrong
    allowed: list   # what it could have been instead


class UnreadableClues(ValueError):
    """The data could not be read as clues at all.

    Carries `.problems`, every MalformedClue found, so a caller can feed the
    whole list back to the AI in one retry.
    """

    def __init__(self, problems):
        self.problems = problems
        super().__init__(
            f"{len(problems)} problem(s) reading the clues: "
            + "; ".join(f"{p.where}: {p.problem}" for p in problems)
        )


def clues_from_json(data):
    """Read a list of clues from already-parsed JSON (dicts and lists, not a
    string). Returns Constraint objects, or raises UnreadableClues listing
    everything wrong."""
    problems = []
    clues = []

    if not isinstance(data, list):
        problems.append(MalformedClue(
            where="the whole reply",
            problem=f"expected a list of clues, got {_describe_type(data)}",
            allowed=["a JSON list"],
        ))
    else:
        for index, item in enumerate(data, 1):
            clue = _read_clue(item, f"clue {index}", problems, depth=0)
            if clue is not None:
                clues.append(clue)

    if problems:
        raise UnreadableClues(problems)
    return clues


def clue_to_json(constraint):
    """The opposite direction: a Constraint as plain JSON-ready data. Used for
    saving puzzles, and for the round-trip test that checks this file against
    itself."""
    data = {"type": type(constraint).__name__}

    if isinstance(constraint, AbsolutePosition):
        data.update(category_value=list(constraint.category_value),
                    operator=constraint.operator, position=constraint.position)
    elif isinstance(constraint, RelativePosition):
        data.update(a=list(constraint.a), b=list(constraint.b),
                    operator=constraint.operator, offset=constraint.offset)
    elif isinstance(constraint, (And, Or)):
        data["constraints"] = [clue_to_json(child) for child in constraint.constraints]
    else:
        raise TypeError(f"cannot write out {type(constraint).__name__}")

    # Left out entirely when absent, so round-tripping produces the same data.
    if constraint.source_text is not None:
        data["source_text"] = constraint.source_text
    return data


def _read_clue(item, where, problems, depth):
    """One clue of any type. Returns None if it could not be read — the caller
    keeps going either way, so the rest of the problems still get found."""
    if depth > _MAX_DEPTH:
        problems.append(MalformedClue(where, f"clues nested more than {_MAX_DEPTH} deep",
                                      ["a flatter clue"]))
        return None

    if not isinstance(item, dict):
        problems.append(MalformedClue(where, f"expected a clue object, got {_describe_type(item)}",
                                      ["a JSON object"]))
        return None

    kind = item.get("type")
    if kind not in _READERS:
        problems.append(MalformedClue(
            where=where,
            problem=f"unknown clue type {kind!r}" if kind is not None else "no 'type' given",
            allowed=sorted(_READERS),
        ))
        return None

    return _READERS[kind](item, where, problems, depth)


def _read_absolute(item, where, problems, depth):
    """(category, value) compared against a literal position."""
    _reject_unknown(item, {"type", "category_value", "operator", "position", "source_text"},
                    where, problems)

    pair = _read_pair(item, "category_value", where, problems)
    operator = _read_operator(item, where, problems)
    position = _read_whole_number(item, "position", where, problems)
    text = _read_source_text(item, where, problems)

    if pair is None or operator is None or position is None:
        return None
    return AbsolutePosition(pair, operator, position, source_text=text)


def _read_relative(item, where, problems, depth):
    """One (category, value) compared against another, with an offset."""
    _reject_unknown(item, {"type", "a", "b", "operator", "offset", "source_text"},
                    where, problems)

    first = _read_pair(item, "a", where, problems)
    second = _read_pair(item, "b", where, problems)
    operator = _read_operator(item, where, problems)
    text = _read_source_text(item, where, problems)

    # The only optional number: "same house" is offset 0, so leaving it out is
    # the common case rather than a mistake.
    offset = 0
    if "offset" in item:
        offset = _read_whole_number(item, "offset", where, problems)

    if first is None or second is None or operator is None or offset is None:
        return None
    return RelativePosition(first, second, operator, offset, source_text=text)


def _read_group(item, where, problems, depth):
    """And / Or: a clue holding more clues, so this recurses."""
    _reject_unknown(item, {"type", "constraints", "source_text"}, where, problems)
    text = _read_source_text(item, where, problems)

    children = item.get("constraints")
    if not isinstance(children, list) or not children:
        problems.append(MalformedClue(
            where=where,
            problem=f"'constraints' must be a non-empty list, got {_describe_type(children)}",
            allowed=["a JSON list holding at least one clue"],
        ))
        return None

    # Read every part even after one fails, so a single retry sees them all.
    parts = [_read_clue(child, f"{where} -> part {number}", problems, depth + 1)
             for number, child in enumerate(children, 1)]
    if any(part is None for part in parts):
        return None

    built = And if item["type"] == "And" else Or
    return built(parts, source_text=text)


_READERS = {
    "AbsolutePosition": _read_absolute,
    "RelativePosition": _read_relative,
    "And": _read_group,
    "Or": _read_group,
}


def _read_pair(item, field, where, problems):
    """A [category, value] pair. Becomes a tuple, which is what constraints use."""
    raw = item.get(field)
    ok = (isinstance(raw, list) and len(raw) == 2
          and all(isinstance(part, str) for part in raw))
    if not ok:
        problems.append(MalformedClue(
            where=where,
            problem=f"'{field}' must be [category, value] as two strings, got {raw!r}",
            allowed=['["category name", "value name"]'],
        ))
        return None
    return tuple(raw)


def _read_operator(item, where, problems):
    """Checked here rather than left to the constraint's __post_init__, which
    raises straight away — that would abandon every problem found after it."""
    raw = item.get("operator")
    if raw not in _OPERATORS:
        problems.append(MalformedClue(
            where=where,
            problem=f"unsupported operator {raw!r}",
            allowed=sorted(_OPERATORS),
        ))
        return None
    return raw


def _read_whole_number(item, field, where, problems):
    """A plain integer.

    The bool check is not fussiness: in Python `True` IS an integer, so a naive
    isinstance test would quietly accept {"position": true} and read it as
    house 1.
    """
    raw = item.get(field)
    if not isinstance(raw, int) or isinstance(raw, bool):
        problems.append(MalformedClue(
            where=where,
            problem=f"'{field}' must be a whole number, got {raw!r}",
            allowed=["a whole number, e.g. 1"],
        ))
        return None
    return raw


def _read_source_text(item, where, problems):
    """The user's original sentence. Optional, but it must be text if present —
    it ends up quoted in the explanation."""
    raw = item.get("source_text")
    if raw is None or isinstance(raw, str):
        return raw
    problems.append(MalformedClue(
        where=where,
        problem=f"'source_text' must be the original sentence as text, got {raw!r}",
        allowed=["the clue's original English sentence"],
    ))
    return None


def _reject_unknown(item, known, where, problems):
    """Anything else in the object is a field the AI invented. Better to say so
    than to ignore it and silently drop what it was trying to express."""
    extra = sorted(set(item) - known)
    if extra:
        problems.append(MalformedClue(
            where=where,
            problem=f"unexpected field(s): {', '.join(extra)}",
            allowed=sorted(known),
        ))


def _describe_type(value):
    """A friendly name for what turned up, for the complaint message."""
    names = {type(None): "nothing", bool: "a true/false", int: "a number",
             float: "a number", str: "a string", list: "a list", dict: "an object"}
    return names.get(type(value), type(value).__name__)
