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

from PyQt5.QtCore import QDir

VERSION = "2.4.3-dev3"
MINIMUM_LIBOPENSHOT_VERSION = "0.2.2"
DATE = "20180922000000"
NAME = "openshot-qt"
PRODUCT_NAME = "OpenShot Video Editor"
GPL_VERSION = "3"
DESCRIPTION = "Create and edit stunning videos, movies, and animations"
COMPANY_NAME = "OpenShot Studios, LLC"
COPYRIGHT = "Copyright (c) 2008-2018 %s" % COMPANY_NAME
CWD = os.getcwd()
PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # Primary openshot folder
HOME_PATH = os.path.join(os.path.expanduser("~"))
USER_PATH = os.path.join(HOME_PATH, ".openshot_qt")
BACKUP_PATH = os.path.join(USER_PATH, "backup")
BLENDER_PATH = os.path.join(USER_PATH, "blender")
ASSETS_PATH = os.path.join(USER_PATH, "assets")
THUMBNAIL_PATH = os.path.join(USER_PATH, "thumbnail")
CACHE_PATH = os.path.join(USER_PATH, "cache")
PREVIEW_CACHE_PATH = os.path.join(USER_PATH, "preview-cache")
TITLE_PATH = os.path.join(USER_PATH, "title")
PROFILES_PATH = os.path.join(PATH, "profiles")
IMAGES_PATH = os.path.join(PATH, "images")
TRANSITIONS_PATH = os.path.join(USER_PATH, "transitions")
EXPORT_PRESETS_PATH = os.path.join(PATH, "presets")
EXPORT_TESTS = os.path.join(USER_PATH, "tests")
USER_PROFILES_PATH = os.path.join(USER_PATH, "profiles")
USER_PRESETS_PATH = os.path.join(USER_PATH, "presets")

# Create PATHS if they do not exist (this is where temp files are stored... such as cached thumbnails)
for folder in [USER_PATH, THUMBNAIL_PATH, CACHE_PATH, BLENDER_PATH, ASSETS_PATH, TITLE_PATH, PROFILES_PATH, IMAGES_PATH,
               TRANSITIONS_PATH, EXPORT_TESTS, BACKUP_PATH, USER_PROFILES_PATH, USER_PRESETS_PATH, PREVIEW_CACHE_PATH]:
    if not os.path.exists(folder.encode("UTF-8")):
        os.makedirs(folder, exist_ok=True)

# names of all contributors, using "u" for unicode encoding
JT = {"name": u"Jonathan Thomas", "email": "jonathan@openshot.org", "website":"http://openshot.org/developers/jonathan"}

# Languages
CMDLINE_LANGUAGE = None
CURRENT_LANGUAGE = 'en_US'
SUPPORTED_LANGUAGES = ['en_US']

try:
    from language import openshot_lang
    language_path=":/locale/"
except ImportError:
    language_path=os.path.join(PATH, 'language')
    print("Compiled translation resources missing!")
    print("Loading translations from: {}".format(language_path))

# Compile language list from :/locale resource
langdir = QDir(language_path)
langs = langdir.entryList(['OpenShot.*.qm'], QDir.NoDotAndDotDot|QDir.Files,
                          sort=QDir.Name)
for trpath in langs:
    SUPPORTED_LANGUAGES.append(trpath.split('.')[1])

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
    website_lang = "www"
    if CURRENT_LANGUAGE == "zh_CN":
        website_lang = "zh-hans"
    elif CURRENT_LANGUAGE == "zh_TW":
        website_lang = "zh-hant"
    elif CURRENT_LANGUAGE != "en_US":
        website_lang = CURRENT_LANGUAGE
    return website_lang
