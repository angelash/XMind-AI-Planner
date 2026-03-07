const mount = document.getElementById("mindmap");
const fallback = document.getElementById("fallback");

const defaultData = {
  nodeData: {
    id: "root",
    topic: "XMind AI Planner",
    children: [{ id: "child-1", topic: "First Idea" }],
  },
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
  mind.init(defaultData);
} else {
  showFallback(
    "MindElixir is not available in this environment. Mount point is ready for integration."
  );
}
