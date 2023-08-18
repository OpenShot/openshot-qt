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

Text & Titles
=============

Adding text and titles is an important aspect of video editing, and OpenShot comes with an easy-to-use Title Editor. Use
the Title menu (located in the main menu of OpenShot) to launch the Title Editor. You can also use the keyboard shortcut
:kbd:`Ctrl+T`.

Titles are simply vector image files with transparent backgrounds (``*.svg``). OpenShot comes with many easy-to-use
templates, but you can also create your own or import new templates into OpenShot. These templates allow you to quickly
change the text, font, size, color, and background color. You can also launch an advanced, external SVG editor for
further customizations (if needed). Once the title is added to your project, drag and drop the title on a
Track above a video clip. The transparent background will allow the video below to appear behind the text.

Overview
--------

.. image:: images/title-editor.jpg

.. table::
   :widths: 5 26 60

   ==  ==================  ============
   #   Name                Description
   ==  ==================  ============
   1   Choose a Template   Choose from any available vector title template
   2   Preview Title       Preview your title as you make changes
   3   Title Properties    Change the text, font, size, colors, or edit in an advanced, external SVG image editor (such as Inkscape)
   4   Save                Save and add the title to your project
   ==  ==================  ============

Custom Title Templates
----------------------
OpenShot can use any vector SVG image file as a custom title template in the :guilabel:`Title Editor` dialog. Just add an SVG image file to your
``~/.openshot_qt/title_templates/`` folder, and it will appear the next time you launch the :guilabel:`Title Editor` dialog. You can
also right click on any SVG files in your **Project Files** panel, and choose **Edit Title** or **Duplicate Title**.

Note: These SVG templates are only used by the :guilabel:`Title Editor` dialog, and not :guilabel:`Animated Title` dialog.

3D Animated Titles
------------------
Adding a 3D animated title is just as easy, using our **Animated Title** dialog. Use the Title menu (located
in the main menu of OpenShot) to launch the Animated Title editor. You can also use the keyboard shortcut **Ctrl+B**.
Note: Blender must be installed and configured before this feature will work in OpenShot. See :ref:`blender_install_ref`.

.. image:: images/animated-title.jpg

==  ==================  ============
#   Name                Description
==  ==================  ============
1   Choose a Template   Choose from any available 3D title templates
2   Preview Title       Preview your title as you make changes
3   Title Properties    Change the text, colors, and advanced properties
4   Render              Render the 3D animation, and add it to your project
==  ==================  ============

Importing Text
--------------

You can generate text & titles in many different programs, such as Blender, Inkscape, Krita, Gimp, etc... Before you
can import text into OpenShot, you must first export the text from these programs into a compatible image format that
contains a **transparent background** and **alpha** channel.

The ``SVG`` format is a great choice for vector graphics (curves, shapes, text effects and paths), however
it is **not** always 100% compatible with OpenShot. Thus, we recommend using ``PNG`` format, which is a great web-based
image format that can include a transparent background and alpha channel. A transparent background and alpha channel
are needed for OpenShot to allow the text to not cover up videos and images on the timeline below them.

For information on importing animated sequences into OpenShot, please see :ref:`animation_image_seq_ref`.

Installing Inkscape
-------------------

The :guilabel:`Advanced Editor` feature in the :guilabel:`Title Editor` dialog requires the latest version of
Inkscape (https://inkscape.org/release/) be installed and the OpenShot **Preferences** updated with the 
correct path to the Inkscape executable. See the :ref:`preferences_general_ref` tab in Preferences. 

.. _blender_install_ref:

Installing Blender
------------------

The :guilabel:`Animated Title` feature in OpenShot requires the latest version of
Blender (https://www.blender.org/download/) be installed and the OpenShot **Preferences** updated 
with the correct path to the Blender executable. See the :ref:`preferences_general_ref` tab 
in Preferences. NOTE: The minimum supported version of Blender is 2.8+. Older versions of Blender are 
not compatible with OpenShot Video Editor.

For a detailed guide on how to install these dependencies, see 
`Blender & Inkscape Guide <https://github.com/OpenShot/openshot-qt/wiki/Blender-and-Inkscape-Guide>`_.
