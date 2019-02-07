## Getting Started

OpenShot Video Editor is an award-winning free and open-source video 
editor for Linux, Mac, and Windows. The quickest way to get started
using OpenShot is to download one of our pre-built **installers**:

https://www.openshot.org/download/

**Tip:** On our download page, click the **Daily Builds** button to view 
the latest, experimental builds, which are created for each new commit 
to this repo.

## Tutorial

Watch the official [step-by-step tutorial](https://www.youtube.com/watch?list=PLymupH2aoNQNezYzv2lhSwvoyZgLp1Q0T&v=1k-ISfd-YBE) video, or read the official [user-guide](https://www.openshot.org/user-guide/).

## Developers

Are you interested in getting more involved in the development of 
OpenShot? Build exciting new features, fix bugs, and become a hero! [Learn More](https://github.com/OpenShot/openshot-qt/wiki/Become-a-Developer)

## Documentation

Beautiful HTML documentation can be generated using Sphinx.

```
cd doc
make html
```

## Dependencies

Although installers are much easier to use, if you must build from 
source, here are some tips: 

OpenShot 2.x is programmed in Python, and thus does not need
to be compiled to run.  However, be sure you have the following 
dependencies in order to run OpenShot successfully: 

1) Python 3.0+ (http://www.python.org)
2) PyQt5 (http://www.riverbankcomputing.co.uk/software/pyqt/download5)
3) libopenshot: OpenShot Library (http://www.openshot.org)
4) FFmpeg or Libav (http://www.ffmpeg.org/ or http://libav.org/)
5) GCC build tools (or MinGW on Windows)

To run OpenShot from the command line, use the following syntax:
(be sure the change the path to match the install location of OpenShot)

    $ cd /home/USER/openshot_qt
    $ python3 src/launch.py

## How to install

If you would like to install OpenShot, use this command:

    $ sudo python3 setup.py install

Installing OpenShot using this command does a few extra things that
the build wizard doesn't do.  It adds MIME Types, adds an icon to your
Application menu, registers icons, adds a /usr/bin/openshot command, and
copies all the code files to the /site-packages/ folder.

## Websites

- http://www.openshot.org/  (Official website and blog)
- https://github.com/OpenShot/openshot-qt (source code and issue tracker)
- https://github.com/OpenShot/libopenshot-audio (source code for audio library)
- https://github.com/OpenShot/libopenshot (source code for video library)
- http://launchpad.net/openshot/

## Report a bug

Please report bugs using the official [Report a Bug](https://www.openshot.org/issues/new/) 
feature on our website. This is a step-by-step guide on creating a high-quality
bug report for the OpenShot community.

## Translations

https://translations.launchpad.net/openshot

## Ask a question  

You can ask any question you have here https://github.com/OpenShot/openshot-qt/issues.

## Contributing

If you would like to help reporting issues or commit fixes to the project please see our [contributor guidelines](CONTRIBUTING.md).


## Copyright

Copyright (c) 2008-2018 OpenShot Studios, LLC
(http://www.openshotstudios.com). This file is part of
OpenShot Video Editor (http://www.openshot.org), an open-source project
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
