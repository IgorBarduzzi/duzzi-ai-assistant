const WS_URL = 'ws://127.0.0.1:9876';
let ws = null;
let reconnectInterval = null;

// UI Elements
const connectionDot = document.getElementById('connection-status');
const connectionText = document.getElementById('connection-text');
const stateTitle = document.getElementById('state-title');
const stateSubtitle = document.getElementById('state-subtitle');
const orbMini = document.getElementById('orb-mini');

const chatHistory = document.getElementById('chat-history');
const commandInput = document.getElementById('command-input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');

const sessionsListDiv = document.getElementById('sessions-list');
const btnNewTopic = document.getElementById('btn-new-topic');

const previewIframe = document.getElementById('preview-iframe');
const previewPlaceholder = document.getElementById('preview-placeholder');
const codeHistory = document.getElementById('code-history');

// Spotify & Profile omitted variables for brevity... (will bind dynamic later)

// Setup Marked with Highlight.js
// (Removido marked.setOptions pois quebra na v12+ e já fazemos o highlight manual no extractAndRenderCode)

// --- Tabs Logic ---
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
    });
});

// --- WebSocket Connection ---
function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        connectionDot.classList.add('connected');
        connectionText.textContent = 'Conectado';
        if (reconnectInterval) clearInterval(reconnectInterval);
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
    };

    ws.onclose = () => {
        connectionDot.classList.remove('connected');
        connectionText.textContent = 'Offline';
        setEstado('idle');
        reconnectInterval = setTimeout(connectWebSocket, 4000);
    };
    
    ws.onerror = (err) => {
        ws.close();
    };
}

// --- Handler Central WS ---
function handleServerEvent(data) {
    const { type, value } = data;

    switch (type) {
        case 'state':
            setEstado(value);
            break;
        case 'sessions_list':
            renderSessionsList(value, data.active_id);
            break;
        case 'session_loaded':
            renderFullSession(value);
            break;
        case 'transcript':
            addChatMessage('user', value);
            break;
        case 'say':
            addChatMessage('duzzi', value);
            extractAndRenderCode(value);
            break;
        case 'profile_data':
            document.getElementById('prof-nome').value = value.nome || '';
            document.getElementById('prof-cidade').value = value.cidade || '';
            break;
    }
}

// --- Status Manager ---
function setEstado(estado) {
    const colors = {
        'idle': 'var(--orb-gold)',
        'listening': 'var(--orb-blue)',
        'processing': 'var(--orb-purple)',
        'speaking': 'var(--orb-green)'
    };
    
    orbMini.style.setProperty('--orb-current', colors[estado] || colors['idle']);

    const titles = {
        'idle': 'Aguardando',
        'listening': 'Ouvindo...',
        'processing': 'Processando...',
        'speaking': 'Respondendo'
    };
    
    stateTitle.textContent = titles[estado] || 'Desconhecido';
}

// --- Sidebar Sessions Logic ---
btnNewTopic.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'new_session' }));
    }
});

function renderSessionsList(sessions, activeId) {
    sessionsListDiv.innerHTML = '';
    
    // Reverse for newest first
    sessions.reverse().forEach(sess => {
        const div = document.createElement('div');
        div.className = 'session-card';
        if (sess.id === activeId) div.classList.add('active');
        
        div.innerHTML = `<h4>${sess.title}</h4><p>${sess.id.split('-')[0]}</p>`;
        
        div.addEventListener('click', () => {
            if (ws && ws.readyState === WebSocket.OPEN && sess.id !== activeId) {
                ws.send(JSON.stringify({ type: 'load_session', value: sess.id }));
            }
        });
        
        sessionsListDiv.appendChild(div);
    });
}

function renderFullSession(messages) {
    chatHistory.innerHTML = '';
    codeHistory.innerHTML = '<div class="placeholder-text">O código gerado aparecerá aqui.</div>';
    previewIframe.srcdoc = '';
    previewPlaceholder.style.display = 'block';

    messages.forEach(msg => {
        if (msg.role === 'system') return; // Hide system messages
        const roleStr = msg.role === 'assistant' ? 'duzzi' : 'user';
        
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble chat-${roleStr}`;
        bubble.innerHTML = marked.parse(msg.content);
        chatHistory.appendChild(bubble);
        
        if (roleStr === 'duzzi') {
            extractAndRenderCode(msg.content);
        }
    });
    scrollToBottom();
}

// --- Chat & Code Extraction ---
function addChatMessage(role, text) {
    const bubbleChat = document.createElement('div');
    bubbleChat.className = `chat-bubble chat-${role}`;
    
    if (role === 'duzzi') {
        chatHistory.appendChild(bubbleChat);
        typeWriterEffect(bubbleChat, text, 10);
    } else {
        bubbleChat.innerHTML = marked.parse(text);
        chatHistory.appendChild(bubbleChat);
        scrollToBottom();
    }
}

function extractAndRenderCode(text) {
    // Regex para pegar tudo dentro de blocos de código markdown (```lang ... ```)
    const codeBlockRegex = /\`\`\`(html|css|js|javascript|python)?\n([\s\S]*?)\`\`\`/gi;
    let match;
    let hasCode = false;
    let fullHtml = '';

    while ((match = codeBlockRegex.exec(text)) !== null) {
        hasCode = true;
        const lang = (match[1] || '').toLowerCase();
        const codeContent = match[2];
        
        // Joga no Code Panel
        if (codeHistory.querySelector('.placeholder-text')) {
            codeHistory.innerHTML = '';
        }
        
        const pre = document.createElement('pre');
        pre.innerHTML = `<code class="hljs language-${lang || 'plaintext'}">${hljs.highlightAuto(codeContent).value}</code>`;
        
        // Botão copiar
        pre.style.position = 'relative';
        const btn = document.createElement('button');
        btn.textContent = 'Copiar';
        btn.className = 'icon-btn';
        btn.style.position = 'absolute'; btn.style.top = '5px'; btn.style.right = '5px';
        btn.addEventListener('click', () => { navigator.clipboard.writeText(codeContent); btn.textContent='Ok!'; setTimeout(()=>btn.textContent='Copiar',2000); });
        pre.appendChild(btn);
        
        codeHistory.appendChild(pre);

        // Se for HTML/CSS/JS, concatena para renderizar no Iframe Preview
        if (['html', 'css', 'js', 'javascript'].includes(lang) || text.includes('<!DOCTYPE html>')) {
            if (lang === 'css') fullHtml += `<style>${codeContent}</style>`;
            else if (lang === 'js' || lang === 'javascript') fullHtml += `<script>${codeContent}</script>`;
            else fullHtml += codeContent;
        }
    }

    if (hasCode && fullHtml.trim().length > 0) {
        previewPlaceholder.style.display = 'none';
        // Se o codigo já tiver <html> ignora envolver, senão cria uma casca basica
        if (fullHtml.includes('<html')) {
            previewIframe.srcdoc = fullHtml;
        } else {
            previewIframe.srcdoc = `
                <html>
                <head><style>body{font-family:sans-serif;color:#333;padding:20px;}</style></head>
                <body>${fullHtml}</body>
                </html>
            `;
        }
    }
}

function typeWriterEffect(element, text, speed) {
    let i = 0;
    let currentHtml = "";
    function type() {
        if (i < text.length) {
            currentHtml += text.charAt(i);
            element.innerHTML = marked.parse(currentHtml);
            i++;
            scrollToBottom();
            setTimeout(type, speed);
        }
    }
    type();
}

function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Enviar comandos de texto
sendBtn.addEventListener('click', () => {
    const text = commandInput.value.trim();
    if (text && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'command', value: text }));
        commandInput.value = '';
    }
});
commandInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendBtn.click();
});


// --- Voz nativa do Navegador (Push to Talk) ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let isRecording = false;

    micBtn.addEventListener('click', () => {
        if (isRecording) {
            recognition.stop();
        } else {
            recognition.start();
        }
    });

    recognition.onstart = () => {
        isRecording = true;
        micBtn.classList.add('recording');
        commandInput.placeholder = 'Ouvindo...';
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        commandInput.value = transcript;
        sendBtn.click(); // Auto envia
    };

    recognition.onend = () => {
        isRecording = false;
        micBtn.classList.remove('recording');
        commandInput.placeholder = 'Pergunte ao Duzzi ou digite um comando...';
    };

    recognition.onerror = (e) => {
        console.error("Mic error:", e.error);
        isRecording = false;
        micBtn.classList.remove('recording');
        commandInput.placeholder = 'Pergunte ao Duzzi ou digite um comando...';
    };
} else {
    micBtn.style.display = 'none'; // Navegador nao suporta
    commandInput.placeholder = 'Seu navegador não suporta voz. Digite aqui...';
}

// Init
connectWebSocket();
