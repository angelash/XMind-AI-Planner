/**
 * History Manager Module
 * GAP-01: 撤销/重做+快捷键
 *
 * Provides undo/redo functionality for mind map operations with:
 * - Command pattern for reversible operations
 * - Undo/redo stacks with configurable depth
 * - Keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y)
 * - Toolbar buttons integration
 */

// History configuration
const MAX_HISTORY_DEPTH = 50;

// State
let undoStack = [];
let redoStack = [];
let mindInstance = null;

// Command types
export const CommandType = {
  ADD_CHILD: "addChild",
  EDIT_NODE: "editNode",
  DELETE_NODE: "deleteNode",
  UPDATE_NODE_TOPIC: "updateNodeTopic",
  MOVE_NODE: "moveNode",
};

/**
 * Initialize the history manager
 * @param {Object} mind - MindElixir instance
 */
export function initHistoryManager(mind) {
  mindInstance = mind;
  bindKeyboardShortcuts();
  updateButtonStates();
}

/**
 * Create a command object for an operation
 * @param {string} type - Command type
 * @param {Object} data - Command data
 * @returns {Object} - Command object with execute/undo functions
 */
export function createCommand(type, data) {
  switch (type) {
    case CommandType.ADD_CHILD:
      return createAddChildCommand(data);
    case CommandType.EDIT_NODE:
      return createEditNodeCommand(data);
    case CommandType.DELETE_NODE:
      return createDeleteNodeCommand(data);
    case CommandType.UPDATE_NODE_TOPIC:
      return createUpdateNodeTopicCommand(data);
    case CommandType.MOVE_NODE:
      return createMoveNodeCommand(data);
    default:
      console.warn(`Unknown command type: ${type}`);
      return null;
  }
}

/**
 * Create add child command
 */
function createAddChildCommand(data) {
  const { parentNode, child, previousChildren } = data;
  return {
    type: CommandType.ADD_CHILD,
    description: `Add child "${child.topic || child.id}"`,
    data: { parentNode, child, previousChildren },
    execute: () => {
      // Already executed when command is created
    },
    undo: () => {
      if (mindInstance && parentNode) {
        // Remove the child from parent's children
        const idx = parentNode.children?.findIndex((c) => c.id === child.id);
        if (idx !== undefined && idx >= 0) {
          parentNode.children.splice(idx, 1);
          if (typeof mindInstance.refresh === "function") {
            mindInstance.refresh();
          }
        }
      }
    },
    redo: () => {
      if (mindInstance && parentNode && child) {
        parentNode.children = parentNode.children || [];
        parentNode.children.push(child);
        if (typeof mindInstance.refresh === "function") {
          mindInstance.refresh();
        }
      }
    },
  };
}

/**
 * Create edit node command
 */
function createEditNodeCommand(data) {
  const { node, oldTopic, newTopic } = data;
  return {
    type: CommandType.EDIT_NODE,
    description: `Edit node "${node.id}"`,
    data: { node, oldTopic, newTopic },
    execute: () => {
      // Already executed
    },
    undo: () => {
      if (node && oldTopic !== undefined) {
        node.topic = oldTopic;
        if (mindInstance && typeof mindInstance.refresh === "function") {
          mindInstance.refresh();
        }
      }
    },
    redo: () => {
      if (node && newTopic !== undefined) {
        node.topic = newTopic;
        if (mindInstance && typeof mindInstance.refresh === "function") {
          mindInstance.refresh();
        }
      }
    },
  };
}

/**
 * Create delete node command
 */
function createDeleteNodeCommand(data) {
  const { node, parent, index, children } = data;
  return {
    type: CommandType.DELETE_NODE,
    description: `Delete node "${node?.topic || node?.id}"`,
    data: { node, parent, index, children },
    execute: () => {
      // Already executed
    },
    undo: () => {
      // Restore the node at its original position
      if (parent && node) {
        parent.children = parent.children || [];
        parent.children.splice(index, 0, node);
        if (children) {
          node.children = children;
        }
        if (mindInstance && typeof mindInstance.refresh === "function") {
          mindInstance.refresh();
        }
      }
    },
    redo: () => {
      // Remove the node again
      if (parent && node) {
        const idx = parent.children?.findIndex((c) => c.id === node.id);
        if (idx !== undefined && idx >= 0) {
          parent.children.splice(idx, 1);
          if (mindInstance && typeof mindInstance.refresh === "function") {
            mindInstance.refresh();
          }
        }
      }
    },
  };
}

/**
 * Create move node command
 */
function createMoveNodeCommand(data) {
  const { targetNode, oldParent, oldIndex, newParent, newIndex } = data;
  return {
    type: CommandType.MOVE_NODE,
    description: `Move node "${targetNode?.topic || targetNode?.id}"`,
    data: { targetNode, oldParent, oldIndex, newParent, newIndex },
    execute: () => {
      // Already executed when command is created
    },
    undo: () => {
      // Move node back to original parent and position
      if (mindInstance && targetNode && oldParent && newParent) {
        // Remove from current parent
        const currentIdx = newParent.children?.findIndex((c) => c.id === targetNode.id);
        if (currentIdx !== undefined && currentIdx >= 0) {
          newParent.children.splice(currentIdx, 1);
        }

        // Restore to old parent
        oldParent.children = oldParent.children || [];
        oldParent.children.splice(oldIndex, 0, targetNode);

        if (typeof mindInstance.refresh === "function") {
          mindInstance.refresh();
        }
      }
    },
    redo: () => {
      // Move node again to new parent and position
      if (mindInstance && targetNode && oldParent && newParent) {
        // Remove from old parent
        oldParent.children = oldParent.children || [];
        const oldIdx = oldParent.children.findIndex((c) => c.id === targetNode.id);
        if (oldIdx >= 0) {
          oldParent.children.splice(oldIdx, 1);
        }

        // Add to new parent
        newParent.children = newParent.children || [];
        const finalIndex = Math.min(Math.max(0, newIndex), newParent.children.length);
        newParent.children.splice(finalIndex, 0, targetNode);

        if (typeof mindInstance.refresh === "function") {
          mindInstance.refresh();
        }
      }
    },
  };
}

/**
 * Create update node topic command
 */
function createUpdateNodeTopicCommand(data) {
  const { node, oldTopic, newTopic } = data;
  return createEditNodeCommand(data);
}

/**
 * Execute a command and add to history
 * @param {Object} command - Command object
 */
export function executeCommand(command) {
  if (!command) return;

  // Clear redo stack when new command is executed
  redoStack = [];

  // Add to undo stack
  undoStack.push(command);

  // Limit stack depth
  if (undoStack.length > MAX_HISTORY_DEPTH) {
    undoStack.shift();
  }

  updateButtonStates();
}

/**
 * Undo the last command
 * @returns {Object|null} - The undone command or null
 */
export function undo() {
  if (!canUndo()) {
    console.log("Nothing to undo");
    return null;
  }

  const command = undoStack.pop();
  if (command && typeof command.undo === "function") {
    command.undo();
    redoStack.push(command);

    // Emit event for status updates
    if (mindInstance && mindInstance.bus) {
      mindInstance.bus.emit("historyUndo", command);
    }
  }

  updateButtonStates();
  return command;
}

/**
 * Redo the last undone command
 * @returns {Object|null} - The redone command or null
 */
export function redo() {
  if (!canRedo()) {
    console.log("Nothing to redo");
    return null;
  }

  const command = redoStack.pop();
  if (command && typeof command.redo === "function") {
    command.redo();
    undoStack.push(command);

    // Emit event for status updates
    if (mindInstance && mindInstance.bus) {
      mindInstance.bus.emit("historyRedo", command);
    }
  }

  updateButtonStates();
  return command;
}

/**
 * Check if undo is available
 */
export function canUndo() {
  return undoStack.length > 0;
}

/**
 * Check if redo is available
 */
export function canRedo() {
  return redoStack.length > 0;
}

/**
 * Get undo stack size
 */
export function getUndoCount() {
  return undoStack.length;
}

/**
 * Get redo stack size
 */
export function getRedoCount() {
  return redoStack.length;
}

/**
 * Clear all history
 */
export function clearHistory() {
  undoStack = [];
  redoStack = [];
  updateButtonStates();
}

/**
 * Update toolbar button states
 */
function updateButtonStates() {
  const undoBtn = document.getElementById("btn-undo");
  const redoBtn = document.getElementById("btn-redo");

  if (undoBtn) {
    undoBtn.disabled = !canUndo();
    undoBtn.title = canUndo()
      ? `Undo: ${undoStack[undoStack.length - 1]?.description || ""}`
      : "Nothing to undo";
  }

  if (redoBtn) {
    redoBtn.disabled = !canRedo();
    redoBtn.title = canRedo()
      ? `Redo: ${redoStack[redoStack.length - 1]?.description || ""}`
      : "Nothing to redo";
  }
}

/**
 * Bind keyboard shortcuts
 */
function bindKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Check for Ctrl/Cmd key
    const isModifier = e.ctrlKey || e.metaKey;

    if (!isModifier) return;

    // Ctrl+Z or Cmd+Z for undo (no shift)
    if ((e.key === "z" || e.key === "Z") && !e.shiftKey) {
      e.preventDefault();
      const cmd = undo();
      if (cmd) {
        console.log("Undo:", cmd.description);
      }
      return;
    }

    // Ctrl+Shift+Z or Cmd+Shift+Z for redo
    if ((e.key === "z" || e.key === "Z") && e.shiftKey) {
      e.preventDefault();
      const cmd = redo();
      if (cmd) {
        console.log("Redo:", cmd.description);
      }
      return;
    }

    // Ctrl+Y or Cmd+Y for redo (alternative)
    if (e.key === "y" || e.key === "Y") {
      e.preventDefault();
      const cmd = redo();
      if (cmd) {
        console.log("Redo:", cmd.description);
      }
      return;
    }
  });
}

/**
 * Bind toolbar buttons
 */
export function bindToolbarButtons() {
  const undoBtn = document.getElementById("btn-undo");
  const redoBtn = document.getElementById("btn-redo");

  undoBtn?.addEventListener("click", () => {
    const cmd = undo();
    if (cmd) {
      console.log("Undo:", cmd.description);
    }
  });

  redoBtn?.addEventListener("click", () => {
    const cmd = redo();
    if (cmd) {
      console.log("Redo:", cmd.description);
    }
  });
}

/**
 * Get history state for debugging
 */
export function getHistoryState() {
  return {
    undoCount: undoStack.length,
    redoCount: redoStack.length,
    canUndo: canUndo(),
    canRedo: canRedo(),
    undoStack: undoStack.map((c) => c.description),
    redoStack: redoStack.map((c) => c.description),
  };
}
