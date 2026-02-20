#!/bin/bash
# Install Manim for Flowcut educational video generation

echo "╔═══════════════════════════════════════════╗"
echo "║   Installing Manim for Flowcut           ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated"
    echo "Activating .venv..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        echo "❌ .venv not found. Please create it first:"
        echo "   python3 -m venv .venv"
        exit 1
    fi
fi

echo "📦 Installing Manim..."
pip install manim

echo ""
echo "🔍 Verifying installation..."
if command -v manim &> /dev/null; then
    echo "✅ Manim installed successfully!"
    manim --version
    echo ""
    echo "🎉 You can now generate educational animations!"
    echo ""
    echo "Try: 'Create a manim video explaining the Pythagorean theorem'"
else
    echo "❌ Installation failed. Please install manually:"
    echo "   pip install manim"
    exit 1
fi

echo ""
echo "📚 Optional: Install LaTeX for mathematical notation"
echo "   Ubuntu/Debian: sudo apt-get install texlive-full"
echo "   macOS:         brew install --cask mactex"
