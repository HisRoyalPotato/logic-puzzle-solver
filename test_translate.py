import json

import pytest

from constraints import AbsolutePosition, Or
from solve import Status, solve
from translate import TranslationFailed, translate


def good_reply(**overrides):
    """A well-formed translation of a tiny three-house puzzle."""
    data = {
        "num_positions": 3,
        "categories": {"color": ["red", "green", "blue"], "pet": ["cat", "dog", "fish"]},
        "clues": [
            {"type": "AbsolutePosition", "category_value": ["color", "red"],
             "operator": "==", "position": 1, "source_text": "The red house is first."},
            {"type": "RelativePosition", "a": ["pet", "cat"], "b": ["color", "red"],
             "operator": "==", "offset": 0, "source_text": "The cat lives in the red house."},
        ],
    }
    data.update(overrides)
    return json.dumps(data)


def replies(*canned):
    """An `ask` that hands back the given replies in order. Records what it was
    asked, so a test can check what the retry actually said."""
    sent = []

    def ask(conversation):
        sent.append(conversation)
        return canned[len(sent) - 1]

    ask.sent = sent
    return ask


# The happy path: one reply, straight through both guards.
def test_reads_a_good_reply():
    puzzle, clues = translate("some puzzle", replies(good_reply()))

    assert puzzle.num_positions == 3
    assert sorted(puzzle.categories) == ["color", "pet"]
    assert clues[0] == AbsolutePosition(("color", "red"), "==", 1)


# The user's own sentences have to survive the trip — they get quoted back in
# the explanation.
def test_keeps_the_original_sentences():
    _, clues = translate("some puzzle", replies(good_reply()))

    assert clues[0].source_text == "The red house is first."


# Models wrap JSON in a markdown fence constantly, whatever the prompt says.
# Being lenient about the WRAPPER is safe; nothing about the clues is guessed.
def test_accepts_json_wrapped_in_a_markdown_fence():
    fenced = "Here you go:\n\n```json\n" + good_reply() + "\n```\n"

    puzzle, _ = translate("some puzzle", replies(fenced))

    assert puzzle.num_positions == 3


# Stray words either side of a bare object are tolerated too.
def test_accepts_json_with_chatter_around_it():
    messy = "Sure! " + good_reply() + " Hope that helps."

    assert translate("some puzzle", replies(messy))[0].num_positions == 3


# A reply with no JSON at all gets one clear instruction back.
def test_a_reply_with_no_json_is_retried():
    ask = replies("I'd rather not.", good_reply())

    translate("some puzzle", ask)

    assert len(ask.sent) == 2
    assert "not a single JSON object" in ask.sent[1][-1]["content"]


# A malformed clue comes back from the parser, and its complaint is passed on.
def test_a_malformed_clue_is_retried_with_the_parser_s_complaint():
    broken = good_reply(clues=[{"type": "AbsolutePosition",
                                "category_value": ["color", "red"],
                                "operator": "~~", "position": 1}])
    ask = replies(broken, good_reply())

    translate("some puzzle", ask)

    complaint = ask.sent[1][-1]["content"]
    assert "clue 1" in complaint
    assert "~~" in complaint


# A clue naming something the puzzle never defined is caught by the second
# guard, not the first, and its complaint is passed on too.
def test_a_clue_naming_nothing_real_is_retried():
    broken = good_reply(clues=[{"type": "AbsolutePosition",
                                "category_value": ["color", "purple"],
                                "operator": "==", "position": 1}])
    ask = replies(broken, good_reply())

    translate("some puzzle", ask)

    assert "purple" in ask.sent[1][-1]["content"]


# The position guard added for exactly this: house 47 is a broken clue, not an
# impossible puzzle.
def test_a_position_outside_the_puzzle_is_retried():
    broken = good_reply(clues=[{"type": "AbsolutePosition",
                                "category_value": ["color", "red"],
                                "operator": "==", "position": 47}])
    ask = replies(broken, good_reply())

    translate("some puzzle", ask)

    assert "47" in ask.sent[1][-1]["content"]


# A category with the wrong number of values is Puzzle's own rule, surfaced
# back to the AI rather than crashing.
def test_a_category_of_the_wrong_size_is_retried():
    broken = good_reply(categories={"color": ["red", "green"], "pet": ["cat", "dog", "fish"]})
    ask = replies(broken, good_reply())

    translate("some puzzle", ask)

    assert "color" in ask.sent[1][-1]["content"]


@pytest.mark.parametrize("broken", [
    {"num_positions": 0},
    {"num_positions": "three"},
    {"num_positions": True},      # in Python True is an integer; it must not pass
    {"categories": {}},
    {"categories": "nope"},
    {"categories": {"color": [1, 2, 3]}},
])
def test_a_broken_puzzle_shape_is_retried(broken):
    ask = replies(good_reply(**broken), good_reply())

    translate("some puzzle", ask)

    assert len(ask.sent) == 2


# Every problem goes back at once, so one retry can fix them all rather than
# the AI being corrected one mistake at a time.
def test_all_the_problems_go_back_together():
    broken = good_reply(clues=[
        {"type": "Banana"},
        {"type": "AbsolutePosition", "category_value": ["color", "red"],
         "operator": "~~", "position": 1},
    ])
    ask = replies(broken, good_reply())

    translate("some puzzle", ask)

    complaint = ask.sent[1][-1]["content"]
    assert "clue 1" in complaint and "clue 2" in complaint


# The retry has to carry the conversation, or the AI is answering blind.
def test_the_retry_keeps_the_earlier_exchange():
    ask = replies("nonsense", good_reply())

    translate("some puzzle", ask)

    roles = [message["role"] for message in ask.sent[1]]
    assert roles == ["user", "assistant", "user"]


# Giving up has to be explicit, and has to carry what went wrong each time.
def test_it_gives_up_after_the_attempt_limit():
    ask = replies("no", "still no", "nope")

    with pytest.raises(TranslationFailed) as raised:
        translate("some puzzle", ask, max_attempts=3)

    assert len(raised.value.attempts) == 3
    assert len(ask.sent) == 3


# The attempt limit is honoured exactly, not off by one.
def test_a_single_attempt_is_respected():
    ask = replies("no")

    with pytest.raises(TranslationFailed):
        translate("some puzzle", ask, max_attempts=1)

    assert len(ask.sent) == 1


# The real test of the whole boundary: text in, solved puzzle with a readable
# chain out, with nothing but the solver doing the reasoning.
def test_a_translated_puzzle_solves_end_to_end():
    reply = json.dumps({
        "num_positions": 3,
        "categories": {"color": ["red", "green", "blue"], "pet": ["cat", "dog", "fish"]},
        "clues": [
            {"type": "AbsolutePosition", "category_value": ["color", "red"],
             "operator": "==", "position": 1, "source_text": "The red house is first."},
            {"type": "AbsolutePosition", "category_value": ["color", "green"],
             "operator": "==", "position": 2, "source_text": "The green house is second."},
            {"type": "RelativePosition", "a": ["pet", "cat"], "b": ["color", "red"],
             "operator": "==", "offset": 0, "source_text": "The cat lives in the red house."},
            {"type": "AbsolutePosition", "category_value": ["pet", "dog"],
             "operator": "==", "position": 2, "source_text": "The dog lives in house two."},
        ],
    })

    puzzle, clues = translate("a puzzle", replies(reply))
    result = solve(puzzle, clues)

    assert result.status is Status.SOLVED
    assert result.assignment[("pet", 3)] == "fish"
    assert result.trace


# An Or clue survives translation, which is what "next to" and "at one end"
# both become.
def test_an_or_clue_translates():
    reply = good_reply(clues=[{
        "type": "Or",
        "source_text": "The red house is at one end.",
        "constraints": [
            {"type": "AbsolutePosition", "category_value": ["color", "red"],
             "operator": "==", "position": 1},
            {"type": "AbsolutePosition", "category_value": ["color", "red"],
             "operator": "==", "position": 3},
        ],
    }])

    _, clues = translate("some puzzle", replies(reply))

    assert isinstance(clues[0], Or)
    assert clues[0].source_text == "The red house is at one end."
