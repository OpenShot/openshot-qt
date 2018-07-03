""" 
 @file
 @brief cx_Freeze script to build OpenShot package with dependencies (for Mac and Windows)
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2016 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.
 
 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 
 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 
 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

# Syntax to build redistributable package:  python3 freeze.py build
#
# Troubleshooting: If you encounter an error while attempting to freeze
# the PyQt5/uic/port_v2, remove the __init__.py in that folder. And if
# you are manually compiling PyQt5 on Windows, remove the -strip line
# from the Makefile. On Mac, just delete the port_v2 folder. Also, you
# might need to remove the QtTest.so from /usr/local/lib/python3.3/site-packages/PyQt5,
# if you get errors while freezing.
#
# Mac Syntax to Build App Bundle:
# 1) python3 freeze.py bdist_mac --qt-menu-nib="/usr/local/Cellar/qt5/5.4.2/plugins/platforms/" --iconfile=installer/openshot.icns --custom-info-plist=installer/Info.plist --bundle-name="OpenShot Video Editor"
# 2) change Contents/Info.plist to use launch-mac.sh as the Executable name
# 3) manually fix rsvg executable:
#    sudo dylibbundler -od -of -b -x ~/apps/rsvg/rsvg-convert -d ./rsvg-libs/ -p @executable_path/rsvg-libs/
# 4) Code sign and create the DMG (disk image)
#    a) cd ~/apps/openshot-qt-git/
#    b) bash installer/build-mac-dmg.sh
#
# Windows Syntax to Build MSI Installer
# NOTE: Python3.5 requires custom build of cx_Freeze (https://github.com/sekrause/cx_Freeze-wheels). Download, python setup.py build, python setup.py install
# 1) python3 freeze.py bdist_msi
# NOTE: Requires a tweak to cx_freeze: http://stackoverflow.com/questions/24195311/how-to-set-shortcut-working-directory-in-cx-freeze-msi-bundle
# 2) Sign MSI with private code signing key (optional)
#  NOTE: Install Windows 10 SDK first
#  signtool sign /v /f OSStudiosSPC.pfx "OpenShot Video Editor-2.0.0-win32.msi"

import inspect
import os
import sys
import fnmatch
from shutil import copytree, rmtree, copy
from cx_Freeze import setup, Executable
from PyQt5.QtCore import QLibraryInfo
import shutil


# Determine which JSON library is installed
json_library = None
try:
    import json

    json_library = "json"
except ImportError:
    import simplejson as json

    json_library = "simplejson"

# Packages to include
python_packages = ["os", "sys", "PyQt5", "openshot", "time", "uuid", "shutil", "threading", "subprocess",
                                 "re", "math", "xml", "logging", "urllib", "requests", "zmq", "webbrowser", json_library]

# Determine absolute PATH of OpenShot folder
PATH = os.path.dirname(os.path.realpath(__file__))  # Primary openshot folder

# Make a copy of the src tree (temporary for naming reasons only)
if os.path.exists(os.path.join(PATH, "src")):
    print("Copying modules to openshot_qt directory: %s" % os.path.join(PATH, "openshot_qt"))
    # Only make a copy if the SRC directory is present (otherwise ignore this)
    copytree(os.path.join(PATH, "src"), os.path.join(PATH, "openshot_qt"))

    # Make a copy of the launch.py script (to name it more appropriately)
    copy(os.path.join(PATH, "src", "launch.py"), os.path.join(PATH, "openshot_qt", "launch-openshot"))

if os.path.exists(os.path.join(PATH, "openshot_qt")):
    # Append path to system path
    sys.path.append(os.path.join(PATH, "openshot_qt"))
    print("Loaded modules from openshot_qt directory: %s" % os.path.join(PATH, "openshot_qt"))

# Append possible build server paths
sys.path.insert(0, os.path.join(PATH, "build", "install-x86", "lib"))
sys.path.insert(0, os.path.join(PATH, "build", "install-x64", "lib"))


from classes import info
from classes.logger import log

log.info("Execution path: %s" % os.path.abspath(__file__))


# Find files matching patterns
def find_files(directory, patterns):
    """ Recursively find all files in a folder tree """
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if ".pyc" not in basename and "__pycache__" not in basename:
                for pattern in patterns:
                    if fnmatch.fnmatch(basename, pattern):
                        filename = os.path.join(root, basename)
                        yield filename


# GUI applications require a different base on Windows
iconFile = "openshot-qt"
base = None
src_files = []
external_so_files = []
build_options = {}
build_exe_options = {}

# Copy QT translations to local folder (to be packaged)
qt_local_path = os.path.join(PATH, "openshot_qt", "locale", "QT")
qt_system_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
if os.path.exists(qt_system_path):
    # Create local QT translation folder (if needed)
    if not os.path.exists(qt_local_path):
        os.mkdir(qt_local_path)
    # Loop through QT translation files and copy them
    for file in os.listdir(qt_system_path):
        # Copy QT locale files
        if file.startswith("qt_") and file.endswith(".qm"):
            shutil.copyfile(os.path.join(qt_system_path, file), os.path.join(qt_local_path, file))

if sys.platform == "win32":
    base = "Win32GUI"
    build_exe_options["include_msvcr"] = True

    # Append Windows ICON file
    iconFile += ".ico"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

    # Append some additional files for Windows (this is a debug launcher)
    src_files.append((os.path.join(PATH, "installer", "launch-win.bat"), "launch-win.bat"))

    # Add additional package
    python_packages.append('idna')

    # Manually add zmq dependency (windows does not freeze it correctly)
    import zmq
    python_packages.remove('zmq')
    zmq_path = os.path.dirname(inspect.getfile(zmq))
    for filename in find_files(zmq_path, ["*"]):
        src_files.append((filename, os.path.join("lib", "zmq", filename.replace(zmq_path + "\\", ""))))

elif sys.platform == "linux":
    # Find libopenshot.so path (GitLab copies artifacts into local build/install folder)
    libopenshot_path = os.path.join(PATH, "build", "install-x64", "lib")
    if not os.path.exists(libopenshot_path):
        libopenshot_path = os.path.join(PATH, "build", "install-x86", "lib")
    if not os.path.exists(libopenshot_path):
        # Default to user install path
        libopenshot_path = "/usr/local/lib"

    # Find all related SO files
    for filename in find_files(libopenshot_path, ["*openshot*.so*"]):
        if '_' in filename or filename.count(".") == 2:
            external_so_files.append((filename, filename.replace("/usr/local/lib/", "").replace(libopenshot_path + "/", "")))

    # Append Linux ICON file
    iconFile += ".svg"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

    # Shorten name (since RPM can't have spaces)
    info.PRODUCT_NAME = "openshot-qt"

    # Add custom launcher script for frozen linux version
    src_files.append((os.path.join(PATH, "installer", "launch-linux.sh"), "launch-linux.sh"))

    # Get a list of all openshot.so dependencies (scan these libraries for their dependencies)
    import subprocess
    for library in [os.path.join(libopenshot_path, "libopenshot.so"),
                    "/usr/lib/python3/dist-packages/PyQt5/QtWebKit.cpython-34m-x86_64-linux-gnu.so",
                    "/usr/lib/python3/dist-packages/PyQt5/QtSvg.cpython-34m-x86_64-linux-gnu.so",
                    "/usr/lib/python3/dist-packages/PyQt5/QtWebKitWidgets.cpython-34m-x86_64-linux-gnu.so",
                    "/usr/lib/python3/dist-packages/PyQt5/QtWidgets.cpython-34m-x86_64-linux-gnu.so",
                    "/usr/lib/python3/dist-packages/PyQt5/QtCore.cpython-34m-x86_64-linux-gnu.so",
                    "/usr/lib/python3/dist-packages/PyQt5/QtGui.cpython-34dm-x86_64-linux-gnu.so",
                    "/usr/lib/python3/dist-packages/PyQt5/QtDBus.cpython-34dm-x86_64-linux-gnu.so",
                    "/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms/libqxcb.so"]:
        p = subprocess.Popen(["ldd", library], stdout=subprocess.PIPE)
        out, err = p.communicate()
        depends = str(out).replace("\\t","").replace("\\n","\n").replace("\'","").split("\n")

        # Loop through each line of output (which outputs dependencies - one per line)
        for line in depends:
            lineparts = line.split("=>")
            libname = lineparts[0].strip()

            if len(lineparts) > 1:
                libdetails = lineparts[1].strip()
                libdetailsparts = libdetails.split("(")

                if len(libdetailsparts) > 1:
                    # Determine if dependency is usr installed (or system installed)
                    # Or if the dependency matches one of the following exceptions
                    libpath = libdetailsparts[0].strip()
                    libpath_folder, libpath_file = os.path.split(libpath)
                    if (libpath \
                        and not libpath.startswith("/lib") \
                        and not "libnvidia-glcore.so" in libpath \
                        and not libpath_file in ["libstdc++.so.6", "libGL.so.1", "libxcb.so.1", "libX11.so.6", "libasound.so.2", "libgcc_s.so.1 ", "libICE.so.6", "libp11-kit.so.0", "libSM.so.6", "libgobject-2.0.so.0"]) \
                            or libpath_file in ["libgcrypt.so.11", "libQt5DBus.so.5", "libpng12.so.0", "libbz2.so.1.0", "libqxcb.so"]:

                        # Ignore paths that start with /lib
                        filepath, filename = os.path.split(libpath)
                        external_so_files.append((libpath, filename))

    # Manually add missing files (that were missed in the above step). These files are required
    # for certain distros (like Fedora, openSUSE, Debian, etc...)
    external_so_files.append(("/lib/x86_64-linux-gnu/libssl.so.1.0.0", "libssl.so.1.0.0"))
    external_so_files.append(("/lib/x86_64-linux-gnu/libcrypto.so.1.0.0", "libcrypto.so.1.0.0"))
    # Glib related files (required for some distros)
    external_so_files.append(("/usr/lib/x86_64-linux-gnu/libglib-2.0.so", "libglib-2.0.so"))
    external_so_files.append(("/usr/lib/x86_64-linux-gnu/libgio-2.0.so", "libgio-2.0.so"))
    external_so_files.append(("/usr/lib/x86_64-linux-gnu/libgmodule-2.0.so", "libgmodule-2.0.so"))
    external_so_files.append(("/usr/lib/x86_64-linux-gnu/libgthread-2.0.so", "libgthread-2.0.so"))

elif sys.platform == "darwin":
    # Copy Mac specific files that cx_Freeze misses
    # JPEG library
    for filename in find_files("/usr/local/Cellar/jpeg/8d/lib", ["libjpeg.8.dylib"]):
        external_so_files.append((filename, filename.replace("/usr/local/Cellar/jpeg/8d/lib/", "")))

    # Copy openshot.py Python bindings
    src_files.append((os.path.join(PATH, "openshot.py"), "openshot.py"))
    src_files.append((os.path.join(PATH, "installer", "launch-mac.sh"), "launch-mac.sh"))

    # Append Mac ICON file
    iconFile += ".hqx"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

# Append all source files
src_files.append((os.path.join(PATH, "installer", "qt.conf"), "qt.conf"))
for filename in find_files("openshot_qt", ["*"]):
    src_files.append((filename, filename.replace("openshot_qt/", "").replace("openshot_qt\\", "")))

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options["packages"] = python_packages
build_exe_options["include_files"] = src_files + external_so_files

# Set options
build_options["build_exe"] = build_exe_options

# Create distutils setup object
setup(name=info.PRODUCT_NAME,
      version=info.VERSION,
      description=info.DESCRIPTION,
      author=info.COMPANY_NAME,
      options=build_options,
      executables=[Executable("openshot_qt/launch.py",
                              base=base,
                              icon=os.path.join(PATH, "xdg", iconFile),
                              shortcutName="%s" % info.PRODUCT_NAME,
                              shortcutDir="ProgramMenuFolder")])


# Remove temporary folder (if SRC folder present)
if os.path.exists(os.path.join(PATH, "src")):
    rmtree(os.path.join(PATH, "openshot_qt"), True)