"""End-to-end test on the real thing: the classic Einstein / Zebra puzzle.

Pure propagation stalls on this one with 18 of the 25 cells still open.
Shaving finishes it, which is exactly why shaving exists.
"""
from constraints import AbsolutePosition, Or, RelativePosition
from puzzle import Puzzle
from solve import Status, propagate_until_stable, shave, solve
from possibilities import PossibilityGrid


def zebra_puzzle():
    return Puzzle({
        "nation": ["English", "Spaniard", "Ukrainian", "Norwegian", "Japanese"],
        "color": ["red", "green", "ivory", "yellow", "blue"],
        "pet": ["dog", "snails", "fox", "horse", "zebra"],
        "drink": ["coffee", "tea", "milk", "juice", "water"],
        "smoke": ["OldGold", "Kools", "Chesterfields", "LuckyStrike", "Parliaments"],
    }, 5)


# Two things sharing a house: same position, no offset.
def same_house(a, b):
    return RelativePosition(a, b, "==", 0)


# "Next to" is genuinely either side, so it needs an Or.
def next_to(a, b):
    return Or([RelativePosition(a, b, "==", 1), RelativePosition(a, b, "==", -1)])


def zebra_clues():
    return [
        same_house(("nation", "English"), ("color", "red")),
        same_house(("nation", "Spaniard"), ("pet", "dog")),
        same_house(("drink", "coffee"), ("color", "green")),
        same_house(("nation", "Ukrainian"), ("drink", "tea")),
        # Green is immediately right of ivory: ivory's position + 1 is green's.
        RelativePosition(("color", "ivory"), ("color", "green"), "==", 1),
        same_house(("smoke", "OldGold"), ("pet", "snails")),
        same_house(("smoke", "Kools"), ("color", "yellow")),
        AbsolutePosition(("drink", "milk"), "==", 3),
        AbsolutePosition(("nation", "Norwegian"), "==", 1),
        next_to(("smoke", "Chesterfields"), ("pet", "fox")),
        next_to(("smoke", "Kools"), ("pet", "horse")),
        same_house(("smoke", "LuckyStrike"), ("drink", "juice")),
        same_house(("nation", "Japanese"), ("smoke", "Parliaments")),
        next_to(("nation", "Norwegian"), ("color", "blue")),
    ]


# The known answer, house by house.
EXPECTED = {
    1: ("Norwegian", "yellow", "fox", "water", "Kools"),
    2: ("Ukrainian", "blue", "horse", "tea", "Chesterfields"),
    3: ("English", "red", "snails", "milk", "OldGold"),
    4: ("Spaniard", "ivory", "dog", "juice", "LuckyStrike"),
    5: ("Japanese", "green", "zebra", "coffee", "Parliaments"),
}


# The whole puzzle, end to end, through the public entry point.
def test_solver_cracks_the_classic_zebra_puzzle():
    result = solve(zebra_puzzle(), zebra_clues())

    assert result.status is Status.SOLVED

    for position, expected_row in EXPECTED.items():
        actual = tuple(result.assignment[(category, position)]
                       for category in ["nation", "color", "pet", "drink", "smoke"])
        assert actual == expected_row, f"house {position}"


# The two questions the puzzle actually asks.
def test_the_japanese_owns_the_zebra_and_the_norwegian_drinks_water():
    result = solve(zebra_puzzle(), zebra_clues())

    zebra_house = result.possibilities.positions_for("pet", "zebra")[0]
    water_house = result.possibilities.positions_for("drink", "water")[0]

    assert result.assignment[("nation", zebra_house)] == "Japanese"
    assert result.assignment[("nation", water_house)] == "Norwegian"


# Records WHY shaving had to exist: without it this puzzle does not finish.
# If a future deduction rule makes plain propagation strong enough, this test
# will fail — that's a good failure, and the comment is the explanation.
def test_plain_propagation_alone_cannot_finish_the_zebra_puzzle():
    puzzle = zebra_puzzle()
    grid = PossibilityGrid(puzzle)

    propagate_until_stable(grid, zebra_clues())

    still_open = [(category, position)
                  for category in puzzle.categories
                  for position in puzzle.positions
                  if not grid.is_forced(category, position)]

    # 18 of 25 cells at the time of writing. Asserting "some are open" rather
    # than the exact number, so a future deduction rule that narrows things
    # further doesn't fail this test for the wrong reason.
    assert still_open

    # Crucially it stalls without ever being WRONG: every value the real
    # answer needs is still alive, it just hasn't been narrowed down.
    for position, expected_row in EXPECTED.items():
        for category, value in zip(["nation", "color", "pet", "drink", "smoke"], expected_row):
            assert grid.is_candidate(category, position, value)


# The exact deduction plain propagation cannot make, from the trace we walked:
# assuming Japanese in house 2 forces tea out, juice in, Lucky Strike into
# house 2 — leaving Parliaments nowhere to go, though Japanese smokes them.
# No single clue can see that chain; assuming it is what makes it visible.
def test_shaving_refutes_what_propagation_could_not_see():
    grid = PossibilityGrid(zebra_puzzle())
    clues = zebra_clues()
    propagate_until_stable(grid, clues)

    # Propagation left both nations open at house 2.
    assert grid.candidates("nation", 2) == {"Japanese", "Ukrainian"}

    assert shave(grid, clues) is True

    # Shaving refutes Japanese there, which forces the Ukrainian in.
    assert grid.forced_value("nation", 2) == "Ukrainian"
