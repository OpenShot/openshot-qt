#!/usr/bin/env bash
# scripts/build-local-mac.sh — Local macOS build and test script for Zenvi
#
# Usage:
#   bash scripts/build-local-mac.sh [x86_64|arm64]
#
# Requires: Python 3.11, PyQt5, cx_Freeze 7.0.0
#   pip3 install -r requirements.txt
#
# Optional env vars (same as installer/build-mac-dmg.sh):
#   SIGN_IDENTITY         — codesign identity for production signing
#   MAC_NOTARIZE_PASSWORD — notarytool password (requires SIGN_IDENTITY)
#   APPLE_ID              — Apple ID for notarytool
#   TEAM_ID               — Apple Team ID for notarytool

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

ARCH="${1:-$(uname -m)}"
APP_NAME="${APP_NAME:-Zenvi}"

# Parse version from source
VER=$(python3 -c "
import re, pathlib
text = pathlib.Path('src/classes/info.py').read_text()
m = re.search(r'VERSION\s*=\s*\"([^\"]+)\"', text)
print(m.group(1))
")

echo "======================================"
echo " Zenvi Local macOS Build"
echo " Version : $VER"
echo " Arch    : $ARCH"
echo " Sign    : ${SIGN_IDENTITY:-ad-hoc (no cert)}"
echo "======================================"
echo ""

# ── Step 1: Install Python dependencies ──────────────────────────────────────
echo "[1/5] Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install -r requirements.txt
pip3 install pyobjc-framework-Cocoa 2>/dev/null || true

# ── Step 2: Freeze ────────────────────────────────────────────────────────────
echo "[2/5] Running cx_Freeze (bdist_mac)..."
python3 freeze.py bdist_mac --git-branch=production

# ── Step 3: Verify .app bundle exists ────────────────────────────────────────
APP_BUNDLE=$(find build -maxdepth 1 -name "*.app" -type d | head -1)
if [ -z "$APP_BUNDLE" ]; then
  echo "ERROR: No .app bundle found in build/. The freeze step likely failed."
  exit 1
fi
echo "Found app bundle: $APP_BUNDLE"

EXPECTED="build/${APP_NAME}.app"
if [ "$APP_BUNDLE" != "$EXPECTED" ]; then
  echo "Renaming $APP_BUNDLE → $EXPECTED"
  mv "$APP_BUNDLE" "$EXPECTED"
fi

# ── Step 4: Structure bundle + sign ──────────────────────────────────────────
echo "[3/5] Structuring .app bundle..."
OS_PATH="$EXPECTED/Contents"
mkdir -p "$OS_PATH/MacOS" "$OS_PATH/Resources"

cp installer/Info.plist "$OS_PATH/Info.plist"
sed -i '' "s/VERSION/${VER}/g" "$OS_PATH/Info.plist"
echo "  Info.plist updated with version $VER"

# Move resource directories to Resources/ and symlink back
for dir in classes effects emojis images themes language presets \
           profiles resources settings timeline titles transitions windows blender; do
  SRC="$OS_PATH/MacOS/lib/$dir"
  DST="$OS_PATH/Resources/$dir"
  if [ -d "$SRC" ]; then
    mv "$SRC" "$DST"
    ln -s "../../Resources/$dir" "$SRC"
    echo "  Symlinked: $dir"
  fi
done

if [ -d "$OS_PATH/MacOS/qtwebengine_locales" ]; then
  mv "$OS_PATH/MacOS/qtwebengine_locales" "$OS_PATH/Resources/"
  ln -s "../Resources/qtwebengine_locales" "$OS_PATH/MacOS/qtwebengine_locales"
  echo "  Symlinked: qtwebengine_locales"
fi

if [ -f "$OS_PATH/MacOS/qt.conf" ]; then
  mv "$OS_PATH/MacOS/qt.conf" "$OS_PATH/Resources/qt.conf"
  ln -s "../Resources/qt.conf" "$OS_PATH/MacOS/qt.conf"
  echo "  Symlinked: qt.conf"
fi

[ -f "$OS_PATH/MacOS/icon.icns" ] && mv "$OS_PATH/MacOS/icon.icns" "$OS_PATH/Resources/icon.icns"
[ ! -f "$OS_PATH/Resources/icon.icns" ] && cp installer/openshot.icns "$OS_PATH/Resources/icon.icns"

[ ! -L "$OS_PATH/Resources/lib" ] && ln -s "../MacOS/lib" "$OS_PATH/Resources/lib"
chmod -R a+rx "$OS_PATH/"

echo "[4/5] Signing..."
if [ -n "${SIGN_IDENTITY:-}" ]; then
  echo "  Production signing with identity: $SIGN_IDENTITY"
  find build \( -name '*.dylib' -o -name '*.so' \) \
    -exec codesign -s "$SIGN_IDENTITY" --timestamp=http://timestamp.apple.com/ts01 \
      --entitlements installer/openshot.entitlements --force "{}" \;
  codesign -s "$SIGN_IDENTITY" --force --deep \
    --entitlements installer/openshot.entitlements \
    --options runtime --timestamp=http://timestamp.apple.com/ts01 \
    "$EXPECTED"
  spctl -a -vv "$EXPECTED"
else
  echo "  Ad-hoc signing (no SIGN_IDENTITY set)"
  find build \( -name '*.dylib' -o -name '*.so' \) \
    -exec codesign -s - --force "{}" \; 2>/dev/null || true
  codesign -s - --deep --force "$EXPECTED"
fi

# ── Step 5: Create DMG ────────────────────────────────────────────────────────
DMG_NAME="Zenvi-v${VER}-${ARCH}.dmg"
echo "[5/5] Creating DMG: $DMG_NAME"
hdiutil create \
  -volname "Zenvi" \
  -srcfolder "$EXPECTED" \
  -ov -format UDZO \
  "$DMG_NAME"

echo ""
echo "======================================"
echo " Build complete!"
echo " Output: $(pwd)/$DMG_NAME"
echo "======================================"
echo ""
echo "Test instructions:"
echo "  1. Double-click $DMG_NAME in Finder to mount it"
echo "  2. Drag Zenvi.app to the Applications folder"
echo "  3. First launch: right-click Zenvi.app → Open → click Open in the dialog"
echo "     (This bypass is only needed once when there is no Apple Developer cert)"
echo "  4. Verify the app launches, opens a project, and plays back video"
echo ""
