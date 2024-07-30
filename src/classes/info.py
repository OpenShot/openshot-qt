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

VERSION = "3.2.1-dev"
MINIMUM_LIBOPENSHOT_VERSION = "0.3.3"
DATE = "20240709000000"
NAME = "openshot-qt"
PRODUCT_NAME = "OpenShot Video Editor"
GPL_VERSION = "3"
DESCRIPTION = "Create and edit stunning videos, films, and animations with an " \
              "easy-to-use interface and rich set of features."
COMPANY_NAME = "OpenShot Studios, LLC"
COPYRIGHT = "(c) 2008-{} {}".format(strftime("%Y"), COMPANY_NAME)
CWD = os.getcwd()

# Application paths
PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
RESOURCES_PATH = os.path.join(PATH, "resources")
PROFILES_PATH = os.path.join(PATH, "profiles")
IMAGES_PATH = os.path.join(PATH, "images")
EXPORT_PRESETS_PATH = os.path.join(PATH, "presets")

# User paths
HOME_PATH = os.path.join(os.path.expanduser("~"))
USER_PATH = os.path.join(HOME_PATH, ".openshot_qt")
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
USER_DEFAULT_PROJECT = os.path.join(USER_PATH, "default.osp")
LEGACY_DEFAULT_PROJECT = USER_DEFAULT_PROJECT.replace(".osp", ".project")

# Back up "default" values for user paths
_path_defaults = {
    k: v for k, v in locals().items()
    if k.endswith("_PATH")
    and v.startswith(USER_PATH)
}

try:
    from PyQt5.QtCore import QSize

    # UI Thumbnail settings
    LIST_ICON_SIZE = QSize(100, 65)
    LIST_GRID_SIZE = LIST_ICON_SIZE + QSize(5, 25)
    TREE_ICON_SIZE = QSize(75, 49)
    EMOJI_ICON_SIZE = QSize(75, 75)
    EMOJI_GRID_SIZE = EMOJI_ICON_SIZE + QSize(5, 25)
except ImportError:
    # Fail gracefully if we're running without PyQt5 (e.g. CI tasks)
    print("Failed to import `PyQt5.QtCore.QSize` (ignoring exception)")

# Maintainer details, for packaging
JT = {"name": "Jonathan Thomas",
      "email": "jonathan@openshot.org",
      "website": "http://openshot.org/developers/jonathan"}

# Desktop launcher ID, for Linux
DESKTOP_ID = "org.openshot.OpenShot.desktop"

# Blender minimum version required (a string value)
BLENDER_MIN_VERSION = "4.1"

# Data-model debugging enabler
MODEL_TEST = False

# Default/initial logging levels
LOG_LEVEL_FILE = 'INFO'
LOG_LEVEL_CONSOLE = 'INFO'

# Web backend selection, overridable at launch
WEB_BACKEND = 'auto'

# Sentry.io error & transaction reporting rate (0.0 TO 1.0)
# 0.0 = no error reporting to Sentry
# 0.5 = 1/2 of errors reported to Sentry
# 1.0 = all errors reporting to Sentry
#    ERROR: Exceptions sent to Sentry
#    TRANS: Transactions sent to Sentry
#    STABLE: If this version matches the current version (reported on openshot.org)
#    UNSTABLE: If this version does not match the current version (reported on openshot.org)
#    STABLE_VERSION: This is the current stable release reported by openshot.org
ERROR_REPORT_RATE_STABLE = 0.0
ERROR_REPORT_RATE_UNSTABLE = 0.0
TRANS_REPORT_RATE_STABLE = 0.0
TRANS_REPORT_RATE_UNSTABLE = 0.0
ERROR_REPORT_STABLE_VERSION = None

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
    print(f"Loading translations from: {language_path}")

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
    print("Failed to import `PyQt5.QtCore.QDir` (ignoring exception)")

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

def setup_userdirs():
    """Create user paths if they do not exist (this is where
    temp files are stored... such as cached thumbnails)"""
    for folder in _path_defaults.values():
        if not os.path.exists(os.fsencode(folder)):
            os.makedirs(folder, exist_ok=True)

    # Migrate USER_DEFAULT_PROJECT from former name
    if all([
        os.path.exists(LEGACY_DEFAULT_PROJECT),
        not os.path.exists(USER_DEFAULT_PROJECT),
    ]):
        print("Migrating default project file to new name")
        os.rename(LEGACY_DEFAULT_PROJECT, USER_DEFAULT_PROJECT)


def reset_userdirs():
    """Reset all info.FOO_PATH attributes back to their initial values,
    as they may have been modified by the runtime code (retargeting
    info.THUMBNAIL_PATH to a project assets directory, for example)"""
    for k, v in _path_defaults.items():
        globals()[k] = v


def get_default_path(varname):
    """Return the default value of the named info.FOO_PATH attribute,
    even if it's been modified"""
    return _path_defaults.get(varname, None)


def website_language():
    """Get the current website language code for URLs"""
    return {
        "zh_CN": "zh-hans/",
        "zh_TW": "zh-hant/",
        "en_US": ""}.get(CURRENT_LANGUAGE,
                         "%s/" % CURRENT_LANGUAGE.split("_")[0].lower())

