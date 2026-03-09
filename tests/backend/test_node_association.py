"""Tests for node association (FILE-04) endpoints.

Tests the ability to:
1. Export a node subtree as a new document
2. Recall (merge) an associated mind map back into the node
3. List workspace documents for the selector
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'node_association_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def test_export_subtree_as_new_document(monkeypatch, tmp_path: Path) -> None:
    """Export a node subtree as a new document and link it to the original node."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login and create document
        client.post('/api/v1/auth/login', json={'staff_no': 'na1001'})
        doc_resp = client.post('/api/v1/documents', json={
            'title': 'Main Mind Map',
            'content': {
                'nodeData': {
                    'id': 'node-root',
                    'topic': 'Root',
                    'children': [
                        {
                            'id': 'node-child-1',
                            'topic': 'Branch A',
                            'children': [
                                {'id': 'node-leaf-1', 'topic': 'Leaf 1'},
                                {'id': 'node-leaf-2', 'topic': 'Leaf 2'},
                            ]
                        },
                        {
                            'id': 'node-child-2',
                            'topic': 'Branch B',
                        }
                    ]
                }
            }
        })
        doc_id = doc_resp.json()['id']

        # Export node-child-1 subtree as new document
        export_resp = client.post(f'/api/v1/documents/{doc_id}/export-subtree', json={
            'node_id': 'node-child-1',
            'clear_original_children': False,
        })
        assert export_resp.status_code == 201
        export_data = export_resp.json()
        
        new_doc_id = export_data['new_document_id']
        assert new_doc_id is not None
        assert export_data['exported_node_id'] == 'node-child-1'
        
        # Verify the new document was created
        new_doc_resp = client.get(f'/api/v1/documents/{new_doc_id}')
        assert new_doc_resp.status_code == 200
        new_doc = new_doc_resp.json()
        assert 'Branch A' in new_doc['title']
        assert new_doc['content']['nodeData']['topic'] == 'Branch A'
        assert len(new_doc['content']['nodeData']['children']) == 2
        
        # Verify the original node now has linkedDocId
        updated_doc_resp = client.get(f'/api/v1/documents/{doc_id}')
        updated_doc = updated_doc_resp.json()
        
        # Find the exported node in the tree
        def find_node(node, node_id):
            if node['id'] == node_id:
                return node
            for child in node.get('children', []):
                result = find_node(child, node_id)
                if result:
                    return result
            return None
        
        exported_node = find_node(updated_doc['content']['nodeData'], 'node-child-1')
        assert exported_node is not None
        assert exported_node.get('linkedDocId') == new_doc_id


def test_export_subtree_with_clear_children(monkeypatch, tmp_path: Path) -> None:
    """Export subtree and clear original children, keeping only linkedDocId."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'na1002'})
        doc_resp = client.post('/api/v1/documents', json={
            'title': 'Main Doc',
            'content': {
                'nodeData': {
                    'id': 'node-root',
                    'topic': 'Root',
                    'children': [
                        {
                            'id': 'node-branch',
                            'topic': 'Branch',
                            'children': [
                                {'id': 'node-leaf', 'topic': 'Leaf'},
                            ]
                        }
                    ]
                }
            }
        })
        doc_id = doc_resp.json()['id']

        # Export with clear_original_children=True
        export_resp = client.post(f'/api/v1/documents/{doc_id}/export-subtree', json={
            'node_id': 'node-branch',
            'clear_original_children': True,
        })
        assert export_resp.status_code == 201
        new_doc_id = export_resp.json()['new_document_id']

        # Verify original node has no children but has linkedDocId
        updated_doc = client.get(f'/api/v1/documents/{doc_id}').json()
        branch = updated_doc['content']['nodeData']['children'][0]
        assert branch.get('linkedDocId') == new_doc_id
        assert branch.get('children') is None or len(branch.get('children', [])) == 0


def test_export_subtree_node_not_found(monkeypatch, tmp_path: Path) -> None:
    """Return 404 when trying to export a non-existent node."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'na1003'})
        doc_resp = client.post('/api/v1/documents', json={
            'title': 'Test Doc',
            'content': {'nodeData': {'id': 'node-root', 'topic': 'Root'}}
        })
        doc_id = doc_resp.json()['id']

        export_resp = client.post(f'/api/v1/documents/{doc_id}/export-subtree', json={
            'node_id': 'non-existent-node',
        })
        assert export_resp.status_code == 404
        assert 'not found' in export_resp.json()['detail'].lower()


def test_recall_association(monkeypatch, tmp_path: Path) -> None:
    """Recall (merge) an associated mind map back into the node."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'na1004'})
        
        # Create main document with linked node
        doc_resp = client.post('/api/v1/documents', json={
            'title': 'Main Doc',
            'content': {
                'nodeData': {
                    'id': 'node-root',
                    'topic': 'Root',
                    'children': [
                        {
                            'id': 'node-linked',
                            'topic': 'Linked Branch',
                            'linkedDocId': None,  # Will be set after export
                        }
                    ]
                }
            }
        })
        main_doc_id = doc_resp.json()['id']

        # Create associated document
        assoc_resp = client.post('/api/v1/documents', json={
            'title': 'Associated Mind Map',
            'content': {
                'nodeData': {
                    'id': 'assoc-root',
                    'topic': 'Associated Root',
                    'children': [
                        {'id': 'assoc-child-1', 'topic': 'Assoc Child 1'},
                        {'id': 'assoc-child-2', 'topic': 'Assoc Child 2'},
                    ]
                }
            }
        })
        assoc_doc_id = assoc_resp.json()['id']

        # Update main doc to link the node
        linked_node = {
            'id': 'node-linked',
            'topic': 'Linked Branch',
            'linkedDocId': assoc_doc_id,
        }
        client.patch(f'/api/v1/documents/{main_doc_id}', json={
            'content': {
                'nodeData': {
                    'id': 'node-root',
                    'topic': 'Root',
                    'children': [linked_node]
                }
            }
        })

        # Recall the association
        recall_resp = client.post(f'/api/v1/documents/{main_doc_id}/recall-association', json={
            'node_id': 'node-linked',
        })
        assert recall_resp.status_code == 200
        recall_data = recall_resp.json()
        
        # Verify the merged children
        assert recall_data['merged_count'] == 2
        
        # Verify the node now has the associated children
        updated_doc = client.get(f'/api/v1/documents/{main_doc_id}').json()
        linked_node_updated = updated_doc['content']['nodeData']['children'][0]
        
        # linkedDocId should be cleared
        assert linked_node_updated.get('linkedDocId') is None
        
        # Children should be merged
        assert len(linked_node_updated.get('children', [])) == 2
        child_topics = {c['topic'] for c in linked_node_updated['children']}
        assert 'Assoc Child 1' in child_topics
        assert 'Assoc Child 2' in child_topics


def test_recall_association_no_link(monkeypatch, tmp_path: Path) -> None:
    """Return 400 when trying to recall a node without linkedDocId."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'na1005'})
        doc_resp = client.post('/api/v1/documents', json={
            'title': 'Test Doc',
            'content': {
                'nodeData': {
                    'id': 'node-root',
                    'topic': 'Root',
                    'children': [
                        {'id': 'node-no-link', 'topic': 'No Link'}
                    ]
                }
            }
        })
        doc_id = doc_resp.json()['id']

        recall_resp = client.post(f'/api/v1/documents/{doc_id}/recall-association', json={
            'node_id': 'node-no-link',
        })
        assert recall_resp.status_code == 400
        assert 'no linked document' in recall_resp.json()['detail'].lower()


def test_list_workspace_documents(monkeypatch, tmp_path: Path) -> None:
    """List documents in a project workspace for the selector."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'na1006'})
        
        # Create project
        proj_resp = client.post('/api/v1/projects', json={'name': 'Test Project'})
        proj_id = proj_resp.json()['id']
        
        # Create documents in project
        client.post('/api/v1/documents', json={
            'title': 'Doc A',
            'content': {'nodeData': {'id': 'root', 'topic': 'A'}},
            'project_id': proj_id,
        })
        client.post('/api/v1/documents', json={
            'title': 'Doc B',
            'content': {'nodeData': {'id': 'root', 'topic': 'B'}},
            'project_id': proj_id,
        })
        # Create personal document (should not appear in project list)
        client.post('/api/v1/documents', json={
            'title': 'Personal Doc',
            'content': {'nodeData': {'id': 'root', 'topic': 'Personal'}},
        })

        # List project documents
        list_resp = client.get(f'/api/v1/documents?project_id={proj_id}')
        assert list_resp.status_code == 200
        items = list_resp.json()['items']
        
        # Should have 2 project documents
        assert len(items) == 2
        titles = {item['title'] for item in items}
        assert 'Doc A' in titles
        assert 'Doc B' in titles
        assert 'Personal Doc' not in titles


def test_bind_existing_document(monkeypatch, tmp_path: Path) -> None:
    """Bind an existing document to a node via linkedDocId."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'na1007'})
        
        # Create main document
        main_resp = client.post('/api/v1/documents', json={
            'title': 'Main Doc',
            'content': {
                'nodeData': {
                    'id': 'node-root',
                    'topic': 'Root',
                    'children': [
                        {'id': 'node-to-link', 'topic': 'To Link'}
                    ]
                }
            }
        })
        main_id = main_resp.json()['id']
        
        # Create target document to link
        target_resp = client.post('/api/v1/documents', json={
            'title': 'Target Doc',
            'content': {
                'nodeData': {
                    'id': 'target-root',
                    'topic': 'Target',
                    'children': [
                        {'id': 'target-child', 'topic': 'Target Child'}
                    ]
                }
            }
        })
        target_id = target_resp.json()['id']
        
        # Bind the target document to the node
        bind_resp = client.post(f'/api/v1/documents/{main_id}/bind-link', json={
            'node_id': 'node-to-link',
            'linked_doc_id': target_id,
        })
        assert bind_resp.status_code == 200
        
        # Verify the binding
        updated_doc = client.get(f'/api/v1/documents/{main_id}').json()
        linked_node = updated_doc['content']['nodeData']['children'][0]
        assert linked_node.get('linkedDocId') == target_id
