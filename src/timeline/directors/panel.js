// Director Panel JavaScript - Canvas-based with Animated Clouds

let bridge = null;
let allDirectors = [];
let selectedDirectors = new Set();
let filteredDirectors = [];

// Canvas and animation
let canvas = null;
let ctx = null;
let directorClouds = [];
let animationFrameId = null;
let mousePos = { x: 0, y: 0 };
let hoveredCloud = null;

// Cloud class for animated director representation
class DirectorCloud {
    constructor(director, x, y) {
        this.director = director;
        this.x = x;
        this.y = y;
        this.targetX = x;
        this.targetY = y;
        this.vx = 0;
        this.vy = 0;
        this.size = 80 + Math.random() * 40;
        this.baseSize = this.size;
        this.hoverSize = this.size * 1.2;
        this.color = this.getColorFromTags(director.tags);
        this.pulseOffset = Math.random() * Math.PI * 2;
        this.floatSpeed = 0.02 + Math.random() * 0.02;
        this.floatAmplitude = 10 + Math.random() * 10;
        this.time = 0;
        this.isHovered = false;
        this.isSelected = false;
    }

    getColorFromTags(tags) {
        // Generate color based on tags/expertise
        const colorMap = {
            'youtube': '#FF0000',
            'genz': '#00D9FF',
            'cinematic': '#FFD700',
            'retention': '#FF6B6B',
            'aesthetics': '#9B59B6',
            'storytelling': '#3498DB',
            'technical': '#2ECC71',
        };

        for (let tag of tags) {
            const key = tag.toLowerCase();
            if (colorMap[key]) {
                return colorMap[key];
            }
        }

        // Default gradient colors
        const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    update(deltaTime) {
        this.time += deltaTime;

        // Floating animation
        const floatY = Math.sin(this.time * this.floatSpeed + this.pulseOffset) * this.floatAmplitude;
        this.targetY += floatY * 0.01;

        // Smooth movement towards target
        this.vx = (this.targetX - this.x) * 0.05;
        this.vy = (this.targetY - this.y) * 0.05;
        this.x += this.vx;
        this.y += this.vy;

        // Pulse effect
        const pulse = Math.sin(this.time * 0.002) * 3;
        const targetSize = this.isHovered ? this.hoverSize : this.baseSize;
        this.size += (targetSize + pulse - this.size) * 0.1;
    }

    draw(ctx) {
        ctx.save();

        // Draw cloud body (multiple overlapping circles)
        const numCircles = 6;
        const gradient = ctx.createRadialGradient(
            this.x, this.y, 0,
            this.x, this.y, this.size * 1.2
        );

        // Selected/hovered states with better opacity
        if (this.isSelected) {
            gradient.addColorStop(0, this.color + 'FF');
            gradient.addColorStop(0.4, this.color + 'DD');
            gradient.addColorStop(0.7, this.color + '88');
            gradient.addColorStop(1, this.color + '00');
        } else if (this.isHovered) {
            gradient.addColorStop(0, this.color + 'EE');
            gradient.addColorStop(0.4, this.color + 'BB');
            gradient.addColorStop(0.7, this.color + '66');
            gradient.addColorStop(1, this.color + '00');
        } else {
            gradient.addColorStop(0, this.color + 'CC');
            gradient.addColorStop(0.4, this.color + '99');
            gradient.addColorStop(0.7, this.color + '44');
            gradient.addColorStop(1, this.color + '00');
        }

        // Draw cloud circles with better distribution
        for (let i = 0; i < numCircles; i++) {
            const angle = (i / numCircles) * Math.PI * 2;
            const offsetX = Math.cos(angle) * (this.size * 0.35);
            const offsetY = Math.sin(angle) * (this.size * 0.28);
            const radius = this.size * (0.45 + Math.sin(i) * 0.1);

            ctx.beginPath();
            ctx.arc(this.x + offsetX, this.y + offsetY, radius, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();
        }

        // Draw semi-transparent background for text readability
        ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
        ctx.beginPath();
        ctx.ellipse(this.x, this.y, this.size * 0.7, this.size * 0.4, 0, 0, Math.PI * 2);
        ctx.fill();

        // Draw director name with better contrast
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 15px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Strong text shadow for readability
        ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
        ctx.shadowBlur = 8;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 2;

        // Draw text twice for extra boldness
        ctx.fillText(this.director.name, this.x, this.y);
        ctx.shadowBlur = 4;
        ctx.fillText(this.director.name, this.x, this.y);

        ctx.shadowBlur = 0;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;

        // Draw selection indicator
        if (this.isSelected) {
            // Outer glow ring
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size + 12, 0, Math.PI * 2);
            ctx.stroke();

            // Inner bright ring
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size + 8, 0, Math.PI * 2);
            ctx.stroke();

            // Checkmark with background
            const checkY = this.y - this.size - 25;
            ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
            ctx.beginPath();
            ctx.arc(this.x, checkY, 18, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#00ff00';
            ctx.font = 'bold 28px Arial';
            ctx.shadowColor = 'rgba(0, 0, 0, 0.8)';
            ctx.shadowBlur = 6;
            ctx.fillText('✓', this.x, checkY);
            ctx.shadowBlur = 0;
        }

        ctx.restore();
    }

    containsPoint(x, y) {
        const dx = x - this.x;
        const dy = y - this.y;
        return Math.sqrt(dx * dx + dy * dy) < this.size;
    }
}

// Initialize QWebChannel
new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.directorPanelBridge;
    console.log("Director Panel Bridge connected");

    // Listen for directors loaded
    bridge.directorsLoaded.connect(function(directorsJson) {
        console.log("Directors loaded:", directorsJson);
        allDirectors = JSON.parse(directorsJson);
        filteredDirectors = [...allDirectors];
        initCanvas();
        createDirectorClouds();
        startAnimation();
    });

    // Request directors on init
    bridge.loadDirectors();
});

// Initialize canvas
function initCanvas() {
    canvas = document.getElementById('directors-canvas');
    ctx = canvas.getContext('2d');

    // Set canvas size
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Mouse events
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('click', handleClick);

    // Hide loading indicator
    document.getElementById('loading-indicator').style.display = 'none';
}

function resizeCanvas() {
    const container = canvas.parentElement;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;

    // Reposition clouds if they exist
    if (directorClouds.length > 0) {
        repositionClouds();
    }
}

function createDirectorClouds() {
    directorClouds = [];

    const padding = 120;
    const cols = Math.ceil(Math.sqrt(filteredDirectors.length));
    const rows = Math.ceil(filteredDirectors.length / cols);

    const cellWidth = (canvas.width - padding * 2) / cols;
    const cellHeight = (canvas.height - padding * 2) / rows;

    filteredDirectors.forEach((director, index) => {
        const col = index % cols;
        const row = Math.floor(index / cols);

        // Add some randomness to position
        const randomOffsetX = (Math.random() - 0.5) * 30;
        const randomOffsetY = (Math.random() - 0.5) * 30;

        const x = padding + col * cellWidth + cellWidth / 2 + randomOffsetX;
        const y = padding + row * cellHeight + cellHeight / 2 + randomOffsetY;

        const cloud = new DirectorCloud(director, x, y);
        cloud.isSelected = selectedDirectors.has(director.id);
        directorClouds.push(cloud);
    });
}

function repositionClouds() {
    const padding = 120;
    const cols = Math.ceil(Math.sqrt(directorClouds.length));
    const rows = Math.ceil(directorClouds.length / cols);

    const cellWidth = (canvas.width - padding * 2) / cols;
    const cellHeight = (canvas.height - padding * 2) / rows;

    directorClouds.forEach((cloud, index) => {
        const col = index % cols;
        const row = Math.floor(index / cols);

        const randomOffsetX = (Math.random() - 0.5) * 30;
        const randomOffsetY = (Math.random() - 0.5) * 30;

        cloud.targetX = padding + col * cellWidth + cellWidth / 2 + randomOffsetX;
        cloud.targetY = padding + row * cellHeight + cellHeight / 2 + randomOffsetY;
    });
}

function handleMouseMove(event) {
    const rect = canvas.getBoundingClientRect();
    mousePos.x = event.clientX - rect.left;
    mousePos.y = event.clientY - rect.top;

    // Check for hovered cloud
    let newHoveredCloud = null;
    for (let cloud of directorClouds) {
        if (cloud.containsPoint(mousePos.x, mousePos.y)) {
            newHoveredCloud = cloud;
            break;
        }
    }

    if (newHoveredCloud !== hoveredCloud) {
        if (hoveredCloud) {
            hoveredCloud.isHovered = false;
        }
        hoveredCloud = newHoveredCloud;
        if (hoveredCloud) {
            hoveredCloud.isHovered = true;
            showTooltip(hoveredCloud.director, event.clientX, event.clientY);
        } else {
            hideTooltip();
        }
    } else if (hoveredCloud) {
        updateTooltipPosition(event.clientX, event.clientY);
    }
}

function handleClick(event) {
    if (hoveredCloud) {
        toggleDirector(hoveredCloud.director.id);
    }
}

function toggleDirector(directorId) {
    if (selectedDirectors.has(directorId)) {
        selectedDirectors.delete(directorId);
    } else {
        selectedDirectors.add(directorId);
    }

    // Update cloud selection state
    for (let cloud of directorClouds) {
        if (cloud.director.id === directorId) {
            cloud.isSelected = selectedDirectors.has(directorId);
        }
    }

    updateSelectionUI();
}

function updateSelectionUI() {
    // Update count
    const count = selectedDirectors.size;
    document.getElementById('selected-count').textContent =
        count === 0 ? 'None selected' :
        count === 1 ? '1 director' :
        `${count} directors`;

    // Enable/disable analyze button
    const analyzeBtn = document.getElementById('btn-analyze');
    analyzeBtn.disabled = count === 0;

    // Update button text
    if (count > 0) {
        analyzeBtn.textContent = `🎬 Analyze with ${count} Director${count > 1 ? 's' : ''}`;
    } else {
        analyzeBtn.textContent = '🎬 Analyze';
    }
}

function showTooltip(director, x, y) {
    const tooltip = document.getElementById('director-tooltip');

    const tagsHtml = director.tags.map(tag =>
        `<span class="tooltip-tag">${escapeHtml(tag)}</span>`
    ).join('');

    const expertiseHtml = director.expertise.map(exp =>
        `<span class="tooltip-expertise-item">${escapeHtml(exp)}</span>`
    ).join('');

    tooltip.innerHTML = `
        <div class="tooltip-name">${escapeHtml(director.name)}</div>
        <div class="tooltip-author">by ${escapeHtml(director.author)}</div>
        <div class="tooltip-description">${escapeHtml(director.description)}</div>
        <div class="tooltip-tags">${tagsHtml}</div>
        <div class="tooltip-expertise">${expertiseHtml}</div>
    `;

    updateTooltipPosition(x, y);
    tooltip.classList.add('visible');
}

function updateTooltipPosition(x, y) {
    const tooltip = document.getElementById('director-tooltip');
    tooltip.style.left = (x + 15) + 'px';
    tooltip.style.top = (y + 15) + 'px';
}

function hideTooltip() {
    const tooltip = document.getElementById('director-tooltip');
    tooltip.classList.remove('visible');
}

// Animation loop
let lastTime = Date.now();

function animate() {
    const currentTime = Date.now();
    const deltaTime = currentTime - lastTime;
    lastTime = currentTime;

    // Clear canvas with gradient background
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, '#1a1a2e');
    gradient.addColorStop(0.5, '#16213e');
    gradient.addColorStop(1, '#0f3460');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Update and draw clouds
    for (let cloud of directorClouds) {
        cloud.update(deltaTime);
        cloud.draw(ctx);
    }

    animationFrameId = requestAnimationFrame(animate);
}

function startAnimation() {
    if (!animationFrameId) {
        lastTime = Date.now();
        animate();
    }
}

function stopAnimation() {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
}

// Filter directors
function filterDirectors() {
    const query = document.getElementById('search-input').value.toLowerCase();

    if (!query) {
        filteredDirectors = [...allDirectors];
    } else {
        filteredDirectors = allDirectors.filter(director => {
            return director.name.toLowerCase().includes(query) ||
                   director.description.toLowerCase().includes(query) ||
                   director.tags.some(tag => tag.toLowerCase().includes(query)) ||
                   director.author.toLowerCase().includes(query);
        });
    }

    createDirectorClouds();
}

// Start analysis with selected directors
function startAnalysis() {
    if (!bridge || selectedDirectors.size === 0) {
        return;
    }

    const selected = Array.from(selectedDirectors);
    console.log("Starting analysis with directors:", selected);

    // Update button to show analyzing state
    const analyzeBtn = document.getElementById('btn-analyze');
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = '⏳ Analyzing...';

    // Trigger director analysis via bridge
    bridge.selectDirectors(JSON.stringify(selected));

    // Visual feedback: pulse selected clouds
    for (let cloud of directorClouds) {
        if (cloud.isSelected) {
            // Add animation feedback
            cloud.hoverSize = cloud.baseSize * 1.3;
            setTimeout(() => {
                cloud.hoverSize = cloud.baseSize * 1.2;
            }, 300);
        }
    }
}

// Open marketplace
function openMarketplace() {
    if (!bridge) return;
    bridge.openMarketplace();
}

// Utility: Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

console.log("Director Panel UI initialized (Canvas mode)");
