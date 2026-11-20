.. Copyright (c) 2008-2026 OpenShot Studios, LLC
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
OpenShot Video Editor has 3 main components, a Python and Qt user interface
(:openshot-github:`openshot-qt`), a C++ audio library
(:openshot-github:`libopenshot-audio`) and a C++ video library
(:openshot-github:`libopenshot`). If you are not familiar with Python,
Qt, or C++, those would be great topics to research and learn more about at this point.

Many interface changes need only Python. Video processing, effects, text rendering, and playback also use the
C++ libraries, so changes to those features may require work in more than one repository.

In ``openshot-qt``, window and dialog code is under ``src/windows``, shared application logic is under
``src/classes``, and tests are under ``src/tests``. Import Qt classes through ``qt_api`` rather than directly
from PyQt or PySide, so changes work with all supported bindings.

The examples below use Ubuntu 24.04 LTS with Qt5/PyQt5. For platform-specific dependencies and build options, see:

* :libopenshot-wiki:`Linux Build Instructions <Linux-Build-Instructions>`
* :libopenshot-wiki:`Windows Build Instructions <Windows-Build-Instructions>`
* :libopenshot-wiki:`Mac Build Instructions <Mac-Build-Instructions>`

Getting the Latest Source Code
------------------------------
Before we can fix any bugs or add any features, we need to get the source code onto your
computer.

Clone the ``develop`` branch of each repository into the same parent directory:

.. code-block:: bash

   git clone --branch develop https://github.com/OpenShot/libopenshot-audio.git
   git clone --branch develop https://github.com/OpenShot/libopenshot.git
   git clone --branch develop https://github.com/OpenShot/openshot-qt.git

Configuring your Development Environment
-----------------------------------------
Install the compiler, native-library dependencies, and Python runtime packages. The following is a Qt5 starting
point, including Wayland screen-capture dependencies. Package requirements for supported Ubuntu releases are maintained
in the `OpenShot packaging repository <https://git.launchpad.net/openshot-packaging/tree/>`_
under each component's ``debian/control`` and ``debian/rules``. Automated build examples are also available in
the source repositories' ``.github/workflows`` and ``.gitlab-ci.yml`` files.

.. code-block:: bash

   sudo apt update
   sudo apt install build-essential cmake pkg-config swig catch2 zlib1g-dev \
       libasound2-dev libx11-dev libxcursor-dev libxinerama-dev libxrandr-dev \
       libavcodec-dev libavdevice-dev libavfilter-dev libavformat-dev \
       libavutil-dev libswscale-dev libswresample-dev \
       libbabl-dev libopencv-dev libprotobuf-dev protobuf-compiler libjsoncpp-dev \
       libmagick++-dev libglib2.0-dev libpipewire-0.3-dev libspa-0.2-dev \
       qtbase5-dev libqt5svg5-dev qtmultimedia5-dev \
       python3-dev python3-pyqt5 python3-pyqt5.qtsvg python3-pyqt5.qtopengl \
       python3-xdg python3-requests python3-distro python3-defusedxml python3-dbus-next \
       python3-sentry-sdk qttranslations5-l10n

This source-build recipe does not need Debian package-building tools such as ``debhelper`` or ``dh-python``,
or the packaged OpenShot libraries: the following steps build those libraries from source. Optional FFmpeg encoders
depend on how FFmpeg itself was built; installing an encoder's development package does not enable it in an
already-built FFmpeg library.

OpenShot supports PyQt5, PyQt6, and PySide6. libopenshot must be built
against the correct Qt version for the binding you are using
(Qt5: PyQt5, Qt6: PyQt6 or PySide6).
Select the Python binding with ``OPENSHOT_QT_API=pyqt5``, ``pyqt6``, or ``pyside6``.
Use ``-DUSE_QT6=OFF`` for Qt5 or ``-DUSE_QT6=ON`` for Qt6 when configuring libopenshot.
Use the same Python interpreter to build the native bindings and launch OpenShot.

For Qt6 development, use a complete PyQt6 or PySide6 environment and build libopenshot against its matching
Qt6 development libraries. Required Python modules include ``QtCore``, ``QtGui``, ``QtWidgets``, ``QtSvg``, and
``QtStateMachine``, plus ``uic`` for PyQt or ``QtUiTools`` for PySide. Avoid mixing Qt libraries from different
installations.

Qt6 package availability varies by distribution; Ubuntu 24.04 does not package PySide6. Verify that your chosen
environment includes all required modules, or use the Qt5/PyQt5 recipe below.

The build commands below run from the parent directory containing all three checkouts. Install the libraries
into a private prefix so development builds do not replace your system libraries:

.. code-block:: bash

   export OPENSHOT_DEV_PREFIX="$PWD/openshot-install"

libopenshot-audio (Build Instructions)
--------------------------------------
This library is required for audio playback and audio effects.
It is based on the JUCE audio framework.
Here are the commands to build it:

.. code-block:: bash

   cmake -S libopenshot-audio -B libopenshot-audio/build \
       -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$OPENSHOT_DEV_PREFIX"
   cmake --build libopenshot-audio/build --parallel 2
   cmake --install libopenshot-audio/build

The private installation does not require administrator permissions. Adjust the parallel build count for your computer.

libopenshot (Build Instructions)
--------------------------------
This library is required for video decoding, encoding, animation, and just about everything else.
It does all the heavy lifting of video editing and video playback.
Here are the commands to build it:

.. code-block:: bash

   cmake -S libopenshot -B libopenshot/build \
       -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$OPENSHOT_DEV_PREFIX" \
       -DCMAKE_PREFIX_PATH="$OPENSHOT_DEV_PREFIX" -DPYTHON_MODULE_PATH=python \
       -DPYTHON_EXECUTABLE=/usr/bin/python3 -DUSE_QT6=OFF \
       -DENABLE_RUBY=OFF -DENABLE_LIB_DOCS=OFF -DBUILD_TESTING=ON
   cmake --build libopenshot/build --parallel 2
   cmake --install libopenshot/build

``CMAKE_PREFIX_PATH`` selects the audio library installed above. Python bindings are installed under
``$OPENSHOT_DEV_PREFIX/python``. If you use another Python interpreter, replace ``/usr/bin/python3`` accordingly.

Vulkan Development
~~~~~~~~~~~~~~~~~~

The packaging rules enable GPU frame processing with FFmpeg 6.1 or newer, Vulkan development files version
1.3.275 or newer, and ``glslangValidator``. Ubuntu 24.04 provides this baseline. Stock Ubuntu 22.04 packages are
older; use the CPU build above or supply a newer compatible dependency stack.

To include GPU frame processing on Ubuntu 24.04, install Vulkan headers and the shader compiler, then enable it
in the same build:

.. code-block:: bash

   sudo apt install libvulkan-dev glslang-tools
   cmake -S libopenshot -B libopenshot/build -DENABLE_GPU_FRAME=ON
   cmake --build libopenshot/build --parallel 2
   cmake --install libopenshot/build

Running this path also requires a compatible GPU and driver. Hardware decoding and encoding depend on the FFmpeg
build as well. Check :ref:`gpu_inspector_ref` for actual activity; compiling Vulkan support alone does not mean
every processing stage uses the GPU.

Language Bindings
-----------------
The ``libopenshot`` API is available in several languages through SWIG bindings.  Python is used by the
OpenShot user interface, and we also provide Ruby and Java bindings.  Experimental support for Godot **4.4**
is included for developers who wish to integrate video editing features into the Godot game engine.  All of
these bindings map to the same C++ codebase so you can edit video from the environment you prefer.

openshot-qt (Launch Instructions)
---------------------------------
This is our main Python/Qt application. Python and UI-file changes do not require compiling the application;
native-library changes require rebuilding and reinstalling the affected library.
To launch OpenShot from the source code with our newly-built
``libopenshot-audio`` and ``libopenshot`` libraries, use the following commands:

.. code-block:: bash

   cd openshot-qt
   export PYTHONPATH="$OPENSHOT_DEV_PREFIX/python"
   export LD_LIBRARY_PATH="$OPENSHOT_DEV_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
   export OPENSHOT_QT_API=pyqt5
   /usr/bin/python3 -c "import openshot; print(openshot.__file__, openshot.OPENSHOT_VERSION_FULL)"
   /usr/bin/python3 src/launch.py

This should launch the OpenShot user interface.
Any changes you have made to the source code files
(``*.py`` Python files, ``*.ui`` PyQt UI files, etc...) will be included.
This requires the ``libopenshot-audio`` and ``libopenshot`` libraries,
and if anything went wrong with the steps above, OpenShot will likely not launch.

If you prefer to run without installing libopenshot, its build-tree Python bindings are under
``libopenshot/build/bindings/python``. Set ``PYTHONPATH`` to that directory and make the matching native libraries
available to the loader. Check ``openshot.__file__`` to confirm which build Python actually imported.

Testing Changes
---------------

From the ``openshot-qt`` checkout, using the same interpreter and library environment as the launch command:

.. code-block:: bash

   QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s src/tests -t src/tests --quiet

For a focused change, run the relevant test module instead, for example
``PYTHONPATH="src:$PYTHONPATH" /usr/bin/python3 -m unittest tests.test_agent_cli.HelpTests``.
Some tests need native libraries, optional dependencies, or a working GPU. Offscreen tests do not replace
checking changed interactions in the editor. For engine changes, also run the libopenshot tests:

.. code-block:: bash

   ctest --test-dir ../libopenshot/build --output-on-failure

Catch2 must be available when configuring libopenshot to build its tests. For GPU changes, compare CPU and Vulkan
results and check transfers with GPU Inspector where applicable.

Building the User Guide
-----------------------

Documentation-only changes do not need the video libraries. From ``openshot-qt``, install Sphinx and the theme
dependencies in a Python environment, then build the English guide:

.. code-block:: bash

   python3 -m pip install sphinx -r doc/requirements.txt
   python3 -m sphinx -W -b html -D language=en doc doc/_build/html

Open ``doc/_build/html/index.html`` to review the result. Keep user-facing instructions clear and concise;
translation updates and localized builds are described in ``doc/README.md``.

.. _launch_options_ref:

Command-Line Launch Options
---------------------------

For editing, animation, batch changes, and exports from a terminal or script,
see :ref:`cli_ref`. Start with ``openshot-qt --cli intro`` (or
``python3 src/launch.py --cli intro`` from source). Put ``--cli`` first, followed
by the editing command and its options.

The CLI supports shared GUI/headless sessions, graceful ``session close``,
portable copies with ``project collect``, and runtime-checked export encoder
selection. For review, choose timeline summaries, zoomed waveform views,
contact sheets, exact frame previews, or rendered video as appropriate; the
CLI guide covers timing conventions and examples.

The launch options below work with the installed OpenShot application, including
``openshot-qt-cmd.exe`` on Windows for visible terminal output. For Windows CLI
usage, follow the console-executable guidance in :ref:`cli_ref`. When running
from source, use
``python3 src/launch.py`` in place of the application name. Put options before
any file paths you want OpenShot to open.

.. list-table:: OpenShot command-line options
   :header-rows: 1
   :widths: 38 62

   * - Option
     - What it does
   * - ``--cli``
     - Enter the :ref:`cli_ref`. Use ``--cli help`` for editing commands.
   * - ``-h``, ``--help``
     - Show application launch options and exit. Use ``--cli help`` for editing commands.
   * - ``-V``, ``--version``
     - Print the OpenShot version and exit.
   * - ``-l CODE``, ``--lang CODE``
     - Use the chosen interface language for this launch. The code must be one
       of those shown by ``--list-languages``.
   * - ``--list-languages``
     - List supported language codes and exit.
   * - ``--path FOLDER``
     - Add a folder to the Python module search path. You can repeat this option
       to add more than one folder.
   * - ``--feedback-preview``
     - Show the feedback notice on launch without marking the invitation as shown
       in saved settings.
   * - ``--update-preview``
     - Show the update notice on launch. Both preview options can be used together.
   * - ``--test-models``
     - Enable Qt's data model tester for development (requires Qt 5.11 or later).
   * - ``-d``, ``--debug``, ``--debug-ui``
     - Add detailed interface messages to its log file and the terminal.
   * - ``--debug-engine``
     - Add detailed video and audio engine messages to its log file and the terminal.
   * - ``--log-level LEVEL``
     - Set the logging level for both parts of OpenShot, in files and the terminal.
   * - ``--log-file-level LEVEL``
     - Set the logging level in both log files.
   * - ``--log-console-level LEVEL``
     - Set the logging level in the terminal for both parts of OpenShot.
   * - ``--debug-file``
     - Add detailed interface messages to its log file only. This older option
       is accepted but is not shown by ``--help``.
   * - ``--debug-console``
     - Add detailed interface messages to the terminal only. This older option
       is accepted but is not shown by ``--help``.
   * - ``PROJECT.osp`` or media file paths
     - Open a project when the first file path ends in ``.osp``. Otherwise,
       start a new project and import the supplied media files.

For ``LEVEL``, use ``debug``, ``info``, ``warning``, ``error``, ``critical``, or
``off``. See :ref:`logging_ref` for log file locations, examples, and more
about choosing logging options.

GitHub Issues
-------------
Now that you have successfully compiled and launched OpenShot Video Editor from source code,
be sure to check out our list of bug reports on GitHub: `OpenShot Issues`_.
Also, you are encouraged to fill out our quick `contributor form <https://forms.gle/CRqkS5tLMJE1V36V8>`_
and introduce yourself!

Share your Changes
------------------
Create a descriptive branch from ``develop`` in your fork, make your changes, and include relevant tests and
documentation. See `CONTRIBUTING.md <https://github.com/OpenShot/openshot-qt/blob/develop/CONTRIBUTING.md>`_
for the contribution workflow.
The easiest way to share your changes is by creating a fork of our repo,
pushing your changes back to GitHub, and creating a `Pull Request`_.
A Pull Request lets the OpenShot team know you have changes ready to be merged.
Target the ``develop`` branch, explain what changed and why, link related issues, and address any failing checks.

.. _Pull Request: https://help.github.com/en/github/collaborating-with-issues-and-pull-requests/proposing-changes-to-your-work-with-pull-requests
.. _OpenShot Issues: https://github.com/OpenShot/openshot-qt/issues/
