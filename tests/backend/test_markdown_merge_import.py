from app.services.markdown_merge_import import merge_markdown_into_document


def test_merge_markdown_merges_same_named_branches() -> None:
    existing = {
        "id": "root-1",
        "text": "Project Plan",
        "children": [
            {
                "id": "n-1",
                "text": "Scope",
                "children": [{"id": "n-2", "text": "Backend"}],
            }
        ],
    }

    merged, stats = merge_markdown_into_document(
        existing,
        """
# Project Plan
## Scope
- API
## Risks
- Delivery
""".strip(),
    )

    scope = next(child for child in merged["children"] if child["text"] == "Scope")
    assert [child["text"] for child in scope["children"]] == ["Backend", "API"]

    risks = next(child for child in merged["children"] if child["text"] == "Risks")
    assert risks["children"][0]["text"] == "Delivery"
    assert stats.merged_nodes >= 1
    assert stats.added_nodes >= 3


def test_merge_markdown_adds_new_section_when_root_differs() -> None:
    existing = {"id": "root-1", "text": "Roadmap", "children": []}

    merged, _ = merge_markdown_into_document(
        existing,
        """
# Launch Plan
- Phase 1
""".strip(),
    )

    assert merged["children"][0]["text"] == "Launch Plan"
    assert merged["children"][0]["children"][0]["text"] == "Phase 1"
