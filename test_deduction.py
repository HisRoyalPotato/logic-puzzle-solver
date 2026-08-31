from constraints import AbsolutePosition
from deduction import (
    Group,
    Rule,
    Step,
    StepKind,
    SubProof,
    describe,
    group_steps,
    relevant,
    to_ai_payload,
)


def eliminate_step(category, position, value, because=None, leaning_on=()):
    return Step(kind=StepKind.ELIMINATE, category=category, position=position,
                value=value, because=because, leaning_on=list(leaning_on))


# The classic dataclass trap: a bare [] default would be shared by every
# instance, so every Step would append into the same list.
def test_each_step_gets_its_own_lists():
    one, other = eliminate_step("color", 1, "red"), eliminate_step("color", 2, "red")

    one.children.append("x")
    one.leaning_on.append("y")

    assert other.children == []
    assert other.leaning_on == []


# Every kind gets a plain factual label, including both shapes of contradiction.
def test_describe_covers_every_kind():
    assert describe(eliminate_step("color", 1, "red")) == "the color at position 1 is not red"
    assert describe(Step(StepKind.CONCLUDE, "color", 1, "red")) == "the color at position 1 is red"
    assert describe(Step(StepKind.SUPPOSE, "color", 1, "red")).startswith("suppose")

    # A cell that ran out of values names the cell but no value.
    assert describe(Step(StepKind.CONTRADICTION, "color", position=3)) == (
        "no value is left for color at position 3"
    )
    # A value that ran out of homes names the value but no position.
    assert describe(Step(StepKind.CONTRADICTION, "color", value="red")) == (
        "no position is left for red in color"
    )
    # An Or with no branch left is about a whole clue, not any one cell.
    assert describe(Step(StepKind.CONTRADICTION)) == "no branch of this clue can hold"


# The backwards walk keeps what a step needed and drops what it didn't.
def test_relevant_follows_dependencies_backwards():
    root = eliminate_step("color", 1, "red")
    middle = eliminate_step("color", 2, "red", leaning_on=[root])
    target = eliminate_step("color", 3, "red", leaning_on=[middle])
    unrelated = eliminate_step("pet", 1, "dog")

    kept = relevant([root, middle, unrelated, target], [target])

    assert kept == [root, middle, target]
    assert unrelated not in kept


# One step feeding several others must not be walked (or returned) twice.
def test_relevant_handles_a_step_used_more_than_once():
    root = eliminate_step("color", 1, "red")
    left = eliminate_step("color", 2, "red", leaning_on=[root])
    right = eliminate_step("color", 3, "red", leaning_on=[root])
    end = eliminate_step("color", 4, "red", leaning_on=[left, right])

    kept = relevant([root, left, right, end], [end])

    assert kept == [root, left, right, end]


# Same reason AND same evidence means one thought, so one sentence.
def test_group_merges_steps_sharing_a_reason_and_evidence():
    trigger = eliminate_step("color", 1, "green")
    steps = [
        eliminate_step("color", position, "red", because=Rule.VALUE_USED_ONCE,
                       leaning_on=[trigger])
        for position in (2, 3, 4)
    ]

    groups = group_steps(steps)

    assert len(groups) == 1
    assert len(groups[0].steps) == 3


# Same clue but different evidence is different reasoning, so it stays apart.
def test_group_keeps_different_evidence_separate():
    first_fact = eliminate_step("color", 1, "green")
    second_fact = eliminate_step("color", 2, "blue")
    steps = [
        eliminate_step("color", 3, "red", because=Rule.VALUE_USED_ONCE,
                       leaning_on=[first_fact]),
        eliminate_step("color", 4, "red", because=Rule.VALUE_USED_ONCE,
                       leaning_on=[second_fact]),
    ]

    assert len(group_steps(steps)) == 2


# A conclusion is its own distinct thought and never merges into a run.
def test_group_never_merges_a_conclusion():
    steps = [
        eliminate_step("color", 2, "red", because=Rule.VALUE_USED_ONCE),
        Step(StepKind.CONCLUDE, "color", 1, "green"),
        eliminate_step("color", 3, "red", because=Rule.VALUE_USED_ONCE),
    ]

    groups = group_steps(steps)

    assert [group.kind for group in groups] == [
        StepKind.ELIMINATE, StepKind.CONCLUDE, StepKind.ELIMINATE
    ]


# Ids must be 1..n with no gaps or repeats — that is what lets the AI's reply
# be checked for dropped or invented steps.
def test_payload_ids_are_unique_and_sequential():
    groups = group_steps([
        eliminate_step("color", 1, "red"),
        Step(StepKind.CONCLUDE, "color", 2, "green"),
        eliminate_step("pet", 1, "dog"),
    ])

    payload = to_ai_payload(groups)
    ids = [entry["id"] for entry in payload]

    assert ids == list(range(1, len(payload) + 1))


# A dependency carries the fact itself, not just a pointer, so the AI never
# has to look anything up.
def test_payload_inlines_the_facts_it_depends_on():
    trigger = eliminate_step("color", 1, "green", because=Rule.VALUE_USED_ONCE)
    dependent = eliminate_step("color", 2, "red", because=Rule.VALUE_MUST_BE_SOMEWHERE,
                               leaning_on=[trigger])

    payload = to_ai_payload(group_steps([trigger, dependent]))

    assert payload[1]["because"] == [
        {"id": 1, "says": "the color at position 1 is not green"}
    ]


# The user's own sentence is what the explanation should quote back at them.
def test_payload_quotes_the_original_clue_text():
    clue = AbsolutePosition(("nation", "Norwegian"), "==", 1,
                            source_text="The Norwegian lives in the first house.")
    steps = [eliminate_step("nation", 2, "Norwegian", because=clue)]

    payload = to_ai_payload(group_steps(steps), constraints=[clue])

    assert payload[0]["clue"] == {
        "kind": "clue",
        "number": 1,
        "text": "The Norwegian lives in the first house.",
    }


# A puzzle rule is named as a rule, since it is not one of the user's clues.
def test_payload_names_a_puzzle_rule():
    steps = [eliminate_step("color", 2, "red", because=Rule.VALUE_USED_ONCE)]

    payload = to_ai_payload(group_steps(steps))

    assert payload[0]["clue"]["kind"] == "rule"
    assert "exactly one position" in payload[0]["clue"]["text"]


# A sub-proof rides along with the step it justifies, and says how it ended.
def test_payload_carries_sub_proofs():
    assumption = Step(StepKind.SUPPOSE, "nation", 2, "Japanese")
    inner = eliminate_step("drink", 2, "tea", leaning_on=[assumption])
    step = eliminate_step("nation", 2, "Japanese", because=Rule.SHAVING)
    step.children = [SubProof(steps=[assumption, inner], refuted=True, about=assumption)]

    payload = to_ai_payload(group_steps([step]))
    child = payload[0]["children"][0]

    assert child["ended_in_contradiction"] is True
    assert child["assuming"] == "suppose the nation at position 2 is Japanese"
    assert len(child["steps"]) == 2


# A Group reports the kind of the steps inside it.
def test_group_kind_reads_from_its_steps():
    assert Group(because=None, steps=[eliminate_step("color", 1, "red")]).kind is StepKind.ELIMINATE


# An Or eliminates through its children, so the recorded step names a child.
# It must still be able to say which of the user's sentences it came from.
def test_payload_resolves_a_clue_nested_inside_a_combined_one():
    from constraints import Or

    inner = AbsolutePosition(("color", "red"), "==", 1)
    clue = Or([inner, AbsolutePosition(("color", "red"), "==", 2)],
              source_text="The red house is at one end of the street.")

    payload = to_ai_payload(
        group_steps([eliminate_step("color", 3, "red", because=inner)]),
        constraints=[clue],
    )

    assert payload[0]["clue"] == {
        "kind": "clue",
        "number": 1,
        "text": "The red house is at one end of the street.",
    }
