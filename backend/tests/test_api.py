"""API integration smoke tests using FastAPI TestClient."""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_ping():
	# Basic run endpoint smoke test
	r = client.post('/run', json={'code': 'say 1', 'inputs': {}})
	assert r.status_code in (200, 400, 422)
