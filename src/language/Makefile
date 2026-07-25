ALL: openshot_lang.py

PYTHON ?= python3
PYRCC ?= pyrcc5

TRANSLATIONS:=$(shell /usr/bin/find ./ -type f -iname \*.qm -newer openshot_lang.py)

openshot_lang.py: openshot_lang.qrc $(TRANSLATIONS)
	$(PYRCC) openshot_lang.qrc -o $@
	$(PYTHON) neutralize_resource_import.py $@
