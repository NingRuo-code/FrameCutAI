# FrameCutAI

FrameCutAI is a local-first multimodal technical video understanding Agent. The
MVP focuses on a transcript-first, vision-on-demand Workflow for turning
technical videos into traceable documents and current-video QA.

## Local App Shell

This repository currently includes the first runnable shell:

- FastAPI backend with a `/health` endpoint.
- Vue 3 + Vite frontend workspace shell.
- Frontend health check that proves the workspace can talk to the backend.
- Reserved workspace areas for task upload/listing, Agent progress,
  VideoContext debug, source Video, generated document, and QA.

## Run The Backend

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

The backend runs at `http://127.0.0.1:8000`.

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Run The Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at `http://127.0.0.1:5173` and proxies `/api/*` requests to
the backend.

## Verify

Backend tests:

```powershell
cd backend
pytest
```

Frontend typecheck and build:

```powershell
cd frontend
npm run build
```

API examples for upload, analysis, events, documents, VideoContext, QA, eval,
and cleanup are in `docs/api-examples.md`.
