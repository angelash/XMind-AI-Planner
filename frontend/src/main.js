import { toMindElixirDocument } from "./nodeModel.js";

const mount = document.getElementById("mindmap");
const fallback = document.getElementById("fallback");

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

function showFallback(message) {
  fallback.textContent = message;
  fallback.classList.remove("hidden");
}

if (window.MindElixir && mount) {
  const mind = new window.MindElixir({
    el: mount,
    direction: window.MindElixir.SIDE,
    draggable: true,
    contextMenu: true,
    toolBar: true,
    nodeMenu: true,
    keypress: true,
  });
  mind.init(toMindElixirDocument(defaultNode));
} else {
  showFallback(
    "MindElixir is not available in this environment. Mount point is ready for integration."
  );
}
