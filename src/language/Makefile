ALL: openshot_lang.py

TRANSLATIONS:=$(shell /usr/bin/find ./ -type f -iname \*.qm -newer openshot_lang.py)

openshot_lang.py: openshot_lang.qrc $(TRANSLATIONS)
	pyrcc5 openshot_lang.qrc -o $@
