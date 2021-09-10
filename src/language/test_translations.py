#!/usr/bin/python3
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
import fnmatch
import sys
from PyQt5.QtCore import QLocale, QLibraryInfo, QTranslator, QCoreApplication


# Get the absolute path of this project
language_path = os.path.dirname(os.path.abspath(__file__))

# Color for errors
red='\033[31m'
endc='\033[0m'

found_errors = False

# Get app instance
app = QCoreApplication(sys.argv)

# Load POT template (all English strings)
all_templates = ['OpenShot.pot', 'OpenShot_transitions.pot', 'OpenShot_blender.pot']
for template_name in all_templates:
    POT_source = open(os.path.join(language_path, 'OpenShot', template_name)).read()
    all_strings = re.findall('^msgid \"(.*)\"', POT_source, re.MULTILINE)

    print("Testing {} strings in {}...".format(len(all_strings), template_name))

    # Loop through folders/languages
    for filename in fnmatch.filter(os.listdir(language_path), 'OpenShot*.qm'):
        lang_code = filename[:-3]
        # Install language
        translator = QTranslator(app)
        app.installTranslator(translator)

        # Load translation
        success = translator.load(lang_code, language_path)
        if not success:
            print(red, '%s-%s' % (success, lang_code), endc)

        # Loop through all test strings
        for source_string in all_strings:
            if "%s" in source_string or "%s(" in source_string or "%d" in source_string:
                translated_string = app.translate("", source_string)
                if source_string.count('%') != translated_string.count('%'):
                    found_errors = True
                    print(red, '\tInvalid string replacement found: "%s" vs "%s" [%s]' %
                          (translated_string, source_string, lang_code), endc)

        # Remove translator
        app.removeTranslator(translator)

if found_errors:
    raise(Exception("Errors detected during translation testing! See above."))
