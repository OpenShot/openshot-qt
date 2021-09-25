ALL: ../src/classes/openshot_rc.py

DUMMY: list-outdated

ICONS:=$(shell /usr/bin/find . -type f -name \*.svg -newer ../src/classes/openshot_rc.py)
ICONS+=$(shell /usr/bin/find . -type f -name \*.png -newer ../src/classes/openshot_rc.py)

../src/classes/openshot_rc.py: openshot.qrc $(ICONS)
	pyrcc5 openshot.qrc -o $@

list-outdated:
	@echo $(ICONS)
