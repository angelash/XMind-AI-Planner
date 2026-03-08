(function (global) {
  function createBus() {
    const listeners = new Map();
    return {
      addListener(event, cb) {
        if (!listeners.has(event)) {
          listeners.set(event, []);
        }
        listeners.get(event).push(cb);
      },
      emit(event, payload) {
        const handlers = listeners.get(event) || [];
        handlers.forEach((cb) => cb(payload));
      },
    };
  }

  function walk(root, visitor, parent) {
    if (!root) {
      return false;
    }
    if (visitor(root, parent)) {
      return true;
    }
    const children = Array.isArray(root.children) ? root.children : [];
    for (const child of children) {
      if (walk(child, visitor, root)) {
        return true;
      }
    }
    return false;
  }

  class MindElixir {
    static SIDE = 1;

    constructor(opts) {
      this.opts = opts || {};
      this.nodeData = null;
      this.scaleVal = 1;
      this.bus = createBus();
      this._mount = this.opts.el || null;
    }

    init(data) {
      this.nodeData = data && data.nodeData ? data.nodeData : null;
      if (this.nodeData) {
        this.nodeData.root = true;
      }
      this.refresh();
      this.bus.emit("selectNode", this.nodeData);
    }

    refresh() {
      if (!this._mount) {
        return;
      }
      const topic = this.nodeData && this.nodeData.topic ? this.nodeData.topic : "(empty)";
      this._mount.textContent = `MindElixir offline mode: ${topic}`;
    }

    addChild(parentNode, child) {
      if (!parentNode || !child) {
        return;
      }
      parentNode.children = parentNode.children || [];
      parentNode.children.push(child);
      this.refresh();
      this.bus.emit("selectNode", child);
    }

    beginEdit(node) {
      if (!node || typeof global.prompt !== "function") {
        return;
      }
      const nextText = global.prompt("Edit node text", node.topic || "");
      if (nextText) {
        node.topic = nextText;
        this.refresh();
      }
    }

    updateNode(nodeId, topic) {
      if (!this.nodeData) {
        return;
      }
      walk(this.nodeData, (node) => {
        if (node.id === nodeId) {
          node.topic = topic;
          return true;
        }
        return false;
      });
      this.refresh();
    }

    removeNode(target) {
      if (!this.nodeData || !target || target.root) {
        return;
      }
      walk(this.nodeData, (node, parent) => {
        if (!parent || !Array.isArray(parent.children)) {
          return false;
        }
        const idx = parent.children.findIndex((child) => child.id === node.id);
        if (idx >= 0 && node.id === target.id) {
          parent.children.splice(idx, 1);
          return true;
        }
        return false;
      });
      this.refresh();
      this.bus.emit("selectNode", this.nodeData);
    }

    expandNode(node) {
      if (node) {
        node.expanded = true;
      }
      this.refresh();
    }

    collapseNode(node) {
      if (node) {
        node.expanded = false;
      }
      this.refresh();
    }

    scale(nextScale) {
      if (typeof nextScale === "number" && Number.isFinite(nextScale)) {
        this.scaleVal = nextScale;
      }
    }

    toCenter() {
      return;
    }
  }

  global.MindElixir = MindElixir;
})(window);
