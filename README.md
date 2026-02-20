# Flowcut

Flowcut is an award-winning free and open-source video editor 
for Linux, Mac, and Windows, and is dedicated to delivering high quality 
video editing and animation solutions to the world.

## Build Status

[![openshot-qt CI Build](https://github.com/OpenShot/openshot-qt/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenShot/openshot-qt/actions/workflows/ci.yml) 
[![libopenshot CI Build](https://github.com/OpenShot/libopenshot/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenShot/libopenshot/actions/workflows/ci.yml) 
[![libopenshot-audio CI Build](https://github.com/OpenShot/libopenshot-audio/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenShot/libopenshot-audio/actions/workflows/ci.yml)
![Discord](https://img.shields.io/discord/1143390791507644496?style=flat)

## Features

* Cross-platform (Linux, Mac, and Windows)
* Support for many video, audio, and image formats (based on FFmpeg)
* Powerful curve-based Key frame animations
* Desktop integration (drag and drop support)
* Unlimited tracks / layers
* Clip resizing, scaling, trimming, snapping, rotation, and cutting
* Video transitions with real-time previews
* Compositing, image overlays, watermarks
* Title templates, title creation, sub-titles
* 2D animation support (image sequences)
* 3D animated titles (and effects)
* SVG friendly, to create and include vector titles and credits
* Scrolling motion picture credits
* Advanced Timeline (including Drag & drop, scrolling, panning, zooming, and snapping)
* Frame accuracy (step through each frame of video)
* Time-mapping and speed changes on clips (slow/fast, forward/backward, etc...)
* Audio mixing and editing
* Digital video effects, including brightness, gamma, hue, greyscale, chroma key, and many more!
* Experimental hardware encoding and decoding (VA-API, NVDEC, D3D9, D3D11, VTB)
* Import & Export widely supported formats (EDL, XML)
* Render videos in many codecs and formats (based on FFmpeg)

## Getting Started

The quickest way to get started using Flowcut is to download one of 
our pre-built installers. On our download page, click the **Daily Builds** 
button to view the latest, experimental builds, which are created for each 
new commit to this repo.

https://flowcut.app/download/

## Tutorial

Watch the official [step-by-step video tutorial](https://www.youtube.com/watch?list=PLymupH2aoNQNezYzv2lhSwvoyZgLp1Q0T&v=1k-ISfd-YBE), or read the official [user-guide](https://www.openshot.org/user-guide/):

## Developers

Are you interested in becoming more involved in the development of 
Flowcut? Build exciting new features, fix bugs, make friends, and become a hero! 
Please read the [step-by-step](https://github.com/OpenShot/openshot-qt/wiki/Become-a-Developer) 
instructions for getting source code, configuring dependencies, and building Flowcut.

## Documentation

Beautiful HTML documentation can be generated using Sphinx.

```sh
cd doc
make html
```

The documentation for the most recent release can be viewed online at [openshot.org/user-guide](https://www.openshot.org/user-guide/).

## Report a bug

Please report bugs using the official [Report a Bug](https://flowcut.app/support/) 
feature on our website. This walks you through the bug reporting process, and helps 
to create a high-quality bug report for the Flowcut community.

Or you can report a new issue directly on GitHub:

https://github.com/OpenShot/openshot-qt/issues

## Translations

Translating OpenShot into other languages is very easy! Please read the [step-by-step](https://github.com/OpenShot/openshot-qt/wiki/Become-a-Translator) instructions or login to LaunchPad and get started.
All you need is a web browser.

* Application Translations: https://translations.launchpad.net/openshot/2.0/+translations
* Website Translations: https://translations.launchpad.net/openshot/website/+pots/django

## Dependencies

Although installers are much easier to use, if you must build from 
source, here are some tips: 

OpenShot is programmed in Python (version 3+), and thus does not need
to be compiled to run. However, be sure you have the following 
dependencies in order to run OpenShot successfully: 

*  Python 3.0+ (http://www.python.org)
*  PyQt5 (http://www.riverbankcomputing.co.uk/software/pyqt/download5)
*  libopenshot: OpenShot Library (https://github.com/OpenShot/libopenshot)
*  libopenshot-audio: OpenShot Audio Library (https://github.com/OpenShot/libopenshot-audio)
*  FFmpeg or Libav (http://www.ffmpeg.org/ or http://libav.org/)
*  GCC build tools (or MinGW on Windows)

## Launch

To run OpenShot from the command line with an installed `libopenshot`,
use the following syntax:
(be sure the change the path to match the install or repo location 
of openshot-qt)

```sh
cd [openshot-qt folder]
python3 src/launch.py
```
    
To run with a version of `libopenshot` built from source but not installed,
set `PYTHONPATH` to the location of the compiled Python bindings. e.g.:

```sh
cd [libopenshot folder]
cmake -B build -S . [options]
cmake --build build
    
cd [openshot-qt folder]
PYTHONPATH=[libopenshot folder]/build/bindings/python \
python3 src/launch.py
```

## Websites

- https://www.openshot.org/  (Official website and blog)
- https://github.com/OpenShot/openshot-qt (source code and issue tracker)
- https://github.com/OpenShot/libopenshot-audio (source code for audio library)
- https://github.com/OpenShot/libopenshot (source code for video library)
- https://launchpad.net/openshot/

### Copyright & License

Copyright (c) 2008-2022 OpenShot Studios, LLC. This file is part of
OpenShot Video Editor (https://www.openshot.org), an open-source project
dedicated to delivering high quality video editing and animation solutions
to the world.

OpenShot Video Editor is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

OpenShot Video Editor is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
