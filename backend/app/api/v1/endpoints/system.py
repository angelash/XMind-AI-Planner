from fastapi import APIRouter

from app.core.exceptions import AppError

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}


@router.get("/boom")
def boom() -> None:
    raise AppError(code="demo_error", message="Demo failure", status_code=418)
