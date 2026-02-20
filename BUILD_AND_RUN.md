# Commands to build and run OpenShot (Zenvi)

Run these from the repo root: `/home/sanjina/project/core`

---

## 1. Activate venv (optional; scripts can use `.venv/bin` directly)

```bash
source .venv/bin/activate
```

---

## 2. Create venv and install Python requirements

**If you don’t have a venv yet:**

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

**If you already have a venv** (only upgrade pip and install deps):

```bash
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

**Alternative (system PyQt5 + libopenshot, no pip Qt):** use `requirements-noqt.txt` and install system Qt first:

```bash
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtsvg python3-pyqt5.qtopengl
.venv/bin/pip uninstall -y PyQt5 PyQtWebEngine PyQt5-Qt5 PyQt5-sip PyQtWebEngine-Qt5 2>/dev/null || true
.venv/bin/pip install -r requirements-noqt.txt
```

---

## 3. Install libopenshot (required to run)

The app supports **libopenshot 0.3.2 or newer**. **0.5.0+** is preferred when available.

**Option A – Stable PPA (often 0.3.x):**

```bash
sudo add-apt-repository ppa:openshot.developers/ppa
sudo apt update
sudo apt install libopenshot-audio-dev libopenshot-dev python3-openshot
```

**Option B – Daily PPA (libopenshot 0.5.0+, for supported Ubuntu versions / architectures):**

```bash
sudo add-apt-repository ppa:openshot.developers/libopenshot-daily
sudo apt update
sudo apt install libopenshot-audio-dev libopenshot-dev python3-openshot
```

If you see “version 0.5.0 is required, but 0.3.2 was detected”, either switch to the daily PPA (Option B) or pull the latest app code (minimum was lowered to 0.3.2 so it runs with the stable PPA).

---

## 4. Verify setup

```bash
.venv/bin/python3 scripts/check_setup.py
```

---

## 5. Run the app

```bash
./run.sh
```

Or directly:

```bash
.venv/bin/python3 src/launch.py
```

**Headless / no display:**

```bash
OPENSHOT_HEADLESS=1 ./run.sh
# or
./run-with-xvfb.sh
```

---

## Optional: Manim (educational video agent)

```bash
sudo apt-get install -y libcairo2-dev libpango1.0-dev pkg-config ffmpeg
.venv/bin/pip install -r requirements-manim.txt
```

---

## Summary

| What              | Command |
|-------------------|--------|
| Create venv       | `python3 -m venv --system-site-packages .venv` |
| Upgrade pip       | `.venv/bin/pip install --upgrade pip` |
| Install deps      | `.venv/bin/pip install -r requirements.txt` |
| Install libopenshot | `sudo apt install libopenshot-audio-dev libopenshot-dev python3-openshot` (after PPA) |
| Check setup       | `.venv/bin/python3 scripts/check_setup.py` |
| Run               | `./run.sh` |
