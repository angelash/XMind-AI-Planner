/**
 * Review Panel Frontend
 * REVIEW-02: 审核面板前端
 *
 * Provides UI for reviewers to:
 * - View pending changes
 * - Approve/reject individual changes
 * - Batch approve changes
 */

const listEl = document.getElementById("review-list");
const countEl = document.getElementById("review-count");
const refreshBtn = document.getElementById("btn-refresh");
const batchApproveBtn = document.getElementById("btn-batch-approve");
const filterDocumentInput = document.getElementById("filter-document");
const filterTypeSelect = document.getElementById("filter-type");

let changes = [];
let currentUser = null;

/**
 * Fetch current user info
 */
async function fetchCurrentUser() {
  try {
    const resp = await fetch("/api/v1/auth/me");
    if (resp.ok) {
      const data = await resp.json();
      currentUser = data.user || null;
    }
  } catch {
    currentUser = null;
  }
}

/**
 * Fetch pending changes from API
 */
async function fetchPendingChanges() {
  const params = new URLSearchParams();
  const docFilter = filterDocumentInput?.value?.trim();
  if (docFilter) {
    params.set("document_id", docFilter);
  }

  const url = `/api/v1/review/pending${params.toString() ? "?" + params.toString() : ""}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error("Failed to fetch pending changes");
  }
  const data = await resp.json();
  return data.changes || [];
}

/**
 * Format timestamp to readable string
 */
function formatTime(timestamp) {
  if (!timestamp) return "N/A";
  const date = new Date(timestamp);
  return date.toLocaleString();
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

/**
 * Render a single change item
 */
function renderChangeItem(change) {
  const typeClass = change.change_type || "update";
  const typeLabel = change.change_type || "update";

  const beforeContent = change.before_content
    ? JSON.stringify(change.before_content, null, 2)
    : "(none)";
  const afterContent = change.after_content
    ? JSON.stringify(change.after_content, null, 2)
    : "(none)";

  const isPending = change.status === "pending";
  const isProcessed = change.status === "approved" || change.status === "rejected";

  const item = document.createElement("div");
  item.className = "review-item";
  item.dataset.changeId = change.id;
  item.dataset.changeType = change.change_type;

  item.innerHTML = `
    <div class="review-item-header">
      <div>
        <span class="review-item-type ${typeClass}">${escapeHtml(typeLabel)}</span>
        <span class="review-status ${change.status}">${escapeHtml(change.status)}</span>
      </div>
      <div class="review-item-meta">
        <div>Node: <code>${escapeHtml(change.node_id)}</code></div>
        <div>Document: <code>${escapeHtml(change.document_id)}</code></div>
        <div>Submitted by: ${escapeHtml(change.submitted_by)} at ${formatTime(change.submitted_at)}</div>
        ${isProcessed ? `<div>Reviewed by: ${escapeHtml(change.reviewed_by)} at ${formatTime(change.reviewed_at)}</div>` : ""}
        ${change.review_comment ? `<div>Comment: ${escapeHtml(change.review_comment)}</div>` : ""}
      </div>
    </div>
    <div class="review-item-content">
      <div class="review-diff-panel">
        <h4>Before</h4>
        <pre>${escapeHtml(beforeContent)}</pre>
      </div>
      <div class="review-diff-panel">
        <h4>After</h4>
        <pre>${escapeHtml(afterContent)}</pre>
      </div>
    </div>
    ${
      isPending
        ? `
      <textarea class="review-comment-input" placeholder="Optional comment..." data-change-id="${change.id}"></textarea>
      <div class="review-item-actions">
        <button type="button" class="btn-approve" data-action="approve" data-change-id="${change.id}">Approve</button>
        <button type="button" class="btn-reject" data-action="reject" data-change-id="${change.id}">Reject</button>
      </div>
    `
        : ""
    }
  `;

  return item;
}

/**
 * Render the list of changes
 */
function renderChanges(filteredChanges) {
  listEl.innerHTML = "";

  if (filteredChanges.length === 0) {
    listEl.innerHTML = `
      <div class="review-empty">
        <div class="review-empty-icon">✓</div>
        <div>No pending changes to review.</div>
      </div>
    `;
    return;
  }

  for (const change of filteredChanges) {
    const item = renderChangeItem(change);
    listEl.appendChild(item);
  }
}

/**
 * Update the count badge
 */
function updateCount(pendingCount) {
  if (countEl) {
    countEl.textContent = `${pendingCount} pending`;
    countEl.className = `review-status ${pendingCount > 0 ? "pending" : "approved"}`;
  }
}

/**
 * Handle approve/reject actions
 */
async function handleReviewAction(changeId, action) {
  const commentInput = document.querySelector(
    `textarea[data-change-id="${changeId}"]`
  );
  const comment = commentInput?.value?.trim() || null;

  const url = `/api/v1/review/${changeId}/${action}`;
  const body = comment ? { review_comment: comment } : {};

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const error = await resp.json();
      alert(error.detail || "Action failed");
      return;
    }

    // Refresh the list
    await refresh();
  } catch (error) {
    alert("Network error: " + error.message);
  }
}

/**
 * Handle batch approve
 */
async function handleBatchApprove() {
  const docFilter = filterDocumentInput?.value?.trim();
  if (!docFilter) {
    alert("Please enter a document ID to batch approve changes for that document.");
    return;
  }

  if (!confirm(`Approve all pending changes for document ${docFilter}?`)) {
    return;
  }

  try {
    const resp = await fetch("/api/v1/review/batch-approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_id: docFilter }),
    });

    if (!resp.ok) {
      const error = await resp.json();
      alert(error.detail || "Batch approve failed");
      return;
    }

    const data = await resp.json();
    alert(`Approved ${data.count} changes.`);
    await refresh();
  } catch (error) {
    alert("Network error: " + error.message);
  }
}

/**
 * Apply type filter
 */
function applyFilters() {
  const typeFilter = filterTypeSelect?.value || "";
  let filtered = changes;

  if (typeFilter) {
    filtered = filtered.filter((c) => c.change_type === typeFilter);
  }

  renderChanges(filtered);

  // Update count for pending only
  const pendingCount = filtered.filter((c) => c.status === "pending").length;
  updateCount(pendingCount);
}

/**
 * Refresh the list
 */
async function refresh() {
  try {
    changes = await fetchPendingChanges();
    applyFilters();
  } catch (error) {
    listEl.innerHTML = `<div class="review-empty"><div>Error loading changes: ${escapeHtml(error.message)}</div></div>`;
  }
}

/**
 * Event delegation for approve/reject buttons
 */
listEl?.addEventListener("click", (event) => {
  const target = event.target;
  if (target.matches("button[data-action]")) {
    const action = target.dataset.action;
    const changeId = parseInt(target.dataset.changeId, 10);
    if (action && changeId) {
      handleReviewAction(changeId, action);
    }
  }
});

/**
 * Bind event listeners
 */
refreshBtn?.addEventListener("click", refresh);
batchApproveBtn?.addEventListener("click", handleBatchApprove);
filterTypeSelect?.addEventListener("change", applyFilters);
filterDocumentInput?.addEventListener("input", () => {
  // Debounce
  clearTimeout(filterDocumentInput._debounce);
  filterDocumentInput._debounce = setTimeout(refresh, 300);
});

/**
 * Initialize
 */
async function init() {
  await fetchCurrentUser();
  await refresh();
}

init().catch(console.error);
