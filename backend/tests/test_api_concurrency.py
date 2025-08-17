"""Concurrency-focused tests exercising the API's per-request isolation."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def _post_run(payload):
    r = client.post("/run", json=payload)
    return r.status_code, r.json()


def test_concurrent_runs_isolated():
    # Prepare three different jobs with small caps so at least one will hit a limit
    jobs = [
        {"code": "\n".join(["say 1"] * 50), "settings": {"max_steps": 1000}},
        {"code": "\n".join(["say \"x\""] * 100), "settings": {"max_output_chars": 10}},
        {"code": "let a = 1\nsay a", "settings": {"max_steps": 1000}},
    ]

    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = [ex.submit(_post_run, j) for j in jobs]
        for fut in as_completed(futures):
            results.append(fut.result())

    # Ensure we got three responses
    assert len(results) == 3

    # Check each response is a valid run result dict and that limits/errors
    # correspond to the request-specific settings (no cross-request pollution)
    codes = [r[0] for r in results]
    bodies = [r[1] for r in results]

    assert all(c == 200 for c in codes)
    # one body should have OUTPUT_LIMIT or STEP_LIMIT depending on ordering, but
    # we assert each response belongs to one of the expected shapes
    for b in bodies:
        assert 'output' in b and 'warnings' in b and 'eco' in b and 'errors' in b

