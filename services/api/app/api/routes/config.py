"""
Configuration endpoints - GET/PUT /config
"""
from fastapi import APIRouter, HTTPException
from app.models.config import AppConfiguration
from app.core.storage import get_storage

router = APIRouter()


@router.get("/config", response_model=AppConfiguration)
async def get_config():
    """Get current application configuration"""
    storage = get_storage()
    return storage.get_config()


@router.put("/config", response_model=AppConfiguration)
async def update_config(config: AppConfiguration):
    """Update application configuration"""
    storage = get_storage()
    return storage.set_config(config)
