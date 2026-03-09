"""Review workflow API endpoints.

REVIEW-01: 审核流程后端

Provides endpoints for:
- Listing pending changes
- Submitting changes for review
- Approving/rejecting changes
- Batch approval
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, ReviewerUser
from app.services.review_store import (
    PendingChange,
    approve_change,
    batch_approve,
    delete_change,
    get_change_by_id,
    get_pending_count,
    list_pending_changes,
    reject_change,
    submit_change,
)

router = APIRouter()


class SubmitChangeBody(BaseModel):
    """Request body for submitting a change."""
    document_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    change_type: str = Field(pattern="^(create|update|delete)$")
    before_content: dict[str, Any] | None = None
    after_content: dict[str, Any] | None = None


class ReviewActionBody(BaseModel):
    """Request body for review actions."""
    review_comment: str | None = None


class BatchApproveBody(BaseModel):
    """Request body for batch approval."""
    document_id: str = Field(min_length=1)
    change_ids: list[int] | None = None


def _change_to_response(change: PendingChange) -> dict[str, Any]:
    """Convert PendingChange to API response dict."""
    return {
        "id": change.id,
        "document_id": change.document_id,
        "node_id": change.node_id,
        "change_type": change.change_type,
        "before_content": change.before_content,
        "after_content": change.after_content,
        "submitted_by": change.submitted_by,
        "submitted_at": change.submitted_at,
        "status": change.status,
        "reviewed_by": change.reviewed_by,
        "reviewed_at": change.reviewed_at,
        "review_comment": change.review_comment,
    }


@router.get("/pending")
def get_pending(
    document_id: str | None = None,
    submitted_by: str | None = None,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """List pending changes.

    Args:
        document_id: Filter by document (optional)
        submitted_by: Filter by submitter (optional)
        user: Current user (required)

    Returns:
        List of pending changes and count
    """
    changes = list_pending_changes(
        document_id=document_id,
        status="pending",
        submitted_by=submitted_by,
    )
    return {
        "changes": [_change_to_response(c) for c in changes],
        "count": len(changes),
    }


@router.get("/count")
def get_count(document_id: str, user: CurrentUser = None) -> dict[str, int]:
    """Get count of pending changes for a document.

    Args:
        document_id: Document to count pending changes for
        user: Current user (required)

    Returns:
        Count of pending changes
    """
    count = get_pending_count(document_id)
    return {"count": count}


@router.get("/{change_id}")
def get_change(change_id: int, user: CurrentUser = None) -> dict[str, Any]:
    """Get a specific pending change by ID.

    Args:
        change_id: ID of the change
        user: Current user (required)

    Returns:
        Pending change details

    Raises:
        404: Change not found
    """
    change = get_change_by_id(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="change not found")
    return _change_to_response(change)


@router.post("/submit")
def submit(
    body: SubmitChangeBody,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """Submit a change for review.

    Employees can submit changes for review. The change will be pending
    until a reviewer or admin approves/rejects it.

    Args:
        body: Change details
        user: Current user (required)

    Returns:
        Created pending change

    Raises:
        400: Validation error or duplicate pending change
    """
    try:
        change = submit_change(
            document_id=body.document_id,
            node_id=body.node_id,
            change_type=body.change_type,
            submitted_by=user["id"],
            before_content=body.before_content,
            after_content=body.after_content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _change_to_response(change)


@router.post("/{change_id}/approve")
def approve(
    change_id: int,
    body: ReviewActionBody = None,
    user: ReviewerUser = None,
) -> dict[str, Any]:
    """Approve a pending change.

    Only reviewers and admins can approve changes.

    Args:
        change_id: ID of the change to approve
        body: Optional review comment
        user: Current user (must be reviewer or admin)

    Returns:
        Updated pending change

    Raises:
        404: Change not found or already processed
    """
    comment = body.review_comment if body else None
    change = approve_change(
        change_id=change_id,
        reviewed_by=user["id"],
        review_comment=comment,
    )
    if change is None:
        raise HTTPException(status_code=404, detail="change not found or already processed")
    return _change_to_response(change)


@router.post("/{change_id}/reject")
def reject(
    change_id: int,
    body: ReviewActionBody = None,
    user: ReviewerUser = None,
) -> dict[str, Any]:
    """Reject a pending change.

    Only reviewers and admins can reject changes.

    Args:
        change_id: ID of the change to reject
        body: Optional review comment
        user: Current user (must be reviewer or admin)

    Returns:
        Updated pending change

    Raises:
        404: Change not found or already processed
    """
    comment = body.review_comment if body else None
    change = reject_change(
        change_id=change_id,
        reviewed_by=user["id"],
        review_comment=comment,
    )
    if change is None:
        raise HTTPException(status_code=404, detail="change not found or already processed")
    return _change_to_response(change)


@router.post("/batch-approve")
def batch_approve_endpoint(
    body: BatchApproveBody,
    user: ReviewerUser = None,
) -> dict[str, Any]:
    """Batch approve pending changes.

    Only reviewers and admins can batch approve.

    Args:
        body: Document ID and optional change IDs
        user: Current user (must be reviewer or admin)

    Returns:
        List of approved changes and count
    """
    approved = batch_approve(
        document_id=body.document_id,
        reviewed_by=user["id"],
        change_ids=body.change_ids,
    )
    return {
        "approved": [_change_to_response(c) for c in approved],
        "count": len(approved),
    }


@router.delete("/{change_id}")
def cancel(change_id: int, user: CurrentUser = None) -> dict[str, bool]:
    """Cancel (delete) a pending change.

    The submitter can cancel their own pending change.

    Args:
        change_id: ID of the change to cancel
        user: Current user (required)

    Returns:
        Success status

    Raises:
        403: Not authorized to cancel
        404: Change not found
    """
    change = get_change_by_id(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="change not found")

    # Only submitter or reviewer/admin can cancel
    is_owner = change.submitted_by == user["id"]
    is_reviewer = user.get("role") in ("reviewer", "admin")

    if not is_owner and not is_reviewer:
        raise HTTPException(status_code=403, detail="not authorized to cancel")

    success = delete_change(change_id)
    return {"ok": success}
