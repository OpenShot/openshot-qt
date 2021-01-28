#!/bin/sh
PATH=/usr/local/Cellar/python@3.7/3.7.9_2/Frameworks/Python.framework/Versions/3.7/bin:/opt/local/bin:/opt/local/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/qt5/5.5/clang_64/bin:/opt/X11/bin

# Get Version
VERSION=$(grep -E '^VERSION = "(.*)"' src/classes/info.py | awk '{print $3}' | tr -d '"')
echo "Found Version $VERSION"

# Set path to app bundle
OS_APP_NAME="OpenShot Video Editor.app"
OS_DMG_NAME="OpenShot-$VERSION.dmg"
OS_PATH="build/$OS_APP_NAME/Contents"
echo "Fixing App Bundle ($OS_PATH)"

echo "Replacing Info.plist"
cp installer/Info.plist "$OS_PATH"
sed -e "s/VERSION/$VERSION/g" "$OS_PATH/Info.plist" > "$OS_PATH/Info.plist_version"
mv  "$OS_PATH/Info.plist_version" "$OS_PATH/Info.plist"

echo "Symlink Non-Code Files to Resources"
mv "$OS_PATH/MacOS/lib/blender" "$OS_PATH/Resources/blender"; ln -s "../../Resources/blender" "$OS_PATH/MacOS/lib/blender";
mv "$OS_PATH/MacOS/lib/classes" "$OS_PATH/Resources/classes"; ln -s "../../Resources/classes" "$OS_PATH/MacOS/lib/classes";
mv "$OS_PATH/MacOS/lib/effects" "$OS_PATH/Resources/effects"; ln -s "../../Resources/effects" "$OS_PATH/MacOS/lib/effects";
mv "$OS_PATH/MacOS/lib/emojis" "$OS_PATH/Resources/emojis"; ln -s "../../Resources/emojis" "$OS_PATH/MacOS/lib/emojis";
mv "$OS_PATH/MacOS/lib/images" "$OS_PATH/Resources/images"; ln -s "../../Resources/images" "$OS_PATH/MacOS/lib/images";
mv "$OS_PATH/MacOS/lib/language" "$OS_PATH/Resources/language"; ln -s "../../Resources/language" "$OS_PATH/MacOS/lib/language";
mv "$OS_PATH/MacOS/qtwebengine_locales" "$OS_PATH/Resources/qtwebengine_locales"; ln -s "../Resources/qtwebengine_locales" "$OS_PATH/MacOS/qtwebengine_locales";
mv "$OS_PATH/MacOS/lib/presets" "$OS_PATH/Resources/presets"; ln -s "../../Resources/presets" "$OS_PATH/MacOS/lib/presets";
mv "$OS_PATH/MacOS/lib/profiles" "$OS_PATH/Resources/profiles"; ln -s "../../Resources/profiles" "$OS_PATH/MacOS/lib/profiles";
mv "$OS_PATH/MacOS/lib/resources" "$OS_PATH/Resources/resources"; ln -s "../../Resources/resources" "$OS_PATH/MacOS/lib/resources";
mv "$OS_PATH/MacOS/lib/settings" "$OS_PATH/Resources/settings"; ln -s "../../Resources/settings" "$OS_PATH/MacOS/lib/settings";
cp "$OS_PATH/MacOS/settings/"*.log "$OS_PATH/Resources/settings/"; # Copy *.log files into settings
rm -r "$OS_PATH/MacOS/settings/" # remove old settings folder
mv "$OS_PATH/MacOS/lib/tests" "$OS_PATH/Resources/tests"; ln -s "../../Resources/tests" "$OS_PATH/MacOS/lib/tests";
mv "$OS_PATH/MacOS/lib/timeline" "$OS_PATH/Resources/timeline"; ln -s "../../Resources/timeline" "$OS_PATH/MacOS/lib/timeline";
mv "$OS_PATH/MacOS/lib/titles" "$OS_PATH/Resources/titles"; ln -s "../../Resources/titles" "$OS_PATH/MacOS/lib/titles";
mv "$OS_PATH/MacOS/lib/transitions" "$OS_PATH/Resources/transitions"; ln -s "../../Resources/transitions" "$OS_PATH/MacOS/lib/transitions";
mv "$OS_PATH/MacOS/lib/windows" "$OS_PATH/Resources/windows"; ln -s "../../Resources/windows" "$OS_PATH/MacOS/lib/windows";
mv "$OS_PATH/MacOS/qt.conf" "$OS_PATH/Resources/qt.conf"; ln -s "../Resources/qt.conf" "$OS_PATH/MacOS/qt.conf";
mv "$OS_PATH/MacOS/openshot-qt.hqx" "$OS_PATH/Resources/openshot-qt.hqx"; ln -s "../Resources/openshot-qt.hqx" "$OS_PATH/MacOS/openshot-qt.hqx";
mv "$OS_PATH/MacOS/lib/launch.py" "$OS_PATH/Resources/launch.py"; ln -s "../../Resources/launch.py" "$OS_PATH/MacOS/lib/launch.py";

echo "Loop through bundled files and sign all binary files"
find "build" \( -iname '*.dylib' -o -iname '*.so' \) -exec codesign -s "OpenShot Studios, LLC" --timestamp=http://timestamp.apple.com/ts01 --entitlements "installer/openshot.entitlements" --force "{}" \;

echo "Code Sign App Bundle (deep)"
codesign -s "OpenShot Studios, LLC" --force --deep --entitlements "installer/openshot.entitlements" --options runtime --timestamp=http://timestamp.apple.com/ts01 "build/$OS_APP_NAME"
codesign -s "OpenShot Studios, LLC" --force --entitlements "installer/qtwebengine.entitlements" --options runtime --timestamp=http://timestamp.apple.com/ts01 "build/$OS_APP_NAME/Contents/MacOS/QtWebEngineProcess"

echo "Verifying App Signing"
spctl -a -vv "build/$OS_APP_NAME"

echo "Building Custom DMG"
appdmg "installer/dmg-template.json" "build/$OS_DMG_NAME"

echo "Code Sign DMG"
codesign -s "OpenShot Studios, LLC" --force --entitlements "installer/openshot.entitlements" --timestamp=http://timestamp.apple.com/ts01 "build/$OS_DMG_NAME"

echo "Notarize DMG file (send to apple)"
# No errors uploading '/Users/jonathan/builds/7d5103a1/0/OpenShot/openshot-qt/build/test.zip'.
# RequestUUID = cc285719-823f-4f0b-8e71-2df4bbbdaf72
notarize_output=$(xcrun altool --notarize-app --primary-bundle-id "org.openshot.openshot-qt.zip" --username "jonathan@openshot.org" --password "@keychain:NOTARIZE_AUTH" --file "build/$OS_DMG_NAME")
echo "$notarize_output"

echo "Parse Notarize Output and get Notarization RequestUUID"
pat='RequestUUID = (.*)'
[[ "$notarize_output" =~ $pat ]]
REQUEST_UUID="${BASH_REMATCH[1]}"
echo " RequestUUID Found: $REQUEST_UUID"

echo "Check Notarization Progress... (list recent notarization records)"
xcrun altool --notarization-history 0 -u "jonathan@openshot.org" -p "@keychain:NOTARIZE_AUTH" | head -n 10

echo "Check Notarization Info (loop until status detected)"
# Wait up to 60 minutes for notarization status to change
START=$(date +%s)
while [ "$(( $(date +%s) - 3600 ))" -lt "$START" ]; do
    notarize_info=$(xcrun altool --notarization-info "$REQUEST_UUID" -u "jonathan@openshot.org" -p "@keychain:NOTARIZE_AUTH")
    echo "$notarize_info"

    pat='Status: (.*)'
    [[ "$notarize_info" =~ $pat ]]
    notarize_status="${BASH_REMATCH[1]}"

    if [ "$notarize_status" != "in progress" ] && [ "$notarize_status" != "" ]; then
      echo "Notarization Status Found: $notarize_status. Wait for notarization to appear in --notarization-history/"
      verify_output=$(xcrun altool --notarization-history 0 -u "jonathan@openshot.org" -p "@keychain:NOTARIZE_AUTH" | grep "$REQUEST_UUID")
      if [ "$verify_output" != "" ]; then
        echo "Notarization record found, and ready for stapling!"
        break
      fi
    fi

    # Wait a few seconds
    sleep 60
done

echo "Staple Notarization Ticket to DMG"
xcrun stapler staple "build/$OS_DMG_NAME"

echo "Verifying DMG Signing"
spctl -a -t open --context context:primary-signature -v "build/$OS_DMG_NAME"
