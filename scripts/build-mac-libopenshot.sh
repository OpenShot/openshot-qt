#!/usr/bin/env bash
# scripts/build-mac-libopenshot.sh
#
# Builds libopenshot-audio + libopenshot v0.5.0 from upstream OpenShot sources
# with the macOS / FFmpeg 8 / Apple Silicon patches required by zenvi-core.
#
# Why this exists:
# - Homebrew does not ship libopenshot. CI on arm64 builds it from source.
# - libopenshot v0.5.0 source predates FFmpeg 7/8 and macOS 26 — won't compile
#   or run cleanly without patches.
# - When running zenvi-core from source (not the frozen .app), libopenshot's
#   absolute Qt paths collide with PyQt5's bundled Qt at runtime → segfault.
#   Post-build install_name_tool rewrites fix this.
#
# What this script does:
#   1. brew install all build deps (cmake, qt@5, swig, ffmpeg, libomp, etc.)
#   2. Clone OpenShot/libopenshot-audio v0.5.0 + apply mac-patches/
#   3. Clone OpenShot/libopenshot v0.5.0 + apply mac-patches/
#   4. cmake configure + build + install to $ZENVI_DEPS (default: $HOME/zenvi-deps)
#   5. install_name_tool: rewrite @rpath for Qt to point at PyQt5's bundled Qt
#
# Result: $ZENVI_DEPS/lib/libopenshot.dylib + $ZENVI_DEPS/python/_openshot.so
# usable by:
#   - zenvi-core from source via PYTHONPATH=$ZENVI_DEPS/python python src/launch.py
#   - freeze.py via ZENVI_OPENSHOT_INSTALL=$ZENVI_DEPS python freeze.py build
#
# Usage:
#   bash scripts/build-mac-libopenshot.sh
#
# Environment:
#   ZENVI_DEPS   install prefix              (default: $HOME/zenvi-deps)
#   SRC_DIR      where to clone the sources  (default: $HOME/src)
#   LIBOPENSHOT_TAG  tag to build            (default: v0.5.0)
#   SKIP_BREW    set to 1 to skip brew installs

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH_DIR="$REPO_ROOT/installer/mac-patches"
ZENVI_DEPS="${ZENVI_DEPS:-$HOME/zenvi-deps}"
SRC_DIR="${SRC_DIR:-$HOME/src}"
TAG="${LIBOPENSHOT_TAG:-v0.5.0}"

echo "============================================="
echo " zenvi-core: Mac libopenshot rebuild"
echo "============================================="
echo "  Install prefix : $ZENVI_DEPS"
echo "  Source dir     : $SRC_DIR"
echo "  libopenshot tag: $TAG"
echo "  Patch dir      : $PATCH_DIR"
echo "============================================="
echo ""

if [[ "$(uname)" != "Darwin" ]]; then
  echo "ERROR: this script is macOS-only. On Linux use the system libopenshot package."
  exit 1
fi

# ── 1. Homebrew dependencies ────────────────────────────────────────────────
if [[ "${SKIP_BREW:-}" != "1" ]]; then
  echo "[1/5] Installing Homebrew dependencies..."
  brew install python@3.11 cmake swig pkg-config doxygen unittest-cpp \
    qt@5 ffmpeg libsamplerate libsndfile librsvg \
    zeromq cppzmq libomp openssl@3
fi

QT5_PREFIX="$(brew --prefix qt@5)"
LIBOMP_PREFIX="$(brew --prefix libomp)"
PY311_PREFIX="$(brew --prefix python@3.11)"
PY311="$PY311_PREFIX/bin/python3.11"
PY311_INCLUDE="$PY311_PREFIX/Frameworks/Python.framework/Versions/3.11/include/python3.11"
PY311_LIB="$PY311_PREFIX/Frameworks/Python.framework/Versions/3.11/lib/libpython3.11.dylib"

mkdir -p "$ZENVI_DEPS" "$SRC_DIR"

# ── 2. Build libopenshot-audio ──────────────────────────────────────────────
echo ""
echo "[2/5] Building libopenshot-audio $TAG..."
rm -rf "$SRC_DIR/libopenshot-audio"
git clone --depth=1 --branch "$TAG" \
  https://github.com/OpenShot/libopenshot-audio.git \
  "$SRC_DIR/libopenshot-audio"

cd "$SRC_DIR/libopenshot-audio"
echo "  Applying libopenshot-audio mac patches..."
git apply --whitespace=nowarn "$PATCH_DIR/libopenshot-audio-${TAG}-mac.patch"

cmake -S . -B build \
  -DCMAKE_INSTALL_PREFIX="$ZENVI_DEPS" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=arm64
cmake --build build --parallel "$(sysctl -n hw.logicalcpu)"
cmake --install build

# ── 3. Build libopenshot ────────────────────────────────────────────────────
echo ""
echo "[3/5] Building libopenshot $TAG..."
rm -rf "$SRC_DIR/libopenshot"
git clone --depth=1 --branch "$TAG" \
  https://github.com/OpenShot/libopenshot.git \
  "$SRC_DIR/libopenshot"

cd "$SRC_DIR/libopenshot"
echo "  Applying libopenshot mac patches..."
git apply --whitespace=nowarn "$PATCH_DIR/libopenshot-${TAG}-mac.patch"

cmake -S . -B build \
  -DCMAKE_INSTALL_PREFIX="$ZENVI_DEPS" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DENABLE_TESTS=OFF \
  -DENABLE_RUBY=OFF \
  -DENABLE_JAVA=OFF \
  -DENABLE_PYTHON=ON \
  -DPYTHON_EXECUTABLE="$PY311" \
  -DPYTHON_INCLUDE_DIR="$PY311_INCLUDE" \
  -DPYTHON_LIBRARY="$PY311_LIB" \
  -DCMAKE_PREFIX_PATH="$ZENVI_DEPS;$QT5_PREFIX;$LIBOMP_PREFIX" \
  -DCMAKE_CXX_FLAGS="-I$LIBOMP_PREFIX/include -Wno-deprecated-declarations" \
  -DCMAKE_EXE_LINKER_FLAGS="-L$LIBOMP_PREFIX/lib -lomp" \
  -DCMAKE_SHARED_LINKER_FLAGS="-L$LIBOMP_PREFIX/lib -lomp"
cmake --build build --parallel "$(sysctl -n hw.logicalcpu)"
cmake --install build

# ── 4. Rewrite Qt absolute paths → @rpath, add PyQt5 wheel Qt as rpath ──────
echo ""
echo "[4/5] Rewriting dylib references for from-source runs..."

# When running zenvi-core from source (not the frozen .app), libopenshot would
# load /opt/homebrew/opt/qt@5/... (its compile-time Qt) while PyQt5 loads its
# wheel-bundled Qt → two QApplication singletons in one process → segfault.
# Solution: rewrite Qt deps to @rpath, then add the PyQt5 wheel's Qt as rpath.
# Result: both libraries share PyQt5's Qt instance.
PYQT5_QT_LIB="$REPO_ROOT/.venv/lib/python3.11/site-packages/PyQt5/Qt5/lib"
HB_QT5_LIB="$QT5_PREFIX/lib"

if [[ ! -d "$PYQT5_QT_LIB" ]]; then
  echo "  WARN: PyQt5 wheel not found at $PYQT5_QT_LIB"
  echo "        Run: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  echo "        Then re-run this script (just step 4 — set SKIP_BREW=1 to skip rebuilds)."
  exit 1
fi

for f in "$ZENVI_DEPS/lib/libopenshot.0.5.0.dylib" "$ZENVI_DEPS/python/_openshot.so"; do
  for qt_ref in $(otool -L "$f" 2>/dev/null | awk -v hb="$HB_QT5_LIB" '$1 ~ hb {print $1}'); do
    new_ref="@rpath/${qt_ref#$HB_QT5_LIB/}"
    install_name_tool -change "$qt_ref" "$new_ref" "$f"
  done
  install_name_tool -add_rpath "$PYQT5_QT_LIB" "$f" 2>/dev/null || true
  install_name_tool -add_rpath "$ZENVI_DEPS/lib"  "$f" 2>/dev/null || true
done

# ── 5. Verify ───────────────────────────────────────────────────────────────
echo ""
echo "[5/5] Verifying..."
PYTHONPATH="$ZENVI_DEPS/python" "$PY311" -c "
import openshot
print('  ✓ libopenshot', openshot.OPENSHOT_VERSION_FULL)
print('  ✓ Frame.GetBytes :', hasattr(openshot.Frame, 'GetBytes'))
print('  ✓ Frame.GetImage :', hasattr(openshot.Frame, 'GetImage'))
import openshot
t = openshot.Timeline(1280, 720, openshot.Fraction(30,1), 48000, 2, openshot.LAYOUT_STEREO)
print('  ✓ Timeline construct OK')
"

echo ""
echo "============================================="
echo " Done. To run zenvi-core from source:"
echo ""
echo "   export ZENVI_OPENSHOT_INSTALL=$ZENVI_DEPS"
echo "   export PYTHONPATH=$ZENVI_DEPS/python"
echo "   export QT_MAC_WANTS_LAYER=1"
echo "   export QTWEBENGINE_DISABLE_SANDBOX=1"
echo "   .venv/bin/python src/launch.py"
echo ""
echo " To freeze a DMG:"
echo "   ZENVI_OPENSHOT_INSTALL=$ZENVI_DEPS bash scripts/build-local-mac.sh arm64"
echo "============================================="
