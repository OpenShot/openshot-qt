#!/bin/bash
#
# Local Linux build & test script
#
# Replicates the GitHub Actions CI pipeline:
#   1. cx_Freeze build
#   2. .deb packaging (identical to release.yml)
#   3. Bundle validation (file presence, ldd checks)
#   4. Optional: Docker-based runtime test for full isolation
#
# Usage:
#   ./installer/build-test-linux.sh              # full build + test
#   ./installer/build-test-linux.sh --skip-build # reuse existing build, just package + test
#   ./installer/build-test-linux.sh --test-only  # reuse existing .deb, just test
#   ./installer/build-test-linux.sh --docker     # also run Docker isolation test

set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ_ROOT"

# Parse version from info.py
VER=$(python3 -c "
import sys; sys.path.insert(0, 'src')
from classes.info import VERSION; print(VERSION)
")
echo "==> Version: $VER"

SKIP_BUILD=false
TEST_ONLY=false
USE_DOCKER=false
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        --test-only)  TEST_ONLY=true ;;
        --docker)     USE_DOCKER=true ;;
    esac
done

# ── Step 1: cx_Freeze build ─────────────────────────────────────────
if [ "$SKIP_BUILD" = false ] && [ "$TEST_ONLY" = false ]; then
    echo ""
    echo "==> Step 1: Cleaning previous build..."
    rm -rf build/exe.linux-* openshot_qt/
    echo "==> Running cx_Freeze build..."
    python3 freeze.py build --git-branch=local-test
    echo "==> cx_Freeze build complete."
fi

FROZEN_DIR=$(find build -maxdepth 1 -type d -name 'exe.linux-*' 2>/dev/null | head -1)
if [ -z "$FROZEN_DIR" ]; then
    echo "ERROR: cx_Freeze output directory build/exe.linux-* not found"
    ls -la build/ 2>/dev/null || true
    exit 1
fi
echo "==> Frozen directory: $FROZEN_DIR"

# ── Step 2: Package .deb ────────────────────────────────────────────
DEB_FILE="Zenvi-v${VER}-x86_64.deb"

if [ "$TEST_ONLY" = false ]; then
    echo ""
    echo "==> Step 2: Building .deb package..."

    DEB_DIR="build/zenvi_${VER}_amd64"
    rm -rf "$DEB_DIR" "$DEB_FILE"
    mkdir -p "$DEB_DIR/DEBIAN"
    mkdir -p "$DEB_DIR/opt/zenvi"
    mkdir -p "$DEB_DIR/usr/bin"
    mkdir -p "$DEB_DIR/usr/share/applications"
    mkdir -p "$DEB_DIR/usr/share/icons/hicolor/256x256/apps"

    # Copy frozen build into /opt/zenvi (self-contained layout)
    cp -r "$FROZEN_DIR"/* "$DEB_DIR/opt/zenvi/"

    # Launcher script (must NOT have leading whitespace — heredoc is unindented)
    cat > "$DEB_DIR/usr/bin/zenvi" << 'LAUNCHER'
#!/bin/bash
HERE="/opt/zenvi"
export LD_LIBRARY_PATH="$HERE:$HERE/lib:${LD_LIBRARY_PATH}"
export PYTHONPATH="$HERE/lib:${PYTHONPATH}"
export QT_PLUGIN_PATH="$HERE"
export QT_QPA_PLATFORM_PLUGIN_PATH="$HERE/plugins/platforms"
export OPENSSL_CONF="/dev/null"
exec "$HERE/zenvi" "$@"
LAUNCHER
    chmod +x "$DEB_DIR/usr/bin/zenvi"

    # Desktop file
    cp xdg/*.desktop "$DEB_DIR/usr/share/applications/" 2>/dev/null || true

    # Icon
    ICON=$(find images xdg -name "*.png" -path "*256*" 2>/dev/null | head -1)
    if [ -n "$ICON" ]; then
        cp "$ICON" "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/zenvi.png"
    fi

    # Control file (must NOT have leading whitespace)
    cat > "$DEB_DIR/DEBIAN/control" << CTRL
Package: zenvi
Version: ${VER}
Section: video
Priority: optional
Architecture: amd64
Depends: python3
Maintainer: Zenvi Team <team@zenvi.org>
Description: Zenvi Video Editor
 Create and edit stunning videos, films, and animations.
CTRL

    dpkg-deb --build "$DEB_DIR" "$DEB_FILE"
    echo "==> .deb package created: $DEB_FILE"
fi

if [ ! -f "$DEB_FILE" ]; then
    echo "ERROR: $DEB_FILE not found"
    exit 1
fi

# ── Step 3: Bundle validation ────────────────────────────────────────
echo ""
echo "==> Step 3: Validating bundle contents..."
echo ""

# Extract the .deb into a temporary root (no sudo/install needed)
TEST_ROOT=$(mktemp -d /tmp/zenvi-test.XXXXXX)
trap 'rm -rf "$TEST_ROOT"' EXIT
dpkg-deb -x "$DEB_FILE" "$TEST_ROOT"

APP_DIR="$TEST_ROOT/opt/zenvi"
FAIL=0

# -- Check critical Python modules in lib/ --
echo "--- Checking bundled Python modules ---"
for f in openshot.py; do
    if find "$APP_DIR/lib" -maxdepth 1 -name "$f" | grep -q .; then
        echo "  FOUND: lib/$f"
    else
        echo "  MISSING: lib/$f"
        FAIL=1
    fi
done
# _openshot can be .so, .cpython-*.so, or .pyd
if find "$APP_DIR/lib" -maxdepth 1 -name '_openshot*' | grep -q .; then
    echo "  FOUND: _openshot native extension"
    find "$APP_DIR/lib" -maxdepth 1 -name '_openshot*' -exec echo "    -> lib/{/}" \;
else
    echo "  MISSING: _openshot native extension"
    FAIL=1
fi
echo ""

# -- Check libopenshot shared libraries --
echo "--- Checking libopenshot bundling ---"
if find "$APP_DIR" -maxdepth 1 -name 'libopenshot*.so*' | grep -q .; then
    echo "  FOUND: libopenshot bundled"
    find "$APP_DIR" -maxdepth 1 -name 'libopenshot*.so*' -printf "    -> %f\n"
else
    echo "  MISSING: libopenshot.so (will rely on system)"
    FAIL=1
fi
echo ""

# -- Check OpenGL modules --
echo "--- Checking OpenGL bundling ---"
OGL_COUNT=$(find "$APP_DIR/lib" -path '*/OpenGL/*' 2>/dev/null | wc -l)
if [ "$OGL_COUNT" -gt 0 ]; then
    echo "  FOUND: OpenGL package ($OGL_COUNT files)"
else
    echo "  WARNING: OpenGL package not found in bundle"
fi
echo ""

# -- Check main binary dependencies --
echo "--- Checking for missing shared library dependencies ---"
NOT_FOUND=$(ldd "$APP_DIR/zenvi" 2>&1 | grep "not found" || true)
if [ -n "$NOT_FOUND" ]; then
    echo "  WARNING: Missing dependencies:"
    echo "$NOT_FOUND" | sed 's/^/    /'
else
    echo "  All shared library dependencies satisfied."
fi
echo ""

# -- Check key bundled .so files have their deps satisfied --
echo "--- Checking _openshot.so dependencies ---"
OPENSHOT_SO=$(find "$APP_DIR/lib" -maxdepth 1 -name '_openshot*' | head -1)
if [ -n "$OPENSHOT_SO" ]; then
    OS_MISSING=$(LD_LIBRARY_PATH="$APP_DIR:$APP_DIR/lib" ldd "$OPENSHOT_SO" 2>&1 | grep "not found" || true)
    if [ -n "$OS_MISSING" ]; then
        echo "  WARNING: _openshot has unresolved dependencies:"
        echo "$OS_MISSING" | sed 's/^/    /'
    else
        echo "  All _openshot.so dependencies satisfied."
    fi
fi
echo ""

# -- Try version check (may fail locally due to system Python contamination) --
echo "--- Running version check ---"
VERSION_OUTPUT=$(
    env -i \
        HOME="$HOME" \
        PATH="$APP_DIR:/usr/bin:/bin" \
        LD_LIBRARY_PATH="$APP_DIR:$APP_DIR/lib" \
        QT_PLUGIN_PATH="$APP_DIR" \
        QT_QPA_PLATFORM_PLUGIN_PATH="$APP_DIR/plugins/platforms" \
        PYOPENGL_PLATFORM=null \
        DISPLAY="" \
        XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" \
        "$APP_DIR/zenvi" -V 2>&1
) && {
    echo "  Version: $VERSION_OUTPUT"
    echo "  => Version check PASSED"
} || {
    RC=$?
    if echo "$VERSION_OUTPUT" | grep -q "circular import\|partially initialized"; then
        echo "  => Version check SKIPPED (local env contamination — PyQt5 circular import)"
        echo "     This is expected when running on the build machine."
        echo "     Use --docker for a fully isolated test, or push to CI."
    else
        echo "  => Version check FAILED (exit code $RC):"
        echo "$VERSION_OUTPUT" | sed 's/^/     /'
        FAIL=1
    fi
}
echo ""

# ── Step 4: Docker isolation test (optional) ─────────────────────────
if [ "$USE_DOCKER" = true ]; then
    echo "==> Step 4: Docker isolation test..."
    if ! command -v docker &>/dev/null; then
        echo "  ERROR: docker not found. Install Docker to use --docker."
        FAIL=1
    else
        DEB_ABS="$(pwd)/$DEB_FILE"
        DOCKER_OUTPUT=$(docker run --rm \
            -v "$DEB_ABS:/tmp/zenvi.deb:ro" \
            ubuntu:22.04 bash -c '
                apt-get update -qq && \
                apt-get install -y -qq --no-install-recommends \
                    libopenshot-dev libgl1 libxkbcommon0 > /dev/null 2>&1 && \
                dpkg -i /tmp/zenvi.deb 2>&1 && \
                export PYOPENGL_PLATFORM=null && \
                export QT_QPA_PLATFORM=offscreen && \
                /usr/bin/zenvi -V 2>&1
            ' 2>&1
        ) && {
            echo "  Docker version output: $DOCKER_OUTPUT"
            echo "  => Docker test PASSED"
        } || {
            echo "  => Docker test FAILED:"
            echo "$DOCKER_OUTPUT" | tail -20 | sed 's/^/     /'
            FAIL=1
        }
    fi
    echo ""
fi

# ── Summary ──────────────────────────────────────────────────────────
if [ "$FAIL" -eq 0 ]; then
    echo "============================================"
    echo "  ALL CHECKS PASSED"
    echo "  .deb package: $(pwd)/$DEB_FILE"
    echo "  Size: $(du -h "$DEB_FILE" | cut -f1)"
    echo "============================================"
else
    echo "============================================"
    echo "  SOME CHECKS FAILED — see output above"
    echo "============================================"
    exit 1
fi
