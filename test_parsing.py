import pytest

from constraints import AbsolutePosition, And, Or, RelativePosition
from parsing import UnreadableClues, clue_to_json, clues_from_json


def absolute(**overrides):
    clue = {"type": "AbsolutePosition", "category_value": ["nation", "Norwegian"],
            "operator": "==", "position": 1}
    clue.update(overrides)
    return clue


def relative(**overrides):
    clue = {"type": "RelativePosition", "a": ["color", "green"],
            "b": ["color", "ivory"], "operator": "==", "offset": 1}
    clue.update(overrides)
    return clue


def problems_from(data):
    with pytest.raises(UnreadableClues) as raised:
        clues_from_json(data)
    return raised.value.problems


# The happy path for the two atomic clue types.
def test_reads_the_atomic_clues():
    clues = clues_from_json([absolute(), relative()])

    assert clues[0] == AbsolutePosition(("nation", "Norwegian"), "==", 1)
    assert clues[1] == RelativePosition(("color", "green"), ("color", "ivory"), "==", 1)


# "Same house" is offset 0, so leaving it out is the common case, not a mistake.
def test_offset_defaults_to_zero():
    clue = relative()
    del clue["offset"]

    assert clues_from_json([clue])[0].offset == 0


# A combined clue holds more clues, so reading it recurses.
def test_reads_nested_clues():
    data = [{"type": "Or", "constraints": [absolute(), {"type": "And", "constraints": [relative()]}]}]

    clue = clues_from_json(data)[0]

    assert isinstance(clue, Or)
    assert isinstance(clue.constraints[0], AbsolutePosition)
    assert isinstance(clue.constraints[1], And)


# The user's own sentence is what the explanation will quote back at them.
def test_keeps_the_original_sentence():
    clue = clues_from_json([absolute(source_text="The Norwegian lives in the first house.")])[0]

    assert clue.source_text == "The Norwegian lives in the first house."


# The AI returning one object instead of a list is a whole-reply problem.
def test_the_reply_must_be_a_list():
    assert problems_from(absolute())[0].where == "the whole reply"


# An invented clue type must be named, with the real ones offered back.
def test_an_unknown_clue_type_is_rejected():
    problem = problems_from([{"type": "Banana"}])[0]

    assert "Banana" in problem.problem
    assert "AbsolutePosition" in problem.allowed


# A clue with no type at all reads differently from one with a wrong type.
def test_a_missing_clue_type_is_rejected():
    assert "no 'type' given" in problems_from([{"position": 1}])[0].problem


# A pair has to be exactly [category, value], both text.
@pytest.mark.parametrize("broken", ["nope", ["only-one"], ["a", "b", "c"], ["a", 2], None])
def test_a_bad_pair_is_rejected(broken):
    problems = problems_from([absolute(category_value=broken)])

    assert any("category_value" in p.problem for p in problems)


# Checked here rather than in __post_init__, which would raise straight away
# and abandon every problem found after it.
def test_an_unsupported_operator_is_rejected():
    problem = problems_from([absolute(operator="~~")])[0]

    assert "~~" in problem.problem
    assert "==" in problem.allowed


# In Python True IS an integer, so a naive isinstance check would read
# {"position": true} as house 1.
def test_a_boolean_is_not_accepted_as_a_position():
    assert any("position" in p.problem for p in problems_from([absolute(position=True)]))


@pytest.mark.parametrize("broken", ["1", 1.5, None, [1]])
def test_a_non_integer_position_is_rejected(broken):
    assert any("position" in p.problem for p in problems_from([absolute(position=broken)]))


# A field the AI invented is reported rather than ignored — quietly dropping it
# would lose whatever it was trying to say.
def test_an_unexpected_field_is_rejected():
    problem = problems_from([absolute(colour="red")])[0]

    assert "colour" in problem.problem


# An empty Or means nothing, so it is a mistake rather than a no-op.
def test_an_empty_group_is_rejected():
    assert any("non-empty" in p.problem for p in problems_from([{"type": "Or", "constraints": []}]))


# The sentence ends up quoted in the explanation, so it has to be text.
def test_a_non_text_sentence_is_rejected():
    assert any("source_text" in p.problem for p in problems_from([absolute(source_text=7)]))


# A problem inside a combined clue has to say WHICH part, or a retry cannot
# tell which piece to fix.
def test_a_nested_problem_says_which_part():
    data = [{"type": "And", "constraints": [absolute(), absolute(operator="~~")]}]

    assert problems_from(data)[0].where == "clue 1 -> part 2"


# The whole point of collecting: one retry fixes everything, rather than the AI
# being corrected once per mistake.
def test_every_problem_is_reported_at_once():
    data = [
        {"type": "Banana"},
        absolute(operator="~~"),
        "not even an object",
    ]

    problems = problems_from(data)

    assert len(problems) >= 3
    assert {p.where for p in problems} == {"clue 1", "clue 2", "clue 3"}


# Runaway nesting must produce a readable complaint, not a blown Python stack.
def test_nesting_too_deep_is_rejected():
    clue = absolute()
    for _ in range(15):
        clue = {"type": "And", "constraints": [clue]}

    assert any("nested" in p.problem for p in problems_from([clue]))


# Writing a clue out and reading it back must give the same clue. One test
# covering every field of every type.
@pytest.mark.parametrize("clue", [
    AbsolutePosition(("nation", "Norwegian"), "==", 1),
    AbsolutePosition(("nation", "Spaniard"), "<=", 3, source_text="No later than house three."),
    RelativePosition(("color", "green"), ("color", "ivory"), "==", 1),
    RelativePosition(("pet", "dog"), ("drink", "milk"), ">", -2, source_text="Somewhere right."),
    And([AbsolutePosition(("color", "red"), "==", 1),
         RelativePosition(("pet", "cat"), ("color", "red"), "==", 0)]),
    Or([AbsolutePosition(("color", "red"), "==", 1),
        AbsolutePosition(("color", "red"), "==", 5)], source_text="Red is at one end."),
])
def test_a_clue_survives_a_round_trip(clue):
    written = clue_to_json(clue)
    read_back = clues_from_json([written])[0]

    assert read_back == clue
    # source_text is compare=False, so equality above does not cover it.
    assert read_back.source_text == clue.source_text


# Round-tripping must not invent fields either, or the data would drift.
def test_writing_a_clue_leaves_out_an_absent_sentence():
    assert "source_text" not in clue_to_json(AbsolutePosition(("nation", "Norwegian"), "==", 1))


# The two guards have different jobs: this one never looks at the puzzle, so a
# clue naming things that do not exist still reads fine here. Catching that is
# validate_constraints' job, and it runs next.
def test_reading_a_clue_does_not_check_it_against_a_puzzle():
    clue = clues_from_json([absolute(category_value=["nonsense", "nobody"])])[0]

    assert clue.category_value == ("nonsense", "nobody")
