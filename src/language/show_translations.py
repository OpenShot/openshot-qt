#!/usr/bin/python3
"""
 @file
 @brief Display all available string translations for each translation file
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Frank Dana <ferdnyc AT gmail com>

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

# Get app instance
app = QCoreApplication(sys.argv)

# Load POT template (all English strings)
all_templates = ['OpenShot.pot', 'OpenShot_transitions.pot', 'OpenShot_blender.pot']
for template_name in all_templates:
    POT_source = open(os.path.join(language_path, 'OpenShot', template_name)).read()
    all_strings = re.findall('^msgid \"(.*)\"', POT_source, re.MULTILINE)

    print("Scanning {} strings in all translation files...".format(len(all_strings)))

    # Loop through folders/languages
    for filename in fnmatch.filter(os.listdir(language_path), 'OpenShot*.qm'):
        lang_code = filename[:-3]
        # Install language
        translator = QTranslator(app)

        # Load translation
        if translator.load(lang_code, language_path):
            app.installTranslator(translator)

            print("\n=================================================")
            print("Showing translations for {}".format(filename))
            print("=================================================")
            # Loop through all test strings
            for source_string in all_strings:
                translated_string = app.translate("", source_string)
                if source_string != translated_string:
                    print('  {} => {}'.format(source_string,translated_string))

                if "%s" in source_string or "%s(" in source_string or "%d" in source_string:
                    if source_string.count('%') != translated_string.count('%'):
                        raise(Exception('Invalid string replacement found: "%s" vs "%s" [%s]' %
                              (translated_string, source_string, lang_code)))

            # Remove translator
            app.removeTranslator(translator)
