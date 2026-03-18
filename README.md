# Zenvi

**Local-first, AI-native video editor.** Zenvi runs 99% of operations on your own machine — your footage never leaves your computer. Built-in AI agents handle tedious editing tasks while you stay in creative control.

[![Zenvi Release](https://github.com/Zenvi-pro/zenvi-core/actions/workflows/release.yml/badge.svg)](https://github.com/Zenvi-pro/zenvi-core/actions/workflows/release.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)]()

---

## What is Zenvi?

Zenvi is a free, open-source video editor for **Linux**, **macOS** (Intel & Apple Silicon), and **Windows**. It combines a full-featured non-linear editing timeline with AI-powered tools that can organize your media, generate voiceovers, create educational animations, and more — all running locally on your hardware.

### Why Zenvi?

- **Local-first** — Your footage, your compute, your privacy. No cloud uploads required.
- **AI-native** — Built-in agents for media tagging, voice/music generation, face detection, and natural-language search — powered by your choice of LLM (OpenAI, Anthropic Claude, Ollama local models).
- **Cross-platform** — Single codebase, native installers for all three desktop OSes.
- **Open source** — GPLv3. Fork it, extend it, ship it.

---

## Features

### Core Editing
- Unlimited tracks and layers
- Clip resizing, scaling, trimming, snapping, rotation, and cutting
- Frame-accurate stepping through video
- Time-mapping and speed changes (slow/fast, forward/backward)
- Powerful curve-based keyframe animations (linear, Bezier, constant)
- Video transitions with real-time previews
- Audio mixing, waveforms, and editing
- Compositing, image overlays, and watermarks
- Title templates, subtitles, and scrolling credits
- Import & export EDL and Final Cut Pro XML

### AI Tools
- **AI Chat** — Describe what you want; the agent executes edits
- **AI Media Manager** — Automatic tagging, search, and organization of assets
- **AI Voice & Music** — Generate voiceovers and background tracks
- **AI Manim** — Create animated educational videos from text prompts
- **Face Detection** — Automatic face tracking and management
- **Natural-language search** — Find clips by describing their content
- **Multi-LLM support** — OpenAI, Anthropic Claude, Google, Ollama (local), AWS

### Media & Rendering
- Supports most video, audio, and image formats (FFmpeg-based)
- 70+ export profiles including YouTube HD, 4K, and social media presets
- Hardware-accelerated encoding/decoding (VA-API, NVDEC, D3D9, D3D11, VideoToolbox)
- 3D animated titles and effects via Blender 5.0+
- SVG vector titles and credits
- 2D animation and rotoscoping (image sequences)

---

## Download

Grab the latest installer for your platform:

| Platform | Format | Architecture |
|----------|--------|--------------|
| **Linux** | `.AppImage`, `.deb` | x86_64 |
| **macOS** | `.dmg` | Intel (x86_64), Apple Silicon (arm64) |
| **Windows** | `.exe` installer | x86_64 |

**[Download the latest release](https://github.com/Zenvi-pro/zenvi-core/releases/latest)**

Or visit [zenvi.org/download](https://zenvi.org/download/) for more options.

---

## Build from Source

### Requirements

- **Python 3.11+**
- **PyQt5** >= 5.15
- **libopenshot** >= 0.5.0 ([build instructions](https://github.com/OpenShot/libopenshot))
- **FFmpeg**
- GCC / Clang / MSVC build tools

### Quick Start

```bash
# Clone
git clone https://github.com/Zenvi-pro/zenvi-core.git
cd zenvi-core

# Install Python dependencies
pip install -r requirements.txt

# Run directly (development)
python3 src/launch.py

# Or freeze into a standalone app
python3 freeze.py build
```

### Platform-specific builds

<details>
<summary><strong>Linux (AppImage)</strong></summary>

```bash
# Install system dependencies (Ubuntu/Debian)
sudo add-apt-repository -y ppa:openshot.developers/libopenshot-daily
sudo apt-get update
sudo apt-get install -y \
  libopenshot-audio-dev libopenshot-dev python3-openshot \
  python3-pyqt5 python3-pyqt5.qtsvg python3-pyqt5.qtwebengine \
  python3-zmq libfuse2

# Freeze
python3 freeze.py build

# Build AppImage
wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
  -O appimagetool && chmod +x appimagetool
# Follow the AppDir structure in .github/workflows/release.yml
```
</details>

<details>
<summary><strong>macOS (DMG)</strong></summary>

```bash
pip3 install -r requirements.txt pyobjc-framework-Cocoa
python3 freeze.py build
bash installer/build-mac-dmg.sh
# Output: build/Zenvi-v<VERSION>-<ARCH>.dmg
```

Requires macOS 10.15 (Catalina) or later. Builds for both Intel and Apple Silicon.
</details>

<details>
<summary><strong>Windows (Installer)</strong></summary>

```powershell
# From MSYS2/MinGW or standard Python
pip install -r requirements.txt
python freeze.py build

# Requires Inno Setup 6
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" `
  /DVERSION=1.0.34 `
  installer/windows-installer.iss
```
</details>

### Using a local libopenshot build

If you built `libopenshot` from source but didn't install it system-wide:

```bash
cd zenvi-core
PYTHONPATH=/path/to/libopenshot/build/bindings/python python3 src/launch.py
```

---

## Project Structure

```
zenvi-core/
  src/
    classes/         # Core application logic, AI tools, settings
    launch.py        # Application entry point
  installer/         # Platform-specific packaging (DMG, Inno Setup, entitlements)
  xdg/               # Linux desktop integration (icons, .desktop, MIME types)
  freeze.py          # cx_Freeze packaging script
  .github/workflows/ # CI/CD (release builds for all platforms)
```

### Project File Format

- **`.zvn`** — Zenvi project files (current)
- **`.osp`** — OpenShot legacy projects (imported automatically)

---

## AI Configuration

Zenvi's AI features work with multiple LLM providers. Configure your preferred provider in the app settings:

| Provider | Local? | Setup |
|----------|--------|-------|
| **Ollama** | Yes | Install [Ollama](https://ollama.ai), pull a model, done |
| **OpenAI** | No | Add your API key in settings |
| **Anthropic Claude** | No | Add your API key in settings |
| **Google** | No | Add your API key in settings |

For fully offline AI editing, use Ollama with a local model — no internet connection needed.

---

## Contributing

We welcome contributions. To get started:

1. Fork this repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes and test locally
4. Submit a pull request against `develop`

### Generate Documentation

```bash
cd doc
make html
```

---

## Report a Bug

- **GitHub Issues**: [zenvi-core/issues](https://github.com/Zenvi-pro/zenvi-core/issues)
- **Website**: [zenvi.org/support](https://zenvi.org/support/)

---

## License

Copyright (c) 2008-2026 Zenvi & contributors.

Zenvi is free software: you can redistribute it and/or modify it under the terms of the [GNU General Public License v3](https://www.gnu.org/licenses/gpl-3.0.html) as published by the Free Software Foundation.

Zenvi builds on the foundation of [OpenShot Video Editor](https://www.openshot.org/) and the [libopenshot](https://github.com/OpenShot/libopenshot) library. We are grateful to the OpenShot community for their work.

---

## Links

- [zenvi.org](https://zenvi.org/) — Official website
- [zenvi.org/community](https://zenvi.org/community/) — Community & support
- [GitHub: Zenvi-pro](https://github.com/Zenvi-pro) — Organization
- [libopenshot](https://github.com/OpenShot/libopenshot) — Video engine
- [libopenshot-audio](https://github.com/OpenShot/libopenshot-audio) — Audio engine
