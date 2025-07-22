import os
from flask import Flask, request, jsonify, render_template_string, make_response
import openai
import base64
import json
from datetime import datetime
import requests
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)

# Configuration
OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Available models
MODELS = {
    "mistral": "mistralai/mistral-7b-instruct:free",
    "llama": "meta-llama/llama-3.2-11b-vision-instruct:free",
    "deepseek": "deepseek/deepseek-chat-v3.0324:free",
    "gemini": "google/gemini-2.0-flash-exp:free",
    "gemma": "google/gemma-3n-e4b-it:free",
    "kimi": "moonshotai/kimi-k2:free",
    "qwen": "qwen/qwen3-8b:free"
}

# In-memory storage
chat_history = {}
user_files = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def encode_file_to_base64(file):
    file_content = file.read()
    return base64.b64encode(file_content).decode('utf-8')

def process_file(file):
    filename = secure_filename(file.filename)
    file_id = str(uuid.uuid4())
    file_content = encode_file_to_base64(file)
    
    user_files[file_id] = {
        "filename": filename,
        "content": file_content,
        "uploaded_at": datetime.now().isoformat()
    }
    
    return file_id

def get_model_response(messages, model_name, temperature=0.7, max_tokens=2000, web_search=False, deep_thinking=False):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-vercel-app-url.vercel.app",
        "X-Title": "AI Chat App"
    }
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    if web_search:
        payload["transforms"] = ["web_search"]
    
    if deep_thinking:
        payload["transforms"] = ["deep_thought"]
    
    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
    return response.json()

# HTML Templates
BASE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Chat App</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        {content}
    </div>
    <script>{js}</script>
</body>
</html>
'''

CHAT_HTML = '''
<div class="chat-container">
    <div class="header">
        <h1>AI Chat Assistant</h1>
        <div class="controls">
            <select id="model-selector">
                {% for model in models %}
                <option value="{{ model }}">{{ model|title }}</option>
                {% endfor %}
            </select>
            <button id="upload-btn">Upload File</button>
            <label class="switch">
                <input type="checkbox" id="web-search">
                <span class="slider round"></span>
                <span>Web Search</span>
            </label>
            <label class="switch">
                <input type="checkbox" id="deep-thinking">
                <span class="slider round"></span>
                <span>Deep Thinking</span>
            </label>
        </div>
    </div>
    
    <div class="chat-history" id="chat-history">
        <!-- Messages will appear here -->
    </div>
    
    <div class="input-area">
        <div class="attachments" id="attachments">
            <!-- Attached files will appear here -->
        </div>
        <div class="message-input">
            <textarea id="user-input" placeholder="Type your message..."></textarea>
            <button id="send-btn">Send</button>
        </div>
    </div>
</div>
'''

UPLOAD_HTML = '''
<div class="upload-container">
    <h2>Upload File</h2>
    <form id="upload-form" enctype="multipart/form-data">
        <input type="file" name="file" id="file-input" accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg">
        <button type="submit">Upload</button>
    </form>
    <div id="upload-status"></div>
    <button id="back-to-chat">Back to Chat</button>
</div>
'''

CSS = '''
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f5f7fa;
    color: #333;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.chat-container {
    display: flex;
    flex-direction: column;
    height: 90vh;
    background-color: white;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    overflow: hidden;
}

.header {
    padding: 15px 20px;
    background-color: #4a6fa5;
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.controls {
    display: flex;
    gap: 15px;
    align-items: center;
}

select, button {
    padding: 8px 12px;
    border-radius: 5px;
    border: none;
    background-color: #f0f4f8;
    cursor: pointer;
}

button {
    background-color: #3a5a78;
    color: white;
    transition: background-color 0.3s;
}

button:hover {
    background-color: #2c3e50;
}

.chat-history {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 15px;
}

.message {
    max-width: 80%;
    padding: 12px 16px;
    border-radius: 18px;
    line-height: 1.4;
}

.user-message {
    align-self: flex-end;
    background-color: #4a6fa5;
    color: white;
    border-bottom-right-radius: 5px;
}

.ai-message {
    align-self: flex-start;
    background-color: #f0f4f8;
    border-bottom-left-radius: 5px;
}

.input-area {
    padding: 15px;
    border-top: 1px solid #e1e5eb;
}

.message-input {
    display: flex;
    gap: 10px;
}

textarea {
    flex: 1;
    padding: 12px;
    border-radius: 5px;
    border: 1px solid #ddd;
    resize: none;
    min-height: 50px;
    max-height: 150px;
}

.attachments {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
    flex-wrap: wrap;
}

.attachment {
    background-color: #f0f4f8;
    padding: 5px 10px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    gap: 5px;
}

.attachment button {
    background: none;
    color: #666;
    padding: 0;
    font-size: 12px;
}

.loading-dots span {
    animation: blink 1.4s infinite;
    animation-fill-mode: both;
    font-size: 24px;
}

.loading-dots span:nth-child(2) {
    animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
    animation-delay: 0.4s;
}

@keyframes blink {
    0% { opacity: 0.2; }
    20% { opacity: 1; }
    100% { opacity: 0.2; }
}

/* Switch styles */
.switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 24px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #ccc;
    transition: .4s;
    border-radius: 24px;
}

.slider:before {
    position: absolute;
    content: "";
    height: 16px;
    width: 16px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
    border-radius: 50%;
}

input:checked + .slider {
    background-color: #4a6fa5;
}

input:checked + .slider:before {
    transform: translateX(26px);
}

.switch span:last-child {
    margin-left: 5px;
    font-size: 14px;
}

/* Upload page styles */
.upload-container {
    max-width: 500px;
    margin: 50px auto;
    padding: 30px;
    background-color: white;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    text-align: center;
}

#file-input {
    margin: 20px 0;
}

#upload-status {
    margin: 15px 0;
    color: #4a6fa5;
}
'''

JS = '''
document.addEventListener('DOMContentLoaded', function() {
    // Generate a unique user ID for this session
    const userId = 'user_' + Math.random().toString(36).substr(2, 9);
    let attachedFiles = [];
    
    // DOM elements
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const uploadBtn = document.getElementById('upload-btn');
    const attachmentsContainer = document.getElementById('attachments');
    const modelSelector = document.getElementById('model-selector');
    const webSearchToggle = document.getElementById('web-search');
    const deepThinkingToggle = document.getElementById('deep-thinking');
    
    // Upload page elements (if we're on the chat page)
    const backToChatBtn = document.getElementById('back-to-chat');
    if (backToChatBtn) {
        backToChatBtn.addEventListener('click', () => {
            window.location.href = '/';
        });
    }
    
    // Send message function
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message && attachedFiles.length === 0) return;
        
        // Add user message to chat
        addMessageToChat('user', message);
        
        // Clear input
        userInput.value = '';
        
        // Show loading indicator
        const loadingId = 'loading-' + Date.now();
        chatHistory.innerHTML += `
            <div class="message ai-message" id="${loadingId}">
                <div class="loading-dots">
                    <span>.</span><span>.</span><span>.</span>
                </div>
            </div>
        `;
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        try {
            // Prepare data for API
            const data = {
                user_id: userId,
                message: message,
                model: modelSelector.value,
                file_ids: attachedFiles.map(f => f.id),
                web_search: webSearchToggle.checked,
                deep_thinking: deepThinkingToggle.checked
            };
            
            // Call API
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (result.error) {
                throw new Error(result.error);
            }
            
            // Remove loading indicator
            const loadingElement = document.getElementById(loadingId);
            if (loadingElement) loadingElement.remove();
            
            // Add AI response to chat
            addMessageToChat('assistant', result.response);
            
            // Clear attachments after successful send
            attachedFiles = [];
            renderAttachments();
        } catch (error) {
            console.error('Error:', error);
            // Update loading message with error
            const loadingElement = document.getElementById(loadingId);
            if (loadingElement) {
                loadingElement.innerHTML = `Error: ${error.message}`;
            }
        }
    }
    
    // Add message to chat UI
    function addMessageToChat(role, content) {
        const messageClass = role === 'user' ? 'user-message' : 'ai-message';
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${messageClass}`;
        messageDiv.textContent = content;
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    
    // Handle file upload
    uploadBtn.addEventListener('click', () => {
        window.location.href = '/upload';
    });
    
    // Handle send button click
    sendBtn.addEventListener('click', sendMessage);
    
    // Handle Enter key in textarea
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Render attached files
    function renderAttachments() {
        attachmentsContainer.innerHTML = '';
        attachedFiles.forEach(file => {
            const attachmentDiv = document.createElement('div');
            attachmentDiv.className = 'attachment';
            attachmentDiv.innerHTML = `
                <span>${file.name}</span>
                <button data-id="${file.id}">×</button>
            `;
            attachmentsContainer.appendChild(attachmentDiv);
        });
        
        // Add event listeners to remove buttons
        document.querySelectorAll('.attachment button').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const fileId = e.target.getAttribute('data-id');
                attachedFiles = attachedFiles.filter(f => f.id !== fileId);
                renderAttachments();
            });
        });
    }
    
    // If we're on the upload page
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const fileInput = document.getElementById('file-input');
            const statusDiv = document.getElementById('upload-status');
            
            if (fileInput.files.length === 0) {
                statusDiv.textContent = 'Please select a file';
                return;
            }
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            try {
                statusDiv.textContent = 'Uploading...';
                
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.error);
                }
                
                statusDiv.textContent = 'Upload successful!';
                
                // Store the file info to attach to next message
                attachedFiles.push({
                    id: result.file_id,
                    name: result.filename
                });
                
                // Return to chat after a delay
                setTimeout(() => {
                    window.location.href = '/';
                }, 1000);
                
            } catch (error) {
                console.error('Upload error:', error);
                statusDiv.textContent = `Upload failed: ${error.message}`;
            }
        });
    }
    
    // Initialize chat if coming back from upload with files
    const urlParams = new URLSearchParams(window.location.search);
    const fileId = urlParams.get('file_id');
    if (fileId) {
        attachedFiles.push({
            id: fileId,
            name: urlParams.get('filename')
        });
        renderAttachments();
    }
});
'''

@app.route('/', methods=['GET'])
def home():
    return render_template_string(
        BASE_HTML,
        css=CSS,
        js=JS,
        content=render_template_string(CHAT_HTML, models=list(MODELS.keys()))
    )

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if file and allowed_file(file):
            if file.content_length > MAX_FILE_SIZE:
                return jsonify({"error": "File too large"}), 400
            
            file_id = process_file(file)
            return jsonify({"file_id": file_id, "filename": file.filename}), 200
        else:
            return jsonify({"error": "File type not allowed"}), 400
    
    return render_template_string(
        BASE_HTML,
        css=CSS,
        js=JS,
        content=UPLOAD_HTML
    )

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data.get('user_id', 'default_user')
    message = data.get('message')
    model = data.get('model', 'mistral')
    file_ids = data.get('file_ids', [])
    web_search = data.get('web_search', False)
    deep_thinking = data.get('deep_thinking', False)
    
    if not message and not file_ids:
        return jsonify({"error": "Message or file is required"}), 400
    
    # Initialize chat history if not exists
    if user_id not in chat_history:
        chat_history[user_id] = []
    
    # Prepare messages with history
    messages = []
    for msg in chat_history[user_id]:
        messages.append({"role": msg['role'], "content": msg['content']})
    
    # Add current message
    if message:
        messages.append({"role": "user", "content": message})
    
    # Add file content if provided
    for file_id in file_ids:
        if file_id in user_files:
            file_data = user_files[file_id]
            messages.append({
                "role": "user",
                "content": f"[Attached file: {file_data['filename']}]"
            })
    
    # Get AI response
    try:
        model_name = MODELS.get(model, MODELS["mistral"])
        response = get_model_response(
            messages, 
            model_name,
            web_search=web_search,
            deep_thinking=deep_thinking
        )
        
        ai_response = response['choices'][0]['message']['content']
        
        # Update chat history
        if message:
            chat_history[user_id].append({"role": "user", "content": message})
        chat_history[user_id].append({"role": "assistant", "content": ai_response})
        
        return jsonify({
            "response": ai_response,
            "model": model_name,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    return make_response('', 204)

if __name__ == '__main__':
    app.run(debug=True)
