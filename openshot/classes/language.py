#!/usr/bin/env python
#	OpenShot Video Editor is a program that creates, modifies, and edits video files.
#   Copyright (C) 2009  Jonathan Thomas, TJ
#
#	This file is part of OpenShot Video Editor (http://launchpad.net/openshot/).
#
#	OpenShot Video Editor is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	OpenShot Video Editor is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with OpenShot Video Editor.  If not, see <http://www.gnu.org/licenses/>.

import os
from PyQt5.QtCore import QLocale, QLibraryInfo, QTranslator
from classes.logger import logger

def init_language(app):
	#Setup of our list of translators and paths
	translator_types = (
		{"type":'QT',
		 "pattern":'qt_%s',
		 "path":QLibraryInfo.location(QLibraryInfo.TranslationsPath)},
		{"type":'OpenShot',
		 "pattern":os.path.join('%s','LC_MESSAGES','openshot'),
		 "path":'locale'},
		 )
	
	#Determine the environment locale, or default to system locale name
	locale_name = os.environ.get('LOCALE', QLocale().system().name())
	
	#Don't try on default locale, since it fails to load what is the default language
	if locale_name == 'en_US':
		return

	#Go through each translator and try to add for current locale
	for type in translator_types:
		trans = QTranslator(app)
		if not find_language_match(type["pattern"], type["path"], trans, locale_name):
			logger.warn(type["type"] + " translations failed to load")
		else:
			app.installTranslator(trans)

# Try the full locale and base locale trying to find a valid path
#  returns True when a match was found.
#  pattern - a string expected to have one pipe to be filled by locale strings
#  path - base path for file (pattern may contain more path)
#  
def find_language_match(pattern, path, translator, locale_name):
	success = False
	locale_parts = locale_name.split('_')
	
	i = len(locale_parts)
	while not success and i > 0:
		formatted_name = pattern % "_".join(locale_parts[:i])
		logger.info('Attempting to load %s in \'%s\'' % (formatted_name, path))
		success = translator.load(formatted_name, path)
		i -= 1
		
	return success
	