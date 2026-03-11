#!/usr/bin/env bash
# scripts/build-local-mac.sh — Local macOS build and test script for Zenvi
#
# Usage:
#   bash scripts/build-local-mac.sh [x86_64|arm64]
#
# Requires: Python 3.11, PyQt5, cx_Freeze 7.0.0
#   pip3 install -r requirements.txt
#
# Optional env vars:
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
echo "[2/5] Running cx_Freeze (build)..."
python3 freeze.py build --git-branch=production

# ── Step 3: Locate frozen output ─────────────────────────────────────────────
FROZEN_DIR=$(find build -maxdepth 1 -type d -name 'exe.*' | head -1)
if [ -z "$FROZEN_DIR" ]; then
  echo "ERROR: No cx_Freeze output directory found in build/. The freeze step likely failed."
  exit 1
fi
echo "Found frozen dir: $FROZEN_DIR"

# ── Step 4: Construct .app bundle ────────────────────────────────────────────
echo "[3/5] Constructing .app bundle..."
APP="${APP_NAME}.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp -R "$FROZEN_DIR"/* "$APP/Contents/MacOS/"

# Substitute VERSION in Info.plist
sed "s/VERSION/${VER}/g" installer/Info.plist > "$APP/Contents/Resources/Info.plist"
cp "$APP/Contents/Resources/Info.plist" "$APP/Contents/Info.plist"

# Icon
if [ -f "installer/openshot.icns" ]; then
  cp installer/openshot.icns "$APP/Contents/Resources/icon.icns"
else
  ICON=$(find xdg images -name "*.png" -path "*256*" 2>/dev/null | head -1)
  [ -n "$ICON" ] && cp "$ICON" "$APP/Contents/Resources/icon.png"
fi

# Ensure all known entry points are executable.
# Info.plist declares CFBundleExecutable=launch-mac so it must be +x.
for bin in zenvi launch launch-openshot launch-mac; do
  [ -f "$APP/Contents/MacOS/$bin" ] && chmod +x "$APP/Contents/MacOS/$bin" || true
done

# ── Step 5: Sign ─────────────────────────────────────────────────────────────
echo "[4/5] Signing..."
if [ -n "${SIGN_IDENTITY:-}" ]; then
  echo "  Production signing with identity: $SIGN_IDENTITY"
  find build \( -name '*.dylib' -o -name '*.so' \) \
    -exec codesign -s "$SIGN_IDENTITY" --timestamp=http://timestamp.apple.com/ts01 \
      --entitlements installer/openshot.entitlements --force "{}" \;
  codesign -s "$SIGN_IDENTITY" --force --deep \
    --entitlements installer/openshot.entitlements \
    --options runtime --timestamp=http://timestamp.apple.com/ts01 \
    "$APP"
  spctl -a -vv "$APP"
else
  echo "  Ad-hoc signing (no SIGN_IDENTITY set)"
  find build \( -name '*.dylib' -o -name '*.so' \) \
    -exec codesign -s - --force "{}" \; 2>/dev/null || true
  codesign -s - --deep --force "$APP"
fi

# ── Step 6: Create DMG ────────────────────────────────────────────────────────
DMG_NAME="Zenvi-v${VER}-${ARCH}.dmg"
echo "[5/5] Creating DMG: $DMG_NAME"
rm -rf dmgroot && mkdir dmgroot
cp -R "$APP" dmgroot/
ln -s /Applications dmgroot/Applications
hdiutil create \
  -volname "Zenvi" \
  -srcfolder "dmgroot" \
  -ov -format UDZO \
  "$DMG_NAME"
rm -rf dmgroot

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
