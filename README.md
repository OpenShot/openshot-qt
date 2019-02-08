OpenShot Video Editor is an award-winning free and open-source video editor 
for Linux, Mac, and Windows, and is dedicated to delivering high quality 
video editing and animation solutions to the world.

## Build Status

[![Build Status](https://travis-ci.org/OpenShot/openshot-qt.svg?branch=develop)](https://travis-ci.org/OpenShot/openshot-qt)

## Getting Started

The quickest way to get started using OpenShot is to download one of 
our pre-built installers. On our download page, click the **Daily Builds** 
button to view the latest, experimental builds, which are created for each 
new commit to this repo.

https://www.openshot.org/download/

## Tutorial

Watch the official [step-by-step video tutorial](https://www.youtube.com/watch?list=PLymupH2aoNQNezYzv2lhSwvoyZgLp1Q0T&v=1k-ISfd-YBE), or read the official [user-guide](https://www.openshot.org/user-guide/):

## Developers

Are you interested in becoming more involved in the development of 
OpenShot? Build exciting new features, fix bugs, make friends, and become a hero! 
Please read the [step-by-step](https://github.com/OpenShot/openshot-qt/wiki/Become-a-Developer) 
instructions for getting source code, configuring dependencies, and building OpenShot.

## Documentation

Beautiful HTML documentation can be generated using Sphinx.

```
cd doc
make html
```

## Report a bug

Please report bugs using the official [Report a Bug](https://www.openshot.org/issues/new/) 
feature on our website. This walks you through the bug reporting process, and helps 
to create a high-quality bug report for the OpenShot community.

Or you can report a new issue directly on GitHub:

https://github.com/OpenShot/openshot-qt/issues

## Translations

Translating OpenShot into other languages is very easy! Please read the [step-by-step](https://github.com/OpenShot/openshot-qt/wiki/Become-a-Translator) instructions or login to LaunchPad and get started.
All you need is a web browser.

https://translations.launchpad.net/openshot/2.0/+translations

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

To run OpenShot from the command line, use the following syntax:
(be sure the change the path to match the install or repo location 
of openshot-qt)

    $ cd [openshot-qt folder]
    $ python3 src/launch.py

## Websites

- https://www.openshot.org/  (Official website and blog)
- https://github.com/OpenShot/openshot-qt (source code and issue tracker)
- https://github.com/OpenShot/libopenshot-audio (source code for audio library)
- https://github.com/OpenShot/libopenshot (source code for video library)
- https://launchpad.net/openshot/

## Copyright

Copyright (c) 2008-2019 OpenShot Studios, LLC. This file is part of
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
