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

Animation
=========

OpenShot has been designed specifically with animation in mind. The powerful curve-based animation framework can
handle most jobs with ease, and is flexible enough to create just about any animation. Key frames specify
values at certain points on a clip, and OpenShot does the hard work of interpolating the in-between values.


Overview
--------

.. image:: _static/animation-overview.jpg

==  ==================  ============
#   Name                Description
==  ==================  ============
1   Green Property      When the play-head is on a key frame, the property appears green
1   Blue Property       When the play-head is on an interpolated value, the property appears blue
2   Value Slider        Click and drag your mouse to adjust the value (this automatically creates a key frame if needed)
3   Play-head           Position the play-head over a clip where you need a key frame
4   Key frame Markers   Small green tick marks are drawn at all key frame positions (on a clip)
==  ==================  ============

Key Frames
----------
To create a key frame in OpenShot, simply position the play-head (i.e. playback position) at any point over a clip,
and edit properties in the property dialog. If the property supports key frames, it will turn green, and a small green
tick mark will appear on your clip at that position. Move your play-head to another point over that clip, and adjust
the properties again. All animations require at least 2 key frames, but can support an unlimited number of them.

To adjust the **interpolation mode**, right click on the small graph icon next to a property value.

==================  ============
Name                Description
==================  ============
Bézier              Interpolated values use a quadratic curve, and ease-in and ease-out
Linear              Interpolated values are calculated linear (each step value is equal)
Constant            Interpolated values stay the same until the next key frame, and jump to the new value
==================  ============

For more info on clip properties, see :ref:`clip_properties_ref`. For more info on preset animations, see :ref:`clip_presets_ref`.

Image Sequences
---------------
If you have a sequence of similarly named images (such as, cat001.png, cat002.png, cat003.png, etc...), you can simply
drag and drop one of them into OpenShot, and you will be prompted to import the entire sequence.

To adjust the frame rate of the animation, right click and choose **File Properties** in the **Project Files** panel,
and adjust the frame rate. Once you have set the correct frame rate, drag the animation onto the timeline.