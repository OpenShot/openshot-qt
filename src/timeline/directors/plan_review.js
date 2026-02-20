// Plan Review UI JavaScript

let bridge = null;
let currentPlan = null;

// Initialize QWebChannel
new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.planReviewBridge;
    console.log("Plan Review Bridge connected");

    // Listen for plan loaded signal
    bridge.planLoaded.connect(function(planJson) {
        console.log("Plan loaded:", planJson);
        loadPlan(JSON.parse(planJson));
    });
});

// Load and display plan
function loadPlan(plan) {
    currentPlan = plan;

    // Hide empty state, show plan
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('plan-container').style.display = 'block';

    // Render header
    document.getElementById('plan-title').textContent = plan.title;

    // Render directors badge
    const directors = plan.created_by.join(', ');
    document.getElementById('plan-directors').textContent = `Directors: ${directors}`;

    // Render confidence badge
    const confidence = plan.confidence || 0.5;
    const confidenceBadge = document.getElementById('plan-confidence');
    confidenceBadge.textContent = `Confidence: ${(confidence * 100).toFixed(0)}%`;
    confidenceBadge.className = 'confidence-badge';
    if (confidence >= 0.7) {
        confidenceBadge.classList.add('confidence-high');
    } else if (confidence >= 0.5) {
        confidenceBadge.classList.add('confidence-medium');
    } else {
        confidenceBadge.classList.add('confidence-low');
    }

    // Render summary
    document.getElementById('plan-summary-text').textContent = plan.summary || 'No summary available.';

    // Render steps
    renderSteps(plan.steps || []);

    // Render debate transcript
    renderDebate(plan.debate_transcript || []);
}

// Render steps
function renderSteps(steps) {
    const stepsList = document.getElementById('steps-list');
    const stepsCount = document.getElementById('steps-count');

    stepsCount.textContent = steps.length;
    stepsList.innerHTML = '';

    if (steps.length === 0) {
        stepsList.innerHTML = '<p style="color: #888; padding: 20px; text-align: center;">No steps in plan</p>';
        return;
    }

    steps.forEach((step, index) => {
        const stepCard = document.createElement('div');
        stepCard.className = 'step-card';
        stepCard.dataset.stepId = step.step_id;

        // Confidence color
        let confidenceColor = '#888';
        if (step.confidence >= 0.7) confidenceColor = '#4ade80';
        else if (step.confidence >= 0.5) confidenceColor = '#facc15';
        else confidenceColor = '#f87171';

        stepCard.innerHTML = `
            <div class="step-header">
                <div class="step-number">${index + 1}</div>
                <div class="step-content">
                    <div class="step-description">${escapeHtml(step.description)}</div>
                    <div class="step-meta">
                        <span class="step-type">${escapeHtml(step.type)}</span>
                        <span class="step-agent">Agent: ${escapeHtml(step.agent)}</span>
                        <span class="step-confidence" style="color: ${confidenceColor}">
                            Confidence: ${(step.confidence * 100).toFixed(0)}%
                        </span>
                    </div>
                </div>
            </div>
            ${step.rationale ? `<div class="step-rationale">💡 ${escapeHtml(step.rationale)}</div>` : ''}
        `;

        stepsList.appendChild(stepCard);
    });
}

// Render debate transcript
function renderDebate(messages) {
    const debateTranscript = document.getElementById('debate-transcript');
    const debateCount = document.getElementById('debate-count');

    debateCount.textContent = messages.length;

    if (messages.length === 0) {
        debateTranscript.innerHTML = '<p style="color: #888; padding: 20px; text-align: center;">No debate messages</p>';
        return;
    }

    debateTranscript.innerHTML = '';

    // Group by round
    const rounds = {};
    messages.forEach(msg => {
        const round = msg.round_number || 0;
        if (!rounds[round]) rounds[round] = [];
        rounds[round].push(msg);
    });

    // Render by round
    Object.keys(rounds).sort((a, b) => a - b).forEach(round => {
        const roundHeader = document.createElement('div');
        roundHeader.style.cssText = 'font-weight: 600; color: #6366f1; margin: 16px 0 8px 0; font-size: 14px;';
        roundHeader.textContent = round == 0 ? 'Initial Analysis' : `Round ${round}`;
        debateTranscript.appendChild(roundHeader);

        rounds[round].forEach(msg => {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'debate-message';

            messageDiv.innerHTML = `
                <div class="debate-message-header">
                    <span class="debate-director">${escapeHtml(msg.director_name)}</span>
                    <span class="debate-round">${escapeHtml(msg.message_type)}</span>
                </div>
                <div class="debate-content">${escapeHtml(msg.content)}</div>
            `;

            debateTranscript.appendChild(messageDiv);
        });
    });
}

// Toggle debate section
function toggleDebate() {
    const debateTranscript = document.getElementById('debate-transcript');
    const toggleIcon = document.getElementById('debate-toggle');

    if (debateTranscript.style.display === 'none') {
        debateTranscript.style.display = 'block';
        toggleIcon.textContent = '▼';
        toggleIcon.classList.add('expanded');
    } else {
        debateTranscript.style.display = 'none';
        toggleIcon.textContent = '▶';
        toggleIcon.classList.remove('expanded');
    }
}

// Approve plan
function approvePlan() {
    if (!currentPlan || !bridge) {
        console.error("No plan or bridge");
        return;
    }

    console.log("Approving plan:", currentPlan.plan_id);
    bridge.approvePlan(currentPlan.plan_id);
}

// Reject plan
function rejectPlan() {
    if (!currentPlan || !bridge) {
        console.error("No plan or bridge");
        return;
    }

    console.log("Rejecting plan:", currentPlan.plan_id);
    bridge.rejectPlan(currentPlan.plan_id);
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

console.log("Plan Review UI initialized");
