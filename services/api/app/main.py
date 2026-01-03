"""
SAVO Backend API
FastAPI application with Supabase integration
Version: 2026-01-02 - UUID fix deployed
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

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
    cors_origins = [o.strip().rstrip("/") for o in cors_env.split(",") if o.strip()] if cors_env else ["*"]

    # Some browser clients (including some Flutter web configurations) use fetch credentials.
    # Support credentials when origins are explicit; fall back to non-credentialed wildcard mode.
    allow_credentials = False
    if cors_origins and cors_origins != ["*"]:
        allow_credentials = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, OPTIONS)
        allow_headers=["*"],  # Allow all headers
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
            "vision_provider": settings.vision_provider
        }

    return app


app = create_app()
