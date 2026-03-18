#!/bin/sh
# build-mac-dmg.sh — Build, sign, and package Zenvi as a macOS DMG
#
# Usage:
#   bash installer/build-mac-dmg.sh
#
# Environment variables (all optional):
#   APP_NAME              — App bundle name without .app (default: Zenvi)
#   ARCH                  — Target architecture label (default: x86_64)
#   SIGN_IDENTITY         — codesign identity (e.g. "Developer ID Application: Zenvi Inc")
#                           If unset, ad-hoc signing is used (no Gatekeeper trust)
#   MAC_NOTARIZE_PASSWORD — App-specific password for notarytool (requires SIGN_IDENTITY)
#   APPLE_ID              — Apple ID for notarytool (requires SIGN_IDENTITY)
#   TEAM_ID               — Apple Team ID for notarytool (requires SIGN_IDENTITY)

set -e

# ── Configuration ────────────────────────────────────────────────────────────
APP_NAME="${APP_NAME:-Zenvi}"
ARCH="${ARCH:-x86_64}"
MAC_NOTARIZE_PASSWORD="${MAC_NOTARIZE_PASSWORD:-}"
APPLE_ID="${APPLE_ID:-}"
TEAM_ID="${TEAM_ID:-}"

# Get Version from source
VERSION=$(grep -E '^VERSION = "(.*)"' src/classes/info.py | awk '{print $3}' | tr -d '"')
echo "Found Version $VERSION"

# Set paths
OS_APP_NAME="${APP_NAME}.app"
OS_DMG_NAME="${APP_NAME}-v${VERSION}-${ARCH}.dmg"
OS_PATH="build/$OS_APP_NAME/Contents"
echo "Fixing App Bundle ($OS_PATH)"

echo "Replacing Info.plist"
cp installer/Info.plist "$OS_PATH"
sed -e "s/VERSION/$VERSION/g" "$OS_PATH/Info.plist" > "$OS_PATH/Info.plist_version"
mv  "$OS_PATH/Info.plist_version" "$OS_PATH/Info.plist"

echo "Symlink Non-Code Files to Resources"
mv "$OS_PATH/MacOS/lib/blender"     "$OS_PATH/Resources/blender"     2>/dev/null && ln -s "../../Resources/blender"     "$OS_PATH/MacOS/lib/blender"     || true
mv "$OS_PATH/MacOS/lib/classes"     "$OS_PATH/Resources/classes"     2>/dev/null && ln -s "../../Resources/classes"     "$OS_PATH/MacOS/lib/classes"     || true
mv "$OS_PATH/MacOS/lib/effects"     "$OS_PATH/Resources/effects"     2>/dev/null && ln -s "../../Resources/effects"     "$OS_PATH/MacOS/lib/effects"     || true
mv "$OS_PATH/MacOS/lib/emojis"      "$OS_PATH/Resources/emojis"      2>/dev/null && ln -s "../../Resources/emojis"      "$OS_PATH/MacOS/lib/emojis"      || true
mv "$OS_PATH/MacOS/lib/images"      "$OS_PATH/Resources/images"      2>/dev/null && ln -s "../../Resources/images"      "$OS_PATH/MacOS/lib/images"      || true
mv "$OS_PATH/MacOS/lib/themes"      "$OS_PATH/Resources/themes"      2>/dev/null && ln -s "../../Resources/themes"      "$OS_PATH/MacOS/lib/themes"      || true
mv "$OS_PATH/MacOS/lib/language"    "$OS_PATH/Resources/language"    2>/dev/null && ln -s "../../Resources/language"    "$OS_PATH/MacOS/lib/language"    || true
mv "$OS_PATH/MacOS/qtwebengine_locales" "$OS_PATH/Resources/qtwebengine_locales" 2>/dev/null && ln -s "../Resources/qtwebengine_locales" "$OS_PATH/MacOS/qtwebengine_locales" || true
mv "$OS_PATH/MacOS/lib/presets"     "$OS_PATH/Resources/presets"     2>/dev/null && ln -s "../../Resources/presets"     "$OS_PATH/MacOS/lib/presets"     || true
mv "$OS_PATH/MacOS/lib/profiles"    "$OS_PATH/Resources/profiles"    2>/dev/null && ln -s "../../Resources/profiles"    "$OS_PATH/MacOS/lib/profiles"    || true
mv "$OS_PATH/MacOS/lib/resources"   "$OS_PATH/Resources/resources"   2>/dev/null && ln -s "../../Resources/resources"   "$OS_PATH/MacOS/lib/resources"   || true
mv "$OS_PATH/MacOS/lib/settings"    "$OS_PATH/Resources/settings"    2>/dev/null && ln -s "../../Resources/settings"    "$OS_PATH/MacOS/lib/settings"    || true
if [ -d "$OS_PATH/MacOS/settings" ]; then
    cp "$OS_PATH/MacOS/settings/"* "$OS_PATH/Resources/settings/" 2>/dev/null || true
    rm -r "$OS_PATH/MacOS/settings/"
fi
mv "$OS_PATH/MacOS/lib/tests"       "$OS_PATH/Resources/tests"       2>/dev/null && ln -s "../../Resources/tests"       "$OS_PATH/MacOS/lib/tests"       || true
mv "$OS_PATH/MacOS/lib/timeline"    "$OS_PATH/Resources/timeline"    2>/dev/null && ln -s "../../Resources/timeline"    "$OS_PATH/MacOS/lib/timeline"    || true
mv "$OS_PATH/MacOS/lib/titles"      "$OS_PATH/Resources/titles"      2>/dev/null && ln -s "../../Resources/titles"      "$OS_PATH/MacOS/lib/titles"      || true
mv "$OS_PATH/MacOS/lib/transitions" "$OS_PATH/Resources/transitions" 2>/dev/null && ln -s "../../Resources/transitions" "$OS_PATH/MacOS/lib/transitions" || true
mv "$OS_PATH/MacOS/lib/windows"     "$OS_PATH/Resources/windows"     2>/dev/null && ln -s "../../Resources/windows"     "$OS_PATH/MacOS/lib/windows"     || true
mv "$OS_PATH/MacOS/qt.conf"         "$OS_PATH/Resources/qt.conf"     2>/dev/null && ln -s "../Resources/qt.conf"         "$OS_PATH/MacOS/qt.conf"         || true

# Move icon (freeze.py places it as icon.icns per Info.plist CFBundleIconFile)
if [ -f "$OS_PATH/MacOS/icon.icns" ]; then
    mv "$OS_PATH/MacOS/icon.icns" "$OS_PATH/Resources/icon.icns"
fi
# Ensure icon.icns exists in Resources (fallback from installer/)
if [ ! -f "$OS_PATH/Resources/icon.icns" ]; then
    cp installer/openshot.icns "$OS_PATH/Resources/icon.icns"
fi

echo "Symlink lib folder into Resources - needed to find lib/babl-ext at runtime"
ln -sf "../MacOS/lib" "$OS_PATH/Resources/lib" 2>/dev/null || true

echo "Fix permissions inside MacOS folder"
# Give read access to all files; do NOT set +x on everything — codesign treats
# any file with execute bits as a code object that must be signed, so non-binary
# files (*.txt, *.json, *.hash, etc.) with +x will cause signing to fail.
chmod -R a+r "$OS_PATH/"
find "$OS_PATH" \( -name '*.dylib' -o -name '*.so' \) -exec chmod +x {} \;
for bin in zenvi launch launch-zenvi launch-mac; do
    [ -f "$OS_PATH/MacOS/$bin" ] && chmod +x "$OS_PATH/MacOS/$bin"
done

echo "Loop through bundled files and sign all binary files"
if [ -n "$SIGN_IDENTITY" ]; then
    # ── Production signing (requires Apple Developer certificate) ──────────
    find "build" \( -iname '*.dylib' -o -iname '*.so' \) \
        -exec codesign -s "$SIGN_IDENTITY" \
            --timestamp=http://timestamp.apple.com/ts01 \
            --entitlements "installer/openshot.entitlements" \
            --force "{}" \;

    echo "Code Sign App Bundle (deep)"
    codesign -s "$SIGN_IDENTITY" --force --deep \
        --entitlements "installer/openshot.entitlements" \
        --options runtime \
        --timestamp=http://timestamp.apple.com/ts01 \
        "build/$OS_APP_NAME"

    if [ -f "build/$OS_APP_NAME/Contents/MacOS/QtWebEngineProcess" ]; then
        codesign -s "$SIGN_IDENTITY" --force \
            --entitlements "installer/qtwebengine.entitlements" \
            --options runtime \
            --timestamp=http://timestamp.apple.com/ts01 \
            "build/$OS_APP_NAME/Contents/MacOS/QtWebEngineProcess"
    fi

    echo "Verifying App Signing"
    spctl -a -vv "build/$OS_APP_NAME"
else
    # ── Ad-hoc signing (no cert — satisfies dyld but NOT Gatekeeper) ──────
    echo "No SIGN_IDENTITY set — using ad-hoc signing"
    echo "Note: Gatekeeper will still warn users for downloaded apps (expected without a cert)"
    find "build" \( -iname '*.dylib' -o -iname '*.so' \) \
        -exec codesign -s - --force "{}" \; 2>/dev/null || true
    codesign -s - --deep --force "build/$OS_APP_NAME"
    codesign -dv --verbose=4 "build/$OS_APP_NAME" 2>&1 || true
fi

echo "Building DMG"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "build/$OS_APP_NAME" \
    -ov -format UDZO \
    "build/$OS_DMG_NAME"

if [ -n "$SIGN_IDENTITY" ]; then
    echo "Code Sign DMG"
    codesign -s "$SIGN_IDENTITY" --force \
        --entitlements "installer/openshot.entitlements" \
        --timestamp=http://timestamp.apple.com/ts01 \
        "build/$OS_DMG_NAME"
fi

# ── Notarization (requires Apple Developer account + app-specific password) ──
# Set SIGN_IDENTITY + MAC_NOTARIZE_PASSWORD + APPLE_ID + TEAM_ID to enable.
# See: https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution
if [ -n "$SIGN_IDENTITY" ] && [ -n "$MAC_NOTARIZE_PASSWORD" ] && [ -n "$APPLE_ID" ] && [ -n "$TEAM_ID" ]; then
    echo "Notarize DMG file (submit to Apple)"
    notarize_output=$(xcrun notarytool submit \
        --apple-id "$APPLE_ID" \
        --password "$MAC_NOTARIZE_PASSWORD" \
        --team-id "$TEAM_ID" \
        --wait "build/$OS_DMG_NAME")
    echo "$notarize_output"

    echo "Parse Notarize Output"
    pat='.*id: (.*)\n.*status: ([^'$'\n'']*)'
    [[ "$notarize_output" =~ $pat ]]
    REQUEST_UUID="${BASH_REMATCH[1]}"
    REQUEST_STATUS="${BASH_REMATCH[2]}"
    echo " Notarization ID: $REQUEST_UUID"
    echo " Notarization Status: $REQUEST_STATUS"

    if [ "$REQUEST_UUID" = "" ]; then
        echo "Failed to locate Notarization ID, exiting with error."
        exit 1
    fi
    if [ "$REQUEST_STATUS" != "Accepted" ]; then
        echo "Failed to locate Notarization Status of Accepted, exiting with error."
        exit 1
    fi

    sleep 30
    echo "Staple Notarization Ticket to DMG"
    xcrun stapler staple "build/$OS_DMG_NAME"

    echo "Verifying DMG Signing"
    spctl -a -t open --context context:primary-signature -v "build/$OS_DMG_NAME"
else
    echo "Notarization skipped (SIGN_IDENTITY / MAC_NOTARIZE_PASSWORD / APPLE_ID / TEAM_ID not set)"
fi

echo ""
echo "=== Done ==="
echo "Output: build/$OS_DMG_NAME"
