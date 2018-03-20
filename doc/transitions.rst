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

Transitions
===========

A transition is used to gradually fade (or wipe) between two clips. In OpenShot, transitions are represented by blue,
rounded rectangles on the timeline. They are automatically created when you overlap two clips, and can be added manually
by dragging one onto the timeline from the **Transitions** panel. A transition must be placed on top of a clip (overlapping it),
with the most common location being the beginning or end.

Overview
--------

.. image:: images/clip-overview.jpg

==  ==================  ============
#   Name                Description
==  ==================  ============
1   Clip 1              A video clip
2   Transition          A gradual fade transition between the 2 clips, created automatically by overlapping the clips.
3   Clip 2              An image clip
==  ==================  ============

Direction
---------
Transitions adjust the alpha/transparency of the clip below it, and can either fade from opaque to transparent, or transparent
to opaque. Right click and choose **Reverse Transition** to change the direction of the fade. You can also manually adjust
the **Brightness** curve, animating the fade in any way you wish.

.. image:: images/transition-reverse.jpg

Cutting & Slicing
-----------------
OpenShot has many easy ways to adjust the start and end positions of a transition (otherwise known as cutting). The most common
method is simply grabbing the left (or right) edge of the transition and dragging. Here is a list of methods for cutting transitions in OpenShot:

.. table::
     :widths: 32

     ==================  ============
     Name                Description
     ==================  ============
     Slice               When the play-head (i.e. red playback line) is overlapping a transition, right click on the transition, and choose Slice
     Slice All           When the play-head is overlapping many transitions, right click on the play-head, and choose Slice All (it will cut all intersecting transitions)
     Resizing Edge       Mouse over the edge of a transition, and resize the edge
     Razor Tool          The razor tool cuts a transition wherever you click, so be careful. Easy and dangerous.
     ==================  ============

Keep in mind that all of the above cutting methods also have :ref:`keyboard_shortcut_ref`.

Mask
----
Like :ref:`clips_ref`, transitions also have properties which can be animated over time. The fade (or wipe) can be adjusted
with the **Brightness** curve, or held at a constant value to create a transparency mask on top of a clip.

Custom Transition
-----------------
Any greyscale image can be used as a transition (or mask), by adding it to your */.openshot_qt/transitions/* folder. Just
be sure to name your file something that is easily recognizable, and restart OpenShot. Your custom transition/mask will now show
up in the list of transitions.

Properties
----------
Below is a list of transition properties which can be edited, and in most cases, animated over time. To view a transition's properties,
right click and choose **Properties**. The property editor will appear, where you can change these properties. NOTE: Pay
close attention to where the play-head (i.e. red playback line) is. Key frames are automatically created at the current playback
position, to help create animations.

.. table::
     :widths: 28

     ==================  ============
     Name                Description
     ==================  ============
     Brightness          Curve representing the brightness of the transition image, which affects the fade/wipe (-1 to 1)
     Contrast            Curve representing the contrast of the transition image, which affects the softness/hardness of the fade/wipe (0 to 20)
     Replace Image       For debugging a problem, this property displays the transition image (instead of becoming a transparency)
     ==================  ============

