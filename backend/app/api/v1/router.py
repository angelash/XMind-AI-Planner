from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.export import router as export_router
from app.api.v1.endpoints.imports import router as imports_router
from app.api.v1.endpoints.shares import router as shares_router
from app.api.v1.endpoints.system import router as system_router

router = APIRouter()
router.include_router(system_router, prefix='/system', tags=['system'])
router.include_router(ai_router, prefix='/ai', tags=['ai'])
router.include_router(export_router, prefix='/export', tags=['export'])
router.include_router(imports_router, prefix='/import', tags=['import'])
router.include_router(documents_router, prefix='/documents', tags=['documents'])
router.include_router(shares_router, tags=['shares'])
