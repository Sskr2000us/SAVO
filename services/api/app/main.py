"""
SAVO Backend API
FastAPI application with Supabase integration
Version: 2026-01-02 - UUID fix deployed
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
import os
import re

from app.api.router import api_router
from app.core.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="SAVO API",
        version="0.1.0",
        description="SAVO backend orchestrator (FastAPI)",
    )

    # Enable CORS for browser clients (Flutter web / Vercel)
    # NOTE: Using allow_credentials=True with allow_origins=['*'] is rejected by browsers.
    cors_env = (os.getenv("CORS_ALLOWED_ORIGIN") or "").strip()
    cors_origin_regex_env = (os.getenv("CORS_ALLOWED_ORIGIN_REGEX") or "").strip()
    if cors_env:
        cors_origins = [o.strip().rstrip("/") for o in cors_env.split(",") if o.strip()]
    else:
        # Safe defaults for common deployments.
        cors_origins = [
            "https://savo-web.vercel.app",
            "http://localhost:3000",
            "http://localhost:5173",
        ]

    # Allow Vercel preview deployments by regex (e.g., savo-web-git-branch-xyz.vercel.app)
    # This complements explicit allow_origins and helps avoid origin mismatch CORS blocks.
    cors_origin_regex: str | None = None
    if cors_origin_regex_env:
        cors_origin_regex = cors_origin_regex_env
    else:
        cors_origin_regex = r"^https://savo-web(?:-[a-z0-9-]+)?\.vercel\.app$"

    # Validate regex early; if invalid, disable rather than crashing.
    try:
        re.compile(cors_origin_regex)
    except Exception:
        cors_origin_regex = None

    # Some browser clients (including some Flutter web configurations) use fetch credentials.
    # Support credentials when origins are explicit; fall back to non-credentialed wildcard mode.
    allow_credentials = False
    if cors_origins and cors_origins != ["*"]:
        allow_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=cors_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, OPTIONS)
        allow_headers=["*"],  # Allow all headers
    )

    # Add exception handler to ensure CORS headers are included in error responses
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        origin = request.headers.get("origin")
        headers = {}
        
        # Add CORS headers to error responses
        if origin:
            # Check if origin is allowed
            allowed = False
            if origin in cors_origins:
                allowed = True
            elif cors_origin_regex:
                try:
                    if re.match(cors_origin_regex, origin):
                        allowed = True
                except Exception:
                    pass
            
            if allowed:
                headers["Access-Control-Allow-Origin"] = origin
                if allow_credentials:
                    headers["Access-Control-Allow-Credentials"] = "true"
        
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )

    app.include_router(api_router)

    @app.get("/")
    def root():
        return {
            "name": "SAVO API",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
            "health": "/health"
        }

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "llm_provider": settings.llm_provider,  # Legacy
            "reasoning_provider": settings.reasoning_provider,
            "vision_provider": settings.vision_provider,
            "cors": {
                "allow_origins": cors_origins,
                "allow_origin_regex": cors_origin_regex,
                "allow_credentials": allow_credentials,
            },
            "build": {
                "git_commit": os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT"),
                "service_id": os.getenv("RENDER_SERVICE_ID"),
            },
        }

    return app


app = create_app()
