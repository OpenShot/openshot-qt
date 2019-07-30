ALL: openshot_rc.py
 
ICONS:=$(shell /usr/bin/find Humanity/ -type f -newer openshot_rc.py)
ICONS+=$(shell /usr/bin/find . -name \*-icon.png -newer openshot_rc.py)
ICONS+=AboutLogo.png openshot.svg
ICONS+=$(shell /usr/bin/find . -type f -name hw-accel\*.svg -newer openshot_rc.py)

openshot_rc.py: openshot.qrc $(ICONS)
	pyrcc5 openshot.qrc -o $@
