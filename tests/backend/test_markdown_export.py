from app.services.markdown_export import render_markdown


def test_render_markdown_tree() -> None:
    output = render_markdown(
        {
            'id': 'root',
            'text': '??????',
            'memo': '2026Q2 focus',
            'children': [
                {
                    'id': 'a',
                    'text': '??',
                    'children': [{'id': 'a1', 'text': '????'}],
                },
                {'id': 'b', 'text': '????', 'memo': '????'},
            ],
        }
    )

    assert output == (
        '# ??????\n'
        '> 2026Q2 focus\n'
        '- ??\n'
        '  - ????\n'
        '- ????\n'
        '  > ????\n'
    )


def test_render_markdown_rejects_invalid_node() -> None:
    try:
        render_markdown({'id': '', 'text': 'invalid'})
        assert False, 'expected ValueError'
    except ValueError as exc:
        assert 'node id is required' in str(exc)
