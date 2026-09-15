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

.. _troubleshoot_ref:

Troubleshooting
===============

If you are experiencing an issue with OpenShot, such as a freeze, crash, or error message, there are many different
techniques which can be useful for troubleshooting the issue.

.. _logging_ref:

Using Logs to Troubleshoot a Problem
--------------------------------------

A log is a text file that records what OpenShot is doing, along with warnings
and errors. These files can help the support team understand a problem, even
when you do not see an error message on screen.

OpenShot keeps two log files in the ``.openshot_qt`` folder inside your home
folder. On Linux and macOS, this location is written as ``~/.openshot_qt/``.
The folder may be hidden in your file manager.

.. list-table:: The two log files
   :header-rows: 1
   :widths: 25 75

   * - File
     - What it records
   * - ``openshot-qt.log``
     - Activity in the editor: starting OpenShot, loading projects, changing
       settings, and using the interface. This is usually the best place to
       start when investigating a problem.
   * - ``libopenshot.log``
     - Activity in OpenShot's video and audio engine, the part that reads media
       and builds the pictures and sound used in previews and exported videos.
       Detailed engine logging can help investigate playback and export problems.

These files record different parts of the same application. When reporting a
problem, include both files if available. You do not need to understand every
line yourself.

Choose which part of OpenShot to log
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Open **Edit → Preferences → Advanced** to find these two settings:

.. list-table:: Preferences and matching terminal options
   :header-rows: 1
   :widths: 45 30 25

   * - Preference
     - Matching argument
     - Log file
   * - User Interface Debug Logging
     - ``--debug-ui``
     - ``openshot-qt.log``
   * - Video & Audio Engine Debug Logging
     - ``--debug-engine``
     - ``libopenshot.log``

Both preferences are off by default, which keeps the normal summary messages.
Turning one on adds detail to its log file immediately. It does not change the
other log or add messages to the terminal. Preferences stay enabled between
launches until you turn them off.

**User Interface Debug Logging** is a good starting point for problems with
startup, project loading, settings, or the interface. **Video & Audio Engine
Debug Logging** adds details about video and audio processing, which can help
investigate playback and export problems. Engine logs can grow very quickly
and may slow OpenShot down. Turn this setting on shortly before repeating the
problem, then turn it off afterward.

The engine preference was previously called **Debug Mode (Verbose)**. Its saved
on/off setting carries over to the new name.

Use a terminal for one launch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A terminal is a window where you type commands. The matching arguments enable
the same extra detail as the preferences, and also display it in the terminal:

.. code-block:: bash

   openshot-qt --debug-ui

This records interface details for one launch. The familiar ``--debug`` and
shorter ``-d`` options mean exactly the same thing as ``--debug-ui``.
For video and audio engine details, use:

.. code-block:: bash

   openshot-qt --debug-engine

To collect both types of detail together:

.. code-block:: bash

   openshot-qt --debug-ui --debug-engine

Repeat the steps that cause the problem, then close OpenShot and collect the
logs. These arguments do not change your saved preferences. Starting OpenShot
normally returns to your usual logging settings.

``openshot-qt.log`` starts a new file when it reaches about 25 MB and keeps
three older copies. ``libopenshot.log`` keeps growing as messages are added.
After saving any logs you need, you can remove old log files while OpenShot
is closed.

Other command-line options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Most users only need the two controls above. The following options let you
choose how much detail goes into the files or appears in the terminal.
Here, *console* means the terminal output.

.. list-table:: Logging options
   :header-rows: 1
   :widths: 40 60

   * - Option
     - What it does
   * - ``--debug-ui``, ``--debug``, or ``-d``
     - Enables User Interface Debug Logging in its file and the terminal.
   * - ``--debug-engine``
     - Enables Video & Audio Engine Debug Logging in its file and the terminal.
   * - ``--debug-file``
     - Adds editor details to ``openshot-qt.log`` without adding terminal detail.
   * - ``--debug-console``
     - Adds editor details in the terminal without adding file detail.
   * - ``--log-level LEVEL``
     - Sets the detail for both logs and their terminal output.
   * - ``--log-file-level LEVEL``
     - Sets the detail for both log files, leaving terminal settings alone.
   * - ``--log-console-level LEVEL``
     - Sets the detail in the terminal for both the editor and engine,
       leaving file settings alone.

Replace ``LEVEL`` with ``debug`` for detailed messages or ``info`` for the
normal summary. ``warning`` shows warnings and errors; ``error`` shows errors
and critical failures; ``critical`` shows only critical failures. ``off`` stops
ordinary log messages, but existing crash diagnostics may still be written.
Uppercase names such as ``DEBUG`` work too.

For example, to collect detailed messages in **both files** while keeping the
terminal at its usual level:

.. code-block:: bash

   openshot-qt --log-file-level debug

This also enables the large engine log, so use it briefly. The older
``--debug-file`` and ``--debug-console`` options still work even though they
are not listed in ``--help``.

Environment variables
^^^^^^^^^^^^^^^^^^^^^^^

An environment variable is a named setting passed to a program when it starts.
These are useful when starting OpenShot from a script or when a support person
asks you to try a particular setting. You do not need to set them for normal use.

.. list-table:: Optional environment settings
   :header-rows: 1
   :widths: 45 55

   * - Variable
     - What it controls
   * - ``OPENSHOT_LOG_LEVEL``
     - Detail in both files and the terminal.
   * - ``OPENSHOT_LOG_FILE_LEVEL``
     - Detail in both files only.
   * - ``OPENSHOT_LOG_CONSOLE_LEVEL``
     - Detail in the terminal only, for both parts of OpenShot.
   * - ``LIBOPENSHOT_LOG_LEVEL``
     - Detail for the video and audio engine, in its file and the terminal.
   * - ``LIBOPENSHOT_LOG_FILE_LEVEL``
     - Detail in ``libopenshot.log`` only.
   * - ``LIBOPENSHOT_LOG_CONSOLE_LEVEL``
     - Engine detail in the terminal only.

For example, this Linux/macOS terminal command requests detailed engine logging
in its file for one launch:

.. code-block:: bash

   LIBOPENSHOT_LOG_FILE_LEVEL=debug openshot-qt

If settings overlap, command-line options take priority, followed by environment
variables, then Preferences, then the normal defaults. Each control only affects
the output it describes: ``--debug`` does not override the engine preference.
Temporary overrides do not change your saved preferences. Hover over either
checkbox to see whether another setting is controlling that log file.

Within the environment settings, ``LIBOPENSHOT_`` values take priority over
``OPENSHOT_`` values for the engine. Within either group, a file-only or
console-only level takes priority over the general level. Command-line options
follow the same file/console rule. Conflicting command-line levels for the same
output are rejected; invalid environment levels are reported and ignored.

For older scripts, ``LIBOPENSHOT_DEBUG`` still enables detailed engine messages
in the terminal whenever it is present, even if its value is ``0``. The newer
level settings take priority over it. ``LIBOPENSHOT_LOG_FILE`` is intended for
programs using the engine separately; OpenShot itself uses the log folder above.
Changing logging settings does not change your error-reporting preference.

Windows 11 Unresponsive
-----------------------

If you experience a freeze on Windows 11, this is a known issue with PyQt5 and Windows 11, related to the
accessibility features in Qt. This is triggered by pressing :kbd:`Ctrl+C` in OpenShot (*only on Windows 11*).
OpenShot will become unresponsive and a memory leak is also present (i.e. the longer OpenShot is unresponsive,
the larger your memory leak will become until OpenShot finally crashes or the user kills the process).

A simple work-around is to avoid :kbd:`Ctrl+C` on Windows 11, and instead use the right-click Copy/Paste menus. Another
work-around is to remap your "Copy" from :kbd:`Ctrl+C` to something else, for example :kbd:`Alt+C`. You can change
your keyboard mappings in the OpenShot Preferences. See :ref:`preferences_keyboard_ref`.

Windows Debugging with GDB
--------------------------

If you are experiencing a crash or freeze with OpenShot in Windows 10/11, the following step by step instructions
will help you determine the cause of the crash. These instructions will display a stack trace of OpenShot's source code,
at the location of the crash. This information can be extremely useful for our development team, and very useful to
attach to bug reports (for a quicker resolution).

Install the Latest Daily Build
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Before attaching a debugger, please download the **latest version** of OpenShot: https://www.openshot.org/download#daily.
Install this version of OpenShot to the default location: ``C:\Program Files\OpenShot Video Editor\``. For details
instructions on debugging OpenShot on Windows, please see `this wiki <https://github.com/OpenShot/openshot-qt/wiki/Windows-Debugging-with-GDB>`_.

Install MSYS2
^^^^^^^^^^^^^

The Windows version of OpenShot is compiled using an environment called MSYS2. In order to attach the GDB debugger
to our executable, ``openshot-qt.exe``, you must first install MSYS2. This step is only required once.

1. Download & Install MSYS2: `<http://www.msys2.org/>`_
2. Run ``MSYS2 MinGW x64`` command prompt (for example: ``C:\msys64\msys2_shell.cmd -mingw64``)
3. Update all packages (*Copy/Paste the following command*):

   .. code-block:: shell

      pacman -Syu

4. Install GDB debugger (*Copy/Paste the following command*):

   .. code-block:: shell

      pacman -S --needed --disable-download-timeout mingw-w64-x86_64-toolchain

Launch OpenShot with GDB Debugger
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run ``MSYS2 MinGW x64`` command prompt (for example: ``C:\msys64\msys2_shell.cmd -mingw64``)

Update the PATH (*Copy/Paste the following commands*):

.. code-block:: bash

    export PATH="/c/Program Files/OpenShot Video Editor/lib:$PATH"
    export PATH="/c/Program Files/OpenShot Video Editor/lib/PyQt5:$PATH"

Load OpenShot into the GDB debugger (*Copy/Paste the following commands*):

.. code-block:: bash

    cd "/c/Program Files/OpenShot Video Editor"/
    gdb openshot-qt.exe

Launch OpenShot from GDB prompt (*Copy/Paste the following command*):

.. code-block:: bash

    run --debug

Print Debugging Info
^^^^^^^^^^^^^^^^^^^^

Once OpenShot has launched successfully with GDB attached, all you need to do is trigger a crash or freeze in OpenShot.
When a crash occurs, switch back to the MSYS2 MinGW64 terminal and run one of the following commands
(by typing it and pressing ENTER). Usually, the first command to enter is ``bt``, which stands for ``backtrace``.
More commands are listed below.

.. code-block:: bash

    (gdb) run            (launch openshot-qt.exe)
    (gdb) CTRL + C       (to manually break out   OR   wait for a crash / segmentation fault)
    (gdb) bt             (Print stack trace for the current thread #)
    (gdb) info threads   (to view all threads, and what they are doing. Look for `__lll_lock_wait` for Mutex/deadlocks)
    (gdb) thread 35      (Switch to thread number, for example thread 35)

High DPI / 4K Monitors
----------------------

OpenShot Video Editor provides robust support for High DPI (Dots Per Inch)
monitors, ensuring that the interface looks sharp and is easily readable on
displays with various DPI settings. This support is particularly helpful on 4K
monitors and other high-resolution displays.

Per Monitor DPI Awareness
^^^^^^^^^^^^^^^^^^^^^^^^^

OpenShot is DPI aware on a per-monitor basis, meaning it can adjust its scaling
dynamically depending on the DPI settings of each connected monitor. This helps
provide a consistent experience across different displays.

DPI Scaling on Windows
^^^^^^^^^^^^^^^^^^^^^^

On Windows, OpenShot rounds the scaling factor to the nearest whole value to
maintain visual integrity. This helps avoid visual artifacts in the UI and
keeps interface elements crisp and well-aligned. Due to this rounding, some
scaling options can lead to larger fonts and UI elements than expected.

- **125% scaling** rounds to **100%**
- **150% scaling** rounds to **200%**

Workarounds for Fine-Grained Adjustment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

While rounding helps maintain a clean interface, there are workarounds for
users who require more precise control over scaling. These methods are **not
recommended** due to potential visual artifacts:

- **QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough**

  - Setting this environment variable can disable rounding and allow more precise scaling.
  - **Note:** This may cause visual artifacts, particularly in the timeline, and is not recommended.

- **QT_SCALE_FACTOR=1.25** (or similar value)

  - Manually setting the scale factor can provide finer adjustments to the font and UI scaling.
  - This can also be set via Preferences (User Interface Scale), but expect border/line issues on Windows with fractional scales.
  - **Note:** This method can also lead to visual artifacts and make OpenShot harder to use.

For more info on adjusting these environment variables, please visit
https://github.com/OpenShot/openshot-qt/wiki/OpenShot-UI-too-large.
