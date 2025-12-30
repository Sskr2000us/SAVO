from fastapi import APIRouter

from app.api.routes.config import router as config_router
from app.api.routes.cuisines import router as cuisines_router
from app.api.routes.history import router as history_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.planning import router as planning_router
from app.api.routes.youtube import router as youtube_router
from app.api.routes.youtube_search import router as youtube_search_router
from app.api.routes.training import router as training_router
from app.api.routes.recipes import router as recipes_router

api_router = APIRouter()

api_router.include_router(config_router, tags=["config"])
api_router.include_router(cuisines_router, tags=["cuisines"])
api_router.include_router(history_router, prefix="/history", tags=["history"])
api_router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])
api_router.include_router(planning_router, prefix="/plan", tags=["planning"])
api_router.include_router(youtube_router, prefix="/youtube", tags=["youtube"])
api_router.include_router(youtube_search_router, prefix="/youtube", tags=["youtube"])
api_router.include_router(training_router, prefix="/training", tags=["training"])
api_router.include_router(recipes_router, prefix="/recipes", tags=["recipes"])
