"""Development task queue API endpoints.

AUTO-01: 自动化任务队列状态机
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import dev_task_store

router = APIRouter()


class CreateTaskRequest(BaseModel):
    requirement: str
    workspace_id: str | None = None
    document_id: str | None = None
    trigger_type: str | None = None
    trigger_node_id: str | None = None


class UpdateTaskStatusRequest(BaseModel):
    status: str
    analysis_result: dict | None = None
    coding_result: dict | None = None
    diff_summary: str | None = None
    sync_result: dict | None = None
    build_result: dict | None = None
    error_message: str | None = None
    need_confirm_reason: str | None = None


class CreateArtifactRequest(BaseModel):
    artifact_type: str
    file_path: str
    content: str | None = None


@router.get("")
def list_tasks(
    workspace_id: str | None = None,
    document_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict:
    """List development tasks."""
    tasks = dev_task_store.list_dev_tasks(
        workspace_id=workspace_id,
        document_id=document_id,
        status=status,
        limit=limit,
    )
    return {"items": tasks}


@router.post("", status_code=201)
def create_task(req: CreateTaskRequest) -> dict:
    """Create a new development task."""
    return dev_task_store.create_dev_task(
        requirement=req.requirement,
        workspace_id=req.workspace_id,
        document_id=req.document_id,
        trigger_type=req.trigger_type,
        trigger_node_id=req.trigger_node_id,
    )


@router.get("/next")
def get_next_task() -> dict | None:
    """Get the next waiting task (FIFO)."""
    task = dev_task_store.get_next_waiting_task()
    return task


@router.get("/{task_id}")
def get_task(task_id: str) -> dict:
    """Get a single task by ID."""
    task = dev_task_store.get_dev_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.patch("/{task_id}/status")
def update_task_status(task_id: str, req: UpdateTaskStatusRequest) -> dict:
    """Update task status with validation."""
    try:
        task = dev_task_store.update_dev_task_status(
            task_id,
            req.status,
            analysis_result=req.analysis_result,
            coding_result=req.coding_result,
            diff_summary=req.diff_summary,
            sync_result=req.sync_result,
            build_result=req.build_result,
            error_message=req.error_message,
            need_confirm_reason=req.need_confirm_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str) -> dict:
    """Cancel a task."""
    try:
        task = dev_task_store.cancel_dev_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/{task_id}/retry")
def retry_task(task_id: str) -> dict:
    """Retry a failed task."""
    try:
        task = dev_task_store.retry_dev_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/{task_id}/confirm")
def confirm_task(task_id: str) -> dict:
    """Confirm a task that needs confirmation."""
    try:
        task = dev_task_store.confirm_dev_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


# Artifact endpoints

@router.get("/{task_id}/artifacts")
def list_artifacts(task_id: str, artifact_type: str | None = None) -> dict:
    """List artifacts for a task."""
    artifacts = dev_task_store.list_task_artifacts(task_id, artifact_type)
    return {"items": artifacts}


@router.post("/{task_id}/artifacts", status_code=201)
def create_artifact(task_id: str, req: CreateArtifactRequest) -> dict:
    """Create an artifact for a task."""
    return dev_task_store.create_task_artifact(
        task_id=task_id,
        artifact_type=req.artifact_type,
        file_path=req.file_path,
        content=req.content,
    )


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: int) -> dict:
    """Get a single artifact by ID."""
    artifact = dev_task_store.get_task_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return artifact
