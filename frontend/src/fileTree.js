/**
 * File Tree Panel Component
 * Displays a hierarchical file/folder tree for project workspaces
 */

// State
let fileTreeData = [];
let selectedItemId = null;
let expandedFolders = new Set();
let currentProjectId = null;

// DOM Elements
let fileTreePanel = null;
let fileTreeContainer = null;
let fileTreeToolbar = null;

/**
 * Initialize the file tree panel
 */
export function initFileTree() {
  // Create panel structure
  createPanelStructure();
  
  // Bind event listeners
  bindEventListeners();
}

/**
 * Create the file tree panel DOM structure
 */
function createPanelStructure() {
  // Check if panel already exists
  fileTreePanel = document.getElementById('file-tree-panel');
  if (fileTreePanel) {
    fileTreeContainer = document.getElementById('file-tree-container');
    fileTreeToolbar = document.getElementById('file-tree-toolbar');
    return;
  }

  // Create panel
  fileTreePanel = document.createElement('aside');
  fileTreePanel.id = 'file-tree-panel';
  fileTreePanel.className = 'file-tree-panel';
  fileTreePanel.innerHTML = `
    <div class="file-tree-header">
      <h3>📁 文件目录</h3>
      <div class="file-tree-actions">
        <button id="btn-new-folder" title="新建文件夹" type="button">📁</button>
        <button id="btn-new-file" title="新建文件" type="button">📄</button>
        <button id="btn-refresh-tree" title="刷新" type="button">🔄</button>
      </div>
    </div>
    <div id="file-tree-container" class="file-tree-container">
      <div class="file-tree-empty">请先选择项目</div>
    </div>
    <div id="file-tree-toolbar" class="file-tree-toolbar hidden">
      <button id="btn-add-as-node" type="button">添加为节点</button>
      <button id="btn-rename-item" type="button">重命名</button>
      <button id="btn-delete-item" type="button">删除</button>
    </div>
  `;

  // Insert before editor-main
  const editorLayout = document.querySelector('.editor-layout');
  const editorMain = document.querySelector('.editor-main');
  if (editorLayout && editorMain) {
    editorLayout.insertBefore(fileTreePanel, editorMain);
  }

  fileTreeContainer = document.getElementById('file-tree-container');
  fileTreeToolbar = document.getElementById('file-tree-toolbar');
}

/**
 * Bind event listeners
 */
function bindEventListeners() {
  // New folder button
  document.getElementById('btn-new-folder')?.addEventListener('click', () => {
    createNewItem('folder');
  });

  // New file button
  document.getElementById('btn-new-file')?.addEventListener('click', () => {
    createNewItem('file');
  });

  // Refresh button
  document.getElementById('btn-refresh-tree')?.addEventListener('click', () => {
    if (currentProjectId) {
      loadFileTree(currentProjectId);
    }
  });

  // Add as node button
  document.getElementById('btn-add-as-node')?.addEventListener('click', () => {
    if (selectedItemId) {
      addAsNode(selectedItemId);
    }
  });

  // Rename button
  document.getElementById('btn-rename-item')?.addEventListener('click', () => {
    if (selectedItemId) {
      renameItem(selectedItemId);
    }
  });

  // Delete button
  document.getElementById('btn-delete-item')?.addEventListener('click', () => {
    if (selectedItemId) {
      deleteItem(selectedItemId);
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (!selectedItemId) return;
    
    if (e.key === 'Delete') {
      e.preventDefault();
      deleteItem(selectedItemId);
    } else if (e.key === 'F2') {
      e.preventDefault();
      renameItem(selectedItemId);
    }
  });
}

/**
 * Load file tree for a project
 * @param {string} projectId - Project ID
 */
export async function loadFileTree(projectId) {
  if (!projectId) {
    fileTreeContainer.innerHTML = '<div class="file-tree-empty">请先选择项目</div>';
    currentProjectId = null;
    return;
  }

  currentProjectId = projectId;

  try {
    const response = await fetch(`/api/v1/projects/${projectId}/file-tree`, {
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error('Failed to load file tree');
    }

    fileTreeData = await response.json();
    renderFileTree();
  } catch (error) {
    console.error('Error loading file tree:', error);
    fileTreeContainer.innerHTML = '<div class="file-tree-error">加载失败</div>';
  }
}

/**
 * Render the file tree
 */
function renderFileTree() {
  if (!fileTreeData || fileTreeData.length === 0) {
    fileTreeContainer.innerHTML = '<div class="file-tree-empty">暂无文件</div>';
    return;
  }

  const html = fileTreeData.map(item => renderTreeItem(item, 0)).join('');
  fileTreeContainer.innerHTML = `<ul class="file-tree-root">${html}</ul>`;

  // Bind click events
  fileTreeContainer.querySelectorAll('.file-tree-item').forEach(el => {
    el.addEventListener('click', handleItemClick);
  });

  fileTreeContainer.querySelectorAll('.file-tree-toggle').forEach(el => {
    el.addEventListener('click', handleToggleClick);
  });

  fileTreeContainer.querySelectorAll('.file-tree-item').forEach(el => {
    el.addEventListener('dblclick', handleItemDblClick);
  });

  // Bind context menu (right-click)
  fileTreeContainer.querySelectorAll('.file-tree-item').forEach(el => {
    el.addEventListener('contextmenu', handleItemContextMenu);
  });
}

/**
 * Render a single tree item and its children
 * @param {Object} item - Tree item
 * @param {number} depth - Nesting depth
 * @returns {string} HTML string
 */
function renderTreeItem(item, depth) {
  const isFolder = item.type === 'folder';
  const isExpanded = expandedFolders.has(item.id);
  const isSelected = selectedItemId === item.id;
  const hasChildren = item.children && item.children.length > 0;

  const icon = isFolder 
    ? (isExpanded ? '📂' : '📁')
    : getFileIcon(item.name);

  const toggleIcon = isFolder 
    ? (isExpanded ? '▼' : '▶')
    : '<span class="toggle-spacer"></span>';

  const childrenHtml = isFolder && hasChildren
    ? `<ul class="file-tree-children ${isExpanded ? '' : 'hidden'}">
        ${item.children.map(child => renderTreeItem(child, depth + 1)).join('')}
       </ul>`
    : '';

  return `
    <li class="file-tree-node" data-id="${item.id}">
      <div class="file-tree-item ${isSelected ? 'selected' : ''} ${isFolder ? 'folder' : 'file'}"
           data-id="${item.id}"
           data-type="${item.type}"
           data-path="${item.path}"
           style="padding-left: ${depth * 16 + 8}px">
        <span class="file-tree-toggle" data-id="${item.id}">${toggleIcon}</span>
        <span class="file-tree-icon">${icon}</span>
        <span class="file-tree-name">${escapeHtml(item.name)}</span>
      </div>
      ${childrenHtml}
    </li>
  `;
}

/**
 * Get icon for file based on extension
 * @param {string} filename - File name
 * @returns {string} Emoji icon
 */
function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const icons = {
    'md': '📝',
    'txt': '📄',
    'pdf': '📕',
    'doc': '📘',
    'docx': '📘',
    'xls': '📗',
    'xlsx': '📗',
    'ppt': '📙',
    'pptx': '📙',
    'jpg': '🖼️',
    'jpeg': '🖼️',
    'png': '🖼️',
    'gif': '🖼️',
    'svg': '🎨',
    'json': '📋',
    'js': '📜',
    'ts': '📜',
    'py': '🐍',
    'html': '🌐',
    'css': '🎨',
    'zip': '📦',
    'tar': '📦',
    'gz': '📦',
  };
  return icons[ext] || '📄';
}

/**
 * Handle item click
 * @param {Event} e - Click event
 */
function handleItemClick(e) {
  e.stopPropagation();
  
  const itemEl = e.currentTarget;
  const id = itemEl.dataset.id;
  const type = itemEl.dataset.type;
  const path = itemEl.dataset.path;

  // Update selection
  fileTreeContainer.querySelectorAll('.file-tree-item').forEach(el => {
    el.classList.remove('selected');
  });
  itemEl.classList.add('selected');
  selectedItemId = id;

  // Show toolbar for selected item
  fileTreeToolbar.classList.remove('hidden');

  // Dispatch custom event
  const event = new CustomEvent('fileTreeSelect', {
    detail: { id, type, path }
  });
  document.dispatchEvent(event);
}

/**
 * Handle right-click context menu
 * @param {Event} e - Contextmenu event
 */
function handleItemContextMenu(e) {
  e.preventDefault();
  e.stopPropagation();
  
  const itemEl = e.currentTarget;
  const id = itemEl.dataset.id;
  const type = itemEl.dataset.type;
  const path = itemEl.dataset.path;

  // Update selection
  fileTreeContainer.querySelectorAll('.file-tree-item').forEach(el => {
    el.classList.remove('selected');
  });
  itemEl.classList.add('selected');
  selectedItemId = id;

  // Show toolbar for selected item
  fileTreeToolbar.classList.remove('hidden');

  // Show context menu
  showContextMenu(e.clientX, e.clientY, id, type);
}

/**
 * Show context menu at position
 * @param {number} x - X position
 * @param {number} y - Y position
 * @param {string} itemId - Item ID
 * @param {string} itemType - Item type (file/folder)
 */
function showContextMenu(x, y, itemId, itemType) {
  // Remove existing context menu
  hideContextMenu();

  const menu = document.createElement('div');
  menu.id = 'file-tree-context-menu';
  menu.className = 'file-tree-context-menu';
  menu.innerHTML = `
    <div class="context-menu-item" data-action="add-node">
      📌 添加为节点
    </div>
    <div class="context-menu-separator"></div>
    <div class="context-menu-item" data-action="rename">
      ✏️ 重命名
    </div>
    <div class="context-menu-item" data-action="delete">
      🗑️ 删除
    </div>
  `;

  // Position menu
  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;

  // Add click handlers
  menu.querySelectorAll('.context-menu-item').forEach(el => {
    el.addEventListener('click', (e) => {
      const action = el.dataset.action;
      hideContextMenu();
      
      switch (action) {
        case 'add-node':
          addAsNode(itemId);
          break;
        case 'rename':
          renameItem(itemId);
          break;
        case 'delete':
          deleteItem(itemId);
          break;
      }
    });
  });

  document.body.appendChild(menu);

  // Close menu when clicking outside
  setTimeout(() => {
    document.addEventListener('click', hideContextMenu, { once: true });
  }, 0);
}

/**
 * Hide context menu
 */
function hideContextMenu() {
  const menu = document.getElementById('file-tree-context-menu');
  if (menu) {
    menu.remove();
  }
}

/**
 * Handle toggle click (expand/collapse folder)
 * @param {Event} e - Click event
 */
function handleToggleClick(e) {
  e.stopPropagation();
  
  const id = e.currentTarget.dataset.id;
  
  if (expandedFolders.has(id)) {
    expandedFolders.delete(id);
  } else {
    expandedFolders.add(id);
  }

  renderFileTree();
}

/**
 * Handle double click
 * @param {Event} e - Double click event
 */
function handleItemDblClick(e) {
  e.stopPropagation();
  
  const itemEl = e.currentTarget;
  const type = itemEl.dataset.type;
  const path = itemEl.dataset.path;

  // Dispatch custom event
  const event = new CustomEvent('fileTreeOpen', {
    detail: { id: itemEl.dataset.id, type, path }
  });
  document.dispatchEvent(event);
}

/**
 * Create new file or folder
 * @param {string} type - 'file' or 'folder'
 */
async function createNewItem(type) {
  if (!currentProjectId) {
    alert('请先选择项目');
    return;
  }

  const name = prompt(type === 'folder' ? '输入文件夹名称:' : '输入文件名称:');
  if (!name || !name.trim()) return;

  try {
    const response = await fetch(`/api/v1/projects/${currentProjectId}/file-tree/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        name: name.trim(),
        type: type,
        parent_id: selectedItemId && fileTreeData.find(i => i.id === selectedItemId)?.type === 'folder' 
          ? selectedItemId 
          : null,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create item');
    }

    await loadFileTree(currentProjectId);
  } catch (error) {
    console.error('Error creating item:', error);
    alert('创建失败: ' + error.message);
  }
}

/**
 * Rename an item
 * @param {string} itemId - Item ID
 */
async function renameItem(itemId) {
  const item = findItem(fileTreeData, itemId);
  if (!item) return;

  const newName = prompt('输入新名称:', item.name);
  if (!newName || !newName.trim() || newName === item.name) return;

  try {
    const response = await fetch(
      `/api/v1/projects/${currentProjectId}/file-tree/items/${itemId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: newName.trim() }),
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to rename item');
    }

    await loadFileTree(currentProjectId);
  } catch (error) {
    console.error('Error renaming item:', error);
    alert('重命名失败: ' + error.message);
  }
}

/**
 * Delete an item
 * @param {string} itemId - Item ID
 */
async function deleteItem(itemId) {
  const item = findItem(fileTreeData, itemId);
  if (!item) return;

  const message = item.type === 'folder'
    ? `确定删除文件夹 "${item.name}" 及其所有内容?`
    : `确定删除文件 "${item.name}"?`;

  if (!confirm(message)) return;

  try {
    const response = await fetch(
      `/api/v1/projects/${currentProjectId}/file-tree/items/${itemId}`,
      {
        method: 'DELETE',
        credentials: 'include',
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete item');
    }

    selectedItemId = null;
    fileTreeToolbar.classList.add('hidden');
    await loadFileTree(currentProjectId);
  } catch (error) {
    console.error('Error deleting item:', error);
    alert('删除失败: ' + error.message);
  }
}

/**
 * Add selected file/folder as a node in the mind map
 * @param {string} itemId - Item ID
 */
function addAsNode(itemId) {
  const item = findItem(fileTreeData, itemId);
  if (!item) return;

  const node = fileTreeItemToNode(item);
  
  // Dispatch custom event for main.js to handle
  const event = new CustomEvent('fileTreeAddAsNode', {
    detail: { item, node }
  });
  document.dispatchEvent(event);
}

/**
 * Convert a file tree item to a mind map node structure
 * @param {Object} item - File tree item
 * @returns {Object} Mind map node
 */
function fileTreeItemToNode(item) {
  const isFolder = item.type === 'folder';
  const icon = isFolder ? '📁' : getFileIcon(item.name);
  
  const node = {
    id: `node-${item.id}`,
    topic: `${icon} ${item.name}`,
    memo: item.path,
  };

  // Recursively convert children for folders
  if (isFolder && item.children && item.children.length > 0) {
    node.children = item.children.map(child => fileTreeItemToNode(child));
  }

  return node;
}

/**
 * Find item in tree by ID
 * @param {Array} items - Tree items
 * @param {string} id - Item ID
 * @returns {Object|null} Found item or null
 */
function findItem(items, id) {
  for (const item of items) {
    if (item.id === id) return item;
    if (item.children) {
      const found = findItem(item.children, id);
      if (found) return found;
    }
  }
  return null;
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Get current project ID
 * @returns {string|null}
 */
export function getCurrentProjectId() {
  return currentProjectId;
}

/**
 * Set current project and load tree
 * @param {string} projectId
 */
export function setProject(projectId) {
  loadFileTree(projectId);
}

/**
 * Get selected item
 * @returns {Object|null}
 */
export function getSelectedItem() {
  if (!selectedItemId) return null;
  return findItem(fileTreeData, selectedItemId);
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initFileTree);
} else {
  initFileTree();
}
