function assertObject(value, message) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(message);
  }
}

function normalizeNode(node) {
  assertObject(node, "node must be an object");
  if (typeof node.id !== "string" || node.id.length === 0) {
    throw new Error("node id is required");
  }
  if (typeof node.text !== "string" || node.text.length === 0) {
    throw new Error("node text is required");
  }

  const children = Array.isArray(node.children) ? node.children.map(normalizeNode) : [];
  const normalized = { id: node.id, text: node.text };

  if (typeof node.memo === "string" && node.memo.length > 0) {
    normalized.memo = node.memo;
  }
  if (node.exportSeparate === true) {
    normalized.exportSeparate = true;
  }
  if (children.length > 0) {
    normalized.children = children;
  }

  return normalized;
}

function toMindElixirNode(node, isRoot = false) {
  const transformed = { id: node.id, topic: node.text };
  if (isRoot) {
    transformed.root = true;
  }
  if (node.memo) {
    transformed.memo = node.memo;
  }
  if (node.exportSeparate) {
    transformed.exportSeparate = true;
  }
  if (Array.isArray(node.children) && node.children.length > 0) {
    transformed.children = node.children.map((child) => toMindElixirNode(child));
  }
  return transformed;
}

function fromMindElixirNode(node) {
  assertObject(node, "mind elixir node must be an object");
  if (typeof node.id !== "string" || node.id.length === 0) {
    throw new Error("mind elixir node id is required");
  }
  if (typeof node.topic !== "string" || node.topic.length === 0) {
    throw new Error("mind elixir node topic is required");
  }

  const transformed = { id: node.id, text: node.topic };
  if (typeof node.memo === "string" && node.memo.length > 0) {
    transformed.memo = node.memo;
  }
  if (node.exportSeparate === true) {
    transformed.exportSeparate = true;
  }

  if (Array.isArray(node.children) && node.children.length > 0) {
    transformed.children = node.children.map(fromMindElixirNode);
  }

  return transformed;
}

export function toMindElixirDocument(rootNode) {
  const normalized = normalizeNode(rootNode);
  return { nodeData: toMindElixirNode(normalized, true) };
}

export function fromMindElixirDocument(document) {
  assertObject(document, "mind elixir document must be an object");
  return fromMindElixirNode(document.nodeData);
}
