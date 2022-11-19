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

.. _effects_ref:

Effects
=======

Effects are used in OpenShot to enhance or modify the audio or video of a clip. They can modify pixels and audio data,
and can generally enhance your video projects. Each effect has its own set of properties, most which can be animated
over time.

Effects can be added to any clip by dragging and dropping them. Each effect is represented by a small colored
icon and the first letter of the effect name. To view an effect's properties, click on the effect icon.
The property editor will appear, where you can edit these properties. Note: Pay close attention to where
the play-head (i.e. red playback line) is. Key frames are automatically created at the current playback
position, to help create animations.

.. image:: images/clip-effects.jpg

Video Effects
-------------

Effects are generally divided into two categories: video and audio effects. Video effects modify the image and pixel
data of a clip. Below is a list of video effects, and their properties. Often it is best to experiment with an effect,
entering different values into the properties, and observing the results.

Alpha Mask / Wipe Transition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Uses a grayscale mask image to gradually wipe / transition between 2 images.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   brightness                  ``(float, -1 to 1)`` This curve controls the motion across the wipe
   contrast                    ``(float, 0 to 20)`` This curve controls the hardness and softness of the wipe edge
   reader                      ``(reader)`` This reader can use any image or video as input for your grayscale wipe
   replace_image               ``(int, choices: ['Yes', 'No'])`` Replace the clips image with the current grayscale wipe image, useful for troubleshooting
   ==========================  ============

Bars
^^^^
Add colored bars around your video.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   bottom                      ``(float, 0 to 0.5)`` The curve to adjust the bottom bar size
   color                       ``(color)`` The curve to adjust the color of bars
   left                        ``(float, 0 to 0.5)`` The curve to adjust the left bar size
   right                       ``(float, 0 to 0.5)`` The curve to adjust the right bar size
   top                         ``(float, 0 to 0.5)`` The curve to adjust the top bar size
   ==========================  ============

Blur
^^^^
Adjust the blur of the frame's image.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   horizontal_radius           ``(float, 0 to 100)`` Horizontal blur radius keyframe. The size of the horizontal blur operation in pixels.
   iterations                  ``(float, 0 to 100)`` Iterations keyframe. The # of blur iterations per pixel. 3 iterations = Gaussian.
   sigma                       ``(float, 0 to 100)`` Sigma keyframe. The amount of spread in the blur operation. Should be larger than radius.
   vertical_radius             ``(float, 0 to 100)`` Vertical blur radius keyframe. The size of the vertical blur operation in pixels.
   ==========================  ============

Brightness & Contrast
^^^^^^^^^^^^^^^^^^^^^
Adjust the brightness and contrast of the frame's image.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   brightness                  ``(float, -1 to 1)`` The curve to adjust the brightness
   contrast                    ``(float, 0 to 100)`` The curve to adjust the contrast (3 is typical, 20 is a lot, 100 is max. 0 is invalid)
   ==========================  ============

Caption
^^^^^^^
Add text captions on top of your video.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   background                  ``(color)`` Color of caption area background
   background_alpha            ``(float, 0 to 1)`` Background color alpha
   background_corner           ``(float, 0 to 60)`` Background corner radius
   background_padding          ``(float, 0 to 60)`` Background padding
   caption_font                ``(font)`` Font name or family name
   caption_text                ``(caption)`` VTT/Subrip formatted caption text (multi-line)
   color                       ``(color)`` Color of caption text
   fade_in                     ``(float, 0 to 3)`` Fade in per caption (# of seconds)
   fade_out                    ``(float, 0 to 3)`` Fade out per caption (# of seconds)
   font_alpha                  ``(float, 0 to 1)`` Font color alpha
   font_size                   ``(float, 0 to 200)`` Font size in points
   left                        ``(float, 0 to 0.5)`` Size of left margin
   line_spacing                ``(float, 0 to 5)`` Distance between lines (1.0 default)
   right                       ``(float, 0 to 0.5)`` Size of right margin
   stroke                      ``(color)`` Color of text border / stroke
   stroke_width                ``(float, 0 to 10)`` Width of text border / stroke
   top                         ``(float, 0 to 1)`` Size of top margin
   ==========================  ============

Chroma Key (Greenscreen)
^^^^^^^^^^^^^^^^^^^^^^^^
Replaces the color (or chroma) of the frame with transparency (i.e. keys out the color).

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   color                       ``(color)`` The color to match
   fuzz                        ``(float, 0 to 125)`` The fuzz factor (or threshold)
   halo                        ``(float, 0 to 125)`` The additional threshold for halo elimination.
   keymethod                   ``(int, choices: ['Basic keying', 'HSV/HSL hue', 'HSV saturation', 'HSL saturation', 'HSV value', 'HSL luminance', 'LCH luminosity', 'LCH chroma', 'LCH hue', 'CIE Distance', 'Cb,Cr vector'])`` The keying method or algorithm to use.
   ==========================  ============

Color Saturation
^^^^^^^^^^^^^^^^
Adjust the color saturation.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   saturation                  ``(float, 0 to 4)`` The curve to adjust the overall saturation of the frame's image (0.0 = greyscale, 1.0 = normal, 2.0 = double saturation)
   saturation_B                ``(float, 0 to 4)`` The curve to adjust blue saturation of the frame's image
   saturation_G                ``(float, 0 to 4)`` The curve to adjust green saturation of the frame's image (0.0 = greyscale, 1.0 = normal, 2.0 = double saturation)
   saturation_R                ``(float, 0 to 4)`` The curve to adjust red saturation of the frame's image
   ==========================  ============

Color Shift
^^^^^^^^^^^
Shift the colors of an image up, down, left, and right (with infinite wrapping).

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   alpha_x                     ``(float, -1 to 1)`` Shift the Alpha X coordinates (left or right)
   alpha_y                     ``(float, -1 to 1)`` Shift the Alpha Y coordinates (up or down)
   blue_x                      ``(float, -1 to 1)`` Shift the Blue X coordinates (left or right)
   blue_y                      ``(float, -1 to 1)`` Shift the Blue Y coordinates (up or down)
   green_x                     ``(float, -1 to 1)`` Shift the Green X coordinates (left or right)
   green_y                     ``(float, -1 to 1)`` Shift the Green Y coordinates (up or down)
   red_x                       ``(float, -1 to 1)`` Shift the Red X coordinates (left or right)
   red_y                       ``(float, -1 to 1)`` Shift the Red Y coordinates (up or down)
   ==========================  ============

Crop
^^^^
Crop out any part of your video.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   bottom                      ``(float, 0 to 1)`` Size of bottom bar
   left                        ``(float, 0 to 1)`` Size of left bar
   right                       ``(float, 0 to 1)`` Size of right bar
   top                         ``(float, 0 to 1)`` Size of top bar
   x                           ``(float, -1 to 1)`` X-offset
   y                           ``(float, -1 to 1)`` Y-offset
   ==========================  ============

Deinterlace
^^^^^^^^^^^
Remove interlacing from a video (i.e. even or odd horizontal lines)

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   isOdd                       ``(bool, choices: ['Yes', 'No'])`` Use odd or even lines
   ==========================  ============

Hue
^^^
Adjust the hue / color of the frame's image.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   hue                         ``(float, 0 to 1)`` The curve to adjust the percentage of hue shift
   ==========================  ============

Negative
^^^^^^^^
Negates the colors, producing a negative of the image.

Object Detector
^^^^^^^^^^^^^^^
Detect objects through the video.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   class_filter                ``(string)`` Type of object class to filter (i.e. car, person)
   confidence_threshold        ``(float, 0 to 1)`` Minimum confidence value to display the detected objects
   display_box_text            ``(int, choices: ['Off', 'On'])`` Draw a rectangle around detected objects
   objects                     ``(list)`` List of detected object ids
   selected_object_index       ``(int, 0 to 200)`` Index of the tracked object that was selected to modify its properties
   ==========================  ============

Pixelate
^^^^^^^^
Pixelate (increase or decrease) the number of visible pixels.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   bottom                      ``(float, 0 to 1)`` The curve to adjust the bottom margin size
   left                        ``(float, 0 to 1)`` The curve to adjust the left margin size
   pixelization                ``(float, 0 to 0.99)`` The curve to adjust the amount of pixelization
   right                       ``(float, 0 to 1)`` The curve to adjust the right margin size
   top                         ``(float, 0 to 1)`` The curve to adjust the top margin size
   ==========================  ============

Shift
^^^^^
Shift the image up, down, left, and right (with infinite wrapping).

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   x                           ``(float, -1 to 1)`` Shift the X coordinates (left or right)
   y                           ``(float, -1 to 1)`` Shift the Y coordinates (up or down)
   ==========================  ============

Stabilizer
^^^^^^^^^^
Stabilize video clip to remove undesired shaking and jitter.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   zoom                        ``(float, 0 to 2)`` Percentage to zoom into the clip, to crop off the shaking and uneven edges
   ==========================  ============

Tracker
^^^^^^^
Track the selected bounding box through the video. The tracked object can be selected as a parent on other clips.

Wave
^^^^
Distort the frame's image into a wave pattern.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   amplitude                   ``(float, 0 to 5)`` The height of the wave
   multiplier                  ``(float, 0 to 10)`` Amount to multiply the wave (make it bigger)
   shift_x                     ``(float, 0 to 1000)`` Amount to shift X-axis
   speed_y                     ``(float, 0 to 300)`` Speed of the wave on the Y-axis
   wavelength                  ``(float, 0 to 3)`` The length of the wave
   ==========================  ============

Audio Effects
-------------

Audio effects modify the waveforms and audio sample data of a clip. Below is a list of audio effects, and
their properties. Often it is best to experiment with an effect, entering different values into the properties,
and observing the results.

Compressor
^^^^^^^^^^
Reduce the volume of loud sounds or amplify quiet sounds.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   attack                      ``(float, 0.1 to 100)``
   bypass                      ``(bool)``
   makeup_gain                 ``(float, -12 to 12)``
   ratio                       ``(float, 1 to 100)``
   release                     ``(float, 10 to 1000)``
   threshold                   ``(float, -60 to 0)``
   ==========================  ============

Delay
^^^^^
Adjust the synchronism between the audio and video track.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   delay_time                  ``(float, 0 to 5)``
   ==========================  ============

Distortion
^^^^^^^^^^
Alter the audio by clipping the signal.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   distortion_type             ``(int, choices: ['Hard Clipping', 'Soft Clipping', 'Exponential', 'Full Wave Rectifier', 'Half Wave Rectifier'])``
   input_gain                  ``(int, -24 to 24)``
   output_gain                 ``(int, -24 to 24)``
   tone                        ``(int, -24 to 24)``
   ==========================  ============

Echo
^^^^
Reflection of sound with a delay after the direct sound.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   echo_time                   ``(float, 0 to 5)``
   feedback                    ``(float, 0 to 1)``
   mix                         ``(float, 0 to 1)``
   ==========================  ============

Expander
^^^^^^^^
Louder parts of audio becomes relatively louder and quieter parts becomes quieter.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   attack                      ``(float, 0.1 to 100)``
   bypass                      ``(bool)``
   makeup_gain                 ``(float, -12 to 12)``
   ratio                       ``(float, 1 to 100)``
   release                     ``(float, 10 to 1000)``
   threshold                   ``(float, -60 to 0)``
   ==========================  ============

Noise
^^^^^
Random signal having equal intensity at different frequencies.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   level                       ``(int, 0 to 100)``
   ==========================  ============

Parametric EQ
^^^^^^^^^^^^^
Filter that allows you to adjust the volume level of a frequency in the audio track.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   filter_type                 ``(int, choices: ['Low Pass', 'High Pass', 'Low Shelf', 'High Shelf', 'Band Pass', 'Band Stop', 'Peaking Notch'])``
   frequency                   ``(int, 20 to 20000)``
   gain                        ``(int, -24 to 24)``
   q_factor                    ``(float, 0 to 20)``
   ==========================  ============

Robotization
^^^^^^^^^^^^
Transform the voice present in an audio track into a robotic voice effect.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   fft_size                    ``(int, choices: ['128', '256', '512', '1024', '2048'])``
   hop_size                    ``(int, choices: ['1/2', '1/4', '1/8'])``
   window_type                 ``(int, choices: ['Rectangular', 'Bart Lett', 'Hann', 'Hamming'])``
   ==========================  ============

Whisperization
^^^^^^^^^^^^^^
Transform the voice present in an audio track into a whispering voice effect.

.. table::
   :widths: 26

   ==========================  ============
   Name                        Description
   ==========================  ============
   fft_size                    ``(int, choices: ['128', '256', '512', '1024', '2048'])``
   hop_size                    ``(int, choices: ['1/2', '1/4', '1/8'])``
   window_type                 ``(int, choices: ['Rectangular', 'Bart Lett', 'Hann', 'Hamming'])``
   ==========================  ============

For more info on key frames and animation, see :ref:`animation_ref`.
