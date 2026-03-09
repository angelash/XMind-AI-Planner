"""Tests for review workflow endpoints.

REVIEW-01: 审核流程后端
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'review_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def _login_employee(client: TestClient) -> dict:
    """Login as employee and return user info."""
    resp = client.post('/api/v1/auth/login', json={'staff_no': 'e1001'})
    assert resp.status_code == 200
    return resp.json()['user']


def _login_reviewer(client: TestClient) -> dict:
    """Login as reviewer and return user info."""
    # First create a reviewer via admin
    admin_resp = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
    assert admin_resp.status_code == 200
    
    # Create reviewer user
    create_resp = client.post('/api/v1/users', json={
        'staff_no': 'r2001',
        'display_name': 'Reviewer',
        'role': 'reviewer',
    })
    assert create_resp.status_code in (200, 201)
    
    # Logout admin and login as reviewer
    client.post('/api/v1/auth/logout')
    reviewer_resp = client.post('/api/v1/auth/login', json={'staff_no': 'r2001'})
    assert reviewer_resp.status_code == 200
    return reviewer_resp.json()['user']


def _create_document(client: TestClient) -> str:
    """Create a test document and return its ID."""
    resp = client.post('/api/v1/documents', json={'title': 'Test Doc'})
    assert resp.status_code in (200, 201)
    return resp.json()['id']


def test_submit_change_for_review(monkeypatch, tmp_path: Path) -> None:
    """Test submitting a change for review."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)

        resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
            'before_content': {'text': 'old'},
            'after_content': {'text': 'new'},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['document_id'] == doc_id
        assert data['node_id'] == 'node-1'
        assert data['change_type'] == 'update'
        assert data['status'] == 'pending'
        assert data['before_content'] == {'text': 'old'}
        assert data['after_content'] == {'text': 'new'}


def test_submit_duplicate_pending_change_fails(monkeypatch, tmp_path: Path) -> None:
    """Test that submitting duplicate pending change for same node fails."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)

        # First submission succeeds
        resp1 = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        assert resp1.status_code == 200

        # Duplicate submission fails
        resp2 = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        assert resp2.status_code == 400
        assert 'already exists' in resp2.json()['detail'].lower()


def test_list_pending_changes(monkeypatch, tmp_path: Path) -> None:
    """Test listing pending changes."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)

        # Submit two changes
        client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'create',
            'after_content': {'text': 'new node'},
        })
        client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-2',
            'change_type': 'delete',
            'before_content': {'text': 'delete me'},
        })

        resp = client.get('/api/v1/review/pending')
        assert resp.status_code == 200
        data = resp.json()
        assert data['count'] == 2
        assert len(data['changes']) == 2


def test_list_pending_changes_filtered_by_document(monkeypatch, tmp_path: Path) -> None:
    """Test listing pending changes filtered by document."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc1 = _create_document(client)
        doc2 = _create_document(client)

        client.post('/api/v1/review/submit', json={
            'document_id': doc1,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        client.post('/api/v1/review/submit', json={
            'document_id': doc2,
            'node_id': 'node-2',
            'change_type': 'update',
        })

        resp = client.get(f'/api/v1/review/pending?document_id={doc1}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['count'] == 1
        assert data['changes'][0]['document_id'] == doc1


def test_get_pending_count(monkeypatch, tmp_path: Path) -> None:
    """Test getting pending change count for a document."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)

        # Initially zero
        resp = client.get(f'/api/v1/review/count?document_id={doc_id}')
        assert resp.status_code == 200
        assert resp.json()['count'] == 0

        # Submit changes
        client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-2',
            'change_type': 'update',
        })

        resp = client.get(f'/api/v1/review/count?document_id={doc_id}')
        assert resp.status_code == 200
        assert resp.json()['count'] == 2


def test_approve_change_as_reviewer(monkeypatch, tmp_path: Path) -> None:
    """Test approving a pending change as reviewer."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Employee submits change
        _login_employee(client)
        doc_id = _create_document(client)
        
        submit_resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        change_id = submit_resp.json()['id']

        # Login as reviewer and approve
        _login_reviewer(client)
        approve_resp = client.post(f'/api/v1/review/{change_id}/approve', json={
            'review_comment': 'Looks good',
        })
        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data['status'] == 'approved'
        assert data['review_comment'] == 'Looks good'


def test_reject_change_as_reviewer(monkeypatch, tmp_path: Path) -> None:
    """Test rejecting a pending change as reviewer."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Employee submits change
        _login_employee(client)
        doc_id = _create_document(client)
        
        submit_resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        change_id = submit_resp.json()['id']

        # Login as reviewer and reject
        _login_reviewer(client)
        reject_resp = client.post(f'/api/v1/review/{change_id}/reject', json={
            'review_comment': 'Needs revision',
        })
        assert reject_resp.status_code == 200
        data = reject_resp.json()
        assert data['status'] == 'rejected'
        assert data['review_comment'] == 'Needs revision'


def test_approve_requires_reviewer_role(monkeypatch, tmp_path: Path) -> None:
    """Test that only reviewers/admins can approve changes."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)
        
        submit_resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        change_id = submit_resp.json()['id']

        # Employee tries to approve - should fail
        approve_resp = client.post(f'/api/v1/review/{change_id}/approve')
        assert approve_resp.status_code == 403


def test_cancel_own_pending_change(monkeypatch, tmp_path: Path) -> None:
    """Test that submitter can cancel their own pending change."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)
        
        submit_resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        change_id = submit_resp.json()['id']

        # Cancel own change
        cancel_resp = client.delete(f'/api/v1/review/{change_id}')
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()['ok'] is True

        # Verify it's gone
        get_resp = client.get(f'/api/v1/review/{change_id}')
        assert get_resp.status_code == 404


def test_batch_approve_changes(monkeypatch, tmp_path: Path) -> None:
    """Test batch approving multiple pending changes."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Employee submits changes
        _login_employee(client)
        doc_id = _create_document(client)
        
        client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-2',
            'change_type': 'update',
        })

        # Login as reviewer and batch approve
        _login_reviewer(client)
        batch_resp = client.post('/api/v1/review/batch-approve', json={
            'document_id': doc_id,
        })
        assert batch_resp.status_code == 200
        data = batch_resp.json()
        assert data['count'] == 2
        assert all(c['status'] == 'approved' for c in data['approved'])


def test_get_change_by_id(monkeypatch, tmp_path: Path) -> None:
    """Test getting a specific pending change by ID."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)
        
        submit_resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'create',
            'after_content': {'text': 'hello'},
        })
        change_id = submit_resp.json()['id']

        get_resp = client.get(f'/api/v1/review/{change_id}')
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data['id'] == change_id
        assert data['node_id'] == 'node-1'


def test_get_nonexistent_change_returns_404(monkeypatch, tmp_path: Path) -> None:
    """Test that getting nonexistent change returns 404."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        
        resp = client.get('/api/v1/review/99999')
        assert resp.status_code == 404


def test_approve_already_processed_change_fails(monkeypatch, tmp_path: Path) -> None:
    """Test that approving an already processed change fails."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Employee submits change
        _login_employee(client)
        doc_id = _create_document(client)
        
        submit_resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'update',
        })
        change_id = submit_resp.json()['id']

        # Reviewer approves
        _login_reviewer(client)
        client.post(f'/api/v1/review/{change_id}/approve')

        # Try to approve again
        resp = client.post(f'/api/v1/review/{change_id}/approve')
        assert resp.status_code == 404


def test_invalid_change_type_fails(monkeypatch, tmp_path: Path) -> None:
    """Test that invalid change type is rejected."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_employee(client)
        doc_id = _create_document(client)

        resp = client.post('/api/v1/review/submit', json={
            'document_id': doc_id,
            'node_id': 'node-1',
            'change_type': 'invalid_type',
        })
        assert resp.status_code == 422  # Validation error
