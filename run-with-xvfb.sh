#!/usr/bin/env bash
# Run OpenShot with a virtual display (xvfb) so the GUI can start without a real display.
# Use this in CI or headless environments. Requires: xvfb-run (apt install xvfb).

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "xvfb-run not found. Install with: sudo apt install xvfb"
  echo "Falling back to headless (offscreen) mode without xvfb."
  export QT_QPA_PLATFORM=offscreen
  exec "$REPO_ROOT/run.sh" "$@"
fi

if [[ ! -d .venv ]]; then
  echo "No .venv found. Run: python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

exec xvfb-run -a .venv/bin/python3 src/launch.py "$@"
