from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_api_step_limit_through_run():
    # use explicit small caps passed in settings so test doesn't rely on server state
    code = "\n".join(["say 1"] * 1000)
    payload = {"code": code, "settings": {"max_steps": 5}}
    r = client.post("/run", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body.get("errors") is not None
    assert body["errors"]["code"] in ("STEP_LIMIT", "TIMEOUT")


def test_api_output_limit_through_run():
    # pass explicit small output cap
    code = "\n".join(["say \"abcdefghij\""] * 100)
    payload = {"code": code, "settings": {"max_output_chars": 10}}
    r = client.post("/run", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body.get("errors") is not None
    assert body["errors"]["code"] == "OUTPUT_LIMIT"


