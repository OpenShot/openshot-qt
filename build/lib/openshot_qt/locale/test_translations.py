"""
 @file
 @brief This file verifies all translations are correctly formatted and have the correct # of string replacements
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
import re
import sys
from PyQt5.QtCore import QLocale, QLibraryInfo, QTranslator, QCoreApplication


# Get the absolute path of this project
locale_path = os.path.dirname(os.path.abspath(__file__))

# Get app instance
app = QCoreApplication(sys.argv)

# Load POT template (all English strings)
POT_source = open(os.path.join(locale_path, 'OpenShot', 'OpenShot.pot')).read()
all_strings = re.findall('^msgid \"(.*)\"', POT_source, re.MULTILINE)

# Loop through folders/languages
for language_code in os.listdir(locale_path):
    folder_path = os.path.join(locale_path, language_code)
    if language_code not in ['OpenShot', 'QT'] and os.path.isdir(folder_path):
        # Install language
        translator = QTranslator(app)
        app.installTranslator(translator)

        # Load translation
        formatted_locale_name = '%s/LC_MESSAGES/OpenShot' % (language_code)
        success = translator.load(formatted_locale_name, locale_path)
        print('%s\t%s' % (success, formatted_locale_name))

        # Loop through all test strings
        for source_string in all_strings:
            if "%s" in source_string or "%s(" in source_string or "%d" in source_string:
                translated_string = app.translate("", source_string)
                if source_string.count('%') != translated_string.count('%'):
                    print('  Invalid string replacement found: %s  (source: %s)' % (translated_string, source_string))

        # Remove translator
        app.removeTranslator(translator)
