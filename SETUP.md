# Flowcut – Setup

This repo is **Flowcut** (Python 3, PyQt5). Follow these steps to set up and run it.

## 1. Python venv and pip dependencies

From the repo root. Use `--system-site-packages` so the venv can see system-installed `python3-openshot` after you install it via apt:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

### Optional: Manim (educational video agent)

The AI assistant can generate Manim educational videos. Manim is optional; the app runs without it (the Manim agent will report that it is not installed). To enable it:

**Ubuntu/Debian** – install system libraries and then the Python package:

```bash
sudo apt-get install -y libcairo2-dev libpango1.0-dev pkg-config ffmpeg
.venv/bin/pip install -r requirements-manim.txt
```

See `requirements-manim.txt` for details.

## 2. libopenshot (required to run the app)

The app and tests require the `openshot` Python module (libopenshot). It is not on PyPI; install it via your system.

### Ubuntu / Debian (recommended)

Add the OpenShot PPA and install:

**Stable (recommended):**
```bash
sudo add-apt-repository ppa:openshot.developers/ppa
sudo apt update
sudo apt install libopenshot-audio-dev libopenshot-dev python3-openshot
```

**Daily/development builds:**
```bash
sudo add-apt-repository ppa:openshot.developers/libopenshot-daily
sudo apt update
sudo apt install libopenshot-audio-dev libopenshot-dev python3-openshot
```

Then use a venv that can see system site-packages so the venv finds `openshot`:

```bash
# Recreate venv with system site-packages (run from repo root)
rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

**Use system PyQt5 with system libopenshot** to avoid ABI mismatch (undefined symbol / version Qt_5). Install system Qt packages and do **not** install PyQt5 from pip:

```bash
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtsvg python3-pyqt5.qtopengl
# If you already installed PyQt5 from pip in the venv, uninstall it:
.venv/bin/pip uninstall -y PyQt5 PyQtWebEngine PyQt5-Qt5 PyQt5-sip PyQtWebEngine-Qt5
# Then install only non-Qt deps in venv:
.venv/bin/pip install -r requirements-noqt.txt
```

### Other systems

Build and install libopenshot and libopenshot-audio from source, then set `PYTHONPATH` to the compiled Python bindings when running (see main [README.md](README.md)).

## 3. Check setup

Verify openshot and PyQt5: `.venv/bin/python3 scripts/check_setup.py`

## 4. Run OpenShot

From the repo root:

```bash
./run.sh
```

Or directly:

```bash
.venv/bin/python3 src/launch.py
```

If you see a Qt “could not load the Qt platform plugin” error, you need a display (X11 or Wayland). For headless/CI:

```bash
./run-with-xvfb.sh
# or
OPENSHOT_HEADLESS=1 ./run.sh
```


## 5. Run tests (CI-style)

Tests also require libopenshot and Qt:

```bash
.venv/bin/python3 src/tests/query_tests.py -platform minimal
```

## Summary

| Step              | Done in this setup |
|-------------------|--------------------|
| `requirements.txt`| ✅ Created          |
| `.venv` + pip deps| ✅ Installed        |
| libopenshot       | ❌ Install via PPA or build from source (see above) |
| Run GUI           | ✅ Use `./run.sh` after libopenshot is installed and display is available (Flowcut) |
