from app.core.node_model import from_mind_elixir_document, to_mind_elixir_document


def test_to_mind_elixir_document_preserves_metadata() -> None:
    root = {
        "id": "node-root",
        "text": "Plan",
        "memo": "root memo",
        "exportSeparate": True,
        "children": [
            {
                "id": "node-a",
                "text": "Branch A",
                "children": [{"id": "node-a1", "text": "Leaf"}],
            }
        ],
    }

    doc = to_mind_elixir_document(root)
    assert doc["nodeData"]["root"] is True
    assert doc["nodeData"]["topic"] == "Plan"
    assert doc["nodeData"]["memo"] == "root memo"
    assert doc["nodeData"]["exportSeparate"] is True
    assert doc["nodeData"]["children"][0]["topic"] == "Branch A"


def test_from_mind_elixir_document_round_trip() -> None:
    doc = {
        "nodeData": {
            "id": "node-root",
            "topic": "Plan",
            "root": True,
            "children": [
                {
                    "id": "node-a",
                    "topic": "Branch A",
                    "memo": "details",
                    "exportSeparate": True,
                }
            ],
        }
    }

    node = from_mind_elixir_document(doc)
    assert node == {
        "id": "node-root",
        "text": "Plan",
        "children": [
            {
                "id": "node-a",
                "text": "Branch A",
                "memo": "details",
                "exportSeparate": True,
            }
        ],
    }


def test_to_mind_elixir_document_rejects_invalid_node() -> None:
    try:
        to_mind_elixir_document({"id": "", "text": "invalid"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "node id is required" in str(exc)


def test_from_mind_elixir_document_rejects_missing_node_data() -> None:
    try:
        from_mind_elixir_document({})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "requires nodeData" in str(exc)
