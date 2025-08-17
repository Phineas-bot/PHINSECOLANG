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

The dev server will run on http://localhost:5173 and the frontend expects the
backend API at http://localhost:8000 by default. You can change the address
using the `VITE_API_BASE` env var when starting Vite.
