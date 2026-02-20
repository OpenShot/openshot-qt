#!/bin/bash
# Complete setup for Zenvi with Manim support

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║        Complete Zenvi + Manim Setup                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

cd /home/vboxuser/Projects/Zenvi

# Step 1: Install system dependencies
echo "📦 Step 1/4: Installing system dependencies (requires sudo)..."
echo ""
sudo apt-get update
sudo apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    ffmpeg \
    pkg-config \
    python3-dev \
    python3-venv

echo ""
echo "✅ System dependencies installed"
echo ""

# Step 2: Ensure venv is correct
echo "🔧 Step 2/4: Setting up Python virtual environment..."
if [ -d ".venv" ]; then
    # Check if venv is broken (pointing to wrong location)
    if grep -q "Zenvi" .venv/bin/activate 2>/dev/null; then
        echo "⚠️  Broken venv detected (pointing to Zenvi). Recreating..."
        mv .venv .venv.broken_backup_$(date +%s)
        python3 -m venv .venv --system-site-packages
    else
        echo "✓ Existing venv looks good"
    fi
else
    echo "Creating new venv..."
    python3 -m venv .venv --system-site-packages
fi

source .venv/bin/activate
echo "✅ Virtual environment ready"
echo "   Location: $VIRTUAL_ENV"
echo ""

# Step 3: Install Python requirements
echo "📦 Step 3/4: Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ Requirements installed"
else
    echo "⚠️  requirements.txt not found, skipping..."
fi
echo ""

# Step 4: Install Manim
echo "🎨 Step 4/4: Installing Manim..."
pip install manim

echo ""
echo "🔍 Verifying Manim installation..."
if python -c "import manim; print('✅ Manim version:', manim.__version__)" 2>&1; then
    echo ""
    manim --version
else
    echo "❌ Manim installation verification failed"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    ✅ Setup Complete!                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Run Zenvi:  ./run_zenvi.sh"
echo "  2. Open AI Chat"
echo "  3. Try: 'Create a manim video explaining the Pythagorean theorem'"
echo ""
echo "Optional: Install LaTeX for better math typesetting:"
echo "  sudo apt-get install texlive-latex-base texlive-fonts-recommended"
echo ""
