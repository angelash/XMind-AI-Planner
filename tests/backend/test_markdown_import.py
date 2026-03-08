from app.services.markdown_import import import_markdown


def test_import_markdown_heading_and_list_structure() -> None:
    root = import_markdown(
        """
# Project Plan
## Scope
- Backend
  - API
- Frontend
""".strip()
    )

    assert root["text"] == "Project Plan"
    assert root["children"][0]["text"] == "Scope"
    assert root["children"][0]["children"][0]["text"] == "Backend"
    assert root["children"][0]["children"][0]["children"][0]["text"] == "API"


def test_import_markdown_uses_explicit_title() -> None:
    root = import_markdown("- A\n- B", title="Custom")
    assert root["text"] == "Custom"
    assert [child["text"] for child in root["children"]] == ["A", "B"]


def test_import_markdown_rejects_blank_content() -> None:
    try:
        import_markdown(" \n\t\n ")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "empty" in str(exc)
