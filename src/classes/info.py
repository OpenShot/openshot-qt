"""
 @file
 @brief This file contains the current version number of OpenShot, along with other global settings.
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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
from time import strftime

from PyQt5.QtCore import QCoreApplication, QStandardPaths
import shutil

VERSION = "2.5.1-dev3"
MINIMUM_LIBOPENSHOT_VERSION = "0.2.5"
DATE = "20200228000000"
NAME = "openshot-qt"
PRODUCT_NAME = "OpenShot Video Editor"
GPL_VERSION = "3"
DESCRIPTION = "Create and edit stunning videos, movies, and animations"
COMPANY_NAME = "OpenShot Studios, LLC"
COPYRIGHT = "Copyright (c) 2008-{} {}".format(strftime("%Y"), COMPANY_NAME)
CWD = os.getcwd()

QCoreApplication.setApplicationName(NAME)

# Application paths
PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
RESOURCES_PATH = os.path.join(PATH, "resources")
PROFILES_PATH = os.path.join(PATH, "profiles")
IMAGES_PATH = os.path.join(PATH, "images")
EXPORT_PRESETS_PATH = os.path.join(PATH, "presets")
HOME_PATH = QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
OLD_USER_PATH = os.path.join(HOME_PATH, ".openshot_qt")
USER_PATH = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)

sentry_file = os.path.join(OLD_USER_PATH, ".settingsMigrated")
if (os.path.exists(OLD_USER_PATH) and not os.path.exists(sentry_file)):
    try:
        # Make sure we have write permission, first
        os.makedirs(USER_PATH, exist_ok=True)
        shutil.copytree(
            OLD_USER_PATH,
            USER_PATH,
            dirs_exist_ok=True,
            ignore_dangling_symlinks=True)
        os.mknod(sentry_file)
    except (PermissionError, FileNotFoundError) as ex:
        ERROR_MIGRATING_CONFIGS = ex

# User paths
BACKUP_PATH = os.path.join(USER_PATH)
RECOVERY_PATH = os.path.join(USER_PATH, "recovery")
THUMBNAIL_PATH = os.path.join(USER_PATH, "thumbnail")
CACHE_PATH = os.path.join(USER_PATH, "cache")
BLENDER_PATH = os.path.join(USER_PATH, "blender")
TITLE_PATH = os.path.join(USER_PATH, "title")
TRANSITIONS_PATH = os.path.join(USER_PATH, "transitions")
EMOJIS_PATH = os.path.join(USER_PATH, "emojis")
PREVIEW_CACHE_PATH = os.path.join(USER_PATH, "preview-cache")
USER_PROFILES_PATH = os.path.join(USER_PATH, "profiles")
USER_PRESETS_PATH = os.path.join(USER_PATH, "presets")
USER_TITLES_PATH = os.path.join(USER_PATH, "title_templates")
PROTOBUF_DATA_PATH = os.path.join(USER_PATH, "protobuf_data")
YOLO_PATH = os.path.join(USER_PATH, "yolo")
# User files
BACKUP_FILE = os.path.join(BACKUP_PATH, "backup.osp")
USER_DEFAULT_PROJECT = os.path.join(USER_PATH, "default.project")

# Create user paths if they do not exist
# (this is where temp files are stored... such as cached thumbnails)
for folder in [
    USER_PATH, BACKUP_PATH, RECOVERY_PATH, THUMBNAIL_PATH, CACHE_PATH,
    BLENDER_PATH, TITLE_PATH, TRANSITIONS_PATH, PREVIEW_CACHE_PATH,
    USER_PROFILES_PATH, USER_PRESETS_PATH, USER_TITLES_PATH, EMOJIS_PATH,
    PROTOBUF_DATA_PATH, YOLO_PATH ]:
    if not os.path.exists(os.fsencode(folder)):
        os.makedirs(folder, exist_ok=True)

# Maintainer details, for packaging
JT = {"name": "Jonathan Thomas",
      "email": "jonathan@openshot.org",
      "website": "http://openshot.org/developers/jonathan"}

# Desktop launcher ID, for Linux
DESKTOP_ID = "org.openshot.OpenShot.desktop"

# Blender minimum version required (a string value)
BLENDER_MIN_VERSION = "2.80"

# Data-model debugging enabler
MODEL_TEST = False

# Default/initial logging levels
LOG_LEVEL_FILE = 'INFO'
LOG_LEVEL_CONSOLE = 'INFO'

# Web backend selection, overridable at launch
WEB_BACKEND = 'auto'

# Languages
CMDLINE_LANGUAGE = None
CURRENT_LANGUAGE = 'en_US'
SUPPORTED_LANGUAGES = ['en_US']

try:
    from language import openshot_lang
    language_path = ":/locale/"
except ImportError:
    language_path = os.path.join(PATH, 'language')
    print("Compiled translation resources missing!")
    print("Loading translations from: {}".format(language_path))

# Compile language list from :/locale resource
try:
    from PyQt5.QtCore import QDir
    langdir = QDir(language_path)
    trpaths = langdir.entryList(
        ['OpenShot_*.qm'],
        QDir.NoDotAndDotDot | QDir.Files,
        sort=QDir.Name)
    for trpath in trpaths:
        # Extract everything between "Openshot_" and ".qm"
        lang=trpath[trpath.find('_')+1:-3]
        SUPPORTED_LANGUAGES.append(lang)
except ImportError:
    # Fail gracefully if we're running without PyQt5 (e.g. CI tasks)
    pass

SETUP = {
    "name": NAME,
    "version": VERSION,
    "author": JT["name"] + " and others",
    "author_email": JT["email"],
    "maintainer": JT["name"],
    "maintainer_email": JT["email"],
    "url": "http://www.openshot.org/",
    "license": "GNU GPL v." + GPL_VERSION,
    "description": DESCRIPTION,
    "long_description": "Create and edit videos and movies\n"
                        " OpenShot Video Editor is a free, open-source, non-linear video editor. It\n"
                        " can create and edit videos and movies using many popular video, audio, \n"
                        " image formats.  Create videos for YouTube, Flickr, Vimeo, Metacafe, iPod,\n"
                        " Xbox, and many more common formats!\n"
                        ".\n"
                        " Features include:\n"
                        "  * Multiple tracks (layers)\n"
                        "  * Compositing, image overlays, and watermarks\n"
                        "  * Support for image sequences (rotoscoping)\n"
                        "  * Key-frame animation\n  * Video and audio effects (chroma-key)\n"
                        "  * Transitions (lumas and masks)\n"
                        "  * 3D animation (titles and simulations)\n"
                        "  * Upload videos (YouTube and Vimeo supported)",

    # see http://pypi.python.org/pypi?%3Aaction=list_classifiers
    "classifiers": [
                       "Development Status :: 5 - Production/Stable",
                       "Environment :: X11 Applications",
                       "Environment :: X11 Applications :: GTK",
                       "Intended Audience :: End Users/Desktop",
                       "License :: OSI Approved :: GNU General Public License (GPL)",
                       "Operating System :: OS Independent",
                       "Operating System :: POSIX :: Linux",
                       "Programming Language :: Python",
                       "Topic :: Artistic Software",
                       "Topic :: Multimedia :: Video :: Non-Linear Editor", ] +
                   ["Natural Language :: " + language for language in SUPPORTED_LANGUAGES],

    # Automatic launch script creation
    "entry_points": {
        "gui_scripts": [
            "openshot-qt = openshot_qt.launch:main"
        ]
    }
}

def website_language():
    """Get the current website language code for URLs"""
    return {
        "zh_CN": "zh-hans/",
        "zh_TW": "zh-hant/",
        "en_US": ""}.get(CURRENT_LANGUAGE,
                         "%s/" % CURRENT_LANGUAGE.split("_")[0].lower())
