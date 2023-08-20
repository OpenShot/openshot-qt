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
and can generally enhance your video projects. Each effect has its own set of properties, most of which can be animated
over time.

Effects can be added to any clip by dragging and dropping them from the Effects tab onto a clip. Each effect is
represented by a small colored icon and the first letter of the effect name. To view an effect's properties,
right-click on the effect icon, revealing the context menu, and choose :guilabel:`Properties`. The property
editor will appear, where you can edit these properties. Note: Pay close attention to where the play-head
(i.e. red playback line) is. Key frames are automatically created at the current playback position,
to help create animations quickly.

.. image:: images/clip-effects.jpg

List of Effects
---------------
OpenShot Video Editor has a total of 27 built-in video and audio effects: 18 video effects and 9 audio effects.
These effects can be added to a clip by dragging the effect onto a clip. The following table contains
the name and short description of each effect.

.. table::
   :widths: 30 80

   =============================  ===============
   Effect Name                    Effect Description
   =============================  ===============
   Alpha Mask / Wipe Transition   Grayscale mask transition between images.
   Bars                           Add colored bars around your video.
   Blur                           Adjust image blur.
   Brightness & Contrast          Modify frame's brightness and contrast.
   Caption                        Add text captions to any clip.
   Chroma Key (Greenscreen)       Replace color with transparency.
   Color Saturation               Adjust color intensity.
   Color Shift                    Shift image colors in various directions.
   Crop                           Crop out parts of your video.
   Deinterlace                    Remove interlacing from video.
   Hue                            Adjust hue / color.
   Negative                       Produce a negative image.
   Object Detector                Detect objects in video.
   Pixelate                       Increase or decrease visible pixels.
   Shift                          Shift image in different directions.
   Stabilizer                     Reduce video shake.
   Tracker                        Track bounding box in video.
   Wave                           Distort image into a wave pattern.
   Compressor                     Reduce loudness or amplify quiet sounds.
   Delay                          Adjust audio-video synchronism.
   Distortion                     Clip audio signal for distortion.
   Echo                           Add delayed sound reflection.
   Expander                       Make loud parts relatively louder.
   Noise                          Add random equal-intensity signals.
   Parametric EQ                  Adjust frequency volume in audio.
   Robotization                   Transform audio into robotic voice.
   Whisperization                 Transform audio into whispers.
   =============================  ===============

Sequencing
----------

Effects are normally applied **before** the Clip processes keyframes. This allows the effect to process the raw image of
the clip, before the clip applies properties such as scaling, rotation, location, etc... Normally, this is the preferred
sequence of events, and this is the default behavior of effects in OpenShot. However, you can optionally override this
behavior with the ``Apply Before Clip Keyframes`` property.

If you set the ``Apply Before Clip Keyframes`` property to ``No``, the effect will be sequenced **after** the clip scales, rotates,
and applies keyframes to the image. This can be useful on certain effects, such as the **Mask** effect, when you want
to animate a clip first and then apply a static mask to the clip.

.. _effect_parent_ref:

Effect Parent
-------------
The :guilabel:`Parent` property of an effect sets the initial keyframe values to a parent effect. For example, if many effects all point to the 
same parent effect, they will inherit all their initial properties, such as font size, font color, and background color for a ``Caption`` effect.
In the example of many ``Caption`` effects using the same Parent effect, it is an efficient way to manage a large number of these effects. 

NOTE: The ``parent`` property for effects should be linked to the **same type** of parent effect, otherwise their defaut initial values
will not match. Also see :ref:`clip_parent_ref`.

Video Effects
-------------

Effects are generally divided into two categories: video and audio effects. Video effects modify the image and pixel
data of a clip. Below is a list of video effects, and their properties. Often it is best to experiment with an effect,
entering different values into the properties, and observing the results.

Alpha Mask / Wipe Transition
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Uses a grayscale mask image to gradually wipe / transition between 2 images (only affects the image, and not the audio track)

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   brightness                  ``(float, -1 to 1)`` This curve controls the motion across the wipe
   contrast                    ``(float, 0 to 20)`` This curve controls the hardness and softness of the wipe edge
   reader                      ``(reader)`` This reader can use any image or video as input for your grayscale wipe
   replace_image               ``(bool, choices: ['Yes', 'No'])`` Replace the clips image with the current grayscale wipe image, useful for troubleshooting
   ==========================  ============

Bars
^^^^
Add colored bars around your video.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
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
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   horizontal_radius           ``(float, 0 to 100)`` Horizontal blur radius keyframe. The size of the horizontal blur operation in pixels.
   iterations                  ``(float, 0 to 100)`` Iterations keyframe. The # of blur iterations per pixel. 3 iterations = Gaussian.
   sigma                       ``(float, 0 to 100)`` Sigma keyframe. The amount of spread in the blur operation. Should be larger than radius.
   vertical_radius             ``(float, 0 to 100)`` Vertical blur radius keyframe. The size of the vertical blur operation in pixels.
   ==========================  ============

Brightness & Contrast
^^^^^^^^^^^^^^^^^^^^^
Adjust the brightness and contrast of the frame's image.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   brightness                  ``(float, -1 to 1)`` The curve to adjust the brightness
   contrast                    ``(float, 0 to 100)`` The curve to adjust the contrast (3 is typical, 20 is a lot, 100 is max. 0 is invalid)
   ==========================  ============

Caption
^^^^^^^
Add text captions on top of your video. We support both VTT (WebVTT) and SubRip (SRT) subtitle file formats. These
formats are used to display captions or subtitles in videos. They allow you to add text-based subtitles to video content,
making it more accessible to a wider audience, especially for those who are deaf or hard of hearing. The Caption
effect can even animate the text fading in/out, and supports any font, size, color, and margin. OpenShot also has an
easy-to-use Caption editor, where you can quickly insert captions at the playhead position, or edit all your caption
text in one place.

.. code-block:: console
   :caption: Show a caption, starting at 5 seconds and ending at 10 seconds.

   00:00:05.000 --> 00:00:10.000
   Hello, welcome to our video!

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
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
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   color                       ``(color)`` The color to match
   fuzz                        ``(float, 0 to 125)`` The fuzz factor (or threshold)
   halo                        ``(float, 0 to 125)`` The additional threshold for halo elimination.
   keymethod                   ``(int, choices: ['Basic keying', 'HSV/HSL hue', 'HSV saturation', 'HSL saturation', 'HSV value', 'HSL luminance', 'LCH luminosity', 'LCH chroma', 'LCH hue', 'CIE Distance', 'Cb,Cr vector'])`` The keying method or algorithm to use.
   ==========================  ============

Color Saturation
^^^^^^^^^^^^^^^^
Adjust the color saturation.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   saturation                  ``(float, 0 to 4)`` The curve to adjust the overall saturation of the frame's image (0.0 = greyscale, 1.0 = normal, 2.0 = double saturation)
   saturation_B                ``(float, 0 to 4)`` The curve to adjust blue saturation of the frame's image
   saturation_G                ``(float, 0 to 4)`` The curve to adjust green saturation of the frame's image (0.0 = greyscale, 1.0 = normal, 2.0 = double saturation)
   saturation_R                ``(float, 0 to 4)`` The curve to adjust red saturation of the frame's image
   ==========================  ============

Color Shift
^^^^^^^^^^^
Shift the colors of an image up, down, left, and right (with infinite wrapping).

**Each pixel has 4 color channels:**

- Red, Green, Blue, and Alpha (i.e. transparency)
- Each channel value is between 0 and 255

The Color Shift effect simply "moves" or "translates" a specific color channel on the X or Y axis. *Not all video and
image formats support an alpha channel, and in those cases, you will not see any changes when adjusting the color
shift of the alpha channel.*

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   alpha_x                     ``(float, -1 to 1)`` Shift the Alpha X coordinates (left or right)
   alpha_y                     ``(float, -1 to 1)`` Shift the Alpha Y coordinates (up or down)
   blue_x                      ``(float, -1 to 1)`` Shift the Blue X coordinates (left or right)
   blue_y                      ``(float, -1 to 1)`` Shift the Blue Y coordinates (up or down)
   green_x                     ``(float, -1 to 1)`` Shift the Green X coordinates (left or right)
   green_y                     ``(float, -1 to 1)`` Shift the Green Y coordinates (up or down)
   red_x                       ``(float, -1 to 1)`` Shift the Red X coordinates (left or right)
   red_y                       ``(float, -1 to 1)`` Shift the Red Y coordinates (up or down)
   ==========================  ============

.. _effects_crop_ref:

Crop
^^^^
Crop out any part of a video clip. This effect is the primary method for cropping a Clip in OpenShot. The ``left``, ``right``,
``top``, and ``bottom`` key-frames can even be animated, for a moving and resizing cropped area. You can leave the cropped area
blank, or you can dynamically resize the cropped area to fill the screen.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   bottom                      ``(float, 0 to 1)`` Size of bottom bar
   left                        ``(float, 0 to 1)`` Size of left bar
   right                       ``(float, 0 to 1)`` Size of right bar
   top                         ``(float, 0 to 1)`` Size of top bar
   x                           ``(float, -1 to 1)`` X-offset
   y                           ``(float, -1 to 1)`` Y-offset
   resize                      ``(bool, choices: ['Yes', 'No'])`` Replace the frame image with the cropped area (allows automatic scaling of the cropped image)
   ==========================  ============

Deinterlace
^^^^^^^^^^^
Remove interlacing from a video (i.e. even or odd horizontal lines)

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   isOdd                       ``(bool, choices: ['Yes', 'No'])`` Use odd or even lines
   ==========================  ============

Hue
^^^
Adjust the hue / color of the frame's image.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   hue                         ``(float, 0 to 1)`` The curve to adjust the percentage of hue shift
   ==========================  ============

Negative
^^^^^^^^
Negates the colors, producing a negative of the image.

Object Detector
^^^^^^^^^^^^^^^
Detect objects through the video.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
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
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
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
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   x                           ``(float, -1 to 1)`` Shift the X coordinates (left or right)
   y                           ``(float, -1 to 1)`` Shift the Y coordinates (up or down)
   ==========================  ============

Stabilizer
^^^^^^^^^^
Stabilize video clip to remove undesired shaking and jitter.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   zoom                        ``(float, 0 to 2)`` Percentage to zoom into the clip, to crop off the shaking and uneven edges
   ==========================  ============

Tracker
^^^^^^^
Track the selected bounding box through the video. The tracked object can be selected as a parent on other clips. See :ref:`clip_parent_ref`.

Wave
^^^^
Distort the frame's image into a wave pattern.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
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
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
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
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   delay_time                  ``(float, 0 to 5)``
   ==========================  ============

Distortion
^^^^^^^^^^
Alter the audio by clipping the signal.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   distortion_type             ``(int, choices: ['Hard Clipping', 'Soft Clipping', 'Exponential', 'Full Wave Rectifier', 'Half Wave Rectifier'])``
   input_gain                  ``(int, -24 to 24)``
   output_gain                 ``(int, -24 to 24)``
   tone                        ``(int, -24 to 24)``
   ==========================  ============

Echo
^^^^
Reflection of sound with a delay after the direct sound.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   echo_time                   ``(float, 0 to 5)``
   feedback                    ``(float, 0 to 1)``
   mix                         ``(float, 0 to 1)``
   ==========================  ============

Expander
^^^^^^^^
Louder parts of audio become relatively louder and quieter parts become quieter.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
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
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   level                       ``(int, 0 to 100)``
   ==========================  ============

Parametric EQ
^^^^^^^^^^^^^
Filter that allows you to adjust the volume level of a frequency in the audio track.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   filter_type                 ``(int, choices: ['Low Pass', 'High Pass', 'Low Shelf', 'High Shelf', 'Band Pass', 'Band Stop', 'Peaking Notch'])``
   frequency                   ``(int, 20 to 20000)``
   gain                        ``(int, -24 to 24)``
   q_factor                    ``(float, 0 to 20)``
   ==========================  ============

Robotization
^^^^^^^^^^^^
Transform the voice present in an audio track into a robotic voice effect.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   fft_size                    ``(int, choices: ['128', '256', '512', '1024', '2048'])``
   hop_size                    ``(int, choices: ['1/2', '1/4', '1/8'])``
   window_type                 ``(int, choices: ['Rectangular', 'Bart Lett', 'Hann', 'Hamming'])``
   ==========================  ============

Whisperization
^^^^^^^^^^^^^^
Transform the voice present in an audio track into a whispering voice effect.

.. table::
   :widths: 26 80

   ==========================  ============
   Property Name               Description
   ==========================  ============
   apply_before_clip           ``(bool, choices: ['Yes', 'No'])`` Apply this effect before the Clip processes keyframes? (default is Yes)
   fft_size                    ``(int, choices: ['128', '256', '512', '1024', '2048'])``
   hop_size                    ``(int, choices: ['1/2', '1/4', '1/8'])``
   window_type                 ``(int, choices: ['Rectangular', 'Bart Lett', 'Hann', 'Hamming'])``
   ==========================  ============

For more info on key frames and animation, see :ref:`animation_ref`.
