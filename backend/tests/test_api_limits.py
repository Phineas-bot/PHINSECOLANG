from fastapi.testclient import TestClient
from backend.app.main import app, interpreter

client = TestClient(app)


def test_api_step_limit_through_run():
    # request settings that would normally allow many steps but server caps them
    # reduce server-side step budget so the run will hit the limit
    interpreter.max_steps = 5
    code = "\n".join(["say 1"] * 1000)
    payload = {"code": code, "settings": {"max_steps": 1000000}}
    r = client.post("/run", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body.get("errors") is not None
    assert body["errors"]["code"] in ("STEP_LIMIT", "TIMEOUT")


def test_api_output_limit_through_run():
    # reduce server-side output cap so the run will hit the limit
    interpreter.max_output_chars = 10
    code = "\n".join(["say \"abcdefghij\""] * 100)
    payload = {"code": code, "settings": {"max_output_chars": 1000000}}
    r = client.post("/run", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body.get("errors") is not None
    assert body["errors"]["code"] == "OUTPUT_LIMIT"
