# Deploying the EcoLang Backend to Railway

This guide walks you through deploying the FastAPI backend on Railway using your existing repository. It’s tailored to this repo’s structure (backend code under `backend/`).

## Prerequisites

- GitHub repository connected (this repo) and a Railway account.
- The backend lives at `backend/app/main.py` and dependencies at `backend/requirements.txt`.

## 1) Create a Railway project and service

1. Sign in to Railway and click “New Project”.
2. Choose “Deploy from GitHub repo” and select this repository.
3. When the service is created, open the service “Settings”.

Important: Since your Python files and requirements are in the `backend/` subfolder, configure Railway accordingly:

- Root Directory: set to `.` (repo root). We’ll override the build command.
- Build Command: `pip install --upgrade pip && pip install -r backend/requirements.txt`
- Start Command: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`

This uses Railway’s Python environment (Nixpacks) and points Uvicorn to the FastAPI app at the correct import path.

## 2) Configure environment variables (secrets)

In the service “Variables” tab, add:

- `ECOLANG_JWT_SECRET`: a long random string.
- `ECOLANG_JWT_EXP_MIN`: optional, token lifetime in minutes (default 120).
- `ECOLANG_DB_PATH`: path to the SQLite file. Set this to `/data/ecolang.db` after adding a volume (next step).

Optional (leave defaults if unsure):

- `ECOLANG_IDLE_POWER_W`, `ECOLANG_CO2_PER_KWH_G`, etc., if you later expose such tunables.

## 3) Add a persistent volume for SQLite

By default, container filesystems are ephemeral. To persist your SQLite DB between deploys:

1. Go to the service “Storage” tab and “Add Volume”.
2. Mount Path: `/data` (recommended). Choose a size (e.g., 1–5 GB is plenty).
3. Save. Ensure the variable `ECOLANG_DB_PATH=/data/ecolang.db` is present.

The backend reads `ECOLANG_DB_PATH`; otherwise it falls back to the bundled db file which will not persist.

## 4) Expose the web service

- Railway automatically assigns a `PORT` and exposes HTTP. The Start Command binds to `0.0.0.0:$PORT`.
- No extra port config is required.

Health check

- FastAPI serves docs at `/docs`. You can set the Railway health check path to `/docs` (HTTP 200), or leave the default.

## 5) Deploy

- Click “Deploy”.
- Watch logs in the “Deployments” or “Logs” tab to confirm:
  - Database initialized (on first start).
  - Uvicorn running and listening on `0.0.0.0:$PORT`.

When live, Railway shows a public URL like `https://your-service.up.railway.app`.

## 6) Verify the API

Use your browser or curl to verify key endpoints.

- Docs: visit `https://your-service.up.railway.app/docs`.
- Run a simple program:

```bash
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{"code":"say \"Hello Eco\"\n","inputs":{}}' \
  https://your-service.up.railway.app/run | jq
```

- Register/login and save a script (replace USER/PASS):

```bash
TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
  -d '{"username":"USER","password":"PASS"}' \
  https://your-service.up.railway.app/auth/register | jq -r .access_token)

curl -s -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"My Script","code":"say \"Hi\"\n"}' \
  https://your-service.up.railway.app/save | jq
```

## 7) Connect the frontend

In the frontend app, set the API Base URL to your Railway URL:

- In the UI, enter the API as `https://your-service.up.railway.app`.
- Or, when running Vite locally, start with:

```powershell
$env:VITE_API_BASE = 'https://your-service.up.railway.app'; npm run dev
```

## Alternative: Dockerfile (optional)

If you prefer a pinned runtime, you can add a `Dockerfile` at repo root and let Railway build from it. Example:

```Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1 \
    ECOLANG_DB_PATH=/data/ecolang.db
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Then in Railway:

- Deployment method: Dockerfile
- Start Command: leave empty (Docker CMD used). Railway will still map `$PORT`; either adapt the image to honor `$PORT` or configure a Start Command that sets `--port $PORT`.

## Recommended Railway setup (Root Directory = backend)

If you prefer a simpler configuration that doesn’t rely on a Procfile or custom env overrides, set your service to use the backend subfolder directly:

- Root Directory: `backend`
- Build Command: `pip install --upgrade pip && pip install -r requirements.txt`
- Start Command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Notes

- Service type must be a Web Service (not Static).
- If you changed the directory or commands, click “Redeploy”.
- With this setup, you do NOT need a Procfile.
- For persistence, add a Volume at `/data` and set `ECOLANG_DB_PATH=/data/ecolang.db`.

## Troubleshooting

- Module import error `backend.app.main:app`:
  - Ensure Start Command matches exactly and you’re at repo root (so `backend/` is on PYTHONPATH).
- Missing packages:
  - Confirm Build Command installs `-r backend/requirements.txt` and the file includes `uvicorn`, `fastapi`, etc.
- 403/401 on scripts/stats:
  - Endpoints require a valid Bearer token; register/login first and include `Authorization: Bearer <token>`.
- DB not persisting:
  - Add a Volume and set `ECOLANG_DB_PATH=/data/ecolang.db`.
- CORS issues from the browser:
  - For production, replace permissive `allow_origins=["*"]` with your frontend origin(s). Until then, ensure you’re calling the correct URL.
- Railway start command issues:
  - If Railway reports “No start command was found”, add a Procfile at the repo root:
  
  ```procfile
  web: python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
  ```
  
  Or set the Start Command explicitly in the service Settings.

## Security hardening checklist (post-deploy)

- Rotate `ECOLANG_JWT_SECRET` and store as a Railway Secret.
- Restrict CORS to your frontend origin(s).
- Consider rate limiting and basic request logging.
- Regularly back up `/data/ecolang.db` (download from Railway Volume or migrate to Postgres).

You’re set—your backend is live on Railway and ready for the frontend to use. ✅
