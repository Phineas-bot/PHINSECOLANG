import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    # create a temporary DB file for isolation
    fd, path = tempfile.mkstemp(prefix="ecolang_test_", suffix=".db")
    os.close(fd)
    os.environ['ECOLANG_DB_PATH'] = path
    # re-import / init DB
    db.init_db()
    client = TestClient(app)
    yield client
    try:
        client.close()
    except Exception:
        pass
    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass


def test_save_and_run_and_stats(client):
    # save a simple script
    save_resp = client.post('/save', json={'title': 't1', 'code': 'say("hello")'})
    assert save_resp.status_code == 200
    data = save_resp.json()
    assert 'script_id' in data

    # list scripts
    scripts_resp = client.get('/scripts')
    assert scripts_resp.status_code == 200
    assert isinstance(scripts_resp.json(), list)

    # run code via /run
    run_resp = client.post('/run', json={'code': 'say("hi")', 'inputs': {}})
    assert run_resp.status_code == 200
    rdata = run_resp.json()
    assert 'output' in rdata

    # stats
    stats_resp = client.get('/stats')
    assert stats_resp.status_code == 200
    assert isinstance(stats_resp.json(), list)
