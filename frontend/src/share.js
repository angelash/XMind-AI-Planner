const params = new URLSearchParams(window.location.search);
const token = params.get("token");

const statusEl = document.getElementById("share-status");
const titleEl = document.getElementById("share-title");
const contentEl = document.getElementById("share-content");
const saveBtn = document.getElementById("share-save");

let autoSaveTimer = null;
let editable = true;

function setStatus(text) {
  if (statusEl) {
    statusEl.textContent = text;
  }
}

function parseContent() {
  try {
    return JSON.parse(contentEl.value || "{}");
  } catch (error) {
    throw new Error("content must be valid JSON");
  }
}

async function fetchShare() {
  if (!token) {
    setStatus("Missing share token.");
    if (saveBtn) {
      saveBtn.disabled = true;
    }
    return;
  }

  const resp = await fetch(`/api/v1/shares/${token}`);
  if (!resp.ok) {
    setStatus("Failed to load share.");
    if (saveBtn) {
      saveBtn.disabled = true;
    }
    return;
  }

  const payload = await resp.json();
  editable = Boolean(payload.is_editable);
  titleEl.value = payload.document.title || "";
  contentEl.value = JSON.stringify(payload.document.content || {}, null, 2);

  if (!editable) {
    titleEl.setAttribute("disabled", "disabled");
    contentEl.setAttribute("disabled", "disabled");
    if (saveBtn) {
      saveBtn.disabled = true;
    }
    setStatus("Read only share loaded.");
    return;
  }

  setStatus("Editable share loaded. Changes auto-save.");
}

async function saveShare() {
  if (!token || !editable) {
    return;
  }

  let content;
  try {
    content = parseContent();
  } catch (error) {
    setStatus(error.message);
    return;
  }

  const resp = await fetch(`/api/v1/shares/${token}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: titleEl.value || "Untitled",
      content,
    }),
  });

  if (!resp.ok) {
    setStatus("Save failed.");
    return;
  }
  setStatus("Saved.");
}

function scheduleAutoSave() {
  if (!editable) {
    return;
  }
  if (autoSaveTimer) {
    window.clearTimeout(autoSaveTimer);
  }
  autoSaveTimer = window.setTimeout(() => {
    saveShare().catch(() => {
      setStatus("Save failed.");
    });
  }, 800);
}

titleEl?.addEventListener("input", scheduleAutoSave);
contentEl?.addEventListener("input", scheduleAutoSave);
saveBtn?.addEventListener("click", () => {
  saveShare().catch(() => {
    setStatus("Save failed.");
  });
});

fetchShare().catch(() => {
  setStatus("Failed to load share.");
});
