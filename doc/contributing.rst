.. Copyright (c) 2008-2020 OpenShot Studios, LLC
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


Contributing
============

Did you find a bug?
-------------------

-  **Please check if this bug was already reported** by searching on
   GitHub under `Issues`_.

-  If you're unable to find an open issue addressing the problem,
   :openshot-issue:`open a new one <new/choose>`.
   Be sure to include a **title and clear description**, as much relevant
   information as possible, and the steps to reproduce the crash or
   issue.

-  Please **attach log files** if you are reporting a crash. Otherwise,
   we will not be able to determine the cause of the crash.

Please download our latest daily installer:
"""""""""""""""""""""""""""""""""""""""""""
1. `openshot.org/download <https://www.openshot.org/download>`_ - click the '**DAILY BUILDS**' button, then grab the latest build from the list.
   (Use the buttons below to download installers for a different Operating System.)
2. Then enable 'Debug Mode (Verbose)' in the Preferences
3. Quit OpenShot and delete both log files:

   -  **Windows**: OpenShot stores its logs in your user profile
      directory (``%USERPROFILE%``, e.g. ``C:\Users\username\``)

      -  ``%USERPROFILE%/.openshot_qt/openshot-qt.log``
      -  ``%USERPROFILE%/.openshot_qt/libopenshot.log``

   -  **Linux/MacOS**: OpenShot stores its logs in your home directory
      (``$HOME``, e.g. ``/home/username/``)

      -  ``$HOME/.openshot_qt/openshot-qt.log``
      -  ``$HOME/.openshot_qt/libopenshot.log``

4. Re-launch OpenShot and trigger the crash as quickly as possible (to
   keep the log files small)
5. Attach **both** log files

Did you write a patch that fixes a bug?
---------------------------------------

-  Open a new GitHub pull request with the patch.

-  Ensure the PR description clearly describes the problem and solution.
   Include the relevant issue number if applicable.

-  Before submitting, please ensure your PR passes all build /
   compilation / and unit tests.

OpenShot Video Editor is a volunteer effort, and a labor of love. Please
be patient with any issues you find, and feel free to get involved and
help us fix them!

Thanks!

OpenShot Team

.. _Issues: https://github.com/OpenShot/openshot-qt/issues/
