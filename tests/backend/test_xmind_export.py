"""Tests for XMind export service."""

import io
import zipfile

from app.services.xmind_export import render_xmind


def test_render_xmind_basic_tree() -> None:
    """Test basic XMind export with a simple tree structure."""
    output = render_xmind(
        {
            'id': 'root',
            'text': '计划',
            'memo': '2026Q2 重点',
            'children': [
                {
                    'id': 'a',
                    'text': '研发',
                    'children': [{'id': 'a1', 'text': '后端'}],
                },
                {'id': 'b', 'text': '测试', 'memo': '重点'},
            ],
        }
    )

    # Verify it's a valid ZIP file
    with zipfile.ZipFile(io.BytesIO(output), 'r') as zf:
        assert 'content.xml' in zf.namelist()
        assert 'META-INF/manifest.xml' in zf.namelist()

        # Check content.xml contains expected structure
        content_xml = zf.read('content.xml').decode('utf-8')
        assert '<xmap-content' in content_xml
        assert '<topic id="root">' in content_xml
        assert '<title>计划</title>' in content_xml
        assert '<plain content="2026Q2 重点"/>' in content_xml
        assert '<topic id="a">' in content_xml
        assert '<title>研发</title>' in content_xml
        assert '<topic id="a1">' in content_xml
        assert '<title>后端</title>' in content_xml
        assert '<topic id="b">' in content_xml
        assert '<title>测试</title>' in content_xml
        assert '<plain content="重点"/>' in content_xml


def test_render_xmind_rejects_invalid_node() -> None:
    """Test that invalid node structure raises ValueError."""
    try:
        render_xmind({'id': '', 'text': 'invalid'})
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert 'node id is required' in str(exc)


def test_render_xmind_single_node() -> None:
    """Test XMind export with just a root node."""
    output = render_xmind({'id': 'root', 'text': '单节点'})

    with zipfile.ZipFile(io.BytesIO(output), 'r') as zf:
        content_xml = zf.read('content.xml').decode('utf-8')
        assert '<topic id="root">' in content_xml
        assert '<title>单节点</title>' in content_xml
        # Should not have children section
        assert '<children>' not in content_xml
