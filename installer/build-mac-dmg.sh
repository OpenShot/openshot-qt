# Set path to app bundle
OS_PATH="build/OpenShot Video Editor.app/Contents"
echo "Fixing App Bundle ($OS_PATH)"

echo "Replacing Info.plist"
cp installer/Info.plist "$OS_PATH"

#echo "Copy Qt Frameworks into App Bundle"
#cp -R /usr/local/Cellar/qt5/5.4.2/lib/QtCore.framework "$OS_PATH/Frameworks"
#cp -R /usr/local/Cellar/qt5/5.4.2/lib/QtGui.framework "$OS_PATH/Frameworks"
#cp -R /usr/local/Cellar/qt5/5.4.2/lib/QtMultimedia.framework "$OS_PATH/Frameworks"
#cp -R /usr/local/Cellar/qt5/5.4.2/lib/QtMultimediaWidgets.framework "$OS_PATH/Frameworks"
#cp -R /usr/local/Cellar/qt5/5.4.2/lib/QtNetwork.framework "$OS_PATH/Frameworks"
#cp -R /usr/local/Cellar/qt5/5.4.2/lib/QtWidgets.framework "$OS_PATH/Frameworks"

#echo "Remove unneeded files in Qt Frameworks"
#find 'build/OpenShot Video Editor.app/Contents/Frameworks' -name '*.prl' -type f -exec rm '{}' +

#echo "Fixing install name on Qt Frameworks"
#install_name_tool -id @executable_path/../Frameworks/QtCore.framework/QtCore build/Open*.app/Contents/Frameworks/QtCore.framework/QtCore
#install_name_tool -id @executable_path/../Frameworks/QtGui.framework/QtGui build/Open*.app/Contents/Frameworks/QtGui.framework/QtGui
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtCore.framework/Versions/5/QtCore @executable_path/../Frameworks/QtCore.framework/QtCore build/Open*.app/Contents/Frameworks/QtGui.framework/QtGui
#install_name_tool -id @executable_path/../Frameworks/QtMultimedia.framework/QtMultimedia build/Open*.app/Contents/Frameworks/QtMultimedia.framework/QtMultimedia
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtNetwork.framework/Versions/5/QtNetwork @executable_path/../Frameworks/QtNetwork.framework/QtNetwork build/Open*.app/Contents/Frameworks/QtMultimedia.framework/QtMultimedia
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtCore.framework/Versions/5/QtCore @executable_path/../Frameworks/QtCore.framework/QtCore build/Open*.app/Contents/Frameworks/QtMultimedia.framework/QtMultimedia
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtGui.framework/Versions/5/QtGui @executable_path/../Frameworks/QtGui.framework/QtGui build/Open*.app/Contents/Frameworks/QtMultimedia.framework/QtMultimedia
#install_name_tool -id @executable_path/../Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets build/Open*.app/Contents/Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtMultimedia.framework/Versions/5/QtMultimedia @executable_path/../Frameworks/QtMultimedia.framework/QtMultimedia build/Open*.app/Contents/Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtNetwork.framework/Versions/5/QtNetwork @executable_path/../Frameworks/QtNetwork.framework/QtNetwork build/Open*.app/Contents/Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtCore.framework/Versions/5/QtCore @executable_path/../Frameworks/QtCore.framework/QtCore build/Open*.app/Contents/Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtGui.framework/Versions/5/QtGui @executable_path/../Frameworks/QtGui.framework/QtGui build/Open*.app/Contents/Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtWidgets.framework/Versions/5/QtWidgets @executable_path/../Frameworks/QtWidgets.framework/QtWidgets build/Open*.app/Contents/Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtOpenGL.framework/Versions/5/QtOpenGL @executable_path/../Frameworks/QtOpenGL.framework/QtOpenGL build/Open*.app/Contents/Frameworks/QtMultimediaWidgets.framework/QtMultimediaWidgets
#install_name_tool -id @executable_path/../Frameworks/QtNetwork.framework/QtNetwork build/Open*.app/Contents/Frameworks/QtNetwork.framework/QtNetwork
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtCore.framework/Versions/5/QtCore @executable_path/../Frameworks/QtCore.framework/QtCore build/Open*.app/Contents/Frameworks/QtNetwork.framework/QtNetwork
#install_name_tool -id @executable_path/../Frameworks/QtWidgets.framework/QtWidgets build/Open*.app/Contents/Frameworks/QtWidgets.framework/QtWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtGui.framework/Versions/5/QtGui @executable_path/../Frameworks/QtGui.framework/QtGui build/Open*.app/Contents/Frameworks/QtWidgets.framework/QtWidgets
#install_name_tool -change /usr/local/Cellar/qt5/5.4.2/lib/QtCore.framework/Versions/5/QtCore @executable_path/../Frameworks/QtCore.framework/QtCore build/Open*.app/Contents/Frameworks/QtWidgets.framework/QtWidgets

#echo "Fixing libJpeg in Bundle"
#install_name_tool -id @executable_path/libjpeg.8.dylib build/Open*.app/Contents/MacOS/libjpeg.8.dylib
#install_name_tool -change /usr/local/lib/libjpeg.8.dylib @executable_path/libjpeg.8.dylib build/Open*.app/Contents/MacOS/libjpeg.8.dylib
#install_name_tool -id @executable_path/libjpeg.dylib build/Open*.app/Contents/MacOS/libjpeg.dylib
#install_name_tool -change /usr/local/lib/libjpeg.8.dylib @executable_path/libjpeg.8.dylib build/Open*.app/Contents/MacOS/libjpeg.dylib


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

#echo "Code Sign Frameworks"
#codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app/Contents/Frameworks/QtCore.framework/Versions/Current" --force
#codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app/Contents/Frameworks/QtGui.framework/Versions/Current" --force
#codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app/Contents/Frameworks/QtMultimedia.framework/Versions/Current" --force
#codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app/Contents/Frameworks/QtMultimediaWidgets.framework/Versions/Current" --force
#codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app/Contents/Frameworks/QtNetwork.framework/Versions/Current" --force
#codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app/Contents/Frameworks/QtWidgets.framework/Versions/Current" --force

#echo "Code Sign Dependencies (*.so files)"
#find 'build/OpenShot Video Editor.app/Contents/MacOS' -name '*.so' -type f -exec codesign -s 'OpenShot Studios, LLC' --force '{}' +
#echo "Code Sign Dependencies (*.dylib files)"
#find 'build/OpenShot Video Editor.app/Contents/MacOS' -name '*.dylib' -type f -exec codesign -s 'OpenShot Studios, LLC' --force '{}' +
#echo "Code Sign Dependencies (*.pyc files)"
#find 'build/OpenShot Video Editor.app/Contents/MacOS' -name '*.pyc' -type f -exec codesign -s 'OpenShot Studios, LLC' --force '{}' +
#echo "Code Sign All Files"
#find 'build/OpenShot Video Editor.app/Contents/MacOS' -type f -exec codesign -s 'OpenShot Studios, LLC' --force '{}' +

echo "Code Sign App Bundle (deep)"
codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app" --deep

echo "Verifying Code Signing"
codesign -s "OpenShot Studios, LLC" "build/OpenShot Video Editor.app" --verify

echo "Building Custom DMG"
appdmg installer/dmg-template.json build/OpenShot-2.0.0.dmg

