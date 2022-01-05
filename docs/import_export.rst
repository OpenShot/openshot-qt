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

Import & Export
===============

Video editing projects (including tracks, clips, and keyframes)
can be **imported** and **exported** from OpenShot Video Editor
in widely supported formats
(**EDL**: Edit Decision Lists, and **XML**: Final Cut Pro format).
For example, if you start editing a video in a different program
(Adobe Premier, Final Cut Pro, etc...),
but later need to move all your edits to OpenShot (or vice versa).

EDL (Edit Decision Lists)
-------------------------
The following features are supported
when importing and exporting an EDL file with OpenShot.

.. table::
   :widths: 25

   ====================  ==============================================
   Name                  Description
   ====================  ==============================================
   EDL Format            CMX-3600 (a very widely supported variation)

   Single Track          Only a single track can be imported at a time
                         (this is a limitation of the EDL format)

   Tape Name             Only **AX** and **BL** tape names
                         are currently supported in OpenShot

   Edits (V and A)       Only edits are currently supported
                         (transitions are not yet supported)

   Opacity               Opacity keyframes are supported

   Audio Levels          Volume keyframes are supported
   ====================  ==============================================

In :ref:`appendix_a:Appendix A: Data Interchange Formats` you can see an 
:ref:`appendix_a:EDL example` file of the type supported by OpenShot.


XML (Final Cut Pro format)
--------------------------
The following features are supported
when importing and exporting an XML file with OpenShot.
This XML format is compatible with many video editors (not just Final Cut Pro).
In fact, most commercial video editors have some support
for importing and exporting this standardized XML format.

.. table::
   :widths: 25

   ====================  ==========================================
   Name                  Description
   ====================  ==========================================
   XML Format            Final Cut Pro format
                         (but most commercial video editors
                         also support this format)
   
   All Tracks            All video and audio tracks are supported
   
   Edits                 All clips on all tracks are supported
                         (video, image, and audio files).
                         Transitions are not yet supported.
   
   Opacity               Opacity keyframes are supported

   Audio Levels          Volume keyframes are supported
   ====================  ==========================================

In :ref:`appendix_a:Appendix A: Data Interchange Formats` you'll find an
:ref:`appendix_a:XML Example` of the data import/export support in OpenShot.

