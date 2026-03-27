-- Templates table (GAP-08)
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    content_json TEXT NOT NULL,
    category TEXT,
    tags TEXT,  -- JSON array of tags
    owner_id TEXT,
    is_public INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category);

-- Index for public templates
CREATE INDEX IF NOT EXISTS idx_templates_public ON templates(is_public);
