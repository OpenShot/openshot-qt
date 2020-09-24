"""
 @file
 @brief Setup script to install OpenShot (on Linux and without any dependencies such as libopenshot)
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

import os
import sys
import fnmatch
import subprocess
from setuptools import setup
from shutil import copytree, rmtree, copy


# Determine absolute PATH of OpenShot folder
PATH = os.path.dirname(os.path.realpath(__file__))  # Primary openshot folder

# Make a copy of the src tree (temporary for naming reasons only)
if os.path.exists(os.path.join(PATH, "src")):
    print("Copying modules to openshot_qt directory: %s" % os.path.join(PATH, "openshot_qt"))
    # Only make a copy if the SRC directory is present (otherwise ignore this)
    copytree(os.path.join(PATH, "src"), os.path.join(PATH, "openshot_qt"))

if os.path.exists(os.path.join(PATH, "openshot_qt")):
    # Append path to system path
    sys.path.append(os.path.join(PATH, "openshot_qt"))
    print("Loaded modules from openshot_qt directory: %s" % os.path.join(PATH, "openshot_qt"))


from classes import info
from classes.logger import log

log.info("Execution path: %s" % os.path.abspath(__file__))

# Boolean: running as root?
ROOT = os.geteuid() == 0
# For Debian packaging it could be a fakeroot so reset flag to prevent execution of
# system update services for Mime and Desktop registrations.
# The debian/openshot.postinst script must do those.
if os.getenv("FAKEROOTKEY") is not None:
    log.info("NOTICE: Detected execution in a FakeRoot so disabling calls to system update services.")
    ROOT = False

os_files = [
    # XDG application description
    ('share/applications', ['xdg/org.openshot.OpenShot.desktop']),
    # AppStream metadata
    ('share/metainfo', ['xdg/org.openshot.OpenShot.appdata.xml']),
    # Debian menu system application icon
    ('share/pixmaps', ['xdg/openshot-qt.svg']),
    # XDG Freedesktop icon paths
    ('share/icons/hicolor/scalable/apps', ['xdg/openshot-qt.svg']),
    ('share/icons/hicolor/scalable/mimetypes', ['xdg/openshot-qt-doc.svg']),
    ('share/icons/hicolor/64x64/apps', ['xdg/icon/64/openshot-qt.png']),
    ('share/icons/hicolor/128x128/apps', ['xdg/icon/128/openshot-qt.png']),
    ('share/icons/hicolor/256x256/apps', ['xdg/icon/256/openshot-qt.png']),
    ('share/icons/hicolor/512x512/apps', ['xdg/icon/512/openshot-qt.png']),
    # XDG desktop mime types cache
    ('share/mime/packages', ['xdg/org.openshot.OpenShot.xml']),
    # launcher (mime.types)
    ('lib/mime/packages', ['xdg/openshot-qt']),
]

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


package_data = {}

# Find all project files
src_files = []
for filename in find_files(os.path.join(PATH, "openshot_qt"), ["*"]):
    src_files.append(filename.replace(os.path.join(PATH, "openshot_qt"), ""))
package_data["openshot_qt"] = src_files

# Call the main Distutils setup command
# -------------------------------------
dist = setup(
    packages=[('openshot_qt')],
    package_data=package_data,
    data_files=os_files,
    include_package_data=True,
    **info.SETUP
)
# -------------------------------------

# Remove temporary folder (if SRC folder present)
if os.path.exists(os.path.join(PATH, "src")):
    rmtree(os.path.join(PATH, "openshot_qt"), True)

FAILED = 'Failed to update.\n'

if ROOT and dist != None:
    # update the XDG Shared MIME-Info database cache
    try:
        sys.stdout.write('Updating the Shared MIME-Info database cache.\n')
        subprocess.call(["update-mime-database", os.path.join(sys.prefix, "share/mime/")])
    except:
        sys.stderr.write(FAILED)

    # update the mime.types database
    try:
        sys.stdout.write('Updating the mime.types database\n')
        subprocess.call("update-mime")
    except:
        sys.stderr.write(FAILED)

    # update the XDG .desktop file database
    try:
        sys.stdout.write('Updating the .desktop file database.\n')
        subprocess.call(["update-desktop-database"])
    except:
        sys.stderr.write(FAILED)
    sys.stdout.write("\n-----------------------------------------------")
    sys.stdout.write("\nInstallation Finished!")
    sys.stdout.write("\nRun OpenShot by typing 'openshot-qt' or through the Applications menu.")
    sys.stdout.write("\n-----------------------------------------------\n")
