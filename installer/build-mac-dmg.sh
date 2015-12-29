# Set path to app bundle
OS_APP_NAME="OpenShot Video Editor.app"
OS_DMG_NAME="OpenShot-2.0.0.dmg"
OS_PATH="build/$OS_APP_NAME/Contents"
echo "Fixing App Bundle ($OS_PATH)"

echo "Replacing Info.plist"
cp installer/Info.plist "$OS_PATH"

echo "Symlink Non-Code Files to Resources"
mv "$OS_PATH/MacOS/blender" "$OS_PATH/Resources/blender"; ln -s "../Resources/blender" "$OS_PATH/MacOS/blender";
mv "$OS_PATH/MacOS/classes" "$OS_PATH/Resources/classes"; ln -s "../Resources/classes" "$OS_PATH/MacOS/classes";
mv "$OS_PATH/MacOS/effects" "$OS_PATH/Resources/effects"; ln -s "../Resources/effects" "$OS_PATH/MacOS/effects";
mv "$OS_PATH/MacOS/images" "$OS_PATH/Resources/images"; ln -s "../Resources/images" "$OS_PATH/MacOS/images";
mv "$OS_PATH/MacOS/locale" "$OS_PATH/Resources/locale"; ln -s "../Resources/locale" "$OS_PATH/MacOS/locale";
mv "$OS_PATH/MacOS/presets" "$OS_PATH/Resources/presets"; ln -s "../Resources/presets" "$OS_PATH/MacOS/presets";
mv "$OS_PATH/MacOS/profiles" "$OS_PATH/Resources/profiles"; ln -s "../Resources/profiles" "$OS_PATH/MacOS/profiles";
mv "$OS_PATH/MacOS/settings" "$OS_PATH/Resources/settings"; ln -s "../Resources/settings" "$OS_PATH/MacOS/settings";
mv "$OS_PATH/MacOS/tests" "$OS_PATH/Resources/tests"; ln -s "../Resources/tests" "$OS_PATH/MacOS/tests";
mv "$OS_PATH/MacOS/timeline" "$OS_PATH/Resources/timeline"; ln -s "../Resources/timeline" "$OS_PATH/MacOS/timeline";
mv "$OS_PATH/MacOS/titles" "$OS_PATH/Resources/titles"; ln -s "../Resources/titles" "$OS_PATH/MacOS/titles";
mv "$OS_PATH/MacOS/transitions" "$OS_PATH/Resources/transitions"; ln -s "../Resources/transitions" "$OS_PATH/MacOS/transitions";
mv "$OS_PATH/MacOS/uploads" "$OS_PATH/Resources/uploads"; ln -s "../Resources/uploads" "$OS_PATH/MacOS/uploads";
mv "$OS_PATH/MacOS/windows" "$OS_PATH/Resources/windows"; ln -s "../Resources/windows" "$OS_PATH/MacOS/windows";
mkdir "$OS_PATH/Resources/ImageMagick"; mv "$OS_PATH/MacOS/ImageMagick/config-Q16" "$OS_PATH/Resources/ImageMagick/config-Q16"; ln -s "../../Resources/ImageMagick/config-Q16" "$OS_PATH/MacOS/ImageMagick/config-Q16";
mv "$OS_PATH/MacOS/ImageMagick/etc" "$OS_PATH/Resources/ImageMagick/etc"; ln -s "../../Resources/ImageMagick/etc" "$OS_PATH/MacOS/ImageMagick/etc";
mv "$OS_PATH/MacOS/PyQt5.uic.widget-plugins" "$OS_PATH/Resources/PyQt5.uic.widget-plugins"; ln -s "../Resources/PyQt5.uic.widget-plugins" "$OS_PATH/MacOS/PyQt5.uic.widget-plugins";

echo "Code Sign App Bundle (deep)"
codesign -s "OpenShot Studios, LLC" "build/$OS_APP_NAME" --deep --force

echo "Verifying App Signing"
spctl -a -vv "build/$OS_APP_NAME"

echo "Building Custom DMG"
appdmg installer/dmg-template.json build/$OS_DMG_NAME

echo "Code Sign DMG"
codesign -s "OpenShot Studios, LLC" "build/$OS_DMG_NAME" --force

echo "Verifying DMG Signing"
spctl -a -vv "build/$OS_DMG_NAME"
