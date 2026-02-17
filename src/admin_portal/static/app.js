/**
 * Practice Brain Admin Portal - JavaScript Application
 * Handles authentication, API calls, and UI interactions
 */

// =============================================================================
// Configuration
// =============================================================================

// API Base URL - Update this when hosting on S3 or different domain
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? '/admin'  // Local development
    : 'https://api.methodpro.com/admin';  // Production (S3 hosting)
let authToken = localStorage.getItem('adminToken');
let currentPracticeId = null;
let currentDocId = null;

// =============================================================================
// Utility Functions
// =============================================================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    toast.innerHTML = `
        <i class="fas ${icons[type]} toast-icon"></i>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        }
    };
    
    if (authToken) {
        options.headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        
        if (response.status === 401) {
            logout();
            throw new Error('Session expired');
        }
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API Error');
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function formatDate(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function getSourceIcon(sourceType) {
    const icons = {
        website: 'fa-globe',
        pdf: 'fa-file-pdf',
        doc: 'fa-file-word',
        faq: 'fa-question-circle',
        sop: 'fa-clipboard-list',
        other: 'fa-file'
    };
    return icons[sourceType] || icons.other;
}

// =============================================================================
// Authentication
// =============================================================================

function isAuthenticated() {
    return !!authToken;
}

function showLoginScreen() {
    document.getElementById('login-screen').style.display = 'flex';
    document.getElementById('dashboard').style.display = 'none';
}

function showDashboard() {
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('dashboard').style.display = 'flex';
    loadPractices();
}

async function login(username, password) {
    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        authToken = data.access_token;
        localStorage.setItem('adminToken', authToken);
        
        document.getElementById('admin-username').textContent = username;
        showToast('Login successful', 'success');
        showDashboard();
        
    } catch (error) {
        document.getElementById('login-error').textContent = error.message;
        document.getElementById('login-error').style.display = 'block';
    }
}

function logout() {
    authToken = null;
    localStorage.removeItem('adminToken');
    currentPracticeId = null;
    showLoginScreen();
    showToast('Logged out', 'info');
}

// =============================================================================
// Navigation
// =============================================================================

function navigateToSection(sectionId) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-section="${sectionId}"]`)?.classList.add('active');

    // Update sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(`${sectionId}-section`)?.classList.add('active');

    // Update header
    const titles = {
        practices: 'Practices',
        knowledge: 'Knowledge Library',
        health: 'Agent Health',
        'clinical-intake': 'Clinical Advisor Intake',
        audit: 'Audit Log'
    };
    document.getElementById('page-title').textContent = titles[sectionId] || 'Dashboard';

    // Show/hide practice selector
    const showSelector = ['knowledge', 'health', 'clinical-intake'].includes(sectionId);
    document.getElementById('practice-selector-container').style.display =
        showSelector ? 'block' : 'none';

    // Load section data
    if (sectionId === 'practices') {
        loadPractices();
    } else if (sectionId === 'knowledge' && currentPracticeId) {
        loadKnowledgeLibrary();
    } else if (sectionId === 'health' && currentPracticeId) {
        loadHealth();
    } else if (sectionId === 'clinical-intake' && currentPracticeId) {
        loadClinicalConfig();
    } else if (sectionId === 'audit') {
        loadAuditLog();
    }
}

// =============================================================================
// Practices
// =============================================================================

async function loadPractices() {
    const grid = document.getElementById('practices-grid');
    grid.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const data = await apiCall('/practices');
        
        if (data.practices.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-building"></i>
                    <h3>No Practices Found</h3>
                    <p>No practices have been configured yet.</p>
                </div>
            `;
            return;
        }
        
        grid.innerHTML = data.practices.map(practice => `
            <div class="practice-card" data-id="${practice.practice_id}">
                <div class="practice-card-header">
                    <div>
                        <h3>${practice.name}</h3>
                        <span class="practice-id">${practice.practice_id}</span>
                    </div>
                    <span class="status-badge ${practice.status}">${practice.status}</span>
                </div>
                <div class="practice-stats">
                    <div class="stat">
                        <span class="stat-value">${practice.document_count}</span>
                        <span class="stat-label">Documents</span>
                    </div>
                    <div class="stat">
                        <span class="stat-value">${formatDate(practice.last_indexed_at)}</span>
                        <span class="stat-label">Last Indexed</span>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Update practice selector
        const selector = document.getElementById('practice-selector');
        selector.innerHTML = '<option value="">Select Practice...</option>' +
            data.practices.map(p => `<option value="${p.practice_id}">${p.name}</option>`).join('');
        
        // Add click handlers
        document.querySelectorAll('.practice-card').forEach(card => {
            card.addEventListener('click', () => selectPractice(card.dataset.id));
        });
        
    } catch (error) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Error Loading Practices</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function selectPractice(practiceId) {
    currentPracticeId = practiceId;
    document.getElementById('practice-selector').value = practiceId;
    navigateToSection('knowledge');
}

// =============================================================================
// Knowledge Library
// =============================================================================

async function loadKnowledgeLibrary() {
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }
    
    await Promise.all([loadSources(), loadDocuments(), loadIndexStats()]);
}

async function loadSources() {
    const grid = document.getElementById('sources-grid');
    grid.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    try {
        const data = await apiCall(`/practices/${currentPracticeId}/sources`);
        
        grid.innerHTML = data.sources.map(source => `
            <div class="source-card">
                <div class="source-icon ${source.source_type}">
                    <i class="fas ${getSourceIcon(source.source_type)}"></i>
                </div>
                <h4>${source.source_type.toUpperCase()}</h4>
                <div class="source-meta">
                    <span>${source.document_count} docs</span>
                    <span class="status-badge ${source.status}">${source.status}</span>
                </div>
                <div class="source-meta" style="margin-top: 8px;">
                    <span>${source.total_chunks} chunks</span>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        grid.innerHTML = '<div class="empty-state"><p>Error loading sources</p></div>';
    }
}

async function loadDocuments() {
    const tbody = document.getElementById('documents-tbody');
    tbody.innerHTML = '<tr><td colspan="7"><div class="loading"><div class="spinner"></div></div></td></tr>';
    
    const statusFilter = document.getElementById('status-filter').value;
    const typeFilter = document.getElementById('type-filter').value;
    
    let query = `/practices/${currentPracticeId}/documents?`;
    if (statusFilter) query += `status=${statusFilter}&`;
    if (typeFilter) query += `source_type=${typeFilter}&`;
    
    try {
        const data = await apiCall(query);
        
        if (data.documents.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7">
                        <div class="empty-state">
                            <i class="fas fa-file"></i>
                            <h3>No Documents Found</h3>
                            <p>No documents match the current filters.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = data.documents.map(doc => `
            <tr data-doc-id="${doc.doc_id}">
                <td><span class="doc-title">${doc.title}</span></td>
                <td>
                    <span class="doc-type">
                        <i class="fas ${getSourceIcon(doc.source_type)}"></i>
                        ${doc.source_type}
                    </span>
                </td>
                <td><span class="status-badge ${doc.status}">${doc.status}</span></td>
                <td>
                    <div class="subagents">
                        ${doc.subagents_allowed.map(s => 
                            `<span class="subagent-badge ${s}">${s}</span>`
                        ).join('')}
                    </div>
                </td>
                <td>${doc.chunk_count}</td>
                <td>${formatDate(doc.last_indexed_at)}</td>
                <td>
                    <div class="action-buttons">
                        <button class="action-btn preview" title="Preview" onclick="previewDocument('${doc.doc_id}')">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn reindex" title="Re-index" onclick="reindexDocument('${doc.doc_id}')">
                            <i class="fas fa-sync"></i>
                        </button>
                        ${doc.status === 'disabled' 
                            ? `<button class="action-btn enable" title="Enable" onclick="enableDocument('${doc.doc_id}')">
                                <i class="fas fa-check"></i>
                               </button>`
                            : `<button class="action-btn disable" title="Disable" onclick="disableDocument('${doc.doc_id}')">
                                <i class="fas fa-ban"></i>
                               </button>`
                        }
                    </div>
                </td>
            </tr>
        `).join('');
        
    } catch (error) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h3>Error Loading Documents</h3>
                        <p>${error.message}</p>
                    </div>
                </td>
            </tr>
        `;
    }
}

async function previewDocument(docId) {
    currentDocId = docId;
    
    try {
        const doc = await apiCall(`/practices/${currentPracticeId}/documents/${docId}`);
        
        document.getElementById('preview-title').textContent = doc.title;
        
        document.getElementById('preview-meta').innerHTML = `
            <div class="meta-item">
                <span class="meta-label">Type</span>
                <span class="meta-value">${doc.source_type}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Status</span>
                <span class="meta-value"><span class="status-badge ${doc.status}">${doc.status}</span></span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Chunks</span>
                <span class="meta-value">${doc.chunk_count}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Last Indexed</span>
                <span class="meta-value">${formatDate(doc.metadata.last_indexed_at)}</span>
            </div>
        `;
        
        document.getElementById('preview-content').textContent = doc.preview_text;
        
        document.getElementById('preview-modal').classList.add('show');
        
    } catch (error) {
        showToast('Error loading document preview', 'error');
    }
}

async function reindexDocument(docId) {
    try {
        const result = await apiCall(
            `/practices/${currentPracticeId}/documents/${docId}/reindex`,
            'POST'
        );
        showToast(result.message, 'success');
        loadDocuments();
    } catch (error) {
        showToast('Error re-indexing document', 'error');
    }
}

async function disableDocument(docId) {
    try {
        const result = await apiCall(
            `/practices/${currentPracticeId}/documents/${docId}/disable`,
            'POST'
        );
        showToast(result.message, 'success');
        loadDocuments();
    } catch (error) {
        showToast('Error disabling document', 'error');
    }
}

async function enableDocument(docId) {
    try {
        const result = await apiCall(
            `/practices/${currentPracticeId}/documents/${docId}/enable`,
            'POST'
        );
        showToast(result.message, 'success');
        loadDocuments();
    } catch (error) {
        showToast('Error enabling document', 'error');
    }
}

async function reindexAllDocuments() {
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }
    
    if (!confirm('Are you sure you want to re-index all documents for this practice?')) {
        return;
    }
    
    try {
        const result = await apiCall(`/practices/${currentPracticeId}/reindex`, 'POST');
        showToast(result.message, 'success');
        loadKnowledgeLibrary();
    } catch (error) {
        showToast('Error re-indexing practice', 'error');
    }
}

// =============================================================================
// File Upload & Indexing
// =============================================================================

function showUploadModal() {
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }
    document.getElementById('upload-modal').classList.add('show');
    resetUploadForm();
}

function hideUploadModal() {
    document.getElementById('upload-modal').classList.remove('show');
    resetUploadForm();
}

function resetUploadForm() {
    document.getElementById('upload-file').value = '';
    document.getElementById('upload-title').value = '';
    document.getElementById('upload-source-type').value = 'pdf';
    document.getElementById('upload-subagents').value = 'chat,clinical';
    document.getElementById('file-name-display').textContent = 'No file selected';
    document.getElementById('upload-progress').style.display = 'none';
    document.getElementById('upload-btn').disabled = false;
    
    // Reset drag-drop area
    const dropZone = document.getElementById('drop-zone');
    dropZone.classList.remove('dragover', 'has-file');
}

function handleFileSelect(file) {
    if (!file) return;
    
    const allowedTypes = ['.txt', '.pdf', '.docx', '.doc', '.md', '.html', '.json'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedTypes.includes(ext)) {
        showToast(`Unsupported file type: ${ext}. Allowed: ${allowedTypes.join(', ')}`, 'error');
        return;
    }
    
    const maxSize = 20 * 1024 * 1024; // 20MB
    if (file.size > maxSize) {
        showToast('File too large. Maximum size: 20MB', 'error');
        return;
    }
    
    // Update UI
    document.getElementById('file-name-display').textContent = file.name;
    document.getElementById('drop-zone').classList.add('has-file');
    
    // Auto-fill title from filename
    if (!document.getElementById('upload-title').value) {
        const title = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
        document.getElementById('upload-title').value = title;
    }
    
    // Auto-detect source type
    const typeMap = {
        '.pdf': 'pdf',
        '.docx': 'doc',
        '.doc': 'doc',
        '.txt': 'website',
        '.md': 'website',
        '.html': 'website',
        '.json': 'other'
    };
    document.getElementById('upload-source-type').value = typeMap[ext] || 'other';
}

async function uploadDocument() {
    const fileInput = document.getElementById('upload-file');
    const file = fileInput.files[0];
    
    if (!file) {
        showToast('Please select a file', 'warning');
        return;
    }
    
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }
    
    const title = document.getElementById('upload-title').value || file.name;
    const sourceType = document.getElementById('upload-source-type').value;
    const subagents = document.getElementById('upload-subagents').value;
    
    // Show progress UI
    document.getElementById('upload-progress').style.display = 'block';
    document.getElementById('upload-btn').disabled = true;
    document.getElementById('upload-progress-text').textContent = 'Starting upload...';
    document.getElementById('upload-progress-bar').style.width = '5%';
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('source_type', sourceType);
    formData.append('subagents', subagents);
    
    try {
        // Use fetch with SSE endpoint for real-time progress
        const response = await fetch(`${API_BASE_URL}/practices/${currentPracticeId}/documents/upload-stream`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Upload request failed');
        }
        
        // Read the SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let finalResult = null;
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const text = decoder.decode(value);
            const lines = text.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        // Update progress bar
                        document.getElementById('upload-progress-bar').style.width = `${data.percent}%`;
                        document.getElementById('upload-progress-text').textContent = data.message;
                        
                        if (data.error) {
                            throw new Error(data.message);
                        }
                        
                        if (data.stage === 'complete' && data.result) {
                            finalResult = data.result;
                        }
                    } catch (parseError) {
                        if (parseError.message !== data?.message) {
                            console.warn('SSE parse error:', parseError);
                        }
                    }
                }
            }
        }
        
        if (finalResult) {
            showToast(`Successfully indexed "${finalResult.title}" with ${finalResult.chunk_count} chunks`, 'success');
            
            setTimeout(() => {
                hideUploadModal();
                loadKnowledgeLibrary();
            }, 1000);
        }
        
    } catch (error) {
        showToast(`Upload failed: ${error.message}`, 'error');
        document.getElementById('upload-progress').style.display = 'none';
        document.getElementById('upload-btn').disabled = false;
    }
}

async function indexTextContent() {
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }
    
    const title = document.getElementById('text-title').value.trim();
    const content = document.getElementById('text-content').value.trim();
    
    if (!title) {
        showToast('Please enter a title', 'warning');
        return;
    }
    
    if (content.length < 50) {
        showToast('Content too short. Minimum 50 characters required.', 'warning');
        return;
    }
    
    document.getElementById('index-text-btn').disabled = true;
    document.getElementById('index-text-btn').textContent = 'Indexing...';
    
    const formData = new FormData();
    formData.append('title', title);
    formData.append('content', content);
    formData.append('source_type', 'manual');
    formData.append('subagents', 'chat,clinical');
    
    try {
        const response = await fetch(`${API_BASE_URL}/practices/${currentPracticeId}/documents/index-text`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Indexing failed');
        }
        
        const result = await response.json();
        
        showToast(`Successfully indexed "${result.title}" with ${result.chunk_count} chunks`, 'success');
        
        // Reset form
        document.getElementById('text-title').value = '';
        document.getElementById('text-content').value = '';
        
        hideUploadModal();
        loadKnowledgeLibrary();
        
    } catch (error) {
        showToast(`Indexing failed: ${error.message}`, 'error');
    } finally {
        document.getElementById('index-text-btn').disabled = false;
        document.getElementById('index-text-btn').textContent = 'Index Text';
    }
}

async function loadIndexStats() {
    if (!currentPracticeId) return;
    
    try {
        const stats = await apiCall(`/practices/${currentPracticeId}/index-stats`);
        
        const statsEl = document.getElementById('index-stats');
        if (statsEl) {
            statsEl.innerHTML = `
                <div class="stat-item">
                    <i class="fas fa-database"></i>
                    <span>${stats.vector_count || 0} vectors in namespace</span>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading index stats:', error);
    }
}

// =============================================================================
// Health
// =============================================================================

async function loadHealth() {
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }
    
    // Reset UI
    setHealthStatus('chat', 'unknown', 'Checking...');
    setHealthStatus('clinical', 'unknown', 'Checking...');
    setHealthStatus('pinecone', 'unknown', 'Checking...');
    setHealthStatus('overall', 'unknown', 'Checking...');
    
    try {
        const health = await apiCall(`/practices/${currentPracticeId}/health`);
        
        // Chat endpoint
        setHealthStatus('chat', health.chat_endpoint.status, 
            health.chat_endpoint.status === 'healthy' ? 'Healthy' : 'Unhealthy',
            health.chat_endpoint.response_time_ms ? `${health.chat_endpoint.response_time_ms}ms` : ''
        );
        
        // Clinical endpoint
        setHealthStatus('clinical', health.clinical_endpoint.status,
            health.clinical_endpoint.status === 'healthy' ? 'Healthy' : 'Unhealthy',
            health.clinical_endpoint.response_time_ms ? `${health.clinical_endpoint.response_time_ms}ms` : ''
        );
        
        // Pinecone
        setHealthStatus('pinecone', health.pinecone.status,
            health.pinecone.status === 'healthy' ? 'Connected' : 'Disconnected',
            health.pinecone.vectors_count ? `${health.pinecone.vectors_count} vectors` : ''
        );
        
        // Overall
        setHealthStatus('overall', health.overall_status,
            health.overall_status === 'healthy' ? 'All Systems Operational' : 'Issues Detected'
        );
        
    } catch (error) {
        showToast('Error checking health', 'error');
    }
}

function setHealthStatus(type, status, text, extra = '') {
    const card = document.getElementById(`${type}-health-card`);
    const statusEl = document.getElementById(`${type}-status`);
    
    card.className = `health-card ${status}`;
    statusEl.className = `health-status ${status}`;
    statusEl.textContent = text;
    
    // Extra info (response time, vector count)
    const extraEl = type === 'pinecone' 
        ? document.getElementById('pinecone-vectors')
        : document.getElementById(`${type}-response-time`);
    
    if (extraEl) {
        extraEl.textContent = extra;
    }
}

// =============================================================================
// Audit Log
// =============================================================================

async function loadAuditLog() {
    const tbody = document.getElementById('audit-tbody');
    tbody.innerHTML = '<tr><td colspan="6"><div class="loading"><div class="spinner"></div></div></td></tr>';
    
    try {
        const data = await apiCall('/audit-log');
        
        if (data.entries.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6">
                        <div class="empty-state">
                            <i class="fas fa-history"></i>
                            <h3>No Audit Entries</h3>
                            <p>No admin actions have been logged yet.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = data.entries.map(entry => `
            <tr>
                <td>${formatDate(entry.timestamp)}</td>
                <td><span class="audit-action">${entry.action}</span></td>
                <td>${entry.actor || '-'}</td>
                <td>${entry.practice_id || '-'}</td>
                <td>${entry.doc_id ? entry.doc_id.substring(0, 8) + '...' : '-'}</td>
                <td><span class="audit-result ${entry.result}">${entry.result}</span></td>
            </tr>
        `).join('');
        
    } catch (error) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6">
                    <div class="empty-state">
                        <i class="fas fa-exclamation-triangle"></i>
                        <h3>Error Loading Audit Log</h3>
                        <p>${error.message}</p>
                    </div>
                </td>
            </tr>
        `;
    }
}

// =============================================================================
// Clinical Intake
// =============================================================================

async function loadClinicalConfig() {
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }

    try {
        const data = await apiCall(`/practices/${currentPracticeId}/clinical-config`);

        // Update status bar
        document.getElementById('config-version').textContent = data.profile_version || '--';
        document.getElementById('config-updated').textContent = data.updated_at ? formatDate(data.updated_at) : 'Never';

        // Populate form if config exists
        if (data.config) {
            populateClinicalForm(data.config);
        } else {
            resetClinicalForm();
        }

    } catch (error) {
        showToast('Error loading clinical config: ' + error.message, 'error');
    }
}

function populateClinicalForm(config) {
    // Philosophy section
    if (config.philosophy) {
        document.getElementById('primary-bias').value = config.philosophy.primary_bias || 'agd';
        document.getElementById('secondary-bias').value = config.philosophy.secondary_bias || '';
        document.getElementById('bias-strength').value = config.philosophy.bias_strength || 'moderate';
        document.getElementById('philosophy-context').value = config.philosophy.additional_context || '';
        updateCharCount('philosophy-context');
    }

    // Procedures section
    if (config.procedures_in_house) {
        const proc = config.procedures_in_house;

        // Endodontics checkboxes
        setCheckboxGroup('endo', proc.endodontics || []);

        // Extractions checkboxes
        setCheckboxGroup('extractions', proc.extractions || []);

        // Implants select
        document.getElementById('implants').value = proc.implants || 'not_performed';

        // Sedation checkboxes
        setCheckboxGroup('sedation', proc.sedation || []);

        // Pediatric
        if (proc.pediatric) {
            document.getElementById('pediatric-min-age').value = proc.pediatric.min_age || '';
            document.getElementById('pediatric-limited').checked = proc.pediatric.limited || false;
            document.getElementById('pediatric-referred').checked = proc.pediatric.referred || false;
        }

        // Other services
        setCheckboxGroup('other-services', proc.other_services || []);
    }

    // Equipment section
    if (config.equipment_technology) {
        const equip = config.equipment_technology;
        setCheckboxGroup('imaging', equip.imaging || []);
        setCheckboxGroup('digital', equip.digital_dentistry || []);
        document.getElementById('equipment-limitations').value = equip.limitations || '';
    }

    // Team section
    if (config.team_experience) {
        const team = config.team_experience;
        document.getElementById('provider-years').value = team.provider_years || '';
        document.getElementById('team-stability').value = team.team_stability || '';
        document.getElementById('hygiene-model').value = team.hygiene_model || '';
    }

    // Referral section
    if (config.referral_philosophy) {
        const ref = config.referral_philosophy;
        setCheckboxGroup('referral-reasons', ref.primary_reasons || []);
        document.getElementById('referral-view').value = ref.view || '';
    }

    // Risk section
    if (config.risk_sensitivity) {
        const risk = config.risk_sensitivity;
        document.getElementById('documentation-level').value = risk.documentation_level || '';
        setCheckboxGroup('caution-areas', risk.extra_caution_areas || []);
    }

    // Operational section
    if (config.operational_preferences) {
        const ops = config.operational_preferences;
        document.getElementById('treatment-approach').value = ops.treatment_approach || '';
        document.getElementById('case-complexity').value = ops.case_complexity || '';
    }

    // Additional notes
    document.getElementById('additional-notes').value = config.additional_notes || '';
    updateCharCount('additional-notes');
}

function resetClinicalForm() {
    document.getElementById('clinical-intake-form').reset();
    document.getElementById('philosophy-context-count').textContent = '0';
    document.getElementById('additional-notes-count').textContent = '0';
}

function setCheckboxGroup(name, values) {
    document.querySelectorAll(`input[name="${name}"]`).forEach(cb => {
        cb.checked = values.includes(cb.value);
    });
}

function getCheckboxGroup(name) {
    const values = [];
    document.querySelectorAll(`input[name="${name}"]:checked`).forEach(cb => {
        values.push(cb.value);
    });
    return values;
}

function collectClinicalConfig() {
    return {
        philosophy: {
            primary_bias: document.getElementById('primary-bias').value,
            secondary_bias: document.getElementById('secondary-bias').value || null,
            bias_strength: document.getElementById('bias-strength').value,
            additional_context: document.getElementById('philosophy-context').value || null
        },
        procedures_in_house: {
            endodontics: getCheckboxGroup('endo'),
            extractions: getCheckboxGroup('extractions'),
            implants: document.getElementById('implants').value,
            sedation: getCheckboxGroup('sedation'),
            pediatric: {
                min_age: parseInt(document.getElementById('pediatric-min-age').value) || null,
                limited: document.getElementById('pediatric-limited').checked,
                referred: document.getElementById('pediatric-referred').checked
            },
            other_services: getCheckboxGroup('other-services')
        },
        equipment_technology: {
            imaging: getCheckboxGroup('imaging'),
            digital_dentistry: getCheckboxGroup('digital'),
            other: [],
            limitations: document.getElementById('equipment-limitations').value || null
        },
        team_experience: {
            provider_years: document.getElementById('provider-years').value || null,
            team_stability: document.getElementById('team-stability').value || null,
            hygiene_model: document.getElementById('hygiene-model').value || null
        },
        referral_philosophy: {
            primary_reasons: getCheckboxGroup('referral-reasons'),
            view: document.getElementById('referral-view').value || null
        },
        risk_sensitivity: {
            documentation_level: document.getElementById('documentation-level').value || null,
            extra_caution_areas: getCheckboxGroup('caution-areas')
        },
        operational_preferences: {
            treatment_approach: document.getElementById('treatment-approach').value || null,
            case_complexity: document.getElementById('case-complexity').value || null
        },
        additional_notes: document.getElementById('additional-notes').value || null
    };
}

async function saveClinicalConfig() {
    if (!currentPracticeId) {
        showToast('Please select a practice first', 'warning');
        return;
    }

    const saveBtn = document.getElementById('save-clinical-config-btn');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    saveBtn.disabled = true;

    try {
        const config = collectClinicalConfig();

        const result = await apiCall(
            `/practices/${currentPracticeId}/clinical-config`,
            'PUT',
            { config }
        );

        showToast('Clinical configuration saved successfully', 'success');

        // Update UI
        document.getElementById('config-version').textContent = result.profile_version;
        document.getElementById('config-updated').textContent = formatDate(new Date().toISOString());

    } catch (error) {
        showToast('Error saving configuration: ' + error.message, 'error');
    } finally {
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    }
}

function updateCharCount(textareaId) {
    const textarea = document.getElementById(textareaId);
    const countEl = document.getElementById(`${textareaId}-count`);
    if (textarea && countEl) {
        countEl.textContent = textarea.value.length;
    }
}

// =============================================================================
// Event Listeners
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Check authentication
    if (isAuthenticated()) {
        showDashboard();
    } else {
        showLoginScreen();
    }
    
    // Login form
    document.getElementById('login-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        login(username, password);
    });
    
    // Logout
    document.getElementById('logout-btn').addEventListener('click', logout);
    
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navigateToSection(item.dataset.section);
        });
    });
    
    // Practice selector
    document.getElementById('practice-selector').addEventListener('change', (e) => {
        if (e.target.value) {
            currentPracticeId = e.target.value;
            const activeSection = document.querySelector('.section.active');
            if (activeSection.id === 'knowledge-section') {
                loadKnowledgeLibrary();
            } else if (activeSection.id === 'health-section') {
                loadHealth();
            } else if (activeSection.id === 'clinical-intake-section') {
                loadClinicalConfig();
            }
        }
    });
    
    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        const activeSection = document.querySelector('.section.active');
        if (activeSection.id === 'practices-section') {
            loadPractices();
        } else if (activeSection.id === 'knowledge-section') {
            loadKnowledgeLibrary();
        } else if (activeSection.id === 'health-section') {
            loadHealth();
        } else if (activeSection.id === 'clinical-intake-section') {
            loadClinicalConfig();
        } else if (activeSection.id === 'audit-section') {
            loadAuditLog();
        }
        showToast('Refreshed', 'info');
    });

    // Clinical Intake buttons
    const saveClinicalBtn = document.getElementById('save-clinical-config-btn');
    if (saveClinicalBtn) {
        saveClinicalBtn.addEventListener('click', saveClinicalConfig);
    }

    // Character count updates for textareas
    const philosophyContext = document.getElementById('philosophy-context');
    if (philosophyContext) {
        philosophyContext.addEventListener('input', () => updateCharCount('philosophy-context'));
    }

    const additionalNotes = document.getElementById('additional-notes');
    if (additionalNotes) {
        additionalNotes.addEventListener('input', () => updateCharCount('additional-notes'));
    }
    
    // Re-index all
    document.getElementById('reindex-all-btn').addEventListener('click', reindexAllDocuments);
    
    // Ping all
    document.getElementById('ping-all-btn').addEventListener('click', loadHealth);
    
    // Filters
    document.getElementById('status-filter').addEventListener('change', loadDocuments);
    document.getElementById('type-filter').addEventListener('change', loadDocuments);
    
    // Modal close
    document.getElementById('close-preview').addEventListener('click', () => {
        document.getElementById('preview-modal').classList.remove('show');
    });
    document.getElementById('close-preview-btn').addEventListener('click', () => {
        document.getElementById('preview-modal').classList.remove('show');
    });
    
    // Preview re-index
    document.getElementById('preview-reindex-btn').addEventListener('click', () => {
        if (currentDocId) {
            reindexDocument(currentDocId);
            document.getElementById('preview-modal').classList.remove('show');
        }
    });
    
    // Close modal on outside click
    document.getElementById('preview-modal').addEventListener('click', (e) => {
        if (e.target.id === 'preview-modal') {
            document.getElementById('preview-modal').classList.remove('show');
        }
    });
    
    // Practice search
    document.getElementById('practice-search').addEventListener('input', (e) => {
        const search = e.target.value.toLowerCase();
        document.querySelectorAll('.practice-card').forEach(card => {
            const name = card.querySelector('h3').textContent.toLowerCase();
            const id = card.querySelector('.practice-id').textContent.toLowerCase();
            card.style.display = (name.includes(search) || id.includes(search)) ? 'block' : 'none';
        });
    });
    
    // Upload modal
    const addDocBtn = document.getElementById('add-doc-btn');
    if (addDocBtn) {
        addDocBtn.addEventListener('click', showUploadModal);
    }
    
    const closeUploadBtn = document.getElementById('close-upload');
    if (closeUploadBtn) {
        closeUploadBtn.addEventListener('click', hideUploadModal);
    }
    
    const cancelUploadBtn = document.getElementById('cancel-upload-btn');
    if (cancelUploadBtn) {
        cancelUploadBtn.addEventListener('click', hideUploadModal);
    }
    
    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', uploadDocument);
    }
    
    const indexTextBtn = document.getElementById('index-text-btn');
    if (indexTextBtn) {
        indexTextBtn.addEventListener('click', indexTextContent);
    }
    
    // File input change
    const uploadFile = document.getElementById('upload-file');
    if (uploadFile) {
        uploadFile.addEventListener('change', (e) => {
            if (e.target.files[0]) {
                handleFileSelect(e.target.files[0]);
            }
        });
    }
    
    // Drag and drop
    const dropZone = document.getElementById('drop-zone');
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                // Set file to input
                const dt = new DataTransfer();
                dt.items.add(file);
                document.getElementById('upload-file').files = dt.files;
                handleFileSelect(file);
            }
        });
        
        // Click to select file - only on the drop zone content, not on child elements that handle their own clicks
        dropZone.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            document.getElementById('upload-file').click();
        });
    }
    
    // Upload modal tabs
    document.querySelectorAll('.upload-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.upload-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            const tabType = tab.dataset.tab;
            document.querySelectorAll('.upload-panel').forEach(panel => {
                panel.classList.toggle('active', panel.dataset.panel === tabType);
            });
            
            // Toggle buttons based on tab
            const uploadBtn = document.getElementById('upload-btn');
            const indexTextBtn = document.getElementById('index-text-btn');
            if (tabType === 'file') {
                uploadBtn.style.display = 'inline-flex';
                indexTextBtn.style.display = 'none';
            } else {
                uploadBtn.style.display = 'none';
                indexTextBtn.style.display = 'inline-flex';
            }
        });
    });
    
    // Close upload modal on outside click
    const uploadModal = document.getElementById('upload-modal');
    if (uploadModal) {
        uploadModal.addEventListener('click', (e) => {
            if (e.target.id === 'upload-modal') {
                hideUploadModal();
            }
        });
    }
});
