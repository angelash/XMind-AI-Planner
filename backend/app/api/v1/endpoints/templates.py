"""
Templates API endpoints (GAP-08)

Templates allow users to save and reuse mind map structures as templates.
Templates can be:
- Personal (only visible to owner)
- Public (visible to all users)

Templates include:
- Title and description
- Mind map content (JSON)
- Category and tags for organization
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import sqlite3

from ..deps import get_db

router = APIRouter(prefix="/templates", tags=["templates"])


# Pydantic models
class TemplateCreate(BaseModel):
    title: str
    description: Optional[str] = None
    content_json: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: bool = False


class TemplateUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content_json: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    content_json: str
    category: Optional[str]
    tags: List[str]
    owner_id: Optional[str]
    is_public: bool
    created_at: str
    updated_at: str


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    public_only: bool = False,
    db: sqlite3.Connection = Depends(get_db)
):
    """List all templates with optional filtering."""
    user_id = None  # TODO: Get from auth context

    query = "SELECT * FROM templates WHERE 1=1"
    params = []

    if public_only:
        query += " AND is_public = 1"
    else:
        # Show public templates + user's own templates
        query += " AND (is_public = 1 OR owner_id = ?)"
        params.append(user_id)

    if category:
        query += " AND category = ?"
        params.append(category)

    # Note: tag filtering would require JSON extraction, simplified here
    if tag:
        query += " AND tags LIKE ?"
        params.append(f'%"{tag}"%')

    query += " ORDER BY created_at DESC"

    cursor = db.execute(query, params)
    rows = cursor.fetchall()

    templates = []
    for row in rows:
        template = {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "content_json": row[3],
            "category": row[4],
            "tags": json.loads(row[5]) if row[5] else [],
            "owner_id": row[6],
            "is_public": bool(row[7]),
            "created_at": row[8],
            "updated_at": row[9]
        }
        templates.append(TemplateResponse(**template))

    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: sqlite3.Connection = Depends(get_db)
):
    """Get a single template by ID."""
    user_id = None  # TODO: Get from auth context

    cursor = db.execute(
        "SELECT * FROM templates WHERE id = ?",
        (template_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    # Check permission
    if not row[7] and row[6] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    template = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "content_json": row[3],
        "category": row[4],
        "tags": json.loads(row[5]) if row[5] else [],
        "owner_id": row[6],
        "is_public": bool(row[7]),
        "created_at": row[8],
        "updated_at": row[9]
    }

    return TemplateResponse(**template)


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template: TemplateCreate,
    db: sqlite3.Connection = Depends(get_db)
):
    """Create a new template."""
    import uuid

    template_id = str(uuid.uuid4())
    user_id = None  # TODO: Get from auth context

    now = datetime.utcnow().isoformat()

    db.execute(
        """INSERT INTO templates
        (id, title, description, content_json, category, tags, owner_id, is_public, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            template_id,
            template.title,
            template.description,
            template.content_json,
            template.category,
            json.dumps(template.tags) if template.tags else None,
            user_id,
            1 if template.is_public else 0,
            now,
            now
        )
    )
    db.commit()

    cursor = db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    row = cursor.fetchone()

    template_response = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "content_json": row[3],
        "category": row[4],
        "tags": json.loads(row[5]) if row[5] else [],
        "owner_id": row[6],
        "is_public": bool(row[7]),
        "created_at": row[8],
        "updated_at": row[9]
    }

    return TemplateResponse(**template_response)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template: TemplateUpdate,
    db: sqlite3.Connection = Depends(get_db)
):
    """Update an existing template."""
    user_id = None  # TODO: Get from auth context

    # Check ownership
    cursor = db.execute(
        "SELECT owner_id FROM templates WHERE id = ?",
        (template_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    if row[0] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Build update query dynamically
    update_fields = []
    update_values = []

    if template.title is not None:
        update_fields.append("title = ?")
        update_values.append(template.title)

    if template.description is not None:
        update_fields.append("description = ?")
        update_values.append(template.description)

    if template.content_json is not None:
        update_fields.append("content_json = ?")
        update_values.append(template.content_json)

    if template.category is not None:
        update_fields.append("category = ?")
        update_values.append(template.category)

    if template.tags is not None:
        update_fields.append("tags = ?")
        update_values.append(json.dumps(template.tags))

    if template.is_public is not None:
        update_fields.append("is_public = ?")
        update_values.append(1 if template.is_public else 0)

    if update_fields:
        update_fields.append("updated_at = ?")
        update_values.append(datetime.utcnow().isoformat())
        update_values.append(template_id)

        query = f"UPDATE templates SET {', '.join(update_fields)} WHERE id = ?"
        db.execute(query, update_values)
        db.commit()

    # Fetch updated template
    cursor = db.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    row = cursor.fetchone()

    template_response = {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "content_json": row[3],
        "category": row[4],
        "tags": json.loads(row[5]) if row[5] else [],
        "owner_id": row[6],
        "is_public": bool(row[7]),
        "created_at": row[8],
        "updated_at": row[9]
    }

    return TemplateResponse(**template_response)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    db: sqlite3.Connection = Depends(get_db)
):
    """Delete a template."""
    user_id = None  # TODO: Get from auth context

    # Check ownership
    cursor = db.execute(
        "SELECT owner_id FROM templates WHERE id = ?",
        (template_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )

    if row[0] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    db.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    db.commit()

    return None
