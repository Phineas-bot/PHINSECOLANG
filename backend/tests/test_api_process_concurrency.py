import os
import multiprocessing
import time
import string
import random
try:
    import requests
except Exception:
    import pytest as _pytest
    _pytest.skip("requests not installed; skipping process-level concurrency test", allow_module_level=True)
import pytest


def _start_server(port: int):
    # run uvicorn in this process hosting the FastAPI app
    import uvicorn
    from backend.app import main

    # uvicorn.run is blocking; run in this process so other processes can use HTTP
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")


def _worker(port: int, n_requests: int, q: multiprocessing.Queue, seed: int):
    random.seed(seed)
    sess = requests.Session()
    for _ in range(n_requests):
        kind = random.choice(["say", "repeat", "let"])
        if kind == "say":
            times = random.randint(1, 50)
            code = "\n".join([
                'say "' + ''.join(random.choices(string.ascii_letters, k=8)) + '"'
                for _ in range(times)
            ])
            settings = {"max_output_chars": 2000}
        elif kind == "repeat":
            times = random.randint(1, 200)
            code = f"repeat {times} times\nsay 1\nend"
            settings = {"max_steps": 5000}
        else:
            code = "let a = 1\nsay a"
            settings = {}
        try:
            r = sess.post(f"http://127.0.0.1:{port}/run", json={"code": code, "settings": settings}, timeout=10)
            q.put((r.status_code, r.json()))
        except Exception as e:
            q.put(("ERR", str(e)))


@pytest.mark.stress
def test_process_level_concurrency_stress():
    # start a real HTTP server in a separate process to exercise process boundaries
    # Allow CI or local runners to tune these via env vars
    port = int(os.getenv("ECOLANG_STRESS_PORT", "8001"))
    server = multiprocessing.Process(target=_start_server, args=(port,), daemon=True)
    server.start()

    # wait for server to be ready
    ready = False
    for _ in range(80):
        try:
            r = requests.get(f"http://127.0.0.1:{port}/docs", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.125)
    if not ready:
        server.terminate()
        pytest.skip("uvicorn server failed to start")

    n_workers = int(os.getenv("ECOLANG_STRESS_WORKERS", "8"))
    n_requests_per_worker = int(os.getenv("ECOLANG_STRESS_REQS_PER_WORKER", "10"))
    q: multiprocessing.Queue = multiprocessing.Queue()
    workers = [
        multiprocessing.Process(target=_worker, args=(port, n_requests_per_worker, q, i))
        for i in range(n_workers)
    ]

    for w in workers:
        w.start()

    # wait for workers to finish
    for w in workers:
        w.join(timeout=30)

    # gather results
    results = []
    while not q.empty():
        results.append(q.get())

    # stop server
    server.terminate()
    server.join(timeout=5)

    expected = n_workers * n_requests_per_worker
    assert len(results) == expected, f"expected {expected} results, got {len(results)}"

    # basic validation: all responses should be HTTP 200 with the run result shape
    for status, body in results:
        assert status == 200, f"bad status: {status}"
        assert isinstance(body, dict)
        assert "output" in body and "warnings" in body and "eco" in body and "errors" in body
