/**
 * Agent Panel Module
 * AG-01: Agent 面板 UI
 *
 * Provides a Cursor-style AI assistant panel with:
 * - Draggable resize handle (300-600px, default 400px)
 * - Linear message flow
 * - Context tags for selected nodes
 * - Pending changes operation bar
 * - Multiline input with Enter to send
 */

// Panel state
let panelEl = null;
let resizeHandle = null;
let messagesEl = null;
let inputEl = null;
let contextTagsEl = null;
let operationBar = null;
let pendingCountEl = null;

let isPanelOpen = true;
let isDragging = false;
let currentWidth = 400;
let contextNodeId = null;
let contextNodeText = null;
let pendingChanges = [];

// Constraints
const MIN_WIDTH = 300;
const MAX_WIDTH = 600;
const DEFAULT_WIDTH = 400;

/**
 * Initialize the agent panel
 */
export function initAgentPanel() {
  panelEl = document.getElementById("agent-panel");
  resizeHandle = document.getElementById("agent-resize-handle");
  messagesEl = document.getElementById("agent-messages");
  inputEl = document.getElementById("agent-input");
  contextTagsEl = document.getElementById("agent-context-tags");
  operationBar = document.getElementById("agent-operation-bar");
  pendingCountEl = document.getElementById("agent-pending-count");

  if (!panelEl) {
    console.warn("Agent panel element not found");
    return;
  }

  // Load persisted state
  loadPersistedState();

  // Set initial width
  panelEl.style.width = `${currentWidth}px`;
  syncCanvasMargin();

  // Bind events
  bindToggleEvent();
  bindResizeEvents();
  bindInputEvents();
  bindHeaderButtons();
  bindOperationButtons();
}

/**
 * Load persisted panel state from localStorage
 */
function loadPersistedState() {
  try {
    const saved = localStorage.getItem("agent-panel-state");
    if (saved) {
      const state = JSON.parse(saved);
      if (typeof state.width === "number") {
        currentWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, state.width));
      }
      if (typeof state.isOpen === "boolean") {
        isPanelOpen = state.isOpen;
      }
    }
  } catch {
    // Ignore parse errors
  }

  if (!isPanelOpen) {
    panelEl?.classList.add("collapsed");
  }
}

/**
 * Save panel state to localStorage
 */
function savePersistedState() {
  try {
    localStorage.setItem(
      "agent-panel-state",
      JSON.stringify({
        width: currentWidth,
        isOpen: isPanelOpen,
      })
    );
  } catch {
    // Ignore storage errors
  }
}

/**
 * Toggle panel visibility
 */
export function togglePanel() {
  isPanelOpen = !isPanelOpen;
  panelEl?.classList.toggle("collapsed", !isPanelOpen);
  syncCanvasMargin();
  savePersistedState();
}

/**
 * Resize panel to a specific width
 */
export function resizePanel(width) {
  currentWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width));
  if (panelEl) {
    panelEl.style.width = `${currentWidth}px`;
  }
  syncCanvasMargin();
  savePersistedState();
}

/**
 * Sync canvas right margin with panel width
 */
function syncCanvasMargin() {
  const mainEl = document.querySelector(".editor-main");
  if (mainEl) {
    mainEl.style.marginRight = isPanelOpen ? `${currentWidth}px` : "0";
  }
}

/**
 * Bind toggle button event
 */
function bindToggleEvent() {
  const toggleBtn = document.getElementById("btn-agent-toggle");
  toggleBtn?.addEventListener("click", togglePanel);
}

/**
 * Bind resize handle drag events
 */
function bindResizeEvents() {
  if (!resizeHandle) return;

  resizeHandle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    isDragging = true;
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const newWidth = document.body.clientWidth - e.clientX;
    resizePanel(newWidth);
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
  });
}

/**
 * Bind input area events
 */
function bindInputEvents() {
  if (!inputEl) return;

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize textarea
  inputEl.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
  });
}

/**
 * Bind header button events
 */
function bindHeaderButtons() {
  const newBtn = document.getElementById("btn-agent-new");
  const historyBtn = document.getElementById("btn-agent-history");

  newBtn?.addEventListener("click", () => {
    // TODO: Implement new conversation
    console.log("New conversation");
  });

  historyBtn?.addEventListener("click", () => {
    // TODO: Implement history modal
    console.log("Show history");
  });
}

/**
 * Bind operation bar button events
 */
function bindOperationButtons() {
  const undoAllBtn = document.getElementById("btn-agent-undo-all");
  const keepAllBtn = document.getElementById("btn-agent-keep-all");

  undoAllBtn?.addEventListener("click", undoAllChanges);
  keepAllBtn?.addEventListener("click", keepAllChanges);
}

/**
 * Set the context node (when a node is selected in the mind map)
 */
export function setContextNode(nodeId, nodeText) {
  contextNodeId = nodeId;
  contextNodeText = nodeText;
  renderContextTags();
}

/**
 * Clear the context node
 */
export function clearContextNode() {
  contextNodeId = null;
  contextNodeText = null;
  renderContextTags();
}

/**
 * Render context tags above the input
 */
function renderContextTags() {
  if (!contextTagsEl) return;

  if (contextNodeId && contextNodeText) {
    const tag = document.createElement("span");
    tag.className = "agent-context-tag";
    tag.innerHTML = `@ ${escapeHtml(contextNodeText)}`;
    tag.addEventListener("click", clearContextNode);
    contextTagsEl.innerHTML = "";
    contextTagsEl.appendChild(tag);
  } else {
    contextTagsEl.innerHTML = "";
  }
}

/**
 * Add a message to the message list
 * @param {Object} message - Message object with type and content
 */
export function addMessage(message) {
  if (!messagesEl) return;

  const { type, content, id } = message;
  const msgEl = document.createElement("div");
  msgEl.className = `agent-message agent-message-${type}`;
  if (id) {
    msgEl.dataset.messageId = id;
  }

  const contentEl = document.createElement("div");
  contentEl.className = "agent-message-content";
  contentEl.innerHTML = formatContent(content);

  msgEl.appendChild(contentEl);
  messagesEl.appendChild(msgEl);

  // Scroll to bottom
  messagesEl.scrollTop = messagesEl.scrollHeight;

  return msgEl;
}

/**
 * Format message content with basic markdown
 */
function formatContent(content) {
  if (!content) return "";
  let formatted = escapeHtml(content);
  // Bold: **text**
  formatted = formatted.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Inline code: `code`
  formatted = formatted.replace(/`(.+?)`/g, "<code>$1</code>");
  // Line breaks
  formatted = formatted.replace(/\n/g, "<br>");
  return formatted;
}

/**
 * Update the pending changes count
 */
export function updatePendingCount(count) {
  if (pendingCountEl) {
    pendingCountEl.textContent = `${count} change${count !== 1 ? "s" : ""}`;
  }
  if (operationBar) {
    operationBar.classList.toggle("hidden", count === 0);
  }
}

/**
 * Send the current input message
 */
function sendMessage() {
  if (!inputEl) return;

  const content = inputEl.value.trim();
  if (!content) return;

  // Add user message
  addMessage({ type: "user", content });

  // Clear input
  inputEl.value = "";
  inputEl.style.height = "auto";

  // TODO: Actually send to backend API
  console.log("Send message:", { content, contextNodeId });
}

/**
 * Undo all pending changes
 */
function undoAllChanges() {
  pendingChanges = [];
  updatePendingCount(0);
  // TODO: Implement actual undo logic
  console.log("Undo all changes");
}

/**
 * Keep all pending changes
 */
function keepAllChanges() {
  pendingChanges = [];
  updatePendingCount(0);
  // TODO: Implement actual keep logic
  console.log("Keep all changes");
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

// Auto-initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initAgentPanel);
} else {
  initAgentPanel();
}
