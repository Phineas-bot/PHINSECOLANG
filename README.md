# PHINSECOLANG

## Quick start (run server)

From the repository root on Windows (PowerShell):

```powershell
# create venv (one-time)
py -3.12 -m venv .venv

# activate the venv
.\.venv\Scripts\Activate.ps1

# install requirements (one-time)
pip install -r backend\requirements.txt

# start the server
python -m uvicorn backend.app.main:app --reload --port 8000

# then open http://127.0.0.1:8000 in your browser or call the endpoints
```

Run tests:

```powershell
pytest -q
```

Notes:
- The project includes two virtual environments in development (`.venv` for Python 3.12 with FastAPI v0.100/pydantic v2 and `.venv-1` with older pins). Use `.venv` for the latest API compatibility.
# PHINSECOLANG

![CI](https://github.com/Phineas-bot/PHINSECOLANG/actions/workflows/ci.yml/badge.svg)

Local developer setup (pre-commit):

```powershell
# install pre-commit in your venv
pip install pre-commit
pre-commit install
pre-commit run --all-files
```