ALL: ../src/classes/openshot_rc.py

PYTHON ?= python3
PYRCC ?= pyrcc5
 
ICONS:=$(shell /usr/bin/find Humanity/ -type f -newer ../src/classes/openshot_rc.py)
ICONS+=$(shell /usr/bin/find actions/ -type f -newer ../src/classes/openshot_rc.py)
ICONS+=$(shell /usr/bin/find . -name \*-icon.svg -newer ../src/classes/openshot_rc.py)
ICONS+=$(shell /usr/bin/find . -name cursor\*.png -newer ../src/classes/openshot_rc.py)
ICONS+=$(shell /usr/bin/find . -name keyframe\*.png -newer ../src/classes/openshot_rc.py)
ICONS+=about-wordmark.svg openshot.svg
ICONS+=$(shell /usr/bin/find . -type f -name hw-accel\*.svg -newer ../src/classes/openshot_rc.py)

../src/classes/openshot_rc.py: openshot.qrc $(ICONS)
	$(PYRCC) openshot.qrc -o $@
	$(PYTHON) ../src/language/neutralize_resource_import.py $@
