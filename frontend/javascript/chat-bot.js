document.addEventListener('DOMContentLoaded', () => {

    // ===== Settings: change these for your project =====
    const CHAT_URL = (typeof AUTH_CONFIG !== 'undefined' && AUTH_CONFIG.apiBaseUrl && !AUTH_CONFIG.apiBaseUrl.startsWith('PASTE_'))
        ? AUTH_CONFIG.apiBaseUrl + '/chat'
        : '';

    // ===== Site navigation (general website features) =====
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const navLinks = document.querySelector('.nav-links');

    if (hamburgerBtn && navLinks) {
        hamburgerBtn.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            hamburgerBtn.textContent = navLinks.classList.contains('active') ? '✕' : '☰';
        });
    }

    const navbar = document.querySelector('.navbar');
    let lastScrollY = window.scrollY;

    if (navbar) {
        window.addEventListener('scroll', () => {
            const currentScrollY = window.scrollY;

            navbar.classList.toggle('scrolled', currentScrollY > 10);

            if (currentScrollY > lastScrollY && currentScrollY > 80) {
                navbar.classList.add('nav-hidden');
            } else {
                navbar.classList.remove('nav-hidden');
            }

            lastScrollY = currentScrollY;
        });
    }

    // ===== Axiomat AI widget =====
    const axiomatTrigger = document.getElementById('axiomatTrigger');
    const axiomatPanel = document.getElementById('axiomatPanel');
    const axiomatClose = document.getElementById('axiomatClose');
    const axiomatBody = document.getElementById('axiomatBody');
    const axiomatForm = document.getElementById('axiomatForm');
    const axiomatInput = document.getElementById('axiomatInput');

    // A session id lets the backend keep one conversation thread per visitor
    let sessionId = sessionStorage.getItem('axiomatSessionId');
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        sessionStorage.setItem('axiomatSessionId', sessionId);
    }

    let isSending = false;

    function openPanel() {
        axiomatPanel.hidden = false;
        axiomatTrigger.style.display = 'none';
        document.body.style.overflow = 'hidden';
        axiomatInput.focus();
    }

    function closePanel() {
        axiomatPanel.hidden = true;
        axiomatTrigger.style.display = 'flex';
        document.body.style.overflow = '';
    }

    function addMessage(text, sender) {
        const msg = document.createElement('div');
        msg.className = sender === 'user' ? 'axiomat-msg axiomat-msg-user' : 'axiomat-msg axiomat-msg-bot';
        msg.textContent = text; // textContent is safe against injected HTML
        axiomatBody.appendChild(msg);
        axiomatBody.scrollTop = axiomatBody.scrollHeight;
        return msg;
    }

    async function sendMessage(text) {
        const message = text.trim();
        if (!message || isSending) return;

        isSending = true;
        addMessage(message, 'user');
        axiomatInput.value = '';
        axiomatInput.style.height = 'auto';

        const thinkingMsg = addMessage('Axiomat AI is thinking...', 'bot');
        thinkingMsg.classList.add('axiomat-thinking');

        try {
            const response = await fetch(CHAT_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, sessionId }),
            });

            if (response.status === 429) {
                thinkingMsg.remove();
                addMessage('You are sending messages quickly. Please wait a moment and try again.', 'bot');
                return;
            }
            if (!response.ok) {
                throw new Error(`Server replied with status ${response.status}`);
            }

            const data = await response.json();
            thinkingMsg.remove();
            addMessage(data.reply || 'Sorry, I did not get a reply. Please try again.', 'bot');
        } catch (error) {
            console.error('Axiomat AI request failed:', error);
            thinkingMsg.remove();
            addMessage("Sorry, I'm having trouble connecting right now. Please try again.", 'bot');
        } finally {
            isSending = false;
        }
    }

    // Open and close
    axiomatTrigger.addEventListener('click', openPanel);
    axiomatClose.addEventListener('click', closePanel);

    // Optional buttons elsewhere on the page (safe if they do not exist)
    ['navAxiomatBtn', 'heroAxiomatBtn', 'navAboutBtn', 'navHelpBtn'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('click', (e) => {
                e.preventDefault();
                openPanel();
            });
        }
    });

    // Sending
    axiomatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage(axiomatInput.value);
    });

    axiomatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(axiomatInput.value);
        }
    });

    axiomatInput.addEventListener('input', () => {
        axiomatInput.style.height = 'auto';
        axiomatInput.style.height = Math.min(axiomatInput.scrollHeight, 130) + 'px';
    });

    // Suggested prompt buttons
    document.querySelectorAll('.axiomat-prompt-btn').forEach(btn => {
        btn.addEventListener('click', () => sendMessage(btn.textContent));
    });

});