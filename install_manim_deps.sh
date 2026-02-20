#!/bin/bash
# Install system dependencies for Manim

echo "╔═══════════════════════════════════════════════════════╗"
echo "║   Installing Manim System Dependencies              ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

echo "📦 Installing required system packages..."
echo ""

sudo apt-get update && sudo apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    ffmpeg \
    pkg-config \
    python3-dev

echo ""
echo "📚 Installing LaTeX (optional, for mathematical notation)..."
echo "   This is large (~1GB). Skip if you don't need math formulas."
echo ""
read -p "Install LaTeX? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo apt-get install -y \
        texlive-latex-base \
        texlive-fonts-recommended \
        texlive-fonts-extra \
        texlive-latex-extra
    echo "✅ LaTeX installed"
else
    echo "⏭️  Skipped LaTeX (you can install later if needed)"
fi

echo ""
echo "✅ System dependencies installed!"
echo ""
echo "Next steps:"
echo "1. Install Manim:  ./install_manim.sh"
echo "2. Run Zenvi:    ./run_zenvi.sh"
