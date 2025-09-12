# EcoLang Frontend (minimal)

This is a minimal Vite + React frontend for the EcoLang backend used in the
repo. It provides a simple textarea-based editor, a Run button that POSTs to
`/run`, and panes for output, warnings and eco stats.

Quickstart (requires Node.js and npm/yarn/pnpm):

```bash
cd frontend
npm install
npm run dev
```

The dev server will run on <http://localhost:5173> and the frontend expects the
backend API at <http://localhost:8000> by default. You can change the address
using the `VITE_API_BASE` env var when starting Vite.

## Deploy (free): Cloudflare Pages

1) In Cloudflare Pages, create a new project and connect this repo.

2) Build settings:

- Project root: `frontend`
- Build command: `npm ci && npm run build`
- Output directory: `dist`

1) Environment variables (Production):

- `VITE_API_BASE` = `https://<your-render-service>.onrender.com`

1) Deploy. Your Pages URL will host the UI and call the backend via `VITE_API_BASE`.

Tips:

- You can override API URL at runtime via the "API Base URL" field in the UI.
- For production tighten CORS in backend `backend/app/main.py` to your Pages domain.
