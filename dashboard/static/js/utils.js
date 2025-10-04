/**
 * FDA Device Query Assistant - Utility Functions
 * Common utilities and helper functions
 */

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copied to clipboard');
        }).catch(err => {
            console.error('Failed to copy:', err);
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

/**
 * Fallback copy method for older browsers
 */
function fallbackCopy(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
        document.execCommand('copy');
        showToast('Copied to clipboard');
    } catch (err) {
        console.error('Fallback copy failed:', err);
        showToast('Failed to copy', 'error');
    }

    document.body.removeChild(textArea);
}

/**
 * Show toast notification
 */
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 20px;
        background: ${type === 'success' ? '#2e7d32' : '#c62828'};
        color: white;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

/**
 * Format large numbers with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Debounce function for search/input
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Parse query for special commands
 */
function parseQueryCommands(query) {
    const commands = {
        clear: () => {
            document.getElementById('messagesArea').innerHTML = '';
            showWelcomeMessage();
        },
        help: () => {
            showHelp();
        },
        export: () => {
            exportResults();
        },
        history: () => {
            loadRecentQueries();
        }
    };

    if (query.startsWith('/')) {
        const command = query.substring(1).toLowerCase();
        if (commands[command]) {
            commands[command]();
            return true;
        }
    }

    return false;
}

/**
 * Show welcome message
 */
function showWelcomeMessage() {
    const messagesArea = document.getElementById('messagesArea');
    messagesArea.innerHTML = `
        <div class="welcome-message">
            <h3>Welcome to FDA Device Query Assistant</h3>
            <p class="lead">Ask questions about FDA device data in natural language.</p>
            <div class="row mt-4">
                <div class="col-md-6">
                    <h6>Example Queries:</h6>
                    <ul class="list-unstyled">
                        <li><i class="fas fa-chevron-right text-primary"></i> Show me Class II recalls from Abbott</li>
                        <li><i class="fas fa-chevron-right text-primary"></i> Find 510k clearances for cardiac devices</li>
                        <li><i class="fas fa-chevron-right text-primary"></i> How many adverse events in 2024?</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <h6>Available Data:</h6>
                    <ul class="list-unstyled">
                        <li><i class="fas fa-check text-success"></i> Device Recalls</li>
                        <li><i class="fas fa-check text-success"></i> 510(k) Clearances</li>
                        <li><i class="fas fa-check text-success"></i> PMA Approvals</li>
                        <li><i class="fas fa-check text-success"></i> Adverse Events (MAUDE)</li>
                        <li><i class="fas fa-check text-success"></i> Device Classifications</li>
                    </ul>
                </div>
            </div>
            <div class="mt-4">
                <h6>Quick Commands:</h6>
                <code>/clear</code> - Clear chat history<br>
                <code>/help</code> - Show help<br>
                <code>/export</code> - Export results<br>
                <code>/history</code> - Show recent queries
            </div>
        </div>
    `;
}

/**
 * Add copy button to code blocks
 */
function addCopyButtons() {
    document.querySelectorAll('pre').forEach(pre => {
        if (pre.querySelector('.copy-button')) return;

        const button = document.createElement('button');
        button.className = 'copy-button';
        button.innerHTML = '<i class="fas fa-copy"></i>';
        button.title = 'Copy to clipboard';
        button.style.cssText = `
            position: absolute;
            top: 5px;
            right: 5px;
            padding: 5px 10px;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
        `;

        button.onclick = () => {
            const code = pre.textContent;
            copyToClipboard(code);
        };

        pre.style.position = 'relative';
        pre.appendChild(button);
    });
}

/**
 * Initialize theme toggle
 */
function initThemeToggle() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
}

/**
 * Toggle theme
 */
function toggleTheme() {
    const currentTheme = document.body.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.body.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

/**
 * Add keyboard shortcuts info
 */
function addKeyboardShortcuts() {
    const shortcuts = {
        'Ctrl+Enter': 'Submit query',
        'Ctrl+K': 'Focus search',
        'Esc': 'Clear input',
        'Ctrl+/': 'Show help'
    };

    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            showHelp();
        }
    });
}

// Initialize utilities on load
document.addEventListener('DOMContentLoaded', () => {
    initThemeToggle();
    addKeyboardShortcuts();

    // Add animation styles
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
});