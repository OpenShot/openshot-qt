#!/usr/bin/env python3
"""Check OpenShot setup: openshot module, PyQt5, and display. Exit 0 if ready to run."""
import sys
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SRC = os.path.join(REPO_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

def main():
    ok = True

    # 1. openshot (libopenshot)
    try:
        import openshot
        print("openshot: OK ({})".format(getattr(openshot, "__file__", "?")))
    except ImportError as e:
        print("openshot: MISSING (install libopenshot / python3-openshot; see SETUP.md)")
        ok = False

    # 2. PyQt5 (must come from system when using system libopenshot to avoid ABI mismatch)
    try:
        from PyQt5.QtCore import QCoreApplication
        from PyQt5 import QtWebEngineWidgets  # noqa
        print("PyQt5: OK")
    except ImportError as e:
        print("PyQt5: MISSING ({})".format(e))
        ok = False
    except OSError as e:
        err = str(e)
        if "undefined symbol" in err or "version " in err:
            print("PyQt5: ABI mismatch – venv's pip PyQt5 conflicts with system Qt.")
            print("  Fix: uninstall venv PyQt5 and use system: .venv/bin/pip uninstall -y PyQt5 PyQtWebEngine PyQt5-Qt5 PyQt5-sip PyQtWebEngine-Qt5")
            print("  Then: sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine")
        else:
            print("PyQt5: LOAD ERROR ({})".format(err))
        ok = False

    # 3. Display
    display = os.environ.get("DISPLAY", "")
    if display:
        print("DISPLAY: {} (GUI should work)".format(display))
    else:
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            print("DISPLAY: none (QT_QPA_PLATFORM=offscreen; headless)")
        else:
            print("DISPLAY: not set (use xvfb-run or set DISPLAY / QT_QPA_PLATFORM=offscreen)")

    if ok:
        print("Setup OK. Run: ./run.sh or OPENSHOT_HEADLESS=1 ./run.sh")
        return 0
    print("Fix the missing items above, then run ./run.sh")
    return 1

if __name__ == "__main__":
    sys.exit(main())
