/**
 * FDA Device Query Assistant - Chat Interface
 * Handles WebSocket communication and message display
 */

// Global variables
let ws = null;
let sessionId = null;
let isConnected = false;
let messageHistory = [];
let showDetails = true;  // Toggle for showing agent details
let currentProgressId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeWebSocket();
    loadTemplates();
    loadRecentQueries();
    setupEventListeners();

    // Focus on input
    document.getElementById('queryInput').focus();
});

/**
 * Initialize WebSocket connection
 */
function initializeWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function() {
        console.log('WebSocket connected');
        isConnected = true;
        updateConnectionStatus(true);
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
    };

    ws.onclose = function() {
        console.log('WebSocket disconnected');
        isConnected = false;
        updateConnectionStatus(false);

        // Attempt to reconnect after 3 seconds
        setTimeout(initializeWebSocket, 3000);
    };
}

/**
 * Handle incoming WebSocket messages
 */
function handleWebSocketMessage(data) {
    if (data.type === 'status') {
        updateStatus(data.message);
    } else if (data.type === 'processing') {
        // Display processing step
        displayProcessingStep(data);
        updateProgressIndicator(data.step);
    } else if (data.type === 'complete') {
        removeTypingIndicator();
        removeProgressIndicator();
        displayAssistantMessage(data.answer, data.metadata, data.provenance);
        updateStatus('Ready');
        enableInput();

        // Update last updated time
        if (data.provenance && data.provenance.last_updated) {
            document.getElementById('lastUpdated').textContent =
                new Date(data.provenance.last_updated).toLocaleDateString();
        }
    } else if (data.type === 'error') {
        removeTypingIndicator();
        removeProgressIndicator();
        displayErrorMessage(data.message);
        updateStatus('Error occurred');
        enableInput();
    }
}

/**
 * Submit a query
 */
function submitQuery() {
    const input = document.getElementById('queryInput');
    const query = input.value.trim();

    if (!query) return;

    if (!isConnected) {
        displayErrorMessage('Not connected to server. Please wait...');
        return;
    }

    // Disable input during processing
    disableInput();

    // Clear welcome message if present
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.style.display = 'none';
    }

    // Display user message
    displayUserMessage(query);

    // Show progress indicator if details are enabled
    if (showDetails) {
        showProgressIndicator();
    } else {
        showTypingIndicator();
    }

    // Send via WebSocket with details preference
    ws.send(JSON.stringify({
        question: query,
        show_details: showDetails
    }));

    // Clear input
    input.value = '';

    // Add to history
    messageHistory.push({ type: 'user', content: query, timestamp: new Date() });
}

/**
 * Display user message in chat
 */
function displayUserMessage(message) {
    const messagesArea = document.getElementById('messagesArea');
    const messageElement = document.createElement('div');
    messageElement.className = 'message user';

    const timestamp = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    messageElement.innerHTML = `
        <div class="message-bubble">
            ${escapeHtml(message)}
        </div>
        <div class="message-time">${timestamp}</div>
    `;

    messagesArea.appendChild(messageElement);
    scrollToBottom();
}

/**
 * Display assistant message with formatted results
 */
function displayAssistantMessage(answer, metadata, provenance) {
    const messagesArea = document.getElementById('messagesArea');
    const messageElement = document.createElement('div');
    messageElement.className = 'message assistant';

    const timestamp = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    // Format the answer for better display
    const formattedAnswer = formatAnswer(answer, metadata);

    messageElement.innerHTML = `
        <div class="message-bubble">
            ${formattedAnswer}
            ${metadata ? createMetadataBadges(metadata) : ''}
        </div>
        <div class="message-time">
            ${timestamp}
            ${provenance ? ` • ${provenance.endpoint || 'Unknown endpoint'}` : ''}
        </div>
    `;

    messagesArea.appendChild(messageElement);
    scrollToBottom();

    // Add to history
    messageHistory.push({
        type: 'assistant',
        content: answer,
        metadata: metadata,
        provenance: provenance,
        timestamp: new Date()
    });
}

/**
 * Format answer for display
 */
function formatAnswer(answer, metadata) {
    // Check if answer contains structured data
    if (answer.includes('Found') && answer.includes('\n')) {
        return formatStructuredResults(answer);
    }

    // Convert markdown-style formatting
    answer = answer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    answer = answer.replace(/\n/g, '<br>');

    return answer;
}

/**
 * Format structured results (recalls, 510k, etc.)
 */
function formatStructuredResults(answer) {
    const lines = answer.split('\n');
    let formatted = '';
    let inItem = false;

    lines.forEach(line => {
        if (line.match(/^\d+\./)) {
            // Start of a numbered item
            if (inItem) formatted += '</div>';
            formatted += '<div class="result-item">';
            formatted += `<div class="result-header">${line}</div>`;
            inItem = true;
        } else if (line.trim().startsWith('•') || line.trim().match(/^[A-Z][\w\s]+:/)) {
            // Detail line
            formatted += `<div class="result-details">${line.trim()}</div>`;
        } else if (line.includes('Total count:')) {
            // Count result
            formatted += `<div class="alert alert-info">${line}</div>`;
        } else if (line.trim()) {
            formatted += `<div>${line}</div>`;
        }
    });

    if (inItem) formatted += '</div>';

    return formatted || answer.replace(/\n/g, '<br>');
}

/**
 * Create metadata badges
 */
function createMetadataBadges(metadata) {
    let badges = '<div class="mt-2">';

    if (metadata.endpoint) {
        badges += `<span class="badge bg-info me-1">${metadata.endpoint}</span>`;
    }

    if (metadata.retry_count > 0) {
        badges += `<span class="badge bg-warning me-1">Retries: ${metadata.retry_count}</span>`;
    }

    if (metadata.is_sufficient === false) {
        badges += `<span class="badge bg-danger me-1">Partial Results</span>`;
    }

    badges += '</div>';
    return badges;
}

/**
 * Display error message
 */
function displayErrorMessage(message) {
    const messagesArea = document.getElementById('messagesArea');
    const messageElement = document.createElement('div');
    messageElement.className = 'message assistant';

    messageElement.innerHTML = `
        <div class="message-bubble alert alert-danger">
            <i class="fas fa-exclamation-triangle me-2"></i>
            ${escapeHtml(message)}
        </div>
    `;

    messagesArea.appendChild(messageElement);
    scrollToBottom();
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const messagesArea = document.getElementById('messagesArea');
    const indicator = document.createElement('div');
    indicator.id = 'typingIndicator';
    indicator.className = 'message assistant';
    indicator.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    messagesArea.appendChild(indicator);
    scrollToBottom();
}

/**
 * Remove typing indicator
 */
function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Update connection status
 */
function updateConnectionStatus(connected) {
    const statusBadge = document.querySelector('.navbar .badge');
    if (statusBadge) {
        if (connected) {
            statusBadge.className = 'badge bg-success me-3';
            statusBadge.innerHTML = '<i class="fas fa-circle me-1"></i> API Connected';
        } else {
            statusBadge.className = 'badge bg-danger me-3';
            statusBadge.innerHTML = '<i class="fas fa-circle me-1"></i> Disconnected';
        }
    }
}

/**
 * Update status message
 */
function updateStatus(message) {
    document.getElementById('statusMessage').textContent = message;
}

/**
 * Scroll messages to bottom
 */
function scrollToBottom() {
    const messagesArea = document.getElementById('messagesArea');
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

/**
 * Disable input during processing
 */
function disableInput() {
    document.getElementById('queryInput').disabled = true;
    document.getElementById('submitBtn').disabled = true;
}

/**
 * Enable input after processing
 */
function enableInput() {
    document.getElementById('queryInput').disabled = false;
    document.getElementById('submitBtn').disabled = false;
    document.getElementById('queryInput').focus();
}

/**
 * Handle key press events
 */
function handleKeyPress(event) {
    // Submit on Ctrl+Enter
    if (event.ctrlKey && event.key === 'Enter') {
        event.preventDefault();
        submitQuery();
    }
    // Clear on Escape
    else if (event.key === 'Escape') {
        event.target.value = '';
    }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Keyboard shortcut for focus
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            document.getElementById('queryInput').focus();
        }
    });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Show help modal
 */
function showHelp() {
    const helpModal = new bootstrap.Modal(document.getElementById('helpModal'));
    helpModal.show();
}

/**
 * Display processing step
 */
function displayProcessingStep(data) {
    if (!showDetails) return;

    const messagesArea = document.getElementById('messagesArea');

    // Remove typing indicator if present
    removeTypingIndicator();

    // Create processing step element
    const stepElement = document.createElement('div');
    stepElement.className = 'processing-step';
    stepElement.innerHTML = `
        ${data.message}
        ${data.details && Object.keys(data.details).length > 0 ?
            `<div class="parameter-display mt-2">${JSON.stringify(data.details, null, 2)}</div>` : ''}
    `;

    messagesArea.appendChild(stepElement);
    scrollToBottom();
}

/**
 * Show progress indicator
 */
function showProgressIndicator() {
    const messagesArea = document.getElementById('messagesArea');

    // Create progress indicator
    const progressId = 'progress-' + Date.now();
    currentProgressId = progressId;

    const progressElement = document.createElement('div');
    progressElement.id = progressId;
    progressElement.className = 'message assistant';
    progressElement.innerHTML = `
        <div class="progress-steps">
            <div class="progress-step" data-step="parse">
                <div class="progress-step-icon">
                    <i class="fas fa-search"></i>
                </div>
                <div class="progress-step-label">Analyze</div>
            </div>
            <div class="progress-step" data-step="route">
                <div class="progress-step-icon">
                    <i class="fas fa-directions"></i>
                </div>
                <div class="progress-step-label">Route</div>
            </div>
            <div class="progress-step" data-step="extract">
                <div class="progress-step-icon">
                    <i class="fas fa-filter"></i>
                </div>
                <div class="progress-step-label">Extract</div>
            </div>
            <div class="progress-step" data-step="search">
                <div class="progress-step-icon">
                    <i class="fas fa-database"></i>
                </div>
                <div class="progress-step-label">Search</div>
            </div>
            <div class="progress-step" data-step="assess">
                <div class="progress-step-icon">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="progress-step-label">Assess</div>
            </div>
            <div class="progress-step" data-step="format">
                <div class="progress-step-icon">
                    <i class="fas fa-file-alt"></i>
                </div>
                <div class="progress-step-label">Format</div>
            </div>
        </div>
    `;

    messagesArea.appendChild(progressElement);
    scrollToBottom();
}

/**
 * Update progress indicator
 */
function updateProgressIndicator(step) {
    if (!currentProgressId) return;

    const progressElement = document.getElementById(currentProgressId);
    if (!progressElement) return;

    // Map step names to progress steps
    const stepMap = {
        'parse': 'parse',
        'route': 'route',
        'strategy': 'route',
        'plan': 'route',
        'extract': 'extract',
        'parameters': 'extract',
        'results': 'search',
        'assess': 'assess',
        'format': 'format'
    };

    const mappedStep = stepMap[step] || step;

    // Update step statuses
    const steps = progressElement.querySelectorAll('.progress-step');
    let foundCurrent = false;

    steps.forEach(stepEl => {
        const stepName = stepEl.dataset.step;

        if (stepName === mappedStep) {
            stepEl.classList.remove('completed');
            stepEl.classList.add('active');
            foundCurrent = true;
        } else if (!foundCurrent) {
            stepEl.classList.remove('active');
            stepEl.classList.add('completed');
        } else {
            stepEl.classList.remove('active', 'completed');
        }
    });
}

/**
 * Remove progress indicator
 */
function removeProgressIndicator() {
    if (currentProgressId) {
        const element = document.getElementById(currentProgressId);
        if (element) {
            element.remove();
        }
        currentProgressId = null;
    }
}

/**
 * Toggle details display
 */
function toggleDetails() {
    showDetails = !showDetails;
    const toggleBtn = document.getElementById('detailsToggle');
    if (toggleBtn) {
        toggleBtn.innerHTML = showDetails ?
            '<i class="fas fa-eye"></i> Hide Details' :
            '<i class="fas fa-eye-slash"></i> Show Details';
    }
}