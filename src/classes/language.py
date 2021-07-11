"""
 @file
 @brief This file loads the current language based on the computer's locale settings
 @author Noah Figg <eggmunkee@hotmail.com>
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
import locale

from PyQt5.QtCore import QLocale, QLibraryInfo, QTranslator, QCoreApplication

from classes.logger import log
from classes import info

try:
    from language import openshot_lang  # noqa
    language_path = ":/locale/"
    log.debug("Using compiled translation resources")
except ImportError:
    language_path = os.path.join(info.PATH, 'language')
    log.debug("Loading translations from: {}".format(language_path))


def init_language():
    """ Find the current locale, and install the correct translators """

    # Get app instance
    app = QCoreApplication.instance()

    # Setup of our list of translators and paths
    translator_types = (
        {"type": 'QT',
         "prefix": 'qt_',        # Older versions of Qt use this file (built-in translations)
         "path": QLibraryInfo.location(QLibraryInfo.TranslationsPath)},
        {"type": 'QT',
         "prefix": 'qtbase_',    # Newer versions of Qt use this file (built-in translations)
         "path": QLibraryInfo.location(QLibraryInfo.TranslationsPath)},
        {"type": 'QT',
         "prefix": 'qt_',
         "path": os.path.join(info.PATH, 'language')}, # Optional path where we package QT translations
        {"type": 'QT',
         "prefix": 'qtbase_',
         "path": os.path.join(info.PATH, 'language')}, # Optional path where we package QT translations
        {"type": 'OpenShot',
         "prefix": 'OpenShot_',  # Our custom translations
         "path": language_path},
    )

    # Determine the environment locale, or default to system locale name
    locale_names = [os.environ.get('LANG', QLocale().system().name()),
                    os.environ.get('LOCALE', QLocale().system().name())
                    ]

    # Get the user's configured language preference
    settings = app.get_settings()
    if settings:
        preference_lang = settings.get('default-language')
    else:
        preference_lang = "Default"

    # Output all languages detected from various sources
    log.info("Qt Detected Languages: {}".format(QLocale().system().uiLanguages()))
    log.info("LANG Environment Variable: {}".format(os.environ.get('LANG', "")))
    log.info("LOCALE Environment Variable: {}".format(os.environ.get('LOCALE', "")))
    log.info("OpenShot Preference Language: {}".format(preference_lang))

    # Check if the language preference is something other than "Default"
    if preference_lang == "en_US":
        # Override language list with en_US, don't add to it
        locale_names = [ "en_US" ]
    elif preference_lang != "Default":
        # Prepend preference setting to list
        locale_names.insert(0, preference_lang)

    # If the user has used the --lang command line arg, override with that
    # (We've already checked that it's in SUPPORTED_LANGUAGES)
    if info.CMDLINE_LANGUAGE:
        locale_names = [ info.CMDLINE_LANGUAGE ]
        log.info("Language overridden on command line, using: {}".format(info.CMDLINE_LANGUAGE))

    # Default the locale to C, for number formatting
    locale.setlocale(locale.LC_ALL, 'C')

    # Loop through environment variables
    found_language = False
    for locale_name in locale_names:

        # Go through each translator and try to add for current locale
        for type in translator_types:
            trans = QTranslator(app)
            if find_language_match(type["prefix"], type["path"], trans, locale_name):
                # Install translation
                app.installTranslator(trans)
                found_language = True

        # Exit if found language for type: "OpenShot"
        if found_language:
            log.debug("Exiting translation system (since we successfully loaded: {})".format(locale_name))
            info.CURRENT_LANGUAGE = locale_name
            break


# Try the full locale and base locale trying to find a valid path
#  returns True when a match was found.
#  pattern - a string expected to have one pipe to be filled by locale strings
#  path - base path for file (pattern may contain more path)
#
def find_language_match(prefix, path, translator, locale_name):
    """ Match all combinations of locale, language, and country """

    filename = prefix + locale_name
    log.debug('Attempting to load {} in \'{}\''.format(filename,path))
    success = translator.load(filename, path)
    if success:
        log.debug('Successfully loaded {} in \'{}\''.format(filename, path))
    return success


def get_all_languages():
    """Get all language names and countries packaged with OpenShot"""

    # Loop through all supported language locale codes
    all_languages = []
    for locale_name in info.SUPPORTED_LANGUAGES:
        try:
            native_lang_name = QLocale(locale_name).nativeLanguageName().title()
            country_name = QLocale(locale_name).nativeCountryName().title()
            all_languages.append((locale_name, native_lang_name, country_name))
        except Exception:
            log.debug('Failed to parse language for %s', locale_name)

    # Return list
    return all_languages


def get_current_locale():
    return info.CURRENT_LANGUAGE
