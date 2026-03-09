from fastapi import APIRouter

from app.api.v1.endpoints.ai import router as ai_router
from app.api.v1.endpoints.artifacts import router as artifacts_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.conversations import router as conversations_router
from app.api.v1.endpoints.dev_tasks import router as dev_tasks_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.export import router as export_router
from app.api.v1.endpoints.imports import router as imports_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.review import router as review_router
from app.api.v1.endpoints.shares import router as shares_router
from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.websocket import router as websocket_router
from app.api.v1.endpoints.workspace import router as workspace_router

router = APIRouter()
router.include_router(system_router, prefix='/system', tags=['system'])
router.include_router(auth_router, prefix='/auth', tags=['auth'])
router.include_router(users_router, prefix='/users', tags=['users'])
router.include_router(ai_router, prefix='/ai', tags=['ai'])
router.include_router(export_router, prefix='/export', tags=['export'])
router.include_router(imports_router, prefix='/import', tags=['import'])
router.include_router(documents_router, prefix='/documents', tags=['documents'])
router.include_router(shares_router, tags=['shares'])
router.include_router(workspace_router, prefix='/workspace', tags=['workspace'])
router.include_router(projects_router, prefix='/projects', tags=['projects'])
router.include_router(review_router, prefix='/review', tags=['review'])
router.include_router(websocket_router, tags=['websocket'])
router.include_router(conversations_router, prefix='/conversations', tags=['conversations'])
router.include_router(dev_tasks_router, prefix='/dev-tasks', tags=['dev-tasks'])
router.include_router(artifacts_router, prefix='/artifacts', tags=['artifacts'])
