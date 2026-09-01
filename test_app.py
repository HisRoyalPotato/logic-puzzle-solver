from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


# The page itself has to load, or nothing else matters.
def test_the_page_loads():
    response = client.get("/")

    assert response.status_code == 200
    assert "Logic Puzzle Solver" in response.text


# The no-key path: the whole point of bundling a translated example.
def test_the_example_solves_without_a_key():
    body = client.get("/api/example").json()

    assert body["status"] == "solved"
    assert body["info"]["name"] == "The Einstein Puzzle"
    assert len(body["answer"]) == 5
    assert len(body["categories"]) == 5


# The answer must be the real one, not just any grid.
def test_the_example_gives_the_known_answer():
    rows = client.get("/api/example").json()["answer"]
    by_position = {row["position"]: row["values"] for row in rows}

    zebra = next(p for p, v in by_position.items() if v["pet"] == "zebra")
    water = next(p for p, v in by_position.items() if v["drink"] == "water")

    assert by_position[zebra]["nation"] == "Japanese"
    assert by_position[water]["nation"] == "Norwegian"


# The explanation is the product, so it has to come back with the answer.
def test_the_example_comes_with_its_explanation():
    body = client.get("/api/example").json()

    assert len(body["trace"]) > 50
    assert any(group["children"] for group in body["trace"])
    # Every group carries its own id, which is what makes the chain checkable.
    assert [g["id"] for g in body["trace"]] == list(range(1, len(body["trace"]) + 1))


# The clues are shown in the user's own words, not as internals.
def test_the_clues_come_back_as_english():
    clues = client.get("/api/example").json()["clues"]

    assert len(clues) == 14
    assert clues[0]["text"] == "The Englishman lives in the red house."


# A missing key is a clear message, not a crash or a server-side charge.
def test_solving_without_a_key_is_refused():
    response = client.post("/api/solve", json={"text": "a puzzle", "api_key": ""})

    assert response.status_code == 400
    assert "API key" in response.json()["detail"]


# An empty puzzle should not reach the API at all.
def test_an_empty_puzzle_is_refused():
    response = client.post("/api/solve", json={"text": "   ", "api_key": "sk-test"})

    assert response.status_code == 400


# A failure inside translation must surface as a clean error, never a stack
# trace, and never a 500.
def test_a_broken_translation_is_reported_cleanly(monkeypatch):
    import app as app_module
    from translate import TranslationFailed

    def fails(text, ask, **kwargs):
        raise TranslationFailed([["clue 1: unsupported operator '~~'"]])

    monkeypatch.setattr(app_module, "translate", fails)
    monkeypatch.setattr(app_module, "anthropic_asker", lambda key: None)

    response = client.post("/api/solve", json={"text": "a puzzle", "api_key": "sk-test"})

    assert response.status_code == 422
    assert "Could not read" in response.json()["detail"]["message"]
    assert "~~" in response.json()["detail"]["attempts"][0][0]


# If the API itself is unreachable or the key is bad, say so plainly.
def test_an_api_failure_is_reported_cleanly(monkeypatch):
    import app as app_module

    def explodes(key):
        raise RuntimeError("invalid x-api-key")

    monkeypatch.setattr(app_module, "anthropic_asker", explodes)

    response = client.post("/api/solve", json={"text": "a puzzle", "api_key": "bad"})

    assert response.status_code == 502
    assert "invalid x-api-key" in response.json()["detail"]


# A successful custom puzzle goes all the way through to an explanation.
def test_a_custom_puzzle_solves_end_to_end(monkeypatch):
    import app as app_module
    from examples import load

    _, puzzle, clues = load()
    monkeypatch.setattr(app_module, "anthropic_asker", lambda key: None)
    monkeypatch.setattr(app_module, "translate", lambda text, ask, **kw: (puzzle, clues))

    body = client.post("/api/solve", json={"text": "a puzzle", "api_key": "sk-test"}).json()

    assert body["status"] == "solved"
    assert body["info"]["name"] == "Your puzzle"
    assert body["trace"]
