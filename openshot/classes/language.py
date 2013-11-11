

from PyQt5.QtCore import QLocale, QLibraryInfo, QTranslator
import os

def init_language(app):
	#Get global app instance
	#Setup of our list of translators and paths
	translator_types = (
		{"type":'QT',
		 "pattern":'qt_%s',
		 "path":QLibraryInfo.location(QLibraryInfo.TranslationsPath)},
		#{"type":'OpenShot1',
		# "pattern":os.path.join('qt_locale','openshot.%s.qm'),
		# "path":''},
		{"type":'OpenShot',
		 "pattern":os.path.join('locale','%s','LC_MESSAGES','openshot.qm'),
		 "path":''},
		 )
	
	#Determine the environment locale, or default to system locale name
	locale_name = os.environ.get('LOCALE', QLocale().system().name())

	for type in translator_types:
		trans = QTranslator(app)
		if not find_language_match(type["pattern"], type["path"], trans, locale_name):
			print (type["type"] + " translations failed to load")
		else:
			#app.removeTranslator(trans)
			#print(trans)
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
		print ('Attempting to load', formatted_name, path)
		success = translator.load(formatted_name, path)
		i -= 1
		
	return success
	