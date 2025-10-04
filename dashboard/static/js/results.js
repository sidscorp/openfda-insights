/**
 * FDA Device Query Assistant - Results Display
 * Handles formatting and display of FDA data results
 */

/**
 * Load query templates from server
 */
async function loadTemplates() {
    try {
        const response = await fetch('/templates');
        const data = await response.json();
        displayTemplates(data.templates);
    } catch (error) {
        console.error('Error loading templates:', error);
    }
}

/**
 * Display query templates in sidebar
 */
function displayTemplates(templates) {
    const accordion = document.getElementById('templateAccordion');
    accordion.innerHTML = '';

    templates.forEach((category, index) => {
        const categoryId = `category${index}`;
        const item = document.createElement('div');
        item.className = 'accordion-item';

        item.innerHTML = `
            <h2 class="accordion-header" id="heading${categoryId}">
                <button class="accordion-button ${index !== 0 ? 'collapsed' : ''}"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target="#collapse${categoryId}"
                        aria-expanded="${index === 0 ? 'true' : 'false'}"
                        aria-controls="collapse${categoryId}">
                    ${category.category}
                </button>
            </h2>
            <div id="collapse${categoryId}"
                 class="accordion-collapse collapse ${index === 0 ? 'show' : ''}"
                 aria-labelledby="heading${categoryId}"
                 data-bs-parent="#templateAccordion">
                <div class="accordion-body p-0">
                    ${category.queries.map(query => `
                        <div class="template-item" onclick="useTemplate('${escapeQuotes(query)}')">
                            <i class="fas fa-chevron-right me-2 small"></i>${query}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        accordion.appendChild(item);
    });
}

/**
 * Use a query template
 */
function useTemplate(template) {
    const input = document.getElementById('queryInput');

    // Replace placeholders with example values
    template = template.replace('{company}', 'Medtronic');
    template = template.replace('{number}', '240190');
    template = template.replace('{code}', 'NBE');
    template = template.replace('{device_type}', 'insulin pumps');

    input.value = template;
    input.focus();

    // Highlight the input briefly
    input.style.backgroundColor = '#e3f2fd';
    setTimeout(() => {
        input.style.backgroundColor = '';
    }, 500);
}

/**
 * Load recent queries
 */
async function loadRecentQueries() {
    try {
        const response = await fetch('/history?limit=5');
        const data = await response.json();
        displayRecentQueries(data.queries);
    } catch (error) {
        console.error('Error loading recent queries:', error);
    }
}

/**
 * Display recent queries in sidebar
 */
function displayRecentQueries(queries) {
    const container = document.getElementById('recentQueries');
    container.innerHTML = '';

    if (queries.length === 0) {
        container.innerHTML = '<div class="p-3 text-muted">No recent queries</div>';
        return;
    }

    queries.forEach(query => {
        const item = document.createElement('a');
        item.href = '#';
        item.className = 'list-group-item list-group-item-action';

        const time = new Date(query.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });

        item.innerHTML = `
            <div class="recent-query-item">
                <div class="recent-query-text">${escapeHtml(query.question)}</div>
                <div class="recent-query-time">
                    <i class="fas fa-clock me-1"></i>${time}
                </div>
            </div>
        `;

        item.onclick = (e) => {
            e.preventDefault();
            document.getElementById('queryInput').value = query.question;
            document.getElementById('queryInput').focus();
        };

        container.appendChild(item);
    });
}

/**
 * Export results
 */
async function exportResults() {
    const modal = createExportModal();
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

/**
 * Create export modal
 */
function createExportModal() {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'exportModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-download me-2"></i>Export Results
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="export-options">
                        <div class="export-option" onclick="performExport('json')">
                            <i class="fas fa-file-code"></i>
                            <h6>JSON</h6>
                            <small class="text-muted">Machine-readable format</small>
                        </div>
                        <div class="export-option" onclick="performExport('csv')">
                            <i class="fas fa-file-csv"></i>
                            <h6>CSV</h6>
                            <small class="text-muted">Excel-compatible</small>
                        </div>
                        <div class="export-option" onclick="performExport('pdf')">
                            <i class="fas fa-file-pdf"></i>
                            <h6>PDF</h6>
                            <small class="text-muted">Formatted report</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    return modal;
}

/**
 * Perform export
 */
async function performExport(format) {
    try {
        const response = await fetch(`/export/${format}`);

        if (format === 'pdf' && response.headers.get('content-type').includes('json')) {
            // PDF not implemented yet
            const data = await response.json();
            alert(data.message);
            return;
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `fda_queries_${new Date().toISOString().split('T')[0]}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);

        // Close modal
        bootstrap.Modal.getInstance(document.getElementById('exportModal')).hide();

    } catch (error) {
        console.error('Export error:', error);
        alert('Error exporting data: ' + error.message);
    }
}

/**
 * Format specific result types
 */
function formatRecallResult(recall) {
    const classMap = {
        'Class I': 'danger',
        'Class II': 'warning',
        'Class III': 'success'
    };

    const badgeClass = classMap[recall.classification] || 'secondary';

    return `
        <div class="result-item">
            <div class="result-header">
                ${recall.recall_number || 'N/A'}
                <span class="badge bg-${badgeClass} ms-2">${recall.classification}</span>
            </div>
            <div class="result-details">
                <strong>Company:</strong> ${recall.recalling_firm || 'N/A'}<br>
                <strong>Product:</strong> ${recall.product_description || 'N/A'}<br>
                <strong>Reason:</strong> ${recall.reason_for_recall || 'N/A'}<br>
                <strong>Date Initiated:</strong> ${formatDate(recall.recall_initiation_date)}
            </div>
        </div>
    `;
}

function format510kResult(clearance) {
    return `
        <div class="result-item">
            <div class="result-header">
                ${clearance.k_number || 'N/A'} - ${clearance.applicant || 'N/A'}
            </div>
            <div class="result-details">
                <strong>Device:</strong> ${clearance.device_name || 'N/A'}<br>
                <strong>Product Code:</strong> ${clearance.product_code || 'N/A'}<br>
                <strong>Decision Date:</strong> ${formatDate(clearance.decision_date)}<br>
                <strong>Type:</strong> ${clearance.clearance_type || 'N/A'}
            </div>
        </div>
    `;
}

/**
 * Format date string
 */
function formatDate(dateStr) {
    if (!dateStr) return 'N/A';

    // Handle YYYYMMDD format
    if (dateStr.length === 8 && !dateStr.includes('-')) {
        const year = dateStr.substring(0, 4);
        const month = dateStr.substring(4, 6);
        const day = dateStr.substring(6, 8);
        dateStr = `${year}-${month}-${day}`;
    }

    const date = new Date(dateStr);
    if (isNaN(date)) return dateStr;

    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Escape quotes for HTML attributes
 */
function escapeQuotes(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

/**
 * Auto-refresh recent queries every 30 seconds
 */
setInterval(loadRecentQueries, 30000);