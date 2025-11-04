console.log("Chat widget script loaded");
document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const chatBubble = document.getElementById('chat-bubble');
    const chatWidgetContainer = document.getElementById('chat-widget-container');
    const chatCloseBtn = document.getElementById('chat-close-btn');
    const chatForm = document.getElementById('chat-input-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');

    // --- API and Client Configuration ---
    const API_ENDPOINT = "http://127.0.0.1:8000/api/chat"; // Your FastAPI backend URL
    const CLIENT_ID = "443f5716-27d3-463a-9377-33a666f5ad88"; // This will eventually be dynamic

    // --- State Management ---
    // Use sessionStorage to keep conversation ID for the duration of the tab session
    let conversationId = sessionStorage.getItem('conversation_id');

    // --- Functions ---
    const toggleWidget = () => {
        chatWidgetContainer.classList.toggle('open');
    };

    const appendMessage = (sender, message) => {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        messageDiv.innerHTML = message; // Using innerHTML to render links
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight; // Auto-scroll to bottom
    };

    const setTypingIndicator = (isTyping) => {
        typingIndicator.style.display = isTyping ? 'block' : 'none';
    };

    const sendMessageToApi = async (userMessage) => {
        appendMessage('user', userMessage);
        setTypingIndicator(true);

        const payload = {
            message: userMessage,
            client_id: CLIENT_ID,
        };
        
        if (conversationId) {
            payload.conversation_id = conversationId;
        }
        
        try {
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload), 
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.conversation_id && !conversationId) {
                conversationId = data.conversation_id;
                sessionStorage.setItem('conversation_id', conversationId);
            }

            appendMessage('bot', data.response);

        } catch (error) {
            console.error("Failed to send message:", error);
            appendMessage('bot', "I'm sorry, I'm having trouble connecting. Please try again later.");
        } finally {
            setTypingIndicator(false);
        }
    };
    
    // --- Initial Bot Message ---
    const welcomeMessage = "Hi! What can I help you with?";
    appendMessage('bot', welcomeMessage);

    // --- Event Listeners ---
    chatBubble.addEventListener('click', toggleWidget);
    chatCloseBtn.addEventListener('click', toggleWidget);

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault(); // Prevent page reload
        const userMessage = chatInput.value.trim();
        if (userMessage) {
            sendMessageToApi(userMessage);
            chatInput.value = '';
        }
    });
});