# SAVO API (FastAPI)

This is the modular-monolith backend for SAVO (mobile-only MVP).

## What’s included
- Orchestrator-style endpoints (`/plan/*`, `/inventory/*`)
- Prompt-pack loader wired to `docs/spec/prompt-pack.gpt-5.2.json`
- JSON Schema validation (fail-closed)
- Mock LLM mode for local development (no API key required)

## Quickstart (Windows PowerShell)
```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SAVO_LLM_PROVIDER="mock"
uvicorn app.main:app --reload --port 8000
```

## Endpoints
- `GET /health`
- `POST /inventory/normalize`
- `POST /plan/daily`
- `POST /plan/party`
- `POST /plan/weekly`
- `POST /youtube/rank`

## Environment variables
See `.env.example`.
