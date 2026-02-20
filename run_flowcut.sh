#!/bin/bash
# Flowcut launcher with GPU acceleration disabled (fixes WebEngine errors)

cd /home/vboxuser/Projects/Flowcut

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Creating..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Disable GPU acceleration for WebEngine (fixes command buffer errors)
export QTWEBENGINE_CHROMIUM_FLAGS="--disable-gpu --no-sandbox --disable-software-rasterizer"

# Optional: Enable logging
# export QT_LOGGING_RULES="qt.webenginecontext.debug=true"

echo "🚀 Starting Flowcut..."
echo "   GPU acceleration: disabled (prevents WebEngine errors)"
echo ""

python src/launch.py "$@"
