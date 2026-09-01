from deduction import StepKind
from examples import load
from solve import Status, solve
from verify import verify


# The bundled example has to actually work, or the site's one no-key demo is
# broken and only a visitor would find out.
def test_the_einstein_example_solves():
    info, puzzle, clues = load()
    result = solve(puzzle, clues)

    assert result.status is Status.SOLVED
    assert verify(puzzle, clues, result.assignment) == []
    assert info["name"] == "The Einstein Puzzle"


# The two questions the puzzle actually asks.
def test_the_japanese_owns_the_zebra_and_the_norwegian_drinks_water():
    _, puzzle, clues = load()
    answer = solve(puzzle, clues).assignment

    house_with = lambda category, value: next(
        position for (c, position), v in answer.items() if c == category and v == value
    )

    assert answer[("nation", house_with("pet", "zebra"))] == "Japanese"
    assert answer[("nation", house_with("drink", "water"))] == "Norwegian"


# Every clue must carry the sentence it came from — that is what the
# explanation quotes back at the reader.
def test_every_clue_keeps_its_english_sentence():
    _, _, clues = load()

    assert len(clues) == 14
    assert all(clue.source_text for clue in clues)
    assert clues[0].source_text == "The Englishman lives in the red house."


# The displayed text must contain the clues themselves, since it is what a
# visitor reads and what they would re-translate with their own key.
def test_the_puzzle_text_contains_its_clues():
    info, _, clues = load()

    assert all(clue.source_text in info["text"] for clue in clues)


# The example is stored in the translator's own output format, so it doubles
# as a worked example of what the AI is asked to produce.
def test_the_example_produces_a_full_explanation():
    _, puzzle, clues = load()
    result = solve(puzzle, clues)

    assert len(result.trace) > 50
    assert any(step.children for group in result.trace for step in group.steps)
    assert any(group.kind is StepKind.CONCLUDE for group in result.trace)
