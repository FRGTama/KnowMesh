from fastapi import APIRouter

from backend.app.api.health import router as health_router
from backend.app.api.providers import router as providers_router
from backend.app.api.rag import router as rag_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(providers_router)
api_router.include_router(rag_router)
