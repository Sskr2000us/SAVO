"""
SAVO Backend API
FastAPI application with Supabase integration
Version: 2026-01-02 - UUID fix deployed
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="SAVO API",
        version="0.1.0",
        description="SAVO backend orchestrator (FastAPI)",
    )

    # Enable CORS for Flutter web app
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins in development
        allow_credentials=True,
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
