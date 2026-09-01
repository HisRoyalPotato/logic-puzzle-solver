# Logic Puzzle Solver

Type an Einstein/Zebra-style logic puzzle in plain English. An AI turns the
sentences into structured clues. A hand-built solver works out the answer and
shows a step-by-step chain explaining why each conclusion follows.

**The AI never solves anything.** It reads language and nothing else. Every
piece of reasoning is done by the solver, which is a plain algorithm with no
model in it anywhere — because a language model cannot be trusted to reliably
chain multi-step constraint logic, and a wrong answer that sounds confident is
worse than no answer.

```
English  ->  AI  ->  JSON  ->  parser  ->  validator  ->  SOLVER  ->  trace  ->  page
             |                 |           |              |
        language only     "is this a   "does the      all the reasoning,
                            clue?"      puzzle have    and a proof of
                                        these?"        every step
```

## What it guarantees

Three independent guards, each catching what the others cannot:

| guard | catches |
|---|---|
| `parsing.clues_from_json` | data that is not a clue at all — bad type, bad operator, missing field |
| `constraints.validate_constraints` | a clue naming a category, value, or position this puzzle does not have |
| `verify.verify` | a finished answer that breaks one of its own clues |
| `verify.verify_trace` | an explanation that does not match what the solver actually did |

The first two objections are fed back to the AI for a retry — they mean the
translation was wrong, not that the puzzle is impossible. The last two can only
mean a bug in this code, so they raise.

## How the solver works

Constraint propagation, not search. Each clue repeatedly crosses off candidates
it can prove impossible, until nothing more falls out.

That alone stalls on the real Zebra puzzle with 18 of 25 cells still open, so it
also does **shaving**: assume a candidate, propagate, and if the puzzle explodes
then that candidate was never possible. Shaving only ever *refutes* — a trial
that survives proves nothing and is discarded. That refusal is what keeps every
conclusion a proof rather than a guess, and it is why the explanation can be
checked line by line.

There is no backtracking and no guessing anywhere in the repository.

### Measured

- Solves the classic Zebra puzzle in ~35 ms
- 2,940 generated puzzles, checked against brute-force ground truth: never a
  wrong answer, never a solvable puzzle called impossible, never a stall on a
  uniquely-solvable one
- 340 *minimal* uniquely-solvable puzzles up to 7x5 — all solved, none stalled

Shaving is essentially Singleton Arc Consistency, which means human techniques
like naked pairs fall out of it for free rather than being coded one by one.

## The explanation

Every removal is recorded with its reason and the earlier steps it leaned on.
Two structures come out of that:

- **nesting** (a tree) — what happened inside an assumption, so facts that were
  only true in a hypothetical cannot be mistaken for real ones
- **dependencies** (a graph) — what each step leaned on, so a chain can say
  "because of step 12" and so a backwards walk can trim a proof to what mattered

Neighbouring steps sharing a reason and its evidence are grouped, so the Zebra
puzzle reads as 74 steps rather than 125.

## Running it

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --reload
```

Then open http://127.0.0.1:8000.

The bundled Einstein puzzle ships already translated, so it solves with **no API
key and no cost**. A key is only needed to translate a new puzzle from English,
and the site asks the visitor for their own — it is used for one request and then
dropped, never stored and never logged.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

214 tests. The translator's retry paths are all covered with canned replies, so
they run without an API key.

## Layout

```
puzzle.py       the shape of a puzzle: categories, values, how many positions
deduction.py    recorded steps, and the tools for grouping and trimming them
possibilities.py the grid of what is still possible, and the trace of why
rules.py        the two facts true of every puzzle, whatever the clues say
constraints.py  the clue types, and the guard on what they may name
verify.py       independent checks on the answer and on the explanation
solve.py        propagation, shaving, and the public solve() front door
parsing.py      untrusted data -> real clues, or a clear list of complaints
translate.py    English -> clues, with the guards as the judge
app.py          the web layer
```
