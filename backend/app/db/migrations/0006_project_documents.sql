-- Add project_id to documents for project workspace support
-- NULL project_id means the document belongs to personal workspace
ALTER TABLE documents ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE SET NULL;

-- Index for efficient lookup of project documents
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
