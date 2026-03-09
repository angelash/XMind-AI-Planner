/**
 * MD Editor Component
 * A simple markdown editor with preview for file tree items
 */

// State
let editorVisible = false;
let currentEditingItem = null;
let currentProjectId = null;
let editorMode = 'edit'; // 'edit' or 'preview'
let isDirty = false;

// DOM Elements
let mdEditorPanel = null;
let editorTextarea = null;
let previewContainer = null;
let editorTitle = null;

/**
 * Initialize the MD editor
 */
export function initMdEditor() {
  createEditorPanel();
  bindEditorEvents();
}

/**
 * Create the editor panel DOM structure
 */
function createEditorPanel() {
  // Check if panel already exists
  mdEditorPanel = document.getElementById('md-editor-panel');
  if (mdEditorPanel) {
    editorTextarea = document.getElementById('md-editor-textarea');
    previewContainer = document.getElementById('md-preview-container');
    editorTitle = document.getElementById('md-editor-title');
    return;
  }

  // Create panel
  mdEditorPanel = document.createElement('aside');
  mdEditorPanel.id = 'md-editor-panel';
  mdEditorPanel.className = 'md-editor-panel hidden';
  mdEditorPanel.innerHTML = `
    <div class="md-editor-header">
      <h3 id="md-editor-title">📝 编辑文件</h3>
      <div class="md-editor-actions">
        <button id="btn-toggle-mode" title="切换模式" type="button">👁️ 预览</button>
        <button id="btn-save-file" title="保存 (Ctrl+S)" type="button">💾 保存</button>
        <button id="btn-close-editor" title="关闭" type="button">✖️</button>
      </div>
    </div>
    <div class="md-editor-body">
      <textarea id="md-editor-textarea" class="md-editor-textarea" placeholder="在此输入 Markdown 内容..."></textarea>
      <div id="md-preview-container" class="md-preview-container hidden"></div>
    </div>
    <div class="md-editor-footer">
      <span id="md-editor-status">就绪</span>
    </div>
  `;

  // Insert into editor layout
  const editorLayout = document.querySelector('.editor-layout');
  if (editorLayout) {
    editorLayout.appendChild(mdEditorPanel);
  }

  editorTextarea = document.getElementById('md-editor-textarea');
  previewContainer = document.getElementById('md-preview-container');
  editorTitle = document.getElementById('md-editor-title');
}

/**
 * Bind event listeners
 */
function bindEditorEvents() {
  // Toggle mode button
  document.getElementById('btn-toggle-mode')?.addEventListener('click', toggleMode);

  // Save button
  document.getElementById('btn-save-file')?.addEventListener('click', saveFile);

  // Close button
  document.getElementById('btn-close-editor')?.addEventListener('click', closeEditor);

  // Textarea input - track dirty state
  editorTextarea?.addEventListener('input', () => {
    isDirty = true;
    updateStatus('未保存');
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (!editorVisible) return;
    
    // Ctrl/Cmd + S: Save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveFile();
    }
    
    // Escape: Close editor (if not dirty or confirmed)
    if (e.key === 'Escape') {
      if (isDirty) {
        if (confirm('文件已修改，确定要关闭吗？')) {
          closeEditor();
        }
      } else {
        closeEditor();
      }
    }
  });

  // Listen for file tree open events
  document.addEventListener('fileTreeOpen', (e) => {
    const { id, type, path } = e.detail;
    if (type === 'file') {
      openFile(id, path);
    }
  });
}

/**
 * Toggle between edit and preview mode
 */
function toggleMode() {
  const btn = document.getElementById('btn-toggle-mode');
  
  if (editorMode === 'edit') {
    editorMode = 'preview';
    editorTextarea.classList.add('hidden');
    previewContainer.classList.remove('hidden');
    renderPreview();
    btn.textContent = '✏️ 编辑';
  } else {
    editorMode = 'edit';
    editorTextarea.classList.remove('hidden');
    previewContainer.classList.add('hidden');
    btn.textContent = '👁️ 预览';
  }
}

/**
 * Render markdown preview
 */
function renderPreview() {
  const markdown = editorTextarea.value;
  const html = renderMarkdown(markdown);
  previewContainer.innerHTML = html;
}

/**
 * Simple markdown renderer
 * Supports: headers, bold, italic, links, lists, code blocks, inline code
 */
function renderMarkdown(md) {
  if (!md) return '<p class="preview-empty">暂无内容</p>';
  
  let html = escapeHtml(md);
  
  // Code blocks (must be before other transformations)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>');
  
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  
  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  
  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  html = html.replace(/_(.+?)_/g, '<em>$1</em>');
  
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  
  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
  
  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  
  // Paragraphs (lines not already wrapped)
  html = html.split('\n\n').map(block => {
    if (block.startsWith('<')) return block;
    return `<p>${block.replace(/\n/g, '<br>')}</p>`;
  }).join('\n');
  
  return html;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * Open a file for editing
 */
export async function openFile(itemId, itemPath) {
  if (!currentProjectId) {
    console.error('No project selected');
    return;
  }

  try {
    const response = await fetch(
      `/api/v1/projects/${currentProjectId}/file-tree/items/${itemId}`,
      { credentials: 'include' }
    );

    if (!response.ok) {
      throw new Error('Failed to load file');
    }

    const item = await response.json();
    currentEditingItem = item;
    
    editorTitle.textContent = `📝 ${item.name}`;
    editorTextarea.value = item.content || '';
    isDirty = false;
    
    showEditor();
    updateStatus('已加载');
  } catch (error) {
    console.error('Error loading file:', error);
    alert('加载文件失败: ' + error.message);
  }
}

/**
 * Save the current file
 */
async function saveFile() {
  if (!currentEditingItem || !currentProjectId) {
    console.error('No file being edited');
    return;
  }

  const content = editorTextarea.value;

  try {
    updateStatus('保存中...');
    
    const response = await fetch(
      `/api/v1/projects/${currentProjectId}/file-tree/items/${currentEditingItem.id}/content`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to save file');
    }

    const updated = await response.json();
    currentEditingItem = updated;
    isDirty = false;
    updateStatus('已保存');
    
    // Dispatch save event
    document.dispatchEvent(new CustomEvent('mdEditorSave', {
      detail: { item: updated }
    }));
  } catch (error) {
    console.error('Error saving file:', error);
    updateStatus('保存失败');
    alert('保存失败: ' + error.message);
  }
}

/**
 * Close the editor
 */
function closeEditor() {
  hideEditor();
  currentEditingItem = null;
  editorTextarea.value = '';
  isDirty = false;
  editorMode = 'edit';
  editorTextarea.classList.remove('hidden');
  previewContainer.classList.add('hidden');
  document.getElementById('btn-toggle-mode').textContent = '👁️ 预览';
}

/**
 * Show the editor panel
 */
function showEditor() {
  editorVisible = true;
  mdEditorPanel.classList.remove('hidden');
}

/**
 * Hide the editor panel
 */
function hideEditor() {
  editorVisible = false;
  mdEditorPanel.classList.add('hidden');
}

/**
 * Update the status text
 */
function updateStatus(text) {
  const statusEl = document.getElementById('md-editor-status');
  if (statusEl) {
    statusEl.textContent = text;
  }
}

/**
 * Set the current project ID
 */
export function setProject(projectId) {
  currentProjectId = projectId;
  if (!projectId) {
    closeEditor();
  }
}

/**
 * Check if editor is visible
 */
export function isVisible() {
  return editorVisible;
}

/**
 * Check if there are unsaved changes
 */
export function hasUnsavedChanges() {
  return isDirty;
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initMdEditor);
} else {
  initMdEditor();
}
