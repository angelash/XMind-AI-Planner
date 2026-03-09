-- Add content column to file_tree_items for storing file content (markdown, text, etc.)
ALTER TABLE file_tree_items ADD COLUMN content TEXT DEFAULT '';
