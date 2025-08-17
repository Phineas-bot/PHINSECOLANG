import os
from fastapi.testclient import TestClient


def test_api_run_save_and_stats(tmp_path, monkeypatch):
    # point the app at a temporary sqlite file before importing the app
    db_file = tmp_path / "ecolang_test.db"
    monkeypatch.setenv("ECOLANG_DB_PATH", str(db_file))

    # import app after setting env so db module picks up the override
    from backend.app.main import app

    with TestClient(app) as client:
        # basic run
        r = client.post("/run", json={"code": 'say "hello"'})
        assert r.status_code == 200
        body = r.json()
        assert "hello" in body.get("output", "")
        assert body.get("errors") is None

        # save a script
        r2 = client.post(
            "/save",
            json={"title": "script1", "code": 'say "saved"', "eco_stats": None},
        )
        assert r2.status_code == 200
        data = r2.json()
        assert "script_id" in data
        sid = data["script_id"]

        # list scripts
        lst = client.get("/scripts")
        assert lst.status_code == 200
        scripts = lst.json()
        assert any(s.get("script_id") == sid for s in scripts)

        # get script by id
        one = client.get(f"/scripts/{sid}")
        assert one.status_code == 200
        s = one.json()
        assert s.get("script_id") == sid

        # run with script_id to persist a run
        r3 = client.post("/run", json={"code": 'say "runpersist"', "script_id": sid})
        assert r3.status_code == 200
        body3 = r3.json()
        assert body3.get("errors") is None

        # stats for script should include at least one entry
        stats = client.get(f"/stats?script_id={sid}")
        assert stats.status_code == 200
        runs = stats.json()
        assert isinstance(runs, list)
        assert len(runs) >= 1
