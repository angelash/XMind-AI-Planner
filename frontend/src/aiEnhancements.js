/**
 * AI Enhancements Module
 * GAP-09: AI 增强（绘图/染色/翻译）
 *
 * Provides UI for:
 * - Text translation
 * - ASCII diagram generation
 * - Node color suggestions
 */

// API base URL (adjust as needed)
const API_BASE_URL = "/api/v1";

// Track selected node
let selectedNodeId = null;
let selectedNodeText = null;

/**
 * Get API headers with auth token
 */
function getAuthHeaders() {
  const headers = {
    "Content-Type": "application/json",
  };

  // Add auth token if available (from cookie or localStorage)
  const token = localStorage.getItem("auth_token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Handle API errors
 */
function handleApiError(error, context = "API call") {
  console.error(`${context} failed:`, error);

  // Show error message in status or alert
  const statusEl = document.getElementById("editor-status");
  if (statusEl) {
    statusEl.textContent = `Error: ${error.message || context}`;
    statusEl.classList.add("error");

    // Clear error after 3 seconds
    setTimeout(() => {
      statusEl.classList.remove("error");
      statusEl.textContent = "No node selected";
    }, 3000);
  }

  throw error;
}

/**
 * Translate node text
 */
export async function translateNode(nodeId, text, targetLanguage, sourceLanguage = "auto") {
  const response = await fetch(`${API_BASE_URL}/ai/translate`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      text,
      target_language: targetLanguage,
      source_language: sourceLanguage,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Translation failed");
  }

  return await response.json();
}

/**
 * Generate ASCII diagram from node text
 */
export async function generateDiagram(nodeId, text, diagramType = "flowchart") {
  const response = await fetch(`${API_BASE_URL}/ai/diagram`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      node_text: text,
      diagram_type: diagramType,
      node_id: nodeId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Diagram generation failed");
  }

  return await response.json();
}

/**
 * Suggest color for a node
 */
export async function suggestColor(nodeId, text) {
  const response = await fetch(`${API_BASE_URL}/ai/color-suggestion`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      node_text: text,
      node_id: nodeId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Color suggestion failed");
  }

  return await response.json();
}

/**
 * Show translation dialog
 */
export function showTranslationDialog(nodeId, text) {
  const modal = createModal({
    title: "翻译节点文本",
    content: `
      <div class="form-group">
        <label for="target-language">目标语言</label>
        <select id="target-language" class="form-control">
          <option value="中文">中文</option>
          <option value="English">English</option>
          <option value="日本語">日本語</option>
          <option value="한국어">한국어</option>
          <option value="Français">Français</option>
          <option value="Deutsch">Deutsch</option>
          <option value="Español">Español</option>
        </select>
      </div>
      <div class="form-group">
        <label>原文</label>
        <div class="translation-original">${text}</div>
      </div>
      <div class="form-group">
        <label>译文</label>
        <div id="translation-result" class="translation-result">
          <span class="loading">翻译中...</span>
        </div>
      </div>
    `,
    buttons: [
      {
        text: "应用",
        class: "btn-primary",
        onClick: async () => {
          const targetLanguage = document.getElementById("target-language").value;
          const resultEl = document.getElementById("translation-result");

          try {
            const result = await translateNode(nodeId, text, targetLanguage);
            resultEl.innerHTML = `<span class="translated-text">${result.translated_text}</span>`;

            // Return the translated text for the caller
            return result.translated_text;
          } catch (error) {
            resultEl.innerHTML = `<span class="error">翻译失败: ${error.message}</span>`;
            return null;
          }
        },
      },
      {
        text: "关闭",
        class: "btn-secondary",
        onClick: () => closeModal(),
      },
    ],
  });

  return modal;
}

/**
 * Show diagram dialog
 */
export function showDiagramDialog(nodeId, text) {
  const modal = createModal({
    title: "生成图表",
    content: `
      <div class="form-group">
        <label for="diagram-type">图表类型</label>
        <select id="diagram-type" class="form-control">
          <option value="flowchart">流程图</option>
          <option value="tree">树状图</option>
          <option value="process">流程图（简化）</option>
        </select>
      </div>
      <div class="form-group">
        <label>节点内容</label>
        <div class="diagram-source">${text}</div>
      </div>
      <div class="form-group">
        <label>生成的图表</label>
        <div id="diagram-result" class="diagram-result">
          <span class="loading">生成中...</span>
        </div>
      </div>
    `,
    buttons: [
      {
        text: "生成",
        class: "btn-primary",
        onClick: async () => {
          const diagramType = document.getElementById("diagram-type").value;
          const resultEl = document.getElementById("diagram-result");

          try {
            const result = await generateDiagram(nodeId, text, diagramType);
            resultEl.innerHTML = `<pre class="diagram-ascii">${escapeHtml(result.diagram)}</pre>`;
          } catch (error) {
            resultEl.innerHTML = `<span class="error">生成失败: ${error.message}</span>`;
          }
        },
      },
      {
        text: "关闭",
        class: "btn-secondary",
        onClick: () => closeModal(),
      },
    ],
  });

  return modal;
}

/**
 * Show color suggestion dialog
 */
export function showColorSuggestionDialog(nodeId, text) {
  const modal = createModal({
    title: "建议节点颜色",
    content: `
      <div class="form-group">
        <label>节点内容</label>
        <div class="color-source">${text}</div>
      </div>
      <div class="form-group">
        <label>建议的颜色</label>
        <div id="color-result" class="color-result">
          <span class="loading">分析中...</span>
        </div>
      </div>
    `,
    buttons: [
      {
        text: "获取建议",
        class: "btn-primary",
        onClick: async () => {
          const resultEl = document.getElementById("color-result");

          try {
            const result = await suggestColor(nodeId, text);
            resultEl.innerHTML = `
              <div class="color-suggestion">
                <div class="color-preview" style="background-color: ${result.suggested_color}"></div>
                <div class="color-info">
                  <strong>建议颜色:</strong> <span class="color-code">${result.suggested_color}</span><br>
                  <strong>原因:</strong> ${escapeHtml(result.reason)}
                </div>
              </div>
            `;
          } catch (error) {
            resultEl.innerHTML = `<span class="error">获取失败: ${error.message}</span>`;
          }
        },
      },
      {
        text: "关闭",
        class: "btn-secondary",
        onClick: () => closeModal(),
      },
    ],
  });

  return modal;
}

/**
 * Create a modal dialog
 */
function createModal({ title, content, buttons = [] }) {
  const modalId = `modal-${Date.now()}`;
  const modal = document.createElement("div");
  modal.id = modalId;
  modal.className = "modal";
  modal.innerHTML = `
    <div class="modal-content">
      <div class="modal-header">
        <h2>${escapeHtml(title)}</h2>
        <button class="btn-close" data-dismiss="modal">&times;</button>
      </div>
      <div class="modal-body">
        ${content}
      </div>
      <div class="modal-footer">
        ${buttons.map((btn, index) => `
          <button type="button" class="btn ${btn.class || ''}" data-btn-index="${index}">
            ${escapeHtml(btn.text)}
          </button>
        `).join("")}
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  // Bind button events
  modal.querySelector('.btn-close').addEventListener('click', () => closeModal());

  buttons.forEach((btn, index) => {
    const buttonEl = modal.querySelector(`[data-btn-index="${index}"]`);
    if (buttonEl && btn.onClick) {
      buttonEl.addEventListener('click', () => {
        btn.onClick(modal);
      });
    }
  });

  // Show modal
  setTimeout(() => modal.classList.remove('hidden'), 0);

  return modal;
}

/**
 * Close modal dialog
 */
function closeModal() {
  const modals = document.querySelectorAll('.modal:not(.hidden)');
  modals.forEach(modal => {
    modal.classList.add('hidden');
    setTimeout(() => modal.remove(), 300);
  });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Initialize AI enhancements (add buttons to toolbar)
 */
export function initAIEnhancements() {
  // Find the toolbar
  const toolbar = document.querySelector('.editor-toolbar');
  if (!toolbar) {
    console.warn("Toolbar not found, AI enhancements buttons not added");
    return;
  }

  // Create a divider
  const divider = document.createElement('span');
  divider.className = 'toolbar-divider';
  toolbar.appendChild(divider);

  // Create translate button
  const translateBtn = document.createElement('button');
  translateBtn.id = 'btn-translate-node';
  translateBtn.type = 'button';
  translateBtn.textContent = '翻译';
  translateBtn.title = '翻译选中的节点文本';
  translateBtn.disabled = true;
  toolbar.appendChild(translateBtn);

  // Create diagram button
  const diagramBtn = document.createElement('button');
  diagramBtn.id = 'btn-generate-diagram';
  diagramBtn.type = 'button';
  diagramBtn.textContent = '生成图表';
  diagramBtn.title = '从节点内容生成图表';
  diagramBtn.disabled = true;
  toolbar.appendChild(diagramBtn);

  // Create color suggestion button
  const colorBtn = document.createElement('button');
  colorBtn.id = 'btn-suggest-color';
  colorBtn.type = 'button';
  colorBtn.textContent = '建议颜色';
  colorBtn.title = '基于内容建议节点颜色';
  colorBtn.disabled = true;
  toolbar.appendChild(colorBtn);

  // Bind button events
  translateBtn.addEventListener('click', () => {
    if (selectedNodeId && selectedNodeText) {
      showTranslationDialog(selectedNodeId, selectedNodeText);
    }
  });

  diagramBtn.addEventListener('click', () => {
    if (selectedNodeId && selectedNodeText) {
      showDiagramDialog(selectedNodeId, selectedNodeText);
    }
  });

  colorBtn.addEventListener('click', () => {
    if (selectedNodeId && selectedNodeText) {
      showColorSuggestionDialog(selectedNodeId, selectedNodeText);
    }
  });

  return {
    updateSelectedNode(nodeId, text) {
      selectedNodeId = nodeId;
      selectedNodeText = text;

      const enabled = !!(nodeId && text);
      translateBtn.disabled = !enabled;
      diagramBtn.disabled = !enabled;
      colorBtn.disabled = !enabled;
    },
  };
}
