#!/usr/bin/env bash
# Run OpenShot Video Editor from the repo root.
# Requires: venv created and libopenshot installed (see SETUP.md).

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

if [[ ! -d .venv ]]; then
  echo "No .venv found. Run: python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Fail fast with a clear message if libopenshot is not available
if ! .venv/bin/python3 -c "import openshot" 2>/dev/null; then
  echo "The 'openshot' module (libopenshot) is not installed."
  echo "Install it, then run again. Examples:"
  echo "  Ubuntu: sudo add-apt-repository ppa:openshot.developers/ppa && sudo apt update && sudo apt install python3-openshot"
  echo "  Check:  .venv/bin/python3 scripts/check_setup.py"
  exit 1
fi

# Optional: for headless / CI use offscreen. Omit for normal GUI (X11/Wayland).
if [[ -n "${OPENSHOT_HEADLESS:-}" ]]; then
  export QT_QPA_PLATFORM=offscreen
fi

exec .venv/bin/python3 src/launch.py "$@"
