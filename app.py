"""The web front door: a page, an example, and a solve endpoint.

Deliberately thin. Every hard thing already happened underneath — this layer
only moves data in and out, so nothing here decides anything about a puzzle.

Two ways in:

    GET  /api/example  the bundled Einstein puzzle, already translated.
                       No API key, no cost, works for everyone.

    POST /api/solve    a puzzle in English, plus the VISITOR'S OWN API key.
                       Their key, their few cents, never the site owner's.

The key is used for one request and then dropped: never stored, never logged,
never written to disk. That is the whole reason it is asked for per request
instead of configured on the server — a public URL with the owner's key on it
is an open tab anyone can run up.
"""
import pathlib

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from deduction import to_ai_payload
from examples import load
from solve import solve
from translate import TranslationFailed, anthropic_asker, translate

app = FastAPI(title="Logic Puzzle Solver")

STATIC = pathlib.Path(__file__).parent / "static"


class PuzzleRequest(BaseModel):
    text: str
    api_key: str


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/example")
def example():
    """The bundled puzzle, solved. The no-key path, and the one that proves the
    solver works without any AI involved at all."""
    info, puzzle, clues = load()
    return {"info": info, **_solved(puzzle, clues)}


@app.post("/api/solve")
def solve_puzzle(request: PuzzleRequest):
    """English in, answer and explanation out. The AI reads the words; the
    solver does every piece of the reasoning."""
    if not request.api_key.strip():
        raise HTTPException(400, "An API key is needed to translate a new puzzle.")
    if not request.text.strip():
        raise HTTPException(400, "There is no puzzle here to solve.")

    try:
        puzzle, clues = translate(request.text, anthropic_asker(request.api_key.strip()))
    except TranslationFailed as failed:
        # The clues could not be read even after retrying. Show what the guards
        # objected to — that is far more useful than "translation failed".
        raise HTTPException(422, {
            "message": "Could not read that puzzle into clues.",
            "attempts": failed.attempts,
        })
    except Exception as broken:  # noqa: BLE001 - the API call can fail many ways
        raise HTTPException(502, f"The translation service failed: {broken}")

    return {"info": {"name": "Your puzzle", "text": request.text, "question": ""},
            **_solved(puzzle, clues)}


def _solved(puzzle, clues):
    """Run the solver and shape the result for the page.

    The trace is serialised with to_ai_payload — the same structure built for
    the AI wording layer. It already writes every fact out in full and gives
    each group a stable id, which is exactly what rendering needs too.
    """
    result = solve(puzzle, clues)

    return {
        "status": result.status.value,
        "reason": result.reason,
        "categories": list(puzzle.categories),
        "answer": _answer_rows(puzzle, result.assignment),
        "clues": [{"number": number, "text": clue.source_text or repr(clue)}
                  for number, clue in enumerate(clues, 1)],
        "trace": to_ai_payload(result.trace or [], clues),
    }


def _answer_rows(puzzle, assignment):
    """The finished grid as one row per position, or None if it never finished."""
    if assignment is None:
        return None
    return [
        {"position": position,
         "values": {category: assignment[(category, position)] for category in puzzle.categories}}
        for position in puzzle.positions
    ]
