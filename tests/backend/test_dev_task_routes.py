"""Tests for development task queue API.

AUTO-01: 自动化任务队列状态机
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


client = TestClient(app)


def _configure_temp_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'dev_task_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    get_settings.cache_clear()


def _login_admin() -> None:
    resp = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
    assert resp.status_code == 200


def test_create_and_list_tasks(monkeypatch, tmp_path: Path) -> None:
    """Test creating and listing development tasks."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a task
    create_resp = client.post(
        '/api/v1/dev-tasks',
        json={
            'requirement': 'Implement user authentication',
            'workspace_id': 'ws-001',
            'document_id': 'doc-001',
        },
    )
    assert create_resp.status_code == 201
    task = create_resp.json()
    assert task['requirement'] == 'Implement user authentication'
    assert task['status'] == 'waiting'
    assert task['workspace_id'] == 'ws-001'
    task_id = task['id']

    # List tasks
    list_resp = client.get('/api/v1/dev-tasks')
    assert list_resp.status_code == 200
    items = list_resp.json()['items']
    assert len(items) == 1
    assert items[0]['id'] == task_id


def test_task_status_transitions(monkeypatch, tmp_path: Path) -> None:
    """Test valid status transitions."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a task
    create_resp = client.post(
        '/api/v1/dev-tasks',
        json={'requirement': 'Test task'},
    )
    task_id = create_resp.json()['id']

    # waiting → coding
    update_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'coding'},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()['status'] == 'coding'
    assert update_resp.json()['started_at'] is not None

    # coding → diff_ready
    update_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'diff_ready', 'diff_summary': 'Changed 3 files'},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()['status'] == 'diff_ready'
    assert update_resp.json()['diff_summary'] == 'Changed 3 files'

    # diff_ready → sync_ok
    update_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'sync_ok', 'sync_result': {'files': ['a.py', 'b.py']}},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()['status'] == 'sync_ok'

    # sync_ok → build_ok
    update_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'build_ok', 'build_result': {'tests_passed': True}},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()['status'] == 'build_ok'

    # build_ok → done
    update_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'done'},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()['status'] == 'done'
    assert update_resp.json()['completed_at'] is not None


def test_invalid_status_transition(monkeypatch, tmp_path: Path) -> None:
    """Test that invalid transitions are rejected."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a task
    create_resp = client.post(
        '/api/v1/dev-tasks',
        json={'requirement': 'Test task'},
    )
    task_id = create_resp.json()['id']

    # waiting → done is invalid
    update_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'done'},
    )
    assert update_resp.status_code == 400
    assert 'Invalid status transition' in update_resp.json()['detail']


def test_cancel_task(monkeypatch, tmp_path: Path) -> None:
    """Test canceling a task."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a task
    create_resp = client.post(
        '/api/v1/dev-tasks',
        json={'requirement': 'Test task'},
    )
    task_id = create_resp.json()['id']

    # Cancel the task
    cancel_resp = client.post(f'/api/v1/dev-tasks/{task_id}/cancel')
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()['status'] == 'canceled'


def test_retry_failed_task(monkeypatch, tmp_path: Path) -> None:
    """Test retrying a failed task."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a task and fail it
    create_resp = client.post(
        '/api/v1/dev-tasks',
        json={'requirement': 'Test task'},
    )
    task_id = create_resp.json()['id']

    # waiting → coding
    client.patch(f'/api/v1/dev-tasks/{task_id}/status', json={'status': 'coding'})

    # coding → failed
    fail_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'failed', 'error_message': 'Something went wrong'},
    )
    assert fail_resp.status_code == 200
    assert fail_resp.json()['status'] == 'failed'

    # Retry the task
    retry_resp = client.post(f'/api/v1/dev-tasks/{task_id}/retry')
    assert retry_resp.status_code == 200
    assert retry_resp.json()['status'] == 'waiting'


def test_confirm_task(monkeypatch, tmp_path: Path) -> None:
    """Test confirming a task that needs confirmation."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a task
    create_resp = client.post(
        '/api/v1/dev-tasks',
        json={'requirement': 'Test task'},
    )
    task_id = create_resp.json()['id']

    # waiting → coding
    client.patch(f'/api/v1/dev-tasks/{task_id}/status', json={'status': 'coding'})

    # coding → need_confirm
    confirm_resp = client.patch(
        f'/api/v1/dev-tasks/{task_id}/status',
        json={'status': 'need_confirm', 'need_confirm_reason': 'Large changes detected'},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()['status'] == 'need_confirm'

    # Confirm the task
    confirm_resp = client.post(f'/api/v1/dev-tasks/{task_id}/confirm')
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()['status'] == 'coding'


def test_get_next_waiting_task(monkeypatch, tmp_path: Path) -> None:
    """Test getting the next waiting task (FIFO)."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create multiple tasks
    client.post('/api/v1/dev-tasks', json={'requirement': 'Task 1'})
    client.post('/api/v1/dev-tasks', json={'requirement': 'Task 2'})
    client.post('/api/v1/dev-tasks', json={'requirement': 'Task 3'})

    # Get next task
    next_resp = client.get('/api/v1/dev-tasks/next')
    assert next_resp.status_code == 200
    assert next_resp.json()['requirement'] == 'Task 1'

    # Start processing first task
    task_id = next_resp.json()['id']
    client.patch(f'/api/v1/dev-tasks/{task_id}/status', json={'status': 'coding'})

    # Next should now be Task 2
    next_resp = client.get('/api/v1/dev-tasks/next')
    assert next_resp.json()['requirement'] == 'Task 2'


def test_task_artifacts(monkeypatch, tmp_path: Path) -> None:
    """Test creating and listing task artifacts."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a task
    create_resp = client.post(
        '/api/v1/dev-tasks',
        json={'requirement': 'Test task'},
    )
    task_id = create_resp.json()['id']

    # Create an artifact
    artifact_resp = client.post(
        f'/api/v1/dev-tasks/{task_id}/artifacts',
        json={
            'artifact_type': 'conversation',
            'file_path': 'conversations/001.jsonl',
            'content': '{"role": "user", "content": "Hello"}',
        },
    )
    assert artifact_resp.status_code == 201
    artifact_id = artifact_resp.json()['id']

    # List artifacts
    list_resp = client.get(f'/api/v1/dev-tasks/{task_id}/artifacts')
    assert list_resp.status_code == 200
    items = list_resp.json()['items']
    assert len(items) == 1
    assert items[0]['artifact_type'] == 'conversation'

    # Get specific artifact
    get_resp = client.get(f'/api/v1/dev-tasks/artifacts/{artifact_id}')
    assert get_resp.status_code == 200
    assert get_resp.json()['content'] == '{"role": "user", "content": "Hello"}'


def test_filter_tasks_by_status(monkeypatch, tmp_path: Path) -> None:
    """Test filtering tasks by status."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create tasks
    resp1 = client.post('/api/v1/dev-tasks', json={'requirement': 'Task 1'})
    resp2 = client.post('/api/v1/dev-tasks', json={'requirement': 'Task 2'})

    # Start processing first task
    task_id_1 = resp1.json()['id']
    client.patch(f'/api/v1/dev-tasks/{task_id_1}/status', json={'status': 'coding'})

    # Filter by waiting status
    list_resp = client.get('/api/v1/dev-tasks?status=waiting')
    assert list_resp.status_code == 200
    items = list_resp.json()['items']
    assert len(items) == 1
    assert items[0]['id'] == resp2.json()['id']

    # Filter by coding status
    list_resp = client.get('/api/v1/dev-tasks?status=coding')
    assert len(list_resp.json()['items']) == 1
    assert list_resp.json()['items'][0]['id'] == task_id_1
