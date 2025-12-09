/**
 * Clinical Advisor Frontend - Practice Brain
 *
 * This micro-app provides a doctor-facing interface for the Clinical Advisor.
 * It reads authentication from URL parameters and supports image uploads.
 *
 * URL Parameters:
 *   - token: The X-Client-Token for authentication (required)
 *   - api: Optional API base URL override (defaults to relative /api)
 *
 * Example URL:
 *   https://yourapp.com/clinical-ui/?token=abc123def456
 */

(function() {
    'use strict';

    // ==========================================================================
    // Configuration
    // ==========================================================================

    const CONFIG = {
        // API endpoint - can be overridden via URL parameter
        apiBaseUrl: getUrlParam('api') || '/api/clinical',

        // Auth token from URL
        authToken: getUrlParam('token'),

        // Maximum image size (10MB)
        maxImageSize: 10 * 1024 * 1024,

        // Supported image types
        supportedImageTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],

        // Max conversation history to send (for context)
        maxHistoryLength: 20,
    };

    // ==========================================================================
    // State
    // ==========================================================================

    const state = {
        // Conversation history (maintained client-side since endpoint is stateless)
        conversationHistory: [],

        // Currently attached image (Base64)
        attachedImage: null,
        attachedImageName: null,

        // Loading state
        isLoading: false,

        // Connection status
        isConnected: false,
    };

    // ==========================================================================
    // DOM Elements
    // ==========================================================================

    let elements = {};

    function initElements() {
        elements = {
            // Status
            connectionStatus: document.getElementById('connection-status'),
            authErrorBanner: document.getElementById('auth-error-banner'),
            authErrorMessage: document.getElementById('auth-error-message'),

            // Messages
            messagesContainer: document.getElementById('messages-container'),
            typingIndicator: document.getElementById('typing-indicator'),

            // Image handling
            imagePreviewArea: document.getElementById('image-preview-area'),
            imagePreview: document.getElementById('image-preview'),
            imageName: document.getElementById('image-name'),
            removeImageBtn: document.getElementById('remove-image-btn'),
            attachBtn: document.getElementById('attach-btn'),
            imageInput: document.getElementById('image-input'),

            // Input
            inputForm: document.getElementById('input-form'),
            messageInput: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),

            // Modal
            metadataModal: document.getElementById('metadata-modal'),
            metadataBody: document.getElementById('metadata-body'),
            closeModalBtn: document.getElementById('close-modal-btn'),
        };
    }

    // ==========================================================================
    // URL Parameter Handling
    // ==========================================================================

    function getUrlParam(param) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(param);
    }

    // ==========================================================================
    // Connection & Auth
    // ==========================================================================

    function updateConnectionStatus(status, message) {
        const statusDot = elements.connectionStatus.querySelector('.status-dot');
        const statusText = elements.connectionStatus.querySelector('.status-text');

        elements.connectionStatus.className = 'connection-status ' + status;
        statusText.textContent = message;

        state.isConnected = (status === 'connected');
    }

    function showAuthError(message) {
        elements.authErrorBanner.style.display = 'flex';
        elements.authErrorMessage.textContent = message;
        updateConnectionStatus('error', 'Not Connected');
    }

    function hideAuthError() {
        elements.authErrorBanner.style.display = 'none';
    }

    async function checkConnection() {
        if (!CONFIG.authToken) {
            showAuthError('No access token provided. Please include ?token=YOUR_TOKEN in the URL.');
            return false;
        }

        updateConnectionStatus('connecting', 'Connecting...');

        try {
            const response = await fetch(`${CONFIG.apiBaseUrl}/profile`, {
                method: 'GET',
                headers: {
                    'X-Client-Token': CONFIG.authToken,
                },
            });

            if (response.ok) {
                const data = await response.json();
                hideAuthError();
                updateConnectionStatus('connected', `Connected: ${data.clinic_name || 'Practice'}`);

                if (!data.has_profile) {
                    appendSystemMessage('Note: Your practice profile is not yet configured. Responses will use general clinical guidelines.');
                }
                return true;
            } else if (response.status === 401) {
                showAuthError('Invalid or expired access token. Please contact support.');
                return false;
            } else {
                showAuthError(`Connection failed: ${response.statusText}`);
                return false;
            }
        } catch (error) {
            console.error('Connection check failed:', error);
            showAuthError('Unable to connect to the server. Please check your network connection.');
            return false;
        }
    }

    // ==========================================================================
    // Message Handling
    // ==========================================================================

    function appendMessage(role, content, metadata = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        // Message content
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (role === 'assistant') {
            // Parse markdown-like formatting for assistant messages
            contentDiv.innerHTML = formatResponse(content);
        } else {
            contentDiv.textContent = content;
        }
        messageDiv.appendChild(contentDiv);

        // Add metadata button for assistant messages
        if (role === 'assistant' && metadata) {
            const metaBtn = document.createElement('button');
            metaBtn.className = 'message-meta-btn';
            metaBtn.title = 'View response details';
            metaBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
            `;
            metaBtn.onclick = () => showMetadataModal(metadata);
            messageDiv.appendChild(metaBtn);

            // Add safety warnings inline if present
            if (metadata.safety_warnings && metadata.safety_warnings.length > 0) {
                const warningsDiv = document.createElement('div');
                warningsDiv.className = 'safety-warnings';
                warningsDiv.innerHTML = metadata.safety_warnings.map(w =>
                    `<span class="warning-badge"><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> ${escapeHtml(w)}</span>`
                ).join('');
                messageDiv.appendChild(warningsDiv);
            }

            // Add referral badge if needed
            if (metadata.requires_referral) {
                const referralDiv = document.createElement('div');
                referralDiv.className = 'referral-badge';
                referralDiv.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="8.5" cy="7" r="4"></circle>
                        <line x1="20" y1="8" x2="20" y2="14"></line>
                        <line x1="23" y1="11" x2="17" y2="11"></line>
                    </svg>
                    Specialist referral may be indicated
                `;
                messageDiv.appendChild(referralDiv);
            }
        }

        // Timestamp
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        messageDiv.appendChild(timeDiv);

        elements.messagesContainer.appendChild(messageDiv);
        scrollToBottom();

        // Add to history
        state.conversationHistory.push({ role, content });

        // Trim history if too long
        if (state.conversationHistory.length > CONFIG.maxHistoryLength) {
            state.conversationHistory = state.conversationHistory.slice(-CONFIG.maxHistoryLength);
        }
    }

    function appendSystemMessage(content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';
        messageDiv.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>${escapeHtml(content)}</span>
        `;
        elements.messagesContainer.appendChild(messageDiv);
        scrollToBottom();
    }

    function appendImageMessage(imageSrc, imageName) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user image-message';
        messageDiv.innerHTML = `
            <div class="attached-image">
                <img src="${imageSrc}" alt="Attached: ${escapeHtml(imageName)}">
                <span class="image-label">${escapeHtml(imageName)}</span>
            </div>
        `;
        elements.messagesContainer.appendChild(messageDiv);
        scrollToBottom();
    }

    function formatResponse(text) {
        // Basic markdown-like formatting
        let formatted = escapeHtml(text);

        // Bold: **text**
        formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Headers: lines starting with ##
        formatted = formatted.replace(/^## (.+)$/gm, '<h4>$1</h4>');
        formatted = formatted.replace(/^### (.+)$/gm, '<h5>$1</h5>');

        // Lists: lines starting with -
        formatted = formatted.replace(/^- (.+)$/gm, '<li>$1</li>');
        formatted = formatted.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');

        return formatted;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function scrollToBottom() {
        elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
    }

    // ==========================================================================
    // Loading State
    // ==========================================================================

    function setLoading(isLoading) {
        state.isLoading = isLoading;
        elements.typingIndicator.style.display = isLoading ? 'flex' : 'none';
        elements.sendBtn.disabled = isLoading;
        elements.messageInput.disabled = isLoading;

        if (isLoading) {
            scrollToBottom();
        }
    }

    // ==========================================================================
    // Image Handling
    // ==========================================================================

    function handleImageSelect(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Validate file type
        if (!CONFIG.supportedImageTypes.includes(file.type)) {
            appendSystemMessage(`Unsupported image type. Please use: ${CONFIG.supportedImageTypes.join(', ')}`);
            return;
        }

        // Validate file size
        if (file.size > CONFIG.maxImageSize) {
            appendSystemMessage(`Image too large. Maximum size: ${CONFIG.maxImageSize / (1024 * 1024)}MB`);
            return;
        }

        // Read and convert to Base64
        const reader = new FileReader();
        reader.onload = (e) => {
            state.attachedImage = e.target.result;
            state.attachedImageName = file.name;
            showImagePreview(e.target.result, file.name);
        };
        reader.onerror = () => {
            appendSystemMessage('Failed to read image file. Please try again.');
        };
        reader.readAsDataURL(file);
    }

    function showImagePreview(imageSrc, imageName) {
        elements.imagePreview.src = imageSrc;
        elements.imageName.textContent = imageName;
        elements.imagePreviewArea.style.display = 'block';
        elements.attachBtn.classList.add('has-image');
    }

    function clearImageAttachment() {
        state.attachedImage = null;
        state.attachedImageName = null;
        elements.imageInput.value = '';
        elements.imagePreviewArea.style.display = 'none';
        elements.attachBtn.classList.remove('has-image');
    }

    // ==========================================================================
    // API Communication
    // ==========================================================================

    async function sendMessage(message, imageBase64 = null) {
        if (!state.isConnected) {
            appendSystemMessage('Not connected. Please check your authentication.');
            return;
        }

        setLoading(true);

        // Show user message
        appendMessage('user', message);

        // Show attached image if present
        if (imageBase64 && state.attachedImageName) {
            appendImageMessage(imageBase64, state.attachedImageName);
        }

        try {
            const payload = {
                message: message,
                conversation_history: state.conversationHistory.slice(0, -1), // Exclude the message we just added
            };

            if (imageBase64) {
                payload.image_base64 = imageBase64;
            }

            const response = await fetch(`${CONFIG.apiBaseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-Token': CONFIG.authToken,
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                if (response.status === 401) {
                    showAuthError('Session expired. Please refresh and re-authenticate.');
                    throw new Error('Authentication failed');
                } else if (response.status === 404) {
                    throw new Error('Practice profile not configured. Please contact support.');
                }
                throw new Error(`API Error: ${response.statusText}`);
            }

            const data = await response.json();

            // Build metadata object
            const metadata = {
                confidence_level: data.confidence_level,
                requires_referral: data.requires_referral,
                safety_warnings: data.safety_warnings || [],
                has_image: data.has_image,
            };

            appendMessage('assistant', data.response, metadata);

        } catch (error) {
            console.error('Failed to send message:', error);
            appendSystemMessage(`Error: ${error.message}`);
        } finally {
            setLoading(false);
            clearImageAttachment();
        }
    }

    // ==========================================================================
    // Metadata Modal
    // ==========================================================================

    function showMetadataModal(metadata) {
        const confidenceColors = {
            low: '#e74c3c',
            moderate: '#f39c12',
            high: '#27ae60',
        };

        elements.metadataBody.innerHTML = `
            <div class="meta-item">
                <span class="meta-label">Confidence Level</span>
                <span class="meta-value confidence-${metadata.confidence_level}" style="color: ${confidenceColors[metadata.confidence_level] || '#666'}">
                    ${metadata.confidence_level?.toUpperCase() || 'Unknown'}
                </span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Referral Indicated</span>
                <span class="meta-value ${metadata.requires_referral ? 'referral-yes' : 'referral-no'}">
                    ${metadata.requires_referral ? 'Yes - Consider Specialist' : 'No'}
                </span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Image Analyzed</span>
                <span class="meta-value">${metadata.has_image ? 'Yes' : 'No'}</span>
            </div>
            ${metadata.safety_warnings?.length > 0 ? `
                <div class="meta-item warnings">
                    <span class="meta-label">Safety Warnings</span>
                    <ul class="meta-warnings-list">
                        ${metadata.safety_warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
            <div class="meta-disclaimer">
                This AI analysis is for reference only. Clinical correlation and professional judgment are required.
            </div>
        `;
        elements.metadataModal.style.display = 'flex';
    }

    function hideMetadataModal() {
        elements.metadataModal.style.display = 'none';
    }

    // ==========================================================================
    // Input Handling
    // ==========================================================================

    function handleFormSubmit(event) {
        event.preventDefault();

        const message = elements.messageInput.value.trim();
        if (!message && !state.attachedImage) return;

        // Send message with optional image
        sendMessage(message || 'Please analyze this image.', state.attachedImage);

        // Clear input
        elements.messageInput.value = '';
        autoResizeTextarea();
    }

    function handleKeyDown(event) {
        // Submit on Enter (without Shift)
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            elements.inputForm.dispatchEvent(new Event('submit'));
        }
    }

    function autoResizeTextarea() {
        const textarea = elements.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }

    // ==========================================================================
    // Welcome Message
    // ==========================================================================

    function showWelcomeMessage() {
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'welcome-message';
        welcomeDiv.innerHTML = `
            <div class="welcome-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 2a4 4 0 0 0-4 4c0 1.5.8 2.8 2 3.5V11a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1V9.5c1.2-.7 2-2 2-3.5a4 4 0 0 0-4-4z"/>
                    <path d="M12 12v10"/>
                    <path d="M8 17h8"/>
                </svg>
            </div>
            <h2>Welcome to Clinical Advisor</h2>
            <p>Your AI-powered clinical colleague, personalized to your practice philosophy.</p>
            <div class="welcome-suggestions">
                <span class="suggestion" data-message="What treatment options should I consider for moderate periodontitis?">Treatment for periodontitis</span>
                <span class="suggestion" data-message="Can you help me interpret this radiograph?">X-ray interpretation</span>
                <span class="suggestion" data-message="What are the contraindications for dental implants?">Implant contraindications</span>
            </div>
        `;
        elements.messagesContainer.appendChild(welcomeDiv);

        // Add click handlers for suggestions
        welcomeDiv.querySelectorAll('.suggestion').forEach(btn => {
            btn.addEventListener('click', () => {
                const message = btn.dataset.message;
                elements.messageInput.value = message;
                elements.messageInput.focus();
            });
        });
    }

    // ==========================================================================
    // Initialization
    // ==========================================================================

    async function init() {
        console.log('Clinical Advisor UI initializing...');

        initElements();

        // Set up event listeners
        elements.inputForm.addEventListener('submit', handleFormSubmit);
        elements.messageInput.addEventListener('keydown', handleKeyDown);
        elements.messageInput.addEventListener('input', autoResizeTextarea);

        elements.attachBtn.addEventListener('click', () => elements.imageInput.click());
        elements.imageInput.addEventListener('change', handleImageSelect);
        elements.removeImageBtn.addEventListener('click', clearImageAttachment);

        elements.closeModalBtn.addEventListener('click', hideMetadataModal);
        elements.metadataModal.addEventListener('click', (e) => {
            if (e.target === elements.metadataModal) hideMetadataModal();
        });

        // Show welcome message
        showWelcomeMessage();

        // Check connection
        const connected = await checkConnection();

        if (connected) {
            elements.messageInput.focus();
        }
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
