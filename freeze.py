""" 
 @file
 @brief cx_Freeze script to build OpenShot package with dependencies (for Mac and Windows)
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2014 OpenShot Studios, LLC
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
# from the Makefile.
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
# 1) python3 freeze.py bdist_msi
# NOTE: Requires a tweak to cx_freeze: http://stackoverflow.com/questions/24195311/how-to-set-shortcut-working-directory-in-cx-freeze-msi-bundle
# 2) Sign MSI with private code signing key (optional)
#  NOTE: Install Windows 10 SDK first
#  signtool sign /v /f OSStudiosSPC.pfx "OpenShot Video Editor-2.0.0-win32.msi"

import os
import sys
import fnmatch
from shutil import copytree, rmtree, copy
from cx_Freeze import setup, Executable

# Determine which JSON library is installed
json_library = None
try:
    import json

    json_library = "json"
except ImportError:
    import simplejson as json

    json_library = "simplejson"


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
iconFile = "openshot"
base = None
src_files = []
external_so_files = []
build_options = {}
build_exe_options = {}


if sys.platform == "win32":
    base = "Win32GUI"
    external_so_files = []
    build_exe_options["include_msvcr"] = True

    # Copy required ImageMagick files
    for filename in find_files("C:\\Program Files\\ImageMagick-Windows7\\etc\\ImageMagick-6", ["*.xml"]):
        external_so_files.append(
            (filename, filename.replace("C:\\Program Files\\ImageMagick-Windows7\\etc\\ImageMagick-6\\",
                                        "ImageMagick/etc/configuration/")))

    # Copy missing SVG dll
    # TODO: Determine why cx_Freeze misses this DLL when freezing. Without it, libopenshot cannot open SVG files
    for filename in find_files("C:\\Qt\\Qt5.4.2\\5.4\\mingw491_32\\bin", ["Qt5Svgd.dll"]):
        external_so_files.append(
            (filename, filename.replace("C:\\Qt\\Qt5.4.2\\5.4\\mingw491_32\\bin\\", "")))

    # Append Windows ICON file
    iconFile += ".ico"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

    # Append some additional files for Windows (this is a debug launcher)
    src_files.append((os.path.join(PATH, "installer", "launch-win.bat"), "launch-win.bat"))

    # Create environment variable for ImageMagick (on install)
    environment_table = [
        ("MAGICK_CONFIGURE_PATH",
         "*=MAGICK_CONFIGURE_PATH",
         "[TARGETDIR]ImageMagick\\etc\\configuration",
         "OpenShot"
         ),
        # TODO: Find a better way to load the qt_plugin_path for libopenshot, which can be imported in
        # different directories from the .exe, causing the plugins (i.e. svg) to not load in some cases.
        ("QT_PLUGIN_PATH",
         "*=QT_PLUGIN_PATH",
         "[TARGETDIR]",
         "OpenShot"
         )
    ]

    # Create custom action table
    # TODO: Revisit this idea, to force the environment variables to be updated after the installer runs.
    # ImageMagick needs an environment variable or it will crash. Forcing a reboot is currently the only
    # option I can get to work correctly.
    # custom_action = [
    #     ("SetVar",
    #      "242",
    #      "[SystemFolder]setx.exe",
    #      "OSVE 1")
    # ]

    # Install an action into the MSI install sequence (schedule a reboot)
    execute_sequence = [
        ("ScheduleReboot",
         "NOT REMOVE",
         "8000")
    ]

    # Now create the table dictionary
    msi_data = {"Environment": environment_table, "InstallExecuteSequence" : execute_sequence, "InstallUISequence" : execute_sequence}

    # Change some default MSI options and specify the use of the above defined tables
    bdist_msi_options = {"data": msi_data}
    build_options["bdist_msi"] = bdist_msi_options

elif sys.platform == "linux":
    # Find all related SO files
    for filename in find_files("/usr/local/lib/", ["*openshot*.so*"]):
        if "python" not in filename:
            external_so_files.append((filename, filename.replace("/usr/local/lib/", "")))

    # Append Linux ICON file
    iconFile += ".svg"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

    # Shorten name (since RPM can't have spaces)
    info.PRODUCT_NAME = "openshot-qt"

    # Get a list of all openshot.so dependencies
    import subprocess
    p = subprocess.Popen(["ldd", "/usr/local/lib/libopenshot.so"], stdout=subprocess.PIPE)
    out, err = p.communicate()
    depends = str(out).replace("\\t","").replace("\\n","\n").replace("\'","").split("\n")
    for line in depends:
        lineparts = line.split("=>")
        libname = lineparts[0].strip()
        if len(lineparts) > 1:
            libdetails = lineparts[1].strip()
            libdetailsparts = libdetails.split("(")
            if len(libdetailsparts) > 1:
                libpath = libdetailsparts[0].strip()
                if libpath:
                    filepath, filename = os.path.split(libpath)
                    external_so_files.append((libpath, filename))


elif sys.platform == "darwin":
    # Copy Mac specific files that cx_Freeze misses
    # ImageMagick files
    for filename in find_files("/usr/local/Cellar/imagemagick/6.8.9-5/lib/ImageMagick/", ["*"]):
        external_so_files.append((filename, filename.replace("/usr/local/Cellar/imagemagick/6.8.9-5/lib/", "")))
    for filename in find_files("/usr/local/Cellar/imagemagick/6.8.9-5/etc/ImageMagick-6/", ["*"]):
        external_so_files.append((filename, filename.replace("/usr/local/Cellar/imagemagick/6.8.9-5/etc/ImageMagick-6/",
                                                             "ImageMagick/etc/configuration/")))
    # SVG executables
    for filename in find_files("/Users/jonathan/apps/rsvg/", ["*"]):
        external_so_files.append((filename, filename.replace("/Users/jonathan/apps/rsvg/", "")))

    # JPEG library
    for filename in find_files("/usr/local/Cellar/jpeg/8d/lib", ["libjpeg.8.dylib"]):
        external_so_files.append((filename, filename.replace("/usr/local/Cellar/jpeg/8d/lib/", "")))

    # Copy openshot.py Python bindings
    src_files.append(("/usr/local/lib/python3.3/site-packages/openshot.py", "openshot.py"))
    src_files.append((os.path.join(PATH, "installer", "launch-mac.sh"), "launch-mac.sh"))

    # Append Mac ICON file
    iconFile += ".hqx"
    src_files.append((os.path.join(PATH, "xdg", iconFile), iconFile))

# Append all source files
for filename in find_files("openshot_qt", ["*"]):
    src_files.append((filename, filename.replace("openshot_qt/", "").replace("openshot_qt\\", "")))

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options["packages"] = ["os", "sys", "PyQt5", "openshot", "time", "uuid", "shutil", "threading", "subprocess",
                                 "re", "math", "subprocess", "xml", "urllib", "webbrowser", json_library]
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
                              shortcutName="%s %s" % (info.PRODUCT_NAME, info.VERSION),
                              shortcutDir="ProgramMenuFolder")])


# Remove temporary folder (if SRC folder present)
if os.path.exists(os.path.join(PATH, "src")):
    rmtree(os.path.join(PATH, "openshot_qt"))