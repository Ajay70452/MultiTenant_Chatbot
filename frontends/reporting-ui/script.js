/**
 * AI Chat Activity Dashboard - Frontend Script
 *
 * Handles authentication, API calls, and UI rendering for the reporting dashboard.
 * Designed to be embedded in Ahsuite via iframe.
 */

// =============================================================================
// Configuration & State
// =============================================================================

const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : 'https://api.methodpro.comok';

let state = {
    clientId: null,
    token: null,
    sessionToken: null,
    clinicName: null,
    dateRange: 30,
    currentTab: 'leads',
    leadsPage: 1,
    conversationsPage: 1,
    pageSize: 20
};

// =============================================================================
// Initialization
// =============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Extract credentials from URL parameters
    const params = new URLSearchParams(window.location.search);
    state.clientId = params.get('client_id');
    state.token = params.get('token');

    if (!state.clientId || !state.token) {
        showAuthError('Missing client_id or token in URL parameters.');
        return;
    }

    // Exchange token for session token
    const authenticated = await exchangeToken();
    if (!authenticated) {
        return;
    }

    // Clean URL (remove token from history)
    const cleanUrl = window.location.pathname + '?client_id=' + state.clientId;
    window.history.replaceState({}, document.title, cleanUrl);

    // Set up event listeners
    setupEventListeners();

    // Load initial data
    await refreshAllData();
});

// =============================================================================
// Authentication
// =============================================================================

async function exchangeToken() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/clinical/auth/exchange`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: state.token })
        });

        if (!response.ok) {
            const error = await response.json();
            showAuthError(error.detail || 'Authentication failed.');
            return false;
        }

        const data = await response.json();
        state.sessionToken = data.session_token;
        state.clinicName = data.clinic_name;

        // Update UI with clinic name
        document.getElementById('clinic-name').textContent = state.clinicName;

        return true;
    } catch (error) {
        console.error('Token exchange error:', error);
        showAuthError('Failed to connect to server. Please try again later.');
        return false;
    }
}

function showAuthError(message) {
    const banner = document.getElementById('auth-error-banner');
    const messageEl = document.getElementById('auth-error-message');
    messageEl.textContent = message;
    banner.style.display = 'flex';
}

// =============================================================================
// API Helpers
// =============================================================================

async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'X-Client-Token': state.sessionToken || state.token,
        ...options.headers
    };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers
        });

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                showAuthError('Session expired. Please refresh the page.');
            }
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

function getDateRange() {
    const days = parseInt(state.dateRange);
    const toDate = new Date();
    const fromDate = new Date();
    fromDate.setDate(fromDate.getDate() - days);

    return {
        from: fromDate.toISOString(),
        to: toDate.toISOString()
    };
}

// =============================================================================
// Data Fetching
// =============================================================================

async function refreshAllData() {
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.classList.add('loading');

    try {
        await Promise.all([
            loadMetrics(),
            loadCurrentTabData()
        ]);
    } finally {
        refreshBtn.classList.remove('loading');
    }
}

async function loadMetrics() {
    try {
        const { from, to } = getDateRange();
        const data = await apiRequest(
            `/api/ahsuite/practices/${state.clientId}/chat/metrics?from_date=${from}&to_date=${to}`
        );

        // Update KPI cards
        document.getElementById('kpi-conversations').textContent = data.conversations_started.toLocaleString();
        document.getElementById('kpi-leads').textContent = data.leads_captured.toLocaleString();
        document.getElementById('kpi-rate').textContent = `${(data.lead_capture_rate * 100).toFixed(1)}%`;
        document.getElementById('kpi-after-hours').textContent = data.after_hours_conversations.toLocaleString();
    } catch (error) {
        console.error('Failed to load metrics:', error);
    }
}

async function loadLeads() {
    const tbody = document.getElementById('leads-table-body');
    tbody.innerHTML = '<tr class="loading-row"><td colspan="6">Loading leads...</td></tr>';

    try {
        const { from, to } = getDateRange();
        const data = await apiRequest(
            `/api/ahsuite/practices/${state.clientId}/chat/leads?page=${state.leadsPage}&page_size=${state.pageSize}&from_date=${from}&to_date=${to}`
        );

        if (data.leads.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No leads found in this period.</td></tr>';
            renderPagination('leads-pagination', 0, state.leadsPage, state.pageSize);
            return;
        }

        tbody.innerHTML = data.leads.map(lead => `
            <tr>
                <td>${formatDate(lead.started_at)}</td>
                <td>${escapeHtml(lead.patient_name || 'N/A')}</td>
                <td>${escapeHtml(lead.patient_phone || 'N/A')}</td>
                <td>${escapeHtml(lead.reason_for_visit || 'N/A')}</td>
                <td>${renderStatusBadge(lead.delivery_status)}</td>
                <td>
                    <button class="action-btn" onclick="viewTranscript('${lead.conversation_id}')">
                        View Chat
                    </button>
                </td>
            </tr>
        `).join('');

        renderPagination('leads-pagination', data.total, state.leadsPage, state.pageSize, 'leads');
    } catch (error) {
        console.error('Failed to load leads:', error);
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Failed to load leads. Please try again.</td></tr>';
    }
}

async function loadConversations() {
    const tbody = document.getElementById('conversations-table-body');
    tbody.innerHTML = '<tr class="loading-row"><td colspan="6">Loading conversations...</td></tr>';

    try {
        const { from, to } = getDateRange();
        const data = await apiRequest(
            `/api/ahsuite/practices/${state.clientId}/chat/conversations?page=${state.conversationsPage}&page_size=${state.pageSize}&from_date=${from}&to_date=${to}`
        );

        if (data.conversations.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="6">No conversations found in this period.</td></tr>';
            renderPagination('conversations-pagination', 0, state.conversationsPage, state.pageSize);
            return;
        }

        tbody.innerHTML = data.conversations.map(conv => `
            <tr>
                <td>${formatDate(conv.started_at)}</td>
                <td>${escapeHtml(formatStage(conv.current_stage))}</td>
                <td>${conv.message_count}</td>
                <td>${renderLeadBadge(conv.lead_captured)}</td>
                <td>${renderAfterHoursBadge(conv.is_after_hours)}</td>
                <td>
                    <button class="action-btn" onclick="viewTranscript('${conv.conversation_id}')">
                        View Chat
                    </button>
                </td>
            </tr>
        `).join('');

        renderPagination('conversations-pagination', data.total, state.conversationsPage, state.pageSize, 'conversations');
    } catch (error) {
        console.error('Failed to load conversations:', error);
        tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Failed to load conversations. Please try again.</td></tr>';
    }
}

async function loadCurrentTabData() {
    if (state.currentTab === 'leads') {
        await loadLeads();
    } else {
        await loadConversations();
    }
}

// =============================================================================
// Transcript Modal
// =============================================================================

async function viewTranscript(conversationId) {
    const modal = document.getElementById('transcript-modal');
    const body = document.getElementById('transcript-body');

    modal.style.display = 'flex';
    body.innerHTML = '<div class="transcript-loading">Loading transcript...</div>';

    try {
        const data = await apiRequest(
            `/api/ahsuite/practices/${state.clientId}/chat/conversations/${conversationId}/transcript`
        );

        if (data.messages.length === 0) {
            body.innerHTML = '<div class="transcript-loading">No messages in this conversation.</div>';
            return;
        }

        body.innerHTML = data.messages.map(msg => `
            <div class="transcript-message ${msg.sender_type}">
                <div class="message-header">
                    <span class="sender-label ${msg.sender_type}">
                        ${msg.sender_type === 'user' ? 'Patient' : 'AI Assistant'}
                    </span>
                    <span class="message-time">${formatDateTime(msg.created_at)}</span>
                </div>
                <div class="message-content">${escapeHtml(msg.message)}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load transcript:', error);
        body.innerHTML = '<div class="transcript-loading">Failed to load transcript. Please try again.</div>';
    }
}

function closeTranscriptModal() {
    document.getElementById('transcript-modal').style.display = 'none';
}

// =============================================================================
// UI Rendering Helpers
// =============================================================================

function renderStatusBadge(status) {
    if (!status) {
        return '<span class="status-badge pending">Pending</span>';
    }
    const statusLower = status.toLowerCase();
    if (statusLower === 'sent' || statusLower === 'delivered') {
        return '<span class="status-badge sent">Sent</span>';
    }
    if (statusLower === 'failed') {
        return '<span class="status-badge failed">Failed</span>';
    }
    return `<span class="status-badge pending">${escapeHtml(status)}</span>`;
}

function renderLeadBadge(isLead) {
    return isLead
        ? '<span class="status-badge yes">Yes</span>'
        : '<span class="status-badge no">No</span>';
}

function renderAfterHoursBadge(isAfterHours) {
    return isAfterHours
        ? '<span class="status-badge yes">Yes</span>'
        : '<span class="status-badge no">No</span>';
}

function renderPagination(containerId, total, currentPage, pageSize, type) {
    const container = document.getElementById(containerId);
    const totalPages = Math.ceil(total / pageSize);

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = '';

    // Previous button
    html += `<button class="page-btn" ${currentPage <= 1 ? 'disabled' : ''} onclick="goToPage('${type}', ${currentPage - 1})">
        &laquo; Prev
    </button>`;

    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        html += `<button class="page-btn" onclick="goToPage('${type}', 1)">1</button>`;
        if (startPage > 2) {
            html += '<span class="page-info">...</span>';
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage('${type}', ${i})">${i}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += '<span class="page-info">...</span>';
        }
        html += `<button class="page-btn" onclick="goToPage('${type}', ${totalPages})">${totalPages}</button>`;
    }

    // Next button
    html += `<button class="page-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="goToPage('${type}', ${currentPage + 1})">
        Next &raquo;
    </button>`;

    container.innerHTML = html;
}

function goToPage(type, page) {
    if (type === 'leads') {
        state.leadsPage = page;
        loadLeads();
    } else {
        state.conversationsPage = page;
        loadConversations();
    }
}

// =============================================================================
// Formatting Helpers
// =============================================================================

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

function formatStage(stage) {
    if (!stage) return 'Unknown';
    return stage
        .replace(/_/g, ' ')
        .toLowerCase()
        .replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================================================
// Event Listeners
// =============================================================================

function setupEventListeners() {
    // Date range selector
    document.getElementById('date-range').addEventListener('change', (e) => {
        state.dateRange = parseInt(e.target.value);
        state.leadsPage = 1;
        state.conversationsPage = 1;
        refreshAllData();
    });

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        refreshAllData();
    });

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.target.dataset.tab;
            switchTab(tab);
        });
    });

    // Close transcript modal
    document.getElementById('close-transcript-btn').addEventListener('click', closeTranscriptModal);

    // Close modal on overlay click
    document.getElementById('transcript-modal').addEventListener('click', (e) => {
        if (e.target.id === 'transcript-modal') {
            closeTranscriptModal();
        }
    });

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeTranscriptModal();
        }
    });
}

function switchTab(tab) {
    state.currentTab = tab;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Show/hide sections
    document.getElementById('leads-section').style.display = tab === 'leads' ? 'block' : 'none';
    document.getElementById('conversations-section').style.display = tab === 'conversations' ? 'block' : 'none';

    // Load data for the new tab
    loadCurrentTabData();
}

// Make functions globally accessible for inline onclick handlers
window.viewTranscript = viewTranscript;
window.goToPage = goToPage;
