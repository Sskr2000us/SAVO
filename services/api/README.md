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

### Dual-Provider Architecture (Recommended)

SAVO uses a **dual-provider system** for optimal performance:

**Vision Tasks** (Image Scanning)
- `SAVO_VISION_PROVIDER=google` - Google Gemini Vision excels at image understanding
- `GOOGLE_API_KEY` - Required for vision tasks
- `GOOGLE_MODEL` - Optional, defaults to `gemini-2.5-flash`

**Reasoning Tasks** (Planning, Recipes, YouTube Ranking)
- `SAVO_REASONING_PROVIDER=openai` - OpenAI GPT excels at structured JSON outputs
- `OPENAI_API_KEY` - Required for reasoning tasks
- `OPENAI_MODEL` - Optional, defaults to `gpt-4-turbo-preview`

### Why Dual-Provider?

1. **Google Gemini Vision** - Best-in-class image detection for pantry/fridge scanning
2. **OpenAI GPT** - Superior structured JSON outputs for meal plans, recipes, constraints
3. **Cost Optimization** - Use each provider's strengths, avoid expensive vision API calls for text tasks
4. **Quality** - Consistent reasoning engine for all planning logic

### Legacy Mode (Single Provider)

For backward compatibility, you can still use a single provider:

```powershell
$env:SAVO_LLM_PROVIDER="google"  # or "openai", "anthropic", "mock"
```

If `SAVO_REASONING_PROVIDER` is not set, it falls back to `SAVO_LLM_PROVIDER`.

### Full Environment Variables

See `.env.example` or [render.yaml](../../render.yaml) for complete configuration.
