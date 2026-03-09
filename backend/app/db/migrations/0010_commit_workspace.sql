-- Migration 0010: Commit workspace and merge area
-- AUTO-04: 提交工作区与合并区

-- Commit workspace stores AI-generated changes before they are merged into documents
CREATE TABLE IF NOT EXISTS commit_workspace (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    snapshot_before TEXT,  -- JSON: document state before changes
    snapshot_after TEXT,   -- JSON: document state after changes (proposed)
    changes_summary TEXT,  -- Human-readable summary of changes
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'merged', 'discarded')),
    created_by TEXT NOT NULL,
    merged_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    merged_at TEXT,
    FOREIGN KEY (task_id) REFERENCES dev_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_commit_workspace_task ON commit_workspace(task_id);
CREATE INDEX IF NOT EXISTS idx_commit_workspace_document ON commit_workspace(document_id);
CREATE INDEX IF NOT EXISTS idx_commit_workspace_status ON commit_workspace(status);
CREATE INDEX IF NOT EXISTS idx_commit_workspace_created ON commit_workspace(created_at);
