echo "Replacing Info.plist"
cp installer/Info.plist build/Open*.app/Contents/

echo "Building Custom DMG"
appdmg installer/dmg-template.json build/OpenShot-2.0.0.dmg



# THE FOLLOW CODE IS COMMENTED OUT, AND PROBABLY UNNEEDED. NEED TO REVISIT.
#echo "Fixing Qt5 Framework in Bundle"
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
