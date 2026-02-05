/**
 * Zenvi Assistant chat – CEP/WebEngine front-end.
 * Communicates with Python via QWebChannel (window.zenviChatBridge).
 */

(function () {
    'use strict';

    const bridgeName = 'zenviChatBridge';
    const qwebchannelUrl = 'qwebchannel.js';

    function getBridge(cb) {
        if (window.qt && window.qt.webChannelTransport && window[bridgeName]) {
            cb(window[bridgeName]);
            return;
        }
        if (window.QWebChannel && window.qt && window.qt.webChannelTransport) {
            new window.QWebChannel(window.qt.webChannelTransport, function (ch) {
                window[bridgeName] = ch.objects[bridgeName];
                cb(window[bridgeName] || null);
            });
            return;
        }
        setTimeout(function () { getBridge(cb); }, 50);
    }

    const preambleEl = document.getElementById('chat-preamble-label');
    const modelSelect = document.getElementById('chat-model-select');
    const messagesEl = document.getElementById('chat-messages');
    const inputEl = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const cancelBtn = document.getElementById('chat-cancel-btn');
    const clearBtn = document.getElementById('chat-clear-btn');

    function escapeHtml(s) {
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function formatTime() {
        const d = new Date();
        const h = String(d.getHours()).padStart(2, '0');
        const m = String(d.getMinutes()).padStart(2, '0');
        const s = String(d.getSeconds()).padStart(2, '0');
        return h + ':' + m + ':' + s;
    }

    function removePlaceholder() {
        const ph = messagesEl.querySelector('.chat-placeholder');
        if (ph) ph.remove();
    }

    window.appendMessage = function (role, bodyHtml, isAssistant) {
        removePlaceholder();
        const roleLabel = escapeHtml(formatTime()) + ' ' + role;
        const div = document.createElement('div');
        div.className = 'chat-message';
        div.innerHTML =
            '<div class="chat-message-role ' + (role === 'user' ? 'user' : '') + '">' + roleLabel + '</div>' +
            '<div class="chat-message-body">' + (isAssistant ? bodyHtml : '<p>' + bodyHtml + '</p>') + '</div>';
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    };

    window.setProcessing = function (processing) {
        sendBtn.disabled = processing;
        sendBtn.textContent = processing ? 'Processing...' : 'Send';
        cancelBtn.style.display = processing ? 'inline-block' : 'none';
        if (!processing) inputEl.focus();
    };

    window.setModels = function (modelListJson) {
        let list = [];
        try {
            list = JSON.parse(modelListJson);
        } catch (e) {
            list = [];
        }
        const currentValue = modelSelect.value;
        modelSelect.innerHTML = '';
        list.forEach(function (item) {
            const opt = document.createElement('option');
            opt.value = item.id || item.name || '';
            opt.textContent = item.name || item.id || '';
            if (item.default) opt.selected = true;
            modelSelect.appendChild(opt);
        });
        if (currentValue && list.some(function (i) { return (i.id || i.name) === currentValue; })) {
            modelSelect.value = currentValue;
        }
    };

    window.setPreamble = function (html) {
        if (preambleEl) preambleEl.innerHTML = html;
    };

    window.setThemeColors = function (cssVarsJson) {
        try {
            const vars = JSON.parse(cssVarsJson);
            const root = document.documentElement;
            Object.keys(vars).forEach(function (key) {
                root.style.setProperty('--' + key, vars[key]);
            });
        } catch (e) {}
    };

    window.clearMessages = function () {
        messagesEl.innerHTML = '<div class="chat-placeholder">Replies appear here. Assistant messages support markdown and code blocks.</div>';
    };

    function sendMessage() {
        const text = (inputEl.value || '').trim();
        if (!text) return;
        getBridge(function (bridge) {
            if (!bridge) return;
            bridge.sendMessage(text, modelSelect.value || '');
            inputEl.value = '';
            window.setProcessing(true);
        });
    }

    function cancelRequest() {
        getBridge(function (bridge) {
            if (bridge) bridge.cancelRequest();
            window.setProcessing(false);
        });
    }

    function clearChat() {
        getBridge(function (bridge) {
            if (bridge && bridge.clearChat) {
                bridge.clearChat();
            } else {
                window.clearMessages();
            }
        });
    }

    sendBtn.addEventListener('click', sendMessage);
    cancelBtn.addEventListener('click', cancelRequest);
    clearBtn.addEventListener('click', clearChat);

    inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    cancelBtn.style.display = 'none';

    getBridge(function (bridge) {
        if (bridge && bridge.ready) bridge.ready();
    });
})();
