#!/usr/bin/env bash
# Flowcut Core Launcher - Clears Snap/host env to avoid library conflicts

set -e

# Save the script directory (repo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python3"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing venv interpreter: $PYTHON_BIN"
  echo "Create it and install deps (example):"
  echo "  python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Guard against pip-installed PyQt5 wheels in the venv.
# libopenshot is typically built/linked against system Qt, and mixing that
# with the Qt bundled in PyQt5 wheels frequently causes symbol errors.
if compgen -G "$VENV_DIR/lib/python*/site-packages/PyQt5" >/dev/null || compgen -G "$VENV_DIR/lib/python*/site-packages/PyQtWebEngine*" >/dev/null; then
  if [[ -n "${PYTHONPATH_LIBOPENSHOT:-}" && -z "${FLOWCUT_ALLOW_VENV_QT:-}" ]]; then
    echo "Detected PyQt5 / PyQtWebEngine installed inside .venv."
    echo "This commonly breaks when using local/system libopenshot (Qt ABI mismatch)."
    echo "Fix (recommended): use system PyQt5 and keep only non-Qt deps in the venv:"
    echo "  sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtsvg python3-pyqt5.qtopengl"
    echo "  .venv/bin/pip uninstall -y PyQt5 PyQtWebEngine PyQt5-Qt5 PyQt5-sip PyQtWebEngine-Qt5"
    echo "  .venv/bin/pip install -r requirements-noqt.txt"
    echo "Also ensure .venv can see system packages (include-system-site-packages = true)."
    echo "Override (not recommended): set FLOWCUT_ALLOW_VENV_QT=1"
    exit 1
  fi
fi

# Preserve selected host values before wiping the environment
HOST_PYTHONPATH="${PYTHONPATH:-}"
HOST_PYTHONPATH_LIBOPENSHOT="${PYTHONPATH_LIBOPENSHOT:-}"

# Merge libopenshot bindings path into PYTHONPATH when provided.
COMBINED_PYTHONPATH="$HOST_PYTHONPATH"
if [[ -n "$HOST_PYTHONPATH_LIBOPENSHOT" ]]; then
  if [[ -n "$COMBINED_PYTHONPATH" ]]; then
    COMBINED_PYTHONPATH="$HOST_PYTHONPATH_LIBOPENSHOT:$COMBINED_PYTHONPATH"
  else
    COMBINED_PYTHONPATH="$HOST_PYTHONPATH_LIBOPENSHOT"
  fi
fi

# If using a local libopenshot build, prefer its shared libraries too.
LIBOPENSHOT_LIB_DIR=""
if [[ -n "$HOST_PYTHONPATH_LIBOPENSHOT" && -d "$HOST_PYTHONPATH_LIBOPENSHOT" ]]; then
  LIBOPENSHOT_BUILD_DIR="$(cd "$(dirname "$HOST_PYTHONPATH_LIBOPENSHOT")/.." && pwd)"
  if [[ -d "$LIBOPENSHOT_BUILD_DIR/src" ]]; then
    LIBOPENSHOT_LIB_DIR="$LIBOPENSHOT_BUILD_DIR/src"
  fi
fi

# Start with a clean environment but ensure we run the venv Python.
# Note: Do NOT force a system LD_LIBRARY_PATH here (it can break PyQt5 by
# mixing system Qt libs with the wheels' bundled Qt).
ENV_ARGS=(
  "HOME=$HOME"
  "USER=${USER:-}"
  "LOGNAME=${LOGNAME:-${USER:-}}"
  "LANG=${LANG:-C.UTF-8}"
  "LC_ALL=${LC_ALL:-}"
  "PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
  "VIRTUAL_ENV=$VENV_DIR"
  "PYTHONNOUSERSITE=1"
  "SHELL=${SHELL:-/bin/bash}"
  "TERM=${TERM:-xterm-256color}"
  "DISPLAY=${DISPLAY:-}"
  "DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-}"
  "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-}"
  "PYTHONPATH=$COMBINED_PYTHONPATH"
  "PYTHONPATH_LIBOPENSHOT=$HOST_PYTHONPATH_LIBOPENSHOT"
)

if [[ -n "$LIBOPENSHOT_LIB_DIR" ]]; then
  ENV_ARGS+=("LD_LIBRARY_PATH=$LIBOPENSHOT_LIB_DIR")
fi

exec env -i "${ENV_ARGS[@]}" \
  "$PYTHON_BIN" "$SCRIPT_DIR/src/launch.py" "$@"
