import { toMindElixirDocument } from "./nodeModel.js";
import { setContextNode, clearContextNode } from "./agent.js";
import { setProject as setMdEditorProject } from "./mdEditor.js";
import {
  initHistoryManager,
  createCommand,
  executeCommand,
  bindToolbarButtons,
  CommandType,
} from "./history.js";

const mount = document.getElementById("mindmap");
const fallback = document.getElementById("fallback");
const statusEl = document.getElementById("editor-status");

const controls = {
  addChild: document.getElementById("btn-add-child"),
  editNode: document.getElementById("btn-edit-node"),
  deleteNode: document.getElementById("btn-delete-node"),
  toggleFold: document.getElementById("btn-toggle-fold"),
  moveNode: document.getElementById("btn-move-node"),
  zoomIn: document.getElementById("btn-zoom-in"),
  zoomOut: document.getElementById("btn-zoom-out"),
  center: document.getElementById("btn-center"),
};

const defaultNode = {
  id: "node-root",
  text: "XMind AI Planner",
  children: [
    {
      id: "node-child-1",
      text: "First Idea",
      memo: "Initial example branch",
    },
  ],
};

let mind = null;
let selectedNode = null;

function showFallback(message) {
  fallback.textContent = message;
  fallback.classList.remove("hidden");
}

function setStatus(text) {
  if (statusEl) {
    statusEl.textContent = text;
  }
}

function getActiveNode() {
  if (selectedNode) {
    return selectedNode;
  }
  if (mind && mind.nodeData) {
    return mind.nodeData;
  }
  return null;
}

function refreshNodeLabel() {
  const node = getActiveNode();
  if (!node) {
    setStatus("No node selected");
    return;
  }
  const topic = node.topic || "(empty)";
  setStatus(`Selected: ${topic}`);
}

function installSelectionListener() {
  if (!mind || !mind.bus || typeof mind.bus.addListener !== "function") {
    refreshNodeLabel();
    return;
  }
  mind.bus.addListener("selectNode", (node) => {
    selectedNode = node || null;
    refreshNodeLabel();
    // Update agent panel context
    if (node && node.id && node.topic) {
      setContextNode(node.id, node.topic);
    } else {
      clearContextNode();
    }
  });
}

function addChildNode() {
  const parentNode = getActiveNode();
  if (!parentNode) {
    setStatus("Cannot add child: no active node");
    return;
  }
  const child = {
    id: `node-${Date.now()}`,
    topic: "New Node",
  };

  // Store previous state for undo
  const previousChildren = parentNode.children ? [...parentNode.children] : [];

  if (typeof mind.addChild === "function") {
    mind.addChild(parentNode, child);
  } else {
    parentNode.children = parentNode.children || [];
    parentNode.children.push(child);
    if (typeof mind.refresh === "function") {
      mind.refresh();
    }
  }

  // Create and execute history command
  const command = createCommand(CommandType.ADD_CHILD, {
    parentNode,
    child,
    previousChildren,
  });
  if (command) {
    executeCommand(command);
  }

  refreshNodeLabel();
}

function editNodeText() {
  const node = getActiveNode();
  if (!node) {
    setStatus("Cannot edit: no active node");
    return;
  }

  if (typeof mind.beginEdit === "function") {
    mind.beginEdit(node);
    return;
  }

  const oldTopic = node.topic || "";
  const nextText = window.prompt("Edit node text", oldTopic);
  if (!nextText || nextText === oldTopic) {
    return;
  }
  if (typeof mind.updateNode === "function") {
    mind.updateNode(node.id, nextText);
  } else {
    node.topic = nextText;
    if (typeof mind.refresh === "function") {
      mind.refresh();
    }
  }

  // Create and execute history command
  const command = createCommand(CommandType.EDIT_NODE, {
    node,
    oldTopic,
    newTopic: nextText,
  });
  if (command) {
    executeCommand(command);
  }

  refreshNodeLabel();
}

function deleteNode() {
  const node = getActiveNode();
  if (!node) {
    setStatus("Cannot delete: no active node");
    return;
  }
  if (node.root) {
    setStatus("Root node cannot be deleted");
    return;
  }

  // Find parent and index for undo
  let parent = null;
  let index = -1;
  if (mind && mind.nodeData) {
    const findParent = (current, target, p) => {
      if (!current || !current.children) return false;
      for (let i = 0; i < current.children.length; i++) {
        if (current.children[i] === target) {
          parent = current;
          index = i;
          return true;
        }
        if (findParent(current.children[i], target, current.children[i])) {
          return true;
        }
      }
      return false;
    };
    findParent(mind.nodeData, node, null);
  }

  const children = node.children ? [...node.children] : null;

  if (typeof mind.removeNode === "function") {
    mind.removeNode(node);
  } else {
    setStatus("Delete is not available in current MindElixir build");
    return;
  }

  // Create and execute history command
  if (parent) {
    const command = createCommand(CommandType.DELETE_NODE, {
      node,
      parent,
      index,
      children,
    });
    if (command) {
      executeCommand(command);
    }
  }

  selectedNode = null;
  refreshNodeLabel();
}

function toggleFold() {
  const node = getActiveNode();
  if (!node) {
    return;
  }
  const hasExpand = typeof mind.expandNode === "function";
  const hasCollapse = typeof mind.collapseNode === "function";
  if (!hasExpand || !hasCollapse) {
    setStatus("Fold controls are not available in current MindElixir build");
    return;
  }
  if (node.expanded === false) {
    mind.expandNode(node);
    node.expanded = true;
  } else {
    mind.collapseNode(node);
    node.expanded = false;
  }
}

function moveNode() {
  const targetNode = getActiveNode();
  if (!targetNode) {
    setStatus("Cannot move: no active node");
    return;
  }
  if (targetNode.root) {
    setStatus("Root node cannot be moved");
    return;
  }

  // Find current parent
  let oldParent = null;
  let oldIndex = -1;
  if (mind && mind.nodeData) {
    const findParent = (current, target, p) => {
      if (!current || !current.children) return false;
      for (let i = 0; i < current.children.length; i++) {
        if (current.children[i] === target) {
          oldParent = current;
          oldIndex = i;
          return true;
        }
        if (findParent(current.children[i], target, current.children[i])) {
          return true;
        }
      }
      return false;
    };
    findParent(mind.nodeData, targetNode, null);
  }

  if (!oldParent) {
    setStatus("Could not find parent node");
    return;
  }

  // Get target node ID to move to (simplified: prompt for sibling/cross-parent)
  const moveType = window.prompt(
    "Move type:\n1. Reorder in current parent (sibling)\n2. Move to different parent (cross-parent)\nEnter 1 or 2:",
    "1"
  );

  let newParentNode = null;
  let newIndex = 0;

  if (moveType === "1") {
    // Sibling reordering
    const newIndexInput = window.prompt(
      `Current position: ${oldIndex}\nEnter new index (0-${oldParent.children.length - 1}):`,
      String(oldIndex)
    );
    newIndex = parseInt(newIndexInput, 10);

    if (isNaN(newIndex) || newIndex === oldIndex) {
      setStatus("Move cancelled");
      return;
    }

    newParentNode = oldParent;
  } else if (moveType === "2") {
    // Cross-parent move - find target parent
    const targetParentId = window.prompt("Enter target parent node ID:");
    if (!targetParentId) {
      setStatus("Move cancelled");
      return;
    }

    let found = false;
    const findTargetParent = (current) => {
      if (!current) return false;
      if (current.id === targetParentId && current !== targetNode) {
        newParentNode = current;
        return true;
      }
      if (current.children) {
        for (const child of current.children) {
          if (findTargetParent(child)) {
            return true;
          }
        }
      }
      return false;
    };
    findTargetParent(mind.nodeData);

    if (!newParentNode) {
      setStatus("Target parent not found");
      return;
    }

    const newIndexInput = window.prompt(
      `Enter new index (0-${newParentNode.children?.length || 0}):`,
      "0"
    );
    newIndex = parseInt(newIndexInput, 10);

    if (isNaN(newIndex)) {
      newIndex = 0;
    }
  } else {
    setStatus("Invalid move type");
    return;
  }

  // Execute the move
  if (typeof mind.moveNode === "function") {
    const success = mind.moveNode(targetNode, newParentNode, newIndex);
    if (success) {
      // Create and execute history command
      const command = createCommand(CommandType.MOVE_NODE, {
        targetNode,
        oldParent,
        oldIndex,
        newParent: newParentNode,
        newIndex,
      });
      if (command) {
        executeCommand(command);
      }

      setStatus(
        `Moved "${targetNode.topic || targetNode.id}" to index ${newIndex}`
      );
    } else {
      setStatus("Move failed");
    }
  } else {
    setStatus("Move is not available in current MindElixir build");
  }
}

function zoom(delta) {
  if (!mind || typeof mind.scale !== "function") {
    setStatus("Zoom is not available in current MindElixir build");
    return;
  }
  const currentScale = Number.isFinite(mind.scaleVal) ? mind.scaleVal : 1;
  const nextScale = Math.max(0.5, Math.min(2, currentScale + delta));
  mind.scale(nextScale);
  setStatus(`Scale: ${nextScale.toFixed(2)}`);
}

function centerCanvas() {
  if (mind && typeof mind.toCenter === "function") {
    mind.toCenter();
  }
}

function bindControls() {
  controls.addChild?.addEventListener("click", addChildNode);
  controls.editNode?.addEventListener("click", editNodeText);
  controls.deleteNode?.addEventListener("click", deleteNode);
  controls.toggleFold?.addEventListener("click", toggleFold);
  controls.moveNode?.addEventListener("click", moveNode);
  controls.zoomIn?.addEventListener("click", () => zoom(0.1));
  controls.zoomOut?.addEventListener("click", () => zoom(-0.1));
  controls.center?.addEventListener("click", centerCanvas);
}

/**
 * Handle file tree add-as-node event
 * @param {CustomEvent} event - Custom event with item and node detail
 */
function handleFileTreeAddAsNode(event) {
  const { item, node } = event.detail;
  if (!node) {
    setStatus("No node data received");
    return;
  }

  const parentNode = getActiveNode();
  if (!parentNode) {
    setStatus("Cannot add node: no active node selected");
    return;
  }

  // Add the node as a child of the selected node
  if (typeof mind.addChild === "function") {
    mind.addChild(parentNode, node);
    setStatus(`Added "${item.name}" as node`);
  } else {
    // Fallback: manually add to children
    parentNode.children = parentNode.children || [];
    parentNode.children.push(node);
    if (typeof mind.refresh === "function") {
      mind.refresh();
    }
    setStatus(`Added "${item.name}" as node`);
  }
}

function installFileTreeListener() {
  document.addEventListener("fileTreeAddAsNode", handleFileTreeAddAsNode);
}

if (window.MindElixir && mount) {
  mind = new window.MindElixir({
    el: mount,
    direction: window.MindElixir.SIDE,
    draggable: true,
    contextMenu: true,
    toolBar: true,
    nodeMenu: true,
    keypress: true,
  });
  mind.init(toMindElixirDocument(defaultNode));
  
  // Initialize history manager for undo/redo (GAP-01)
  initHistoryManager(mind);
  bindToolbarButtons();
  
  installSelectionListener();
  installFileTreeListener();
  bindControls();
  refreshNodeLabel();
} else {
  showFallback(
    "MindElixir is not available in this environment. Mount point is ready for integration."
  );
}
