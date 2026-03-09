-- File tree items table: files and folders in project workspaces
CREATE TABLE IF NOT EXISTS file_tree_items (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES file_tree_items(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'folder',  -- 'folder' or 'file'
    path TEXT NOT NULL,  -- virtual path like /folder1/folder2/file.md
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT REFERENCES users(id),
    UNIQUE(project_id, path)
);

-- Index for efficient lookup of project's file tree
CREATE INDEX IF NOT EXISTS idx_file_tree_items_project_id ON file_tree_items(project_id);

-- Index for efficient lookup of parent's children
CREATE INDEX IF NOT EXISTS idx_file_tree_items_parent_id ON file_tree_items(parent_id);
