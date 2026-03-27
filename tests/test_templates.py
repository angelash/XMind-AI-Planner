"""
Tests for Templates (GAP-08)

Template library should provide:
- Database table for storing templates
- API endpoints for CRUD operations
- Frontend UI for browsing and managing templates
- Ability to create documents from templates
"""

from pathlib import Path


def test_templates_database_migration_exists() -> None:
    """Templates migration file should exist."""
    root = Path(__file__).resolve().parents[1]
    migration = root / "backend" / "app" / "db" / "migrations" / "0013_templates.sql"
    assert migration.exists()

    content = migration.read_text(encoding="utf-8")

    # Table creation
    assert "CREATE TABLE IF NOT EXISTS templates" in content

    # Required columns
    assert "id TEXT PRIMARY KEY" in content
    assert "title TEXT NOT NULL" in content
    assert "content_json TEXT NOT NULL" in content
    assert "category TEXT" in content
    assert "tags TEXT" in content
    assert "owner_id TEXT" in content
    assert "is_public INTEGER NOT NULL DEFAULT 0" in content

    # Indexes
    assert "CREATE INDEX" in content
    assert "idx_templates_category" in content
    assert "idx_templates_public" in content


def test_templates_api_endpoints_file_exists() -> None:
    """Templates API endpoints module should exist."""
    root = Path(__file__).resolve().parents[1]
    templates_api = root / "backend" / "app" / "api" / "v1" / "endpoints" / "templates.py"
    assert templates_api.exists()

    content = templates_api.read_text(encoding="utf-8")

    # Router setup
    assert "APIRouter" in content
    assert "prefix=\"/templates\"" in content

    # Required endpoints
    assert "@router.get(" in content  # List templates
    assert "@router.get" in content  # Get single template
    assert "@router.post" in content  # Create template
    assert "@router.put" in content  # Update template
    assert "@router.delete" in content  # Delete template

    # Pydantic models
    assert "class TemplateCreate" in content
    assert "class TemplateUpdate" in content
    assert "class TemplateResponse" in content


def test_templates_api_registered_in_router() -> None:
    """Templates API should be registered in the v1 router."""
    root = Path(__file__).resolve().parents[1]
    router = root / "backend" / "app" / "api" / "v1" / "router.py"
    assert router.exists()

    content = router.read_text(encoding="utf-8")

    # Import templates router
    assert "from app.api.v1.endpoints.templates import router as templates_router" in content

    # Register templates router
    assert "templates_router" in content
    assert "tags=['templates']" in content


def test_templates_frontend_module_exists() -> None:
    """Templates JavaScript module should exist."""
    root = Path(__file__).resolve().parents[1]
    templates_js = root / "frontend" / "src" / "templates.js"
    assert templates_js.exists()

    content = templates_js.read_text(encoding="utf-8")

    # Core functions
    assert "initTemplates" in content
    assert "loadTemplates" in content
    assert "renderTemplateList" in content
    assert "showCreateTemplateModal" in content
    assert "createTemplate" in content
    assert "useTemplate" in content
    assert "deleteTemplate" in content

    # API calls
    assert "fetch('/api/v1/templates')" in content
    assert "fetch(`/api/v1/templates/" in content or "fetch('/api/v1/templates/" in content

    # Module export
    assert "window.TemplateModule" in content


def test_templates_ui_in_html() -> None:
    """Template library UI should be present in index.html."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")

    # Template library modal
    assert 'id="template-modal"' in html
    assert "模板库" in html

    # Template list container
    assert 'id="template-list"' in html

    # Create template button
    assert 'id="btn-create-template"' in html

    # Create template modal
    assert 'id="template-create-modal"' in html
    assert 'id="template-title-input"' in html
    assert 'id="template-description-input"' in html
    assert 'id="template-category-input"' in html
    assert 'id="template-tags-input"' in html
    assert 'id="template-public-check"' in html

    # Templates script module
    assert 'src="./src/templates.js"' in html


def test_templates_css_styles_exist() -> None:
    """Template library styles should be present."""
    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

    # Modal styles
    assert ".modal" in css
    assert ".modal-content" in css
    assert ".modal-header" in css
    assert ".modal-body" in css

    # Template-specific styles
    assert ".template-list" in css
    assert ".template-card" in css
    assert ".template-grid" in css
    assert ".template-category" in css
    assert ".template-title" in css
    assert ".template-description" in css
    assert ".template-tags" in css
    assert ".template-actions" in css

    # Template toolbar and filters
    assert ".template-toolbar" in css
    assert ".template-filter" in css


def test_template_create_form_structure() -> None:
    """Template create form should have all required fields."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")

    # Form structure
    assert 'id="template-create-form"' in html

    # Required fields
    assert 'id="template-title-input"' in html
    assert 'type="text"' in html
    assert 'required' in html

    # Optional fields
    assert 'id="template-description-input"' in html
    assert 'id="template-category-input"' in html
    assert 'id="template-tags-input"' in html

    # Public checkbox
    assert 'id="template-public-check"' in html
    assert 'type="checkbox"' in html

    # Submit and cancel buttons
    assert 'type="submit"' in html
    assert 'id="btn-cancel-create-template"' in html


def test_template_use_functionality() -> None:
    """Template usage flow should be implemented."""
    root = Path(__file__).resolve().parents[1]
    templates_js = root / "frontend" / "src" / "templates.js"
    content = templates_js.read_text(encoding="utf-8")

    # Get template
    assert "fetch(`/api/v1/templates/${templateId}`)" in content

    # Create new document
    assert "fetch('/api/v1/documents'" in content
    assert "method: 'POST'" in content

    # Redirect to new document
    assert "window.location.href" in content


def test_template_permission_handling() -> None:
    """Template API should handle permissions correctly."""
    root = Path(__file__).resolve().parents[1]
    templates_api = root / "backend" / "app" / "api" / "v1" / "endpoints" / "templates.py"
    content = templates_api.read_text(encoding="utf-8")

    # Owner check
    assert "owner_id" in content

    # Is public check
    assert "is_public" in content

    # Permission checks in operations
    assert "Access denied" in content
    assert "HTTP_403_FORBIDDEN" in content


def test_template_category_and_tags() -> None:
    """Templates should support category and tags."""
    root = Path(__file__).resolve().parents[1]

    # Backend
    templates_api = root / "backend" / "app" / "api" / "v1" / "endpoints" / "templates.py"
    api_content = templates_api.read_text(encoding="utf-8")

    assert "category" in api_content
    assert "tags" in api_content

    # Filtering support
    assert "category: Optional[str]" in api_content
    assert "tag: Optional[str]" in api_content

    # Frontend
    templates_js = root / "frontend" / "src" / "templates.js"
    js_content = templates_js.read_text(encoding="utf-8")

    assert "currentFilter" in js_content
    assert "grouped" in js_content  # Group by category
    assert "template-category" in js_content
    assert "template-tag" in js_content


def test_template_content_json_handling() -> None:
    """Templates should store and retrieve content JSON correctly."""
    root = Path(__file__).resolve().parents[1]

    # Database schema
    migration = root / "backend" / "app" / "db" / "migrations" / "0013_templates.sql"
    migration_content = migration.read_text(encoding="utf-8")
    assert "content_json TEXT NOT NULL" in migration_content

    # Backend API
    templates_api = root / "backend" / "app" / "api" / "v1" / "endpoints" / "templates.py"
    api_content = templates_api.read_text(encoding="utf-8")
    assert "content_json" in api_content

    # Frontend
    templates_js = root / "frontend" / "src" / "templates.js"
    js_content = templates_js.read_text(encoding="utf-8")
    assert "JSON.parse" in js_content
    assert "JSON.stringify" in js_content


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
