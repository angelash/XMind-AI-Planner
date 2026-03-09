"""Need confirm rule engine for automation tasks.

AUTO-02: need_confirm 规则引擎

Determines whether a task needs human confirmation based on analysis results.

Rules (from DESIGN.md section 16.6):
- Files to delete > 3
- Files to modify > 10
- Confidence < 0.7
- Risky operations flag exists
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Rule thresholds
MAX_DELETE_FILES = 3
MAX_MODIFY_FILES = 10
MIN_CONFIDENCE = 0.7


@dataclass
class NeedConfirmResult:
    """Result of need_confirm evaluation."""
    needs_confirm: bool
    reason: str | None = None
    triggered_rules: list[str] | None = None


def evaluate_need_confirm(analysis_result: dict[str, Any] | None) -> NeedConfirmResult:
    """Evaluate whether a task needs human confirmation.

    Args:
        analysis_result: The analysis result from the coding phase.
            Expected fields:
            - files_to_delete: int (number of files to delete)
            - files_to_modify: int (number of files to modify)
            - confidence: float (0.0 to 1.0)
            - risky_operations: list[str] (list of risky operation identifiers)

    Returns:
        NeedConfirmResult with needs_confirm flag and reason.
    """
    if analysis_result is None:
        return NeedConfirmResult(needs_confirm=False)

    triggered_rules: list[str] = []

    # Rule 1: Too many files to delete
    files_to_delete = analysis_result.get("files_to_delete", 0)
    if isinstance(files_to_delete, int) and files_to_delete > MAX_DELETE_FILES:
        triggered_rules.append(
            f"待删除文件数({files_to_delete})超过阈值({MAX_DELETE_FILES})"
        )

    # Rule 2: Too many files to modify
    files_to_modify = analysis_result.get("files_to_modify", 0)
    if isinstance(files_to_modify, int) and files_to_modify > MAX_MODIFY_FILES:
        triggered_rules.append(
            f"待修改文件数({files_to_modify})超过阈值({MAX_MODIFY_FILES})"
        )

    # Rule 3: Low confidence
    confidence = analysis_result.get("confidence")
    if confidence is not None and isinstance(confidence, (int, float)):
        if confidence < MIN_CONFIDENCE:
            triggered_rules.append(
                f"置信度({confidence:.2f})低于阈值({MIN_CONFIDENCE})"
            )

    # Rule 4: Risky operations present
    risky_operations = analysis_result.get("risky_operations", [])
    if risky_operations and isinstance(risky_operations, list) and len(risky_operations) > 0:
        triggered_rules.append(
            f"存在风险操作: {', '.join(str(op) for op in risky_operations[:3])}"
        )

    if triggered_rules:
        reason = "; ".join(triggered_rules)
        return NeedConfirmResult(
            needs_confirm=True,
            reason=reason,
            triggered_rules=triggered_rules,
        )

    return NeedConfirmResult(needs_confirm=False)


def get_rule_summary() -> dict[str, Any]:
    """Get a summary of the current rules and thresholds.

    Returns:
        Dict with rule names and their thresholds.
    """
    return {
        "max_delete_files": MAX_DELETE_FILES,
        "max_modify_files": MAX_MODIFY_FILES,
        "min_confidence": MIN_CONFIDENCE,
        "rules": [
            {
                "name": "files_to_delete",
                "description": "待删除文件数超过阈值",
                "threshold": MAX_DELETE_FILES,
            },
            {
                "name": "files_to_modify",
                "description": "待修改文件数超过阈值",
                "threshold": MAX_MODIFY_FILES,
            },
            {
                "name": "confidence",
                "description": "置信度低于阈值",
                "threshold": MIN_CONFIDENCE,
            },
            {
                "name": "risky_operations",
                "description": "存在风险操作标记",
                "threshold": None,
            },
        ],
    }
