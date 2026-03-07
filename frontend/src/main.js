import { toMindElixirDocument } from "./nodeModel.js";

const mount = document.getElementById("mindmap");
const fallback = document.getElementById("fallback");
const statusEl = document.getElementById("editor-status");

const controls = {
  addChild: document.getElementById("btn-add-child"),
  editNode: document.getElementById("btn-edit-node"),
  deleteNode: document.getElementById("btn-delete-node"),
  toggleFold: document.getElementById("btn-toggle-fold"),
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

  if (typeof mind.addChild === "function") {
    mind.addChild(parentNode, child);
  } else {
    parentNode.children = parentNode.children || [];
    parentNode.children.push(child);
    if (typeof mind.refresh === "function") {
      mind.refresh();
    }
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

  const nextText = window.prompt("Edit node text", node.topic || "");
  if (!nextText) {
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
  if (typeof mind.removeNode === "function") {
    mind.removeNode(node);
    selectedNode = null;
    refreshNodeLabel();
  } else {
    setStatus("Delete is not available in current MindElixir build");
  }
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
  controls.zoomIn?.addEventListener("click", () => zoom(0.1));
  controls.zoomOut?.addEventListener("click", () => zoom(-0.1));
  controls.center?.addEventListener("click", centerCanvas);
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
  installSelectionListener();
  bindControls();
  refreshNodeLabel();
} else {
  showFallback(
    "MindElixir is not available in this environment. Mount point is ready for integration."
  );
}
