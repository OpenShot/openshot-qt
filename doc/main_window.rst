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

Main Window
===========

OpenShot Video Editor has one main window which contains most of the information, buttons,
and menus needed to edit your video project.

Overview
--------

.. image:: images/main-window.jpg

.. table::
   :widths: 5 22 73

   ==  ==================  ============
   #   Name                Description
   ==  ==================  ============
   1   Main Toolbar        Contains buttons to open, save, and export your video project.
   2   Function Tabs       Switch between Project Files, Transitions, Effects, and Emojis.
   3   Project Files       All audio, video, and image files that have been imported into your project.
   4   Preview Window      This is the area that the video will playback on the screen.
   5   Edit Toolbar        This toolbar contains buttons used for snapping, inserting markers, slicing razor, and jumping between markers.
   6   Zoom Slider         This slider will adjust the time-scale of your timeline. Drag the left or right edge to zoom in or out. Drag the blue area to scroll the timeline left or right. Clips and transitions are displayed as simple rectangles, to give you context for adjusting the zoom to specific clips.
   7   Play-head / Ruler   The ruler shows the time-scale, and the red line is the play-head. The play-head represents the current playback position. Hold :kbd:`Shift` key while dragging the playhead to snap to nearby clips.
   8   Timeline            The timeline visualizes your video project, and each clip and transition in your project. You can drag the mouse to select, move, or delete multiple items.
   9   Filter              Filter the list of items shown (project files, transitions, effects, and emojis) by using these buttons and filter textbox. Enter a few letters of what you are looking for, and the results will be shown.
   10  Playback            Left to Right: Jump to Start, Rewind, Play/Pause, Fast Forward, and Jump to End
   ==  ==================  ============

For step-by-step instructions on the basic usage of OpenShot, be sure to read the
:ref:`quick_tutorial_ref`.

Built-in Tutorial
-----------------
When you first launch OpenShot, you will be presented with a friendly built-in tutorial. It will demonstrate and explain
the basics. Clicking :guilabel:`Next` will jump to the next topic. You can always view this tutorial again from the :guilabel:`Help→Tutorial` menu.

.. image:: images/built-in-tutorial.jpg

.. _tracks_ref:

Tracks & Layers
------------------

OpenShot uses tracks to layer videos and images. The top most track is the top
layer, and the bottom track is the bottom layer. If you are familiar with layers
in a photo editing application, then you should be quite familiar with this
concept. OpenShot will stack the layers and mix each one together, just like a
photo editing application. You can have an unlimited number of tracks, but
typically a simple video project will not need more than 5 tracks.

For example, imagine a 3 track video project

.. image:: images/tracks.jpg

.. table::
   :widths: 5 18 77

   ==  ==================  ============
   #   Name                Description
   ==  ==================  ============
   1   Top Track           Clips on this track will always be on top and visible. Often watermarks and titles are placed on higher tracks.
   2   Middle Track        Clips in the middle (might or might not be visible, depending on what is above them)
   3   Bottom Track        Clips on this track will always be on the bottom. Often audio clips are placed on lower tracks.
   ==  ==================  ============

.. _keyboard_shortcut_ref:

Keyboard Shortcuts
------------------
Here is a list of the default keyboard shortcuts supported by OpenShot. You can
configure these shortcuts in the Preferences window, which is opened by selecting
:guilabel:`Edit→Preferences` from the OpenShot menu bar.
(On macOS, choose :guilabel:`OpenShot Video Editor→Preferences`.)
Learning a few of these shortcuts can save you a bunch of time!

=========================  ============
Shortcut                   Action
=========================  ============
:kbd:`Ctrl+H`              About OpenShot
:kbd:`Ctrl+M`              Add Marker
:kbd:`Ctrl+Shift+T`        Add Track
:kbd:`Ctrl+W`              Add to Timeline
:kbd:`Ctrl+B`              Animated Title
:kbd:`Ctrl+Up`             Center on Playhead
:kbd:`Ctrl+P`              Choose Profile
:kbd:`Ctrl+Shift+ESC`      Clear All Cache
:kbd:`Ctrl+C`              Copy
:kbd:`Delete`              Delete Item
:kbd:`Backspace`           Delete Item (Alternate 1)
:kbd:`Ctrl+D`              Details View
:kbd:`Ctrl+Shift+C`        Duplicate Title
Not Set                    Edit Title
:kbd:`Ctrl+E`              Export Video
:kbd:`L`                   Fast Forward
:kbd:`F11`                 Fullscreen
:kbd:`Ctrl+F`              Import Files...
:kbd:`Ctrl+Shift+E`        Insert Keyframe
:kbd:`Ctrl+End`            Jump To End
:kbd:`Ctrl+Home`           Jump To Start
:kbd:`Ctrl+N`              New Project
:kbd:`Right`               Next Frame
:kbd:`Ctrl+Right`          Next Marker
:kbd:`Shift+Left`          Nudge left
:kbd:`Shift+Right`         Nudge right
:kbd:`Ctrl+O`              Open Project...
:kbd:`Ctrl+V`              Paste
:kbd:`Space`               Play/Pause Toggle
:kbd:`Up`                  Play/Pause Toggle (Alternate 1)
:kbd:`Down`                Play/Pause Toggle (Alternate 2)
:kbd:`K`                   Play/Pause Toggle (Alternate 3)
:kbd:`Ctrl+Shift+P`        Preferences
:kbd:`Left`                Previous Frame
:kbd:`Ctrl+Left`           Previous Marker
:kbd:`Ctrl+I`              Properties
:kbd:`Ctrl+Q`              Quit
:kbd:`Ctrl+Y`              Redo
:kbd:`J`                   Rewind
Not Set                    Save Current Frame
:kbd:`Ctrl+S`              Save Project
:kbd:`Ctrl+Shift+S`        Save Project As...
:kbd:`Ctrl+A`              Select All
:kbd:`Ctrl+Shift+A`        Select None
:kbd:`Ctrl+K`              Slice All: Keep Both Sides
:kbd:`Ctrl+L`              Slice All: Keep Left Side
:kbd:`Ctrl+J`              Slice All: Keep Right Side
:kbd:`s`                   Slice Selected: Keep Both Sides
:kbd:`d`                   Slice Selected: Keep Left Side
:kbd:`a`                   Slice Selected: Keep Right Side
:kbd:`Ctrl+G`              Snapping Enabled
:kbd:`Ctrl+X`              Split Clip...
:kbd:`Ctrl+Shift+D`        Thumbnail View
:kbd:`Ctrl+T`              Title
:kbd:`R`                   Toggle Razor
:kbd:`Ctrl+R`              Transform
:kbd:`Ctrl+Z`              Undo
:kbd:`=`                   Zoom In
:kbd:`-`                   Zoom Out
:kbd:`Ctrl+Middle Button`  Scroll Timeline
=========================  ============

Menu
----
The following menu options are available on the main window on OpenShot. Most of these options can be accessed
by the keyboard shortcuts mentioned above. On some Operating Systems (such as macOS) a few of these options
are renamed and/or rearranged.

.. table::
   :widths: 10 73

   ==================  ============
   Menu Name           Description
   ==================  ============
   File                :guilabel:`New Project`, :guilabel:`Open Project`, :guilabel:`Recent Projects`,
                       :guilabel:`Save Project`, :guilabel:`Import Files`, :guilabel:`Choose Profile`,
                       :guilabel:`Import`, :guilabel:`Export`, :guilabel:`Quit`
   Edit                :guilabel:`Undo`, :guilabel:`Redo`, :guilabel:`Clear`, :guilabel:`Preferences`
   Title               :guilabel:`Title`, :guilabel:`Animated Title`
   View                :guilabel:`Toolbar`, :guilabel:`Fullscreen`, :guilabel:`Views` `(Simple, Advanced, Freeze, Show All)`,
                       :guilabel:`Docks`
   Help                :guilabel:`Contents`, :guilabel:`Tutorial`, :guilabel:`Report a Bug`, :guilabel:`Ask a Question`,
                       :guilabel:`Translate`, :guilabel:`Donate`, :guilabel:`About`
   ==================  ============

Views
-----

The OpenShot main window is composed of multiple **docks**. These **docks** are arranged and snapped together
into a grouping that we call a **View**. OpenShot comes with two primary views: :guilabel:`Simple View` and
:guilabel:`Advanced View`.

Simple View
^^^^^^^^^^^
This is the **default** view, and is designed to be easy-to-use, especially for first-time users. It contains
:guilabel:`Project Files` on the top left, :guilabel:`Preview Window` on the top right, and :guilabel:`Timeline` on
the bottom. If you accidentally close or move a dock, you can quickly reset all the docks back to their default
location using the :guilabel:`View->Views->Simple View` menu at the top of the screen.

Advanced View
^^^^^^^^^^^^^
This is an advanced view, which adds more docks to the screen at once, improving access to many features that are
not visible in Simple View. Once you have mastered the Simple View, we recommend giving this view a try as well.
NOTE: You can also drag and drop the docks anywhere you would like, for a fully custom view.

Docks
^^^^^
Each widget on the OpenShot main window is contained in a **dock**. These docks can be dragged and snapped around the
main window, and even grouped together (into tabs). OpenShot will always save your main window dock layout when you
exit the program. Re-launching OpenShot will restore your custom dock layout automatically.

If you have accidentally closed or moved a dock and can no longer find it, there are a couple easy solutions.
First, you can use the :guilabel:`View->Views->Simple View` menu option at the top of the screen, to restore the view back to its
default. Or you can use the :guilabel:`View->Views->Docks->...` menu to show or hide specific dock widgets on the main window.
