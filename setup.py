""" 
 @file
 @brief Setup script to install OpenShot (on Linux and without any dependencies such as libopenshot)
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

import glob
import os
import sys
import subprocess
from distutils.core import setup

from src.classes.logger import log
from src.classes import info

log.info("Execution path: %s" % os.path.abspath(__file__))

# Boolean: running as root?
ROOT = os.geteuid() == 0
# For Debian packaging it could be a fakeroot so reset flag to prevent execution of
# system update services for Mime and Desktop registrations.
# The debian/openshot.postinst script must do those.
if not os.getenv("FAKEROOTKEY") == None:
    log.info("NOTICE: Detected execution in a FakeRoot so disabling calls to system update services.")
    ROOT = False

os_files = [
    # XDG application description
    ('share/applications', ['xdg/openshot.desktop']),
    # XDG application icon
    ('share/pixmaps', ['xdg/openshot.svg']),
    # XDG desktop mime types cache
    ('share/mime/packages', ['xdg/openshot.xml']),
    # launcher (mime.types)
    ('lib/mime/packages', ['xdg/openshot']),
    # man-page ("man 1 openshot")
    ('share/man/man1', ['doc/openshot.1']),
    ('share/man/man1', ['doc/openshot-render.1']),
]

# Add all the translations
locale_files = []
for filepath in glob.glob("src/locale/*/LC_MESSAGES/*"):
    filepath = filepath.replace('src/', '')
    locale_files.append(filepath)


# Call the main Distutils setup command
# -------------------------------------
dist = setup(
    scripts=['bin/openshot', 'bin/openshot-render'],
    packages=['src', 'src.classes', 'src.images', 'src.locale', 'src.settings', 'src.timeline', 'src.windows',
              'src.windows.ui'],
    package_data={
        'src': ['presets/*', 'images/*', 'locale/OpenShot/*', 'locale/README', 'profiles/*',
                'transitions/icons/medium/*.png', 'transitions/icons/small/*.png', 'transitions/*.pgm',
                'transitions/*.png', 'transitions/*.svg', 'effects/icons/medium/*.png', 'effects/icons/small/*.png',
                'effects/*.xml', 'blender/blend/*.blend', 'blender/icons/*.png', 'blender/earth/*.jpg',
                'blender/scripts/*.py', 'blender/*.xml'] + locale_files,
        'src.windows': ['ui/*.ui'],
    },
    data_files=os_files,
    **info.SETUP
)
# -------------------------------------


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
    sys.stdout.write("\nRun OpenShot by typing 'openshot' or through the Applications menu.")
    sys.stdout.write("\n-----------------------------------------------\n")
