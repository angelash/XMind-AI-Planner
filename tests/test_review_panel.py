"""Tests for review panel frontend.

REVIEW-02: 审核面板前端
"""
from pathlib import Path


def test_review_panel_html_exists() -> None:
    """Test that review.html exists."""
    root = Path(__file__).resolve().parents[1]
    assert (root / "frontend" / "review.html").exists()


def test_review_panel_js_exists() -> None:
    """Test that review.js exists."""
    root = Path(__file__).resolve().parents[1]
    assert (root / "frontend" / "src" / "review.js").exists()


def test_review_html_has_required_elements() -> None:
    """Test that review.html contains required UI elements."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "review.html").read_text(encoding="utf-8")

    # Check for key elements
    assert 'id="review-list"' in html
    assert 'id="review-count"' in html
    assert 'id="btn-refresh"' in html
    assert 'id="btn-batch-approve"' in html
    assert 'id="filter-document"' in html
    assert 'id="filter-type"' in html
    assert "review.js" in html


def test_review_html_has_change_type_styles() -> None:
    """Test that review.html has styles for change types."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "review.html").read_text(encoding="utf-8")

    # Check for change type badges
    assert "review-item-type.create" in html
    assert "review-item-type.update" in html
    assert "review-item-type.delete" in html


def test_review_html_has_status_styles() -> None:
    """Test that review.html has styles for review statuses."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "review.html").read_text(encoding="utf-8")

    assert "review-status.pending" in html
    assert "review-status.approved" in html
    assert "review-status.rejected" in html


def test_review_js_has_fetch_function() -> None:
    """Test that review.js has fetchPendingChanges function."""
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend" / "src" / "review.js").read_text(encoding="utf-8")

    assert "fetchPendingChanges" in js
    assert "/api/v1/review/pending" in js


def test_review_js_has_approve_reject_handlers() -> None:
    """Test that review.js has approve/reject handlers."""
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend" / "src" / "review.js").read_text(encoding="utf-8")

    assert "handleReviewAction" in js
    assert "approve" in js.lower()
    assert "reject" in js.lower()


def test_review_js_has_batch_approve() -> None:
    """Test that review.js has batch approve handler."""
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend" / "src" / "review.js").read_text(encoding="utf-8")

    assert "handleBatchApprove" in js
    assert "batch-approve" in js


def test_review_js_renders_change_items() -> None:
    """Test that review.js renders change items."""
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend" / "src" / "review.js").read_text(encoding="utf-8")

    assert "renderChangeItem" in js
    assert "renderChanges" in js


def test_review_js_has_xss_protection() -> None:
    """Test that review.js has XSS protection via escapeHtml."""
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend" / "src" / "review.js").read_text(encoding="utf-8")

    assert "escapeHtml" in js


def test_review_js_has_filters() -> None:
    """Test that review.js supports filtering."""
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend" / "src" / "review.js").read_text(encoding="utf-8")

    assert "applyFilters" in js
    assert "filterTypeSelect" in js
    assert "filterDocumentInput" in js
