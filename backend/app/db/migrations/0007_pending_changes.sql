-- Migration 0007: Pending changes table for review workflow
-- REVIEW-01: 审核流程后端

CREATE TABLE IF NOT EXISTS pending_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('create', 'update', 'delete')),
    before_content TEXT,  -- JSON: node state before change (null for create)
    after_content TEXT,   -- JSON: node state after change (null for delete)
    submitted_by TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_comment TEXT,
    UNIQUE(document_id, node_id, status)  -- Only one pending change per node per document
);

CREATE INDEX IF NOT EXISTS idx_pending_changes_document ON pending_changes(document_id);
CREATE INDEX IF NOT EXISTS idx_pending_changes_status ON pending_changes(status);
CREATE INDEX IF NOT EXISTS idx_pending_changes_submitted_by ON pending_changes(submitted_by);
