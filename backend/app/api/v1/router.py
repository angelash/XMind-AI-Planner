from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.export import router as export_router
from app.api.v1.endpoints.system import router as system_router

router = APIRouter()
router.include_router(system_router, prefix='/system', tags=['system'])
router.include_router(ai_router, prefix='/ai', tags=['ai'])
router.include_router(export_router, prefix='/export', tags=['export'])
