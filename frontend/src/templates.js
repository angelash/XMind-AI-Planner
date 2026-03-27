/**
 * Templates functionality (GAP-08)
 *
 * Template library allows users to:
 * - Browse public and personal templates
 * - Create templates from current document
 * - Use templates to create new documents
 * - Manage personal templates (edit, delete)
 */

let templates = [];
let currentFilter = { category: null, tag: null };

/**
 * Initialize template library
 */
async function initTemplates() {
    await loadTemplates();
    renderTemplateList();
    setupTemplateEventListeners();
}

/**
 * Load templates from server
 */
async function loadTemplates() {
    try {
        const response = await fetch('/api/v1/templates');
        if (!response.ok) throw new Error('Failed to load templates');
        templates = await response.json();
    } catch (error) {
        console.error('Error loading templates:', error);
        templates = [];
    }
}

/**
 * Render template list in UI
 */
function renderTemplateList() {
    const container = document.getElementById('template-list');
    if (!container) return;

    // Filter templates
    let filtered = templates;
    if (currentFilter.category) {
        filtered = filtered.filter(t => t.category === currentFilter.category);
    }
    if (currentFilter.tag) {
        filtered = filtered.filter(t => t.tags && t.tags.includes(currentFilter.tag));
    }

    // Group by category
    const grouped = {};
    filtered.forEach(template => {
        const category = template.category || '未分类';
        if (!grouped[category]) grouped[category] = [];
        grouped[category].push(template);
    });

    // Render
    let html = '';
    for (const [category, categoryTemplates] of Object.entries(grouped)) {
        html += `
            <div class="template-category">
                <h3 class="template-category-title">${escapeHtml(category)}</h3>
                <div class="template-grid">
                    ${categoryTemplates.map(template => renderTemplateCard(template)).join('')}
                </div>
            </div>
        `;
    }

    if (filtered.length === 0) {
        html = '<div class="template-empty">暂无模板</div>';
    }

    container.innerHTML = html;
}

/**
 * Render a single template card
 */
function renderTemplateCard(template) {
    const tagsHtml = template.tags && template.tags.length > 0
        ? `<div class="template-tags">
            ${template.tags.map(tag => `<span class="template-tag">${escapeHtml(tag)}</span>`).join('')}
           </div>`
        : '';

    return `
        <div class="template-card" data-template-id="${template.id}">
            <div class="template-header">
                <h4 class="template-title">${escapeHtml(template.title)}</h4>
                ${template.is_public ? '<span class="template-badge template-public">公开</span>' : ''}
            </div>
            ${template.description ? `<p class="template-description">${escapeHtml(template.description)}</p>` : ''}
            <div class="template-meta">
                <span class="template-date">${formatDate(template.updated_at)}</span>
                ${tagsHtml}
            </div>
            <div class="template-actions">
                <button class="btn btn-primary btn-use-template" data-template-id="${template.id}">
                    使用模板
                </button>
                ${template.owner_id === getCurrentUserId() ? `
                    <button class="btn btn-secondary btn-edit-template" data-template-id="${template.id}">
                        编辑
                    </button>
                    <button class="btn btn-danger btn-delete-template" data-template-id="${template.id}">
                        删除
                    </button>
                ` : ''}
            </div>
        </div>
    `;
}

/**
 * Show create template modal
 */
function showCreateTemplateModal() {
    const modal = document.getElementById('template-create-modal');
    if (!modal) {
        console.error('Template create modal not found');
        return;
    }

    // Pre-fill with current document content
    const data = window.mindElixir.getData();
    document.getElementById('template-title-input').value = document.getElementById('document-title')?.value || '';
    document.getElementById('template-content-input').value = JSON.stringify(data.nodeData);
    document.getElementById('template-category-input').value = '';
    document.getElementById('template-tags-input').value = '';
    document.getElementById('template-description-input').value = '';

    modal.classList.remove('hidden');
}

/**
 * Create new template
 */
async function createTemplate() {
    const title = document.getElementById('template-title-input').value.trim();
    const contentJson = document.getElementById('template-content-input').value;
    const description = document.getElementById('template-description-input').value.trim();
    const category = document.getElementById('template-category-input').value.trim();
    const tagsStr = document.getElementById('template-tags-input').value.trim();
    const isPublic = document.getElementById('template-public-check')?.checked || false;

    if (!title) {
        alert('请输入模板标题');
        return;
    }

    if (!contentJson) {
        alert('请提供模板内容');
        return;
    }

    const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];

    try {
        const response = await fetch('/api/v1/templates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                content_json: contentJson,
                category: category || null,
                tags,
                is_public: isPublic
            })
        });

        if (!response.ok) {
            throw new Error('Failed to create template');
        }

        // Close modal and reload templates
        document.getElementById('template-create-modal').classList.add('hidden');
        await loadTemplates();
        renderTemplateList();
        alert('模板创建成功');
    } catch (error) {
        console.error('Error creating template:', error);
        alert('模板创建失败: ' + error.message);
    }
}

/**
 * Use template to create new document
 */
async function useTemplate(templateId) {
    try {
        // Get template details
        const response = await fetch(`/api/v1/templates/${templateId}`);
        if (!response.ok) throw new Error('Failed to get template');
        const template = await response.json();

        // Parse template content
        const nodeData = JSON.parse(template.content_json);

        // Create new document with template content
        const createResponse = await fetch('/api/v1/documents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: template.title + ' (副本)',
                content_json: JSON.stringify({ nodeData })
            })
        });

        if (!createResponse.ok) {
            throw new Error('Failed to create document');
        }

        const document = await createResponse.json();

        // Redirect to new document
        window.location.href = `/?doc_id=${document.id}`;
    } catch (error) {
        console.error('Error using template:', error);
        alert('使用模板失败: ' + error.message);
    }
}

/**
 * Delete template
 */
async function deleteTemplate(templateId) {
    if (!confirm('确定要删除此模板吗？')) return;

    try {
        const response = await fetch(`/api/v1/templates/${templateId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete template');

        await loadTemplates();
        renderTemplateList();
        alert('模板删除成功');
    } catch (error) {
        console.error('Error deleting template:', error);
        alert('模板删除失败: ' + error.message);
    }
}

/**
 * Setup template event listeners
 */
function setupTemplateEventListeners() {
    // Use template buttons
    document.addEventListener('click', async (e) => {
        if (e.target.closest('.btn-use-template')) {
            const templateId = e.target.closest('.btn-use-template').dataset.templateId;
            await useTemplate(templateId);
        }

        if (e.target.closest('.btn-delete-template')) {
            const templateId = e.target.closest('.btn-delete-template').dataset.templateId;
            await deleteTemplate(templateId);
        }
    });

    // Create template button
    const createBtn = document.getElementById('btn-create-template');
    if (createBtn) {
        createBtn.addEventListener('click', showCreateTemplateModal);
    }

    // Create template form
    const createForm = document.getElementById('template-create-form');
    if (createForm) {
        createForm.addEventListener('submit', (e) => {
            e.preventDefault();
            createTemplate();
        });
    }

    // Cancel create template
    const cancelCreateBtn = document.getElementById('btn-cancel-create-template');
    if (cancelCreateBtn) {
        cancelCreateBtn.addEventListener('click', () => {
            document.getElementById('template-create-modal').classList.add('hidden');
        });
    }
}

/**
 * Utility: escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Utility: format date
 */
function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString('zh-CN');
}

/**
 * Utility: get current user ID
 */
function getCurrentUserId() {
    // TODO: Get from auth context
    return localStorage.getItem('user_id') || null;
}

// Export functions for external use
window.TemplateModule = {
    initTemplates,
    loadTemplates,
    renderTemplateList,
    showCreateTemplateModal,
    createTemplate,
    useTemplate,
    deleteTemplate
};
