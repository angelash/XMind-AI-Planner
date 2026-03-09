-- Migration 0009: Development task queue state machine
-- AUTO-01: 自动化任务队列状态机

-- Development tasks table
CREATE TABLE IF NOT EXISTS dev_tasks (
    id TEXT PRIMARY KEY,
    workspace_id TEXT,
    document_id TEXT,
    status TEXT NOT NULL DEFAULT 'waiting' CHECK(status IN (
        'waiting', 'coding', 'diff_ready', 'sync_ok', 'build_ok', 'done',
        'need_confirm', 'failed', 'canceled', 'rolled_back'
    )),
    trigger_type TEXT CHECK(trigger_type IN ('manual', 'auto', 'node_change')),
    trigger_node_id TEXT,
    requirement TEXT,
    analysis_result TEXT,  -- JSON: analysis result from AI
    coding_result TEXT,    -- JSON: coding result from AI
    diff_summary TEXT,
    sync_result TEXT,
    build_result TEXT,
    error_message TEXT,
    need_confirm_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT
);

-- Task artifacts table (stores conversation logs, diffs, patches, manifests)
CREATE TABLE IF NOT EXISTS task_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL CHECK(artifact_type IN ('conversation', 'diff', 'patch', 'manifest')),
    file_path TEXT NOT NULL,
    content TEXT,  -- JSON or text content
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES dev_tasks(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_dev_tasks_status ON dev_tasks(status);
CREATE INDEX IF NOT EXISTS idx_dev_tasks_workspace ON dev_tasks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_dev_tasks_document ON dev_tasks(document_id);
CREATE INDEX IF NOT EXISTS idx_dev_tasks_created ON dev_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_task_artifacts_task ON task_artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_task_artifacts_type ON task_artifacts(artifact_type);
