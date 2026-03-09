"""Tests for need_confirm rule engine.

AUTO-02: need_confirm 规则引擎
"""

import pytest

from app.services.need_confirm_engine import (
    NeedConfirmResult,
    evaluate_need_confirm,
    get_rule_summary,
    MAX_DELETE_FILES,
    MAX_MODIFY_FILES,
    MIN_CONFIDENCE,
)


class TestEvaluateNeedConfirm:
    """Test cases for evaluate_need_confirm function."""

    def test_none_analysis_returns_no_confirm(self) -> None:
        """None analysis should not need confirmation."""
        result = evaluate_need_confirm(None)
        assert result.needs_confirm is False
        assert result.reason is None
        assert result.triggered_rules is None

    def test_empty_analysis_returns_no_confirm(self) -> None:
        """Empty analysis should not need confirmation."""
        result = evaluate_need_confirm({})
        assert result.needs_confirm is False
        assert result.reason is None

    def test_safe_analysis_returns_no_confirm(self) -> None:
        """Safe analysis with small changes should not need confirmation."""
        result = evaluate_need_confirm({
            "files_to_delete": 1,
            "files_to_modify": 5,
            "confidence": 0.9,
            "risky_operations": [],
        })
        assert result.needs_confirm is False

    def test_too_many_files_to_delete(self) -> None:
        """Files to delete exceeding threshold should trigger confirm."""
        result = evaluate_need_confirm({
            "files_to_delete": MAX_DELETE_FILES + 1,
            "files_to_modify": 0,
            "confidence": 0.9,
        })
        assert result.needs_confirm is True
        assert result.triggered_rules is not None
        assert len(result.triggered_rules) == 1
        assert "待删除文件数" in result.reason
        assert str(MAX_DELETE_FILES + 1) in result.reason

    def test_too_many_files_to_modify(self) -> None:
        """Files to modify exceeding threshold should trigger confirm."""
        result = evaluate_need_confirm({
            "files_to_delete": 0,
            "files_to_modify": MAX_MODIFY_FILES + 1,
            "confidence": 0.9,
        })
        assert result.needs_confirm is True
        assert "待修改文件数" in result.reason

    def test_low_confidence(self) -> None:
        """Low confidence should trigger confirm."""
        result = evaluate_need_confirm({
            "files_to_delete": 0,
            "files_to_modify": 0,
            "confidence": MIN_CONFIDENCE - 0.1,
        })
        assert result.needs_confirm is True
        assert "置信度" in result.reason

    def test_confidence_at_threshold_is_ok(self) -> None:
        """Confidence at exact threshold should not trigger."""
        result = evaluate_need_confirm({
            "confidence": MIN_CONFIDENCE,
        })
        assert result.needs_confirm is False

    def test_risky_operations_trigger(self) -> None:
        """Presence of risky operations should trigger confirm."""
        result = evaluate_need_confirm({
            "risky_operations": ["drop_table", "truncate_data"],
        })
        assert result.needs_confirm is True
        assert "风险操作" in result.reason
        assert "drop_table" in result.reason

    def test_empty_risky_operations_no_trigger(self) -> None:
        """Empty risky operations should not trigger."""
        result = evaluate_need_confirm({
            "risky_operations": [],
        })
        assert result.needs_confirm is False

    def test_multiple_rules_trigger(self) -> None:
        """Multiple rules triggered should all be in reason."""
        result = evaluate_need_confirm({
            "files_to_delete": 5,
            "files_to_modify": 15,
            "confidence": 0.5,
            "risky_operations": ["force_delete"],
        })
        assert result.needs_confirm is True
        assert result.triggered_rules is not None
        assert len(result.triggered_rules) == 4
        assert "待删除文件数" in result.reason
        assert "待修改文件数" in result.reason
        assert "置信度" in result.reason
        assert "风险操作" in result.reason

    def test_non_int_files_counts_ignored(self) -> None:
        """Non-integer file counts should be ignored."""
        result = evaluate_need_confirm({
            "files_to_delete": "many",
            "files_to_modify": [1, 2, 3],
        })
        assert result.needs_confirm is False

    def test_non_numeric_confidence_ignored(self) -> None:
        """Non-numeric confidence should be ignored."""
        result = evaluate_need_confirm({
            "confidence": "high",
        })
        assert result.needs_confirm is False

    def test_boundary_delete_files(self) -> None:
        """Test boundary: exactly MAX_DELETE_FILES should not trigger."""
        result = evaluate_need_confirm({
            "files_to_delete": MAX_DELETE_FILES,
        })
        assert result.needs_confirm is False

    def test_boundary_modify_files(self) -> None:
        """Test boundary: exactly MAX_MODIFY_FILES should not trigger."""
        result = evaluate_need_confirm({
            "files_to_modify": MAX_MODIFY_FILES,
        })
        assert result.needs_confirm is False

    def test_missing_optional_fields(self) -> None:
        """Missing optional fields should use defaults."""
        result = evaluate_need_confirm({
            "confidence": 0.8,  # only confidence provided
        })
        assert result.needs_confirm is False


class TestGetRuleSummary:
    """Test cases for get_rule_summary function."""

    def test_returns_dict(self) -> None:
        """Should return a dictionary."""
        summary = get_rule_summary()
        assert isinstance(summary, dict)

    def test_contains_thresholds(self) -> None:
        """Should contain all threshold values."""
        summary = get_rule_summary()
        assert summary["max_delete_files"] == MAX_DELETE_FILES
        assert summary["max_modify_files"] == MAX_MODIFY_FILES
        assert summary["min_confidence"] == MIN_CONFIDENCE

    def test_contains_rules_list(self) -> None:
        """Should contain rules list with details."""
        summary = get_rule_summary()
        assert "rules" in summary
        assert len(summary["rules"]) == 4

        rule_names = {r["name"] for r in summary["rules"]}
        assert "files_to_delete" in rule_names
        assert "files_to_modify" in rule_names
        assert "confidence" in rule_names
        assert "risky_operations" in rule_names
