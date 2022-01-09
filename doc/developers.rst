.. Copyright (c) 2008-2016 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

.. OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

.. OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

.. You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.

Developers
==========

If you are a programmer (or want to become a programmer), and are interested in
developing new features, fixing bugs, or improving the user interface for OpenShot,
the following sections will explain how to get started and get involved!

The Big Picture
---------------
OpenShot Video Editor has 3 main components, a Python & PyQt user interface
(:openshot-github:`openshot-qt`), a C++ audio library
(:openshot-github:`libopenshot-audio`) and a C++ video library
(:openshot-github:`libopenshot`). If you are not familiar with Python,
PyQt, or C++, those would be great topics to research and learn more about at this point.

However, many bugs can be fixed and new features added with only Python knowledge, since the C++
components are not involved in the user interface at all. Python is an amazing language, and
is super fun to learn, and is the only prerequisite skill needed to become an OpenShot
developer!

.. warning::

    The instructions that follow are for Ubuntu Linux,
    which is the easiest environment to configure for OpenShot development.
    If you are using another OS,
    I suggest running a virtual machine with Ubuntu LTS before continuing any further.

    If you must use a Windows or Mac system for development,
    start by referring to the build notes in the ``libopenshot`` wiki.
    Building the library with all of its dependencies is the most challenging part of the process.
    
    * :libopenshot-wiki:`Windows Build Instructions <Windows-Build-Instructions>`
    * :libopenshot-wiki:`Mac Build Instructions <Mac-Build-Instructions>`

Getting the Latest Source Code
------------------------------
Before we can fix any bugs or add any features, we need to get the source code onto your
computer.

Use git to clone our 3 repositories:

.. code-block:: bash

   git clone https://github.com/OpenShot/libopenshot-audio.git
   git clone https://github.com/OpenShot/libopenshot.git
   git clone https://github.com/OpenShot/openshot-qt.git

Configuring your Development Environment
-----------------------------------------
In order to actually compile or run OpenShot, we need to install some dependencies on your system. The
easiest way to accomplish this is with our `Daily PPA <https://www.openshot.org/ppa/>`_. A PPA is an
unofficial Ubuntu repository, which has our software packages available to download and install.

.. code-block:: bash

   sudo add-apt-repository ppa:openshot.developers/libopenshot-daily
   sudo apt-get update
   sudo apt-get install openshot-qt \
                        cmake \
                        libx11-dev \
                        libasound2-dev \
                        libavcodec-dev \
                        libavdevice-dev \
                        libavfilter-dev \
                        libavformat-dev \
                        libavresample-dev \
                        libavutil-dev \
                        libfdk-aac-dev \
                        libfreetype6-dev \
                        libjsoncpp-dev \
                        libmagick++-dev \
                        libopenshot-audio-dev \
                        libswscale-dev \
                        libunittest++-dev \
                        libxcursor-dev \
                        libxinerama-dev \
                        libxrandr-dev \
                        libzmq3-dev \
                        pkg-config \
                        python3-dev \
                        qtbase5-dev \
                        libqt5svg5-dev \
                        libxcb-xfixes0-dev \
                        qtmultimedia5-dev \
                        swig

At this point, you should have all 3 OpenShot components source code cloned into local folders, the OpenShot
daily PPA installed, and all of the required development and runtime dependencies installed. This is a
great start, and we are now ready to start compiling some code!

libopenshot-audio (Build Instructions)
--------------------------------------
This library is required for audio playback and audio effects.
It is based on the JUCE audio framework.
Here are the commands to build it:

.. code-block:: bash

   cd libopenshot-audio
   mkdir build
   cd build
   cmake -DCMAKE_INSTALL_PREFIX=dist ..
   make
   make install

Essentially, we are switching to the ``libopenshot-audio/build`` folder,
then running ``cmake ..`` on the parent folder.
This finds dependencies and creates all the needed Makefiles used to compile this library.
Then ``make`` uses those Makefiles to compile this library,
and ``make install`` installs them in the location we specified.
If ``CMAKE_INSTALL_PREFIX`` isn't set, the files will install to ``/usr/local/`` (by default) and ``make install`` will require administrative privileges to run.

libopenshot (Build Instructions)
--------------------------------
This library is required for video decoding, encoding, animation, and just about everything else.
It does all the heavy lifting of video editing and video playback.
Here are the commands to build it:

.. code-block:: bash

   cd libopenshot
   mkdir build
   cd build
   cmake -DLIBOPENSHOT_AUDIO_DIR=../../libopenshot-audio/build/dist ..
   make

Essentially, we are switching to the ``libopenshot/build`` folder,
then running ``cmake ..`` on the parent folder.
This finds dependencies and creates all the needed Makefiles used to compile this library.
Then ``make`` uses those Makefiles to compile this library.
Because we provided the location of our compiled ``libopenshot-audio`` installation,
that version of the library will be used instead of the system version (if any).

We don't install our ``libopenshot`` after building, because we don't need to.
For testing purposes, we can tell OpenShot to use ``libopenshot`` right from our ``build`` directory.

openshot-qt (Launch Instructions)
---------------------------------
This is our main PyQt Python application.
Because it is written in Python, it does not require any compiling to run.
To launch OpenShot from the source code with our newly-built
``libopenshot-audio`` and ``libopenshot`` libraries, use the following commands:

.. code-block:: bash

   cd openshot-qt
   PYTHONPATH=../libopenshot/build/src/bindings/python
   python3 src/launch.py

This should launch the OpenShot user interface.
Any changes you have made to the source code files
(``*.py`` Python files, ``*.ui`` PyQt UI files, etc...) will be included.
This requires the ``libopenshot-audio`` and ``libopenshot`` libraries,
and if anything went wrong with the steps above, OpenShot will likely not launch.

If OpenShot launches at this point, congratulations!
You now have a working local version of OpenShot, which is running off your local source code.
Try making some changes to the source code and re-launch OpenShot...
you should now see your changes!

GitHub Issues
-------------
Now that you have successfully compiled and launched OpenShot Video Editor,
be sure to check out our list of bug reports on GitHub: `OpenShot Issues`_.
Also, feel free to send me an email:
`jonathan@openshot.org <mailto:jonathan@openshot.org>`_ and introduce yourself!
I'm always here to help if you have any questions.

Share your Changes
------------------
Once you have fixed a bug or added an amazing new feature, be sure to share it with the OpenShot team.
Ideally, we can merge this into our main source code branch.
The easiest way to share your changes is by creating a fork of our repo,
pushing your changes back to GitHub, and creating a `Pull Request`_.
A Pull Request lets the OpenShot team know you have changes ready to be merged.
Then we can review things, give feedback, and hopefully merge your changes into the main branch.

.. _Pull Request: https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests
.. _OpenShot Issues: https://github.com/OpenShot/openshot-qt/issues/
