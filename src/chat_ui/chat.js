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
    const preambleStatus = document.getElementById('chat-preamble-status');
    const modelSelect = document.getElementById('chat-model-select');
    const modelTrigger = document.getElementById('chat-model-trigger');
    const modelLabel = document.getElementById('chat-model-label');
    const modelMenu = document.getElementById('chat-model-menu');
    const messagesEl = document.getElementById('chat-messages');
    const inputEl = document.getElementById('chat-input');
    const inputRow = document.getElementById('chat-input-row');
    const glowWrap = document.getElementById('chat-input-glow-wrap');
    const inputOverlay = document.getElementById('chat-input-overlay');
    const typingTextEl = document.getElementById('chat-typing-text');
    const sendBtn = document.getElementById('chat-send-btn');
    const cancelBtn = document.getElementById('chat-cancel-btn');
    const clearBtn = document.getElementById('chat-clear-btn');

    var processingStartTime = null;
    var lastRunTimestamp = null;
    var lastThoughtSec = null;
    var statusInterval = null;

    var activityContainer = null;
    var activitySteps = [];

    var ACTIVITY_SPINNER_SVG = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none">' +
        '<circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.2" stroke-dasharray="16 16" stroke-linecap="round"/></svg>';

    var ACTIVITY_CHECK_SVG = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none">' +
        '<path d="M3.5 7.5l2.5 2L10.5 4.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    const SUGGESTED_PROMPTS = 'List my files · Add a track · Export video · Undo';
    let typingInterval = null;
    let typingIndex = 0;
    let overlayVisible = true;

    function escapeHtml(s) {
        const div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function removePlaceholder() {
        const ph = messagesEl.querySelector('.chat-placeholder');
        if (ph) ph.remove();
    }

    function setInputIdle(idle) {
        const container = document.querySelector('.chat-container');
        if (!container) return;
        if (idle) container.classList.add('chat-input-idle');
        else container.classList.remove('chat-input-idle');
    }

    function hideOverlay() {
        if (!overlayVisible) return;
        overlayVisible = false;
        if (typingInterval) {
            clearInterval(typingInterval);
            typingInterval = null;
        }
        if (inputOverlay) inputOverlay.classList.add('hidden');
        // Stay centered; only move down on send
        if (inputEl) inputEl.focus();
    }

    function exitIdle() {
        setInputIdle(false);
    }

    function tickTyping() {
        if (!typingTextEl || !overlayVisible) return;
        if (typingIndex <= SUGGESTED_PROMPTS.length) {
            typingTextEl.textContent = SUGGESTED_PROMPTS.slice(0, typingIndex);
            typingIndex++;
        } else {
            typingIndex = 0;
            typingTextEl.textContent = '';
        }
    }

    function startTypingAnimation() {
        if (typingInterval) return;
        typingIndex = 0;
        tickTyping();
        typingInterval = setInterval(tickTyping, 80);
    }

    function stopTypingAnimation() {
        if (typingInterval) {
            clearInterval(typingInterval);
            typingInterval = null;
        }
    }

    window.appendMessage = function (role, bodyHtml, isAssistant) {
        if (role === 'system') return;
        removePlaceholder();
        const div = document.createElement('div');
        div.className = 'chat-message chat-message-enter ' + (role === 'user' ? 'chat-message-user' : '');
        div.innerHTML = '<div class="chat-message-body">' + (isAssistant ? bodyHtml : '<p>' + bodyHtml + '</p>') + '</div>';
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    };

    /* ── Activity log helpers (tool step display during processing) ── */

    function addReasoningStep() {
        if (!activityContainer) return;
        var step = document.createElement('div');
        step.className = 'chat-activity-step running';
        step.setAttribute('data-type', 'reasoning');
        step.innerHTML = '<span class="activity-icon">' + ACTIVITY_SPINNER_SVG + '</span>' +
                         '<span class="activity-label activity-reasoning">Reasoning</span>';
        activityContainer.appendChild(step);
        activitySteps.push(step);
    }

    function completeActivityStep(step) {
        if (!step) return;
        step.classList.remove('running');
        step.classList.add('done');
        var icon = step.querySelector('.activity-icon');
        if (icon) icon.innerHTML = ACTIVITY_CHECK_SVG;
        // Remove animated dots class from reasoning labels when completed
        var label = step.querySelector('.activity-reasoning');
        if (label) label.classList.remove('activity-reasoning');
    }

    window.addActivityStep = function (label, detail) {
        if (!activityContainer) return;
        // Complete current step (reasoning or previous tool)
        if (activitySteps.length > 0) {
            completeActivityStep(activitySteps[activitySteps.length - 1]);
        }
        // Add new tool step
        var step = document.createElement('div');
        step.className = 'chat-activity-step running';
        step.setAttribute('data-type', 'tool');
        var h = '<span class="activity-icon">' + ACTIVITY_SPINNER_SVG + '</span>' +
                '<span class="activity-label">' + escapeHtml(label) + '</span>';
        if (detail) {
            h += '<span class="activity-detail">' + escapeHtml(detail) + '</span>';
        }
        step.innerHTML = h;
        activityContainer.appendChild(step);
        activitySteps.push(step);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    };

    window.completeLastActivityStep = function () {
        if (!activityContainer || activitySteps.length === 0) return;
        completeActivityStep(activitySteps[activitySteps.length - 1]);
        // LLM will reason about the tool result next
        addReasoningStep();
        messagesEl.scrollTop = messagesEl.scrollHeight;
    };

    /* ── Processing state ── */

    let typingEl = null;
    window.setProcessing = function (processing) {
        sendBtn.disabled = processing;
        cancelBtn.style.display = processing ? 'flex' : 'none';
        if (processing) {
            processingStartTime = Date.now();
            if (glowWrap) glowWrap.classList.add('glow-active');
            removePlaceholder();
            // Create activity log for this request
            activityContainer = document.createElement('div');
            activityContainer.className = 'chat-activity-log';
            activityContainer.setAttribute('aria-live', 'polite');
            messagesEl.appendChild(activityContainer);
            addReasoningStep();
            messagesEl.scrollTop = messagesEl.scrollHeight;
        } else {
            if (glowWrap) glowWrap.classList.remove('glow-active');
            // Finalize activity log: remove trailing reasoning step
            if (activityContainer && activitySteps.length > 0) {
                var last = activitySteps[activitySteps.length - 1];
                if (last.getAttribute('data-type') === 'reasoning') {
                    last.remove();
                    activitySteps.pop();
                }
            }
            // Complete any remaining running steps
            for (var i = 0; i < activitySteps.length; i++) {
                if (activitySteps[i].classList.contains('running')) {
                    completeActivityStep(activitySteps[i]);
                }
            }
            // Remove empty activity container
            if (activityContainer && activitySteps.length === 0) {
                activityContainer.remove();
            }
            activityContainer = null;
            activitySteps = [];
            // Calculate thought time
            if (processingStartTime) {
                var elapsed = Math.round((Date.now() - processingStartTime) / 1000);
                lastThoughtSec = elapsed;
                lastRunTimestamp = Date.now();
                processingStartTime = null;
                // Insert "Thought X sec" badge before the last assistant message
                var badge = document.createElement('div');
                badge.className = 'chat-thought-badge';
                badge.textContent = 'Thought ' + (elapsed < 1 ? '<1' : elapsed) + ' sec';
                var lastMsg = messagesEl.querySelector('.chat-message:last-child');
                if (lastMsg) {
                    messagesEl.insertBefore(badge, lastMsg);
                }
                updatePreambleStatus();
            }
            if (inputEl) inputEl.focus();
        }
    };

    function formatTimeAgo(ts) {
        if (!ts) return '';
        var sec = Math.round((Date.now() - ts) / 1000);
        if (sec < 5) return 'just now';
        if (sec < 60) return sec + 's ago';
        var min = Math.round(sec / 60);
        if (min < 60) return min + 'm ago';
        var hr = Math.round(min / 60);
        return hr + 'h ago';
    }

    function updatePreambleStatus() {
        if (!preambleStatus) return;
        if (!lastRunTimestamp) {
            preambleStatus.classList.remove('visible');
            return;
        }
        var parts = [];
        parts.push(formatTimeAgo(lastRunTimestamp));
        if (lastThoughtSec !== null) {
            parts.push('Thought ' + (lastThoughtSec < 1 ? '<1' : lastThoughtSec) + ' sec');
        }
        var modelName = modelLabel ? modelLabel.textContent : '';
        if (modelName && modelName !== 'Model') parts.push(modelName);
        preambleStatus.innerHTML = parts.join('<span class="status-sep">&middot;</span>');
        preambleStatus.classList.add('visible');
    }

    // Refresh the "Xm ago" text periodically
    statusInterval = setInterval(function () {
        if (lastRunTimestamp) updatePreambleStatus();
    }, 10000);

    var modelItems = [];
    var selectedModelId = '';
    var menuOpen = false;

    // Provider SVG logos (16x16) keyed by provider slug
    var PROVIDER_ICONS = {
        openai:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">' +
            '<path d="M22.282 9.821a5.985 5.985 0 00-.516-4.91 6.046 6.046 0 00-6.51-2.9A6.065 6.065 0 0011.684.18a6.038 6.038 0 00-5.77 4.22 5.99 5.99 0 00-3.997 2.9 6.05 6.05 0 00.743 7.097 5.98 5.98 0 00.51 4.911 6.05 6.05 0 006.515 2.9A5.999 5.999 0 0014.297 23.8a6.04 6.04 0 005.772-4.206 5.98 5.98 0 003.997-2.9 6.056 6.056 0 00-.784-6.873zM14.297 22.27a4.49 4.49 0 01-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 00.392-.681v-6.737l2.02 1.166a.071.071 0 01.038.052v5.583a4.504 4.504 0 01-4.494 4.496zM3.958 18.14a4.477 4.477 0 01-.537-3.018l.142.085 4.783 2.759a.771.771 0 00.78 0l5.843-3.369v2.332a.08.08 0 01-.033.062L9.74 19.77a4.506 4.506 0 01-5.782-1.63zM2.468 7.87a4.485 4.485 0 012.344-1.974V11.6a.766.766 0 00.388.676l5.815 3.355-2.02 1.168a.076.076 0 01-.071.005l-4.83-2.786A4.504 4.504 0 012.468 7.87zm16.597 3.855L13.22 8.37l2.02-1.166a.076.076 0 01.071-.006l4.83 2.787a4.494 4.494 0 01-.676 8.105v-5.818a.79.79 0 00-.4-.687zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 00-.785 0L9.534 9.203V6.87a.08.08 0 01.033-.062l4.83-2.787a4.5 4.5 0 016.678 4.681zM8.392 12.497l-2.02-1.164a.076.076 0 01-.038-.057V5.694a4.504 4.504 0 017.37-3.455l-.14.079-4.78 2.758a.795.795 0 00-.392.681zm1.097-2.365L12 8.612l2.511 1.45v2.906l-2.511 1.45-2.511-1.45z" fill="currentColor"/></svg>',
        anthropic:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">' +
            '<path d="M17.304 3.541h-3.672l6.696 16.918h3.672L17.304 3.541zm-10.608 0L0 20.459h3.744l1.38-3.588h7.104l1.38 3.588h3.744L10.656 3.541H6.696zm.456 10.2l2.544-6.612 2.544 6.612H7.152z" fill="currentColor"/></svg>',
        ollama:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">' +
            '<path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 2a8 8 0 110 16 8 8 0 010-16zm-2.5 5a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm5 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3zM8.5 13.5s1 2 3.5 2 3.5-2 3.5-2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        google:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">' +
            '<path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="currentColor" opacity=".7"/>' +
            '<path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="currentColor" opacity=".8"/>' +
            '<path d="M5.84 14.1a6.84 6.84 0 010-4.24V7.02H2.18A11.96 11.96 0 001 12c0 1.94.46 3.77 1.18 5.02l3.66-2.92z" fill="currentColor" opacity=".6"/>' +
            '<path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.02l3.66 2.84c.87-2.6 3.3-4.48 6.16-4.48z" fill="currentColor" opacity=".9"/></svg>',
        meta:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">' +
            '<path d="M6.915 4.03c-1.968 0-3.042 1.566-3.042 4.158 0 1.86.756 4.08 2.028 5.946.834 1.224 2.31 2.844 3.93 2.844.87 0 1.494-.432 2.16-1.266.708-.894 1.2-2.064 1.2-2.064s.498 1.17 1.2 2.064c.666.834 1.29 1.266 2.16 1.266 1.62 0 3.096-1.62 3.93-2.844 1.272-1.866 2.028-4.086 2.028-5.946 0-2.592-1.074-4.158-3.042-4.158-1.59 0-3.06 1.386-4.278 3.498-.456.798-.822 1.578-1.158 2.352-.336-.774-.702-1.554-1.158-2.352C11.976 5.416 10.506 4.03 8.915 4.03z" fill="currentColor" opacity=".85"/></svg>',
        mistral:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">' +
            '<rect x="1" y="3" width="5" height="5" fill="currentColor"/><rect x="18" y="3" width="5" height="5" fill="currentColor"/>' +
            '<rect x="1" y="9.5" width="5" height="5" fill="currentColor"/><rect x="9.5" y="9.5" width="5" height="5" fill="currentColor"/><rect x="18" y="9.5" width="5" height="5" fill="currentColor"/>' +
            '<rect x="1" y="16" width="5" height="5" fill="currentColor"/><rect x="5.25" y="16" width="5" height="5" fill="currentColor" opacity=".5"/><rect x="9.5" y="16" width="5" height="5" fill="currentColor"/><rect x="13.75" y="16" width="5" height="5" fill="currentColor" opacity=".5"/><rect x="18" y="16" width="5" height="5" fill="currentColor"/></svg>',
        cohere:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 24 24" fill="none">' +
            '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" fill="none"/>' +
            '<circle cx="12" cy="12" r="4" fill="currentColor"/></svg>',
        default:
            '<svg class="chat-model-option-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">' +
            '<path d="M8 1a3 3 0 00-3 3v1H4a2 2 0 00-2 2v6a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-1V4a3 3 0 00-3-3zm0 1.5A1.5 1.5 0 019.5 4v1h-3V4A1.5 1.5 0 018 2.5zM6 9a1 1 0 112 0 1 1 0 01-2 0zm4 0a1 1 0 112 0 1 1 0 01-2 0z" fill="currentColor"/></svg>'
    };

    function detectProvider(modelId) {
        var id = (modelId || '').toLowerCase();
        if (id.indexOf('openai') === 0 || id.indexOf('gpt') !== -1 || id.indexOf('o1') !== -1 || id.indexOf('o3') !== -1) return 'openai';
        if (id.indexOf('anthropic') !== -1 || id.indexOf('claude') !== -1) return 'anthropic';
        if (id.indexOf('ollama') !== -1 || id.indexOf('llama') !== -1 || id.indexOf('local') !== -1) return 'ollama';
        if (id.indexOf('gemini') !== -1 || id.indexOf('google') !== -1) return 'google';
        if (id.indexOf('meta') !== -1) return 'meta';
        if (id.indexOf('mistral') !== -1 || id.indexOf('mixtral') !== -1) return 'mistral';
        if (id.indexOf('cohere') !== -1 || id.indexOf('command') !== -1) return 'cohere';
        return 'default';
    }

    function getModelIcon(modelId) {
        var provider = detectProvider(modelId);
        return PROVIDER_ICONS[provider] || PROVIDER_ICONS['default'];
    }

    function getCheckIcon() {
        return '<svg class="chat-model-option-check" width="14" height="14" viewBox="0 0 14 14" fill="none">' +
            '<path d="M3 7.5l2.5 2.5L11 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }

    function renderMenu() {
        modelMenu.innerHTML = '';
        modelItems.forEach(function (item) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'chat-model-option' + (item.id === selectedModelId ? ' selected' : '');
            btn.setAttribute('role', 'option');
            btn.setAttribute('aria-selected', item.id === selectedModelId ? 'true' : 'false');
            btn.innerHTML = getModelIcon(item.id) +
                '<span class="chat-model-option-name">' + escapeHtml(item.name) + '</span>' +
                getCheckIcon();
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                selectModel(item.id, item.name);
                closeMenu();
            });
            modelMenu.appendChild(btn);
        });
    }

    function updateTriggerIcon(modelId) {
        var iconEl = modelTrigger.querySelector('.chat-model-icon');
        if (iconEl) {
            var tmp = document.createElement('span');
            tmp.innerHTML = getModelIcon(modelId);
            var newIcon = tmp.firstChild;
            if (newIcon) {
                newIcon.classList.add('chat-model-icon');
                newIcon.classList.remove('chat-model-option-icon');
                newIcon.setAttribute('width', '14');
                newIcon.setAttribute('height', '14');
                iconEl.parentNode.replaceChild(newIcon, iconEl);
            }
        }
    }

    function selectModel(id, name) {
        selectedModelId = id;
        modelSelect.value = id;
        if (modelLabel) modelLabel.textContent = name || id || 'Model';
        updateTriggerIcon(id);
        renderMenu();
    }

    function openMenu() {
        if (menuOpen) return;
        menuOpen = true;
        renderMenu();
        modelMenu.style.display = 'block';
        modelTrigger.classList.add('active');
    }

    function closeMenu() {
        if (!menuOpen) return;
        menuOpen = false;
        modelMenu.style.display = 'none';
        modelTrigger.classList.remove('active');
    }

    function toggleMenu(e) {
        e.stopPropagation();
        if (menuOpen) closeMenu();
        else openMenu();
    }

    modelTrigger.addEventListener('click', toggleMenu);
    document.addEventListener('click', function (e) {
        if (menuOpen && !modelMenu.contains(e.target) && !modelTrigger.contains(e.target)) {
            closeMenu();
        }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && menuOpen) closeMenu();
    });

    window.setModels = function (modelListJson) {
        var list = [];
        try {
            list = JSON.parse(modelListJson);
        } catch (e) {
            list = [];
        }
        modelItems = list.map(function (item) {
            return { id: item.id || item.name || '', name: item.name || item.id || '', isDefault: !!item.default };
        });
        // Keep hidden select in sync
        var currentValue = modelSelect.value;
        modelSelect.innerHTML = '';
        modelItems.forEach(function (item) {
            var opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.name;
            if (item.isDefault) opt.selected = true;
            modelSelect.appendChild(opt);
        });
        // Determine selected
        var picked = modelItems.find(function (i) { return i.id === currentValue; });
        if (!picked) picked = modelItems.find(function (i) { return i.isDefault; });
        if (!picked && modelItems.length) picked = modelItems[0];
        if (picked) selectModel(picked.id, picked.name);
        else if (modelLabel) modelLabel.textContent = 'Model';
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
        typingEl = null;
        messagesEl.innerHTML = '';
    };

    function sendMessage() {
        const text = (inputEl.value || '').trim();
        if (!text) return;
        exitIdle();
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
    inputEl.addEventListener('focus', function () {
        hideOverlay();
        if (glowWrap) glowWrap.classList.add('glow-active');
    });
    inputEl.addEventListener('blur', function () {
        if (glowWrap) glowWrap.classList.remove('glow-active');
    });
    inputEl.addEventListener('input', function () {
        if ((inputEl.value || '').trim().length > 0) hideOverlay();
    });

    if (inputOverlay) {
        inputOverlay.addEventListener('click', function () { hideOverlay(); });
    }

    function updateIdleState() {
        const hasMessages = messagesEl.querySelectorAll('.chat-message').length > 0;
        if (hasMessages) {
            setInputIdle(false);
            stopTypingAnimation();
        } else if (overlayVisible) {
            setInputIdle(true);
            startTypingAnimation();
        }
    }

    setInputIdle(true);
    startTypingAnimation();

    getBridge(function (bridge) {
        if (bridge && bridge.ready) bridge.ready();
    });

    window.clearMessages = (function (orig) {
        return function () {
            if (orig) orig();
            typingEl = null;
            activityContainer = null;
            activitySteps = [];
            overlayVisible = true;
            if (inputOverlay) inputOverlay.classList.remove('hidden');
            typingIndex = 0;
            lastRunTimestamp = null;
            lastThoughtSec = null;
            processingStartTime = null;
            if (preambleStatus) {
                preambleStatus.classList.remove('visible');
                preambleStatus.innerHTML = '';
            }
            updateIdleState();
        };
    })(window.clearMessages);

    window.appendMessage = (function (orig) {
        return function (role, bodyHtml, isAssistant) {
            if (orig) orig(role, bodyHtml, isAssistant);
            updateIdleState();
        };
    })(window.appendMessage);

    // ==================================================================
    // Multi-chat tab bar
    // ==================================================================
    var tabBarEl = document.getElementById('chat-tab-bar');
    var tabAddBtn = document.getElementById('chat-tab-add');
    var currentTabs = [];
    var unreadSessions = {};  // sessionId -> true if has unread messages

    window.setTabs = function (tabsJson) {
        var list = [];
        try { list = JSON.parse(tabsJson); } catch (e) { list = []; }
        currentTabs = list;
        renderTabs();
    };

    function renderTabs() {
        // Remove all existing tab buttons (keep the "+" button)
        var existing = tabBarEl.querySelectorAll('.chat-tab');
        existing.forEach(function (el) { el.remove(); });

        currentTabs.forEach(function (tab) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'chat-tab' + (tab.active ? ' active' : '') + (unreadSessions[tab.id] ? ' has-unread' : '');
            btn.setAttribute('role', 'tab');
            btn.setAttribute('data-session-id', tab.id);
            btn.setAttribute('aria-selected', tab.active ? 'true' : 'false');

            var titleSpan = '<span class="chat-tab-title">' + escapeHtml(tab.title || 'New Chat') + '</span>';
            var badge = '<span class="chat-tab-badge"></span>';
            var closeBtn = '<button type="button" class="chat-tab-close" data-close-id="' + escapeHtml(tab.id) + '" title="Close">&times;</button>';
            btn.innerHTML = badge + titleSpan + closeBtn;

            btn.addEventListener('click', function (e) {
                if (e.target.classList.contains('chat-tab-close') || e.target.closest('.chat-tab-close')) {
                    return; // handled by close button
                }
                unreadSessions[tab.id] = false;
                getBridge(function (bridge) {
                    if (bridge && bridge.switchSession) bridge.switchSession(tab.id);
                });
            });

            // Close button handler
            var closeBtnEl = btn.querySelector('.chat-tab-close');
            if (closeBtnEl) {
                closeBtnEl.addEventListener('click', function (e) {
                    e.stopPropagation();
                    var closeId = this.getAttribute('data-close-id');
                    getBridge(function (bridge) {
                        if (bridge && bridge.closeSession) bridge.closeSession(closeId);
                    });
                });
            }

            tabBarEl.insertBefore(btn, tabAddBtn);
        });
    }

    tabAddBtn.addEventListener('click', function () {
        getBridge(function (bridge) {
            if (bridge && bridge.createSession) bridge.createSession(modelSelect.value || '');
        });
    });

    // Handle background responses (marks tab as unread)
    window.onBackgroundResponse = function (sessionId, bodyHtml) {
        unreadSessions[sessionId] = true;
        renderTabs();
    };

    // ==================================================================
    // Context progress ring + popover
    // ==================================================================
    var contextRingWrap = document.getElementById('chat-context-ring-wrap');
    var contextRingFg = document.getElementById('chat-context-ring-fg');
    var carryForwardBtn = document.getElementById('chat-carry-forward-btn');
    var popoverPct = document.getElementById('chat-context-popover-pct');
    var popoverTokens = document.getElementById('chat-context-popover-tokens');
    var popoverBarFill = document.getElementById('chat-context-popover-bar-fill');
    var RING_CIRCUMFERENCE = 2 * Math.PI * 8; // r=8 -> ~50.265

    window.updateContextUsage = function (usageJson) {
        var usage;
        try { usage = JSON.parse(usageJson); } catch (e) { return; }
        var fraction = usage.fraction || 0;
        var used = usage.used || 0;
        var total = usage.total || 1;
        var pctText = (fraction * 100).toFixed(1) + '%';
        var colorClass = fraction >= 0.85 ? 'danger' : (fraction >= 0.70 ? 'warn' : '');

        // Update ring stroke-dashoffset
        var offset = RING_CIRCUMFERENCE * (1 - fraction);
        if (contextRingFg) {
            contextRingFg.style.strokeDashoffset = offset;
            contextRingFg.classList.remove('warn', 'danger');
            if (colorClass) contextRingFg.classList.add(colorClass);
        }

        // Update popover contents
        if (popoverPct) {
            popoverPct.textContent = pctText;
            popoverPct.classList.remove('warn', 'danger');
            if (colorClass) popoverPct.classList.add(colorClass);
        }
        if (popoverTokens) {
            popoverTokens.textContent = numberWithCommas(used) + ' / ' + numberWithCommas(total);
        }
        if (popoverBarFill) {
            popoverBarFill.style.width = (fraction * 100).toFixed(2) + '%';
            popoverBarFill.classList.remove('warn', 'danger');
            if (colorClass) popoverBarFill.classList.add(colorClass);
        }

        // Show/hide carry-forward button
        if (carryForwardBtn) {
            carryForwardBtn.style.display = fraction >= 0.85 ? 'flex' : 'none';
        }
    };

    function numberWithCommas(x) {
        return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    // Carry-forward button handler
    if (carryForwardBtn) {
        carryForwardBtn.addEventListener('click', function () {
            getBridge(function (bridge) {
                if (bridge && bridge.carryForward) {
                    // Pass empty string to mean "active session"
                    bridge.carryForward('');
                }
            });
        });
    }
})();
