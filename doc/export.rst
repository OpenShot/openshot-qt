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

Export
======

Exporting converts your OpenShot project (clips, effects, animations, titles) into a single video output
file (using a process called ``video encoding``). By using the default settings, the exported video will be compatible
with most media players (such as VLC) and websites (such as YouTube, Vimeo, Facebook) and creates a
``MP4 (h.264 + AAC)`` formatted video file. See :ref:`profiles_mp4_h264_ref`.

Click on the :guilabel:`Export Video` icon at the top of the screen (or use the :guilabel:`File→Export Video` menu).
The default values will work fine, so just click the :guilabel:`Export Video` button to render your
new video. You can also create your own custom export profiles, see :ref:`profiles_ref`.

Simple Mode
-----------

While video encoding is very complicated, with dozens of interrelated settings and options, OpenShot
makes it easy, with sensible defaults, and most of this complexity hidden away behind our `Simple` tab,
which is the default export view.

.. image:: images/export-simple.jpg

.. table::
   :widths: 10 30

   ==================  ============
   Simple Setting      Description
   ==================  ============
   Profile             Common presets (combinations of presets and video profiles grouped by category, for example: **Web**)
   Target              Target presets related to the current profile (collections of common formats, codecs, and quality settings, see :ref:`preset_list_ref`)
   Video Profile       Video profiles related to the current target (collections of common size, frame rate, and aspect ratios, see :ref:`profile_list_ref` or create your own :ref:`profiles_ref`)
   Quality             Quality settings (low, med, high), which relate to various video and audio bitrates.
   ==================  ============

Advanced Mode
-------------

Most users will never need to switch to the `Advanced` tab, but if you need to customize any of the
video encoding settings, for example, custom bitrates, different codecs, or limiting the range of frames
exported, this is the tab for you.

Advanced Options
^^^^^^^^^^^^^^^^

.. image:: images/export-advanced.jpg

.. table::
   :widths: 10 30

   =======================  ============
   Advanced Setting         Description
   =======================  ============
   Export To                Export both `video & audio`, `only audio`, `only video`, or an `image sequence`
   Start Frame              The first frame to export (default is 1)
   End Frame                The final frame to export (default is the last frame in your project to contain a clip)
   Start at First Clip      This checkbox will toggle the **Start Frame** between `0.0` and the `start` of the first clip/transition position.
   End at Last Clip         This checkbox will toggle the **End Frame** between the `end` of the furthest clip/transition and the full `project duration`. The project duration can be adjusted by dragging the right edge of any track. You will need to zoom out (:guilabel:`Ctrl+Scroll Wheel`) of the timeline before you can drag the right edge of a track.
   =======================  ============

Profile
^^^^^^^

A video profile is a collection of common video settings (*size, frame rate, aspect ratio*). Profiles are used
during editing, previewing, and exporting to provide a quick way to switch between common combinations of
these settings. The :guilabel:`Export Dialog` will **default** to the same profile used by the project.

*NOTE: It is important to choose a **Profile** with the same **aspect ratio** used when editing your project. If
you are exporting at a **different aspect ratio**, it might stretch the image, crop the image, add black bars, or otherwise
introduce an issue which changes the exported video, making it appear differently than the :guilabel:`Preview` inside
OpenShot.*

.. image:: images/export-advanced-profile.jpg

.. table::
   :widths: 10 80

   ==================  =============================================================================
   Profile Setting     Description
   ==================  =============================================================================
   Profile             The video profile to use during export (collection of size, frame rate, and aspect ratios, see :ref:`profile_list_ref`)
   Width               The width of the video export (in pixels)
   Height              The height of the video export (in pixels)
   Aspect Ratio        The aspect ratio of the final exported video. 1920×1080 reduces to 16:9. This also takes into account the pixel ratio, for example 2:1 rectangular pixels will affect the aspect ratio.
   Pixel Ratio         The ratio representing pixel shape. Most video profiles use a 1:1 square pixel shape, but others will use rectangular pixels.
   Frame Rate          The frequency that the frames will be displayed at.
   Interlaced          Is this format used on alternating scan lines (i.e. broadcast and analog formats)
   Spherical           When enabled, injects spherical 360° metadata (SV3D atom) into the exported file so compatible players immediately recognize it as a 360° video.
   ==================  =============================================================================

Image Sequence Settings
^^^^^^^^^^^^^^^^^^^^^^^

.. image:: images/export-advanced-image-seq.jpg

.. table::
   :widths: 10 30

   ==================  ============
   Image Setting Name  Description
   ==================  ============
   Image Format        The string format that represents the output file name in a sequence of images. For example, %05d.png would pad a number with 5 digits: 00001.png, 00002.png.
   ==================  ============

Video Settings
^^^^^^^^^^^^^^

.. image:: images/export-advanced-video.jpg

.. table::
   :widths: 10 30

   ==================  ============
   Video Setting Name  Description
   ==================  ============
   Video Format        The name of the container format (``mp4``, ``mov``, ``avi``, ``webm``, etc...)
   Video Codec         The name of the video codec used during video encoding (``libx264``, ``mpeg4``, ``libaom-av1``, etc...)
   Bit Rate / Quality  The bitrate to use for video encoding. Accepts the following formats: ``5 Mb/s``, ``96 kb/s``, ``23 crf``, etc...
   ==================  ============

Audio Settings
^^^^^^^^^^^^^^

.. image:: images/export-advanced-audio.jpg

.. table::
   :widths: 10 30

   ==================  ============
   Audio Setting Name  Description
   ==================  ============
   Audio Codec         The name of the audio codec used during audio encoding (``aac``, ``mp2``, ``libmp3lame``, etc...)
   Sample Rate         The number of audio samples per second. Common values are ``44100`` and ``48000``.
   Channel Layout      The number and layout of audio channels (``Stereo``, ``Mono``, ``Surround``, etc...)
   Bit Rate / Quality  The bitrate to use for audio encoding. Accepts the following formats: ``96 kb/s``, ``128 kb/s``, ``192 kb/s``, etc...
   ==================  ============

.. _export_complete_ref:

Export Complete
---------------

When an export finishes, a :guilabel:`Complete` tab opens in the Export window (unless
:guilabel:`Show Export Dialog when Finished` is turned off in :ref:`preferences_ref`). It shows where
the file was saved, with a button to copy its path, along with a summary of the export: format,
resolution, quality, file size, duration, and how long the export took.

* :guilabel:`Watch Video` opens the exported file in your default video player (:guilabel:`Play Audio`
  for audio-only exports).
* :guilabel:`Open Containing Folder` opens your file manager with the exported file selected.

The `Simple` and `Advanced` tabs are still available, but read-only, so you can review exactly which
settings were used. Click :guilabel:`Done` to close the window.

If an export fails, an :guilabel:`Export Failed` tab explains what went wrong. :guilabel:`Copy Error Details`
copies the error and export settings (helpful when reporting a problem), and :guilabel:`Try Again` reopens
the Export window with the same settings.

A successful export also fires a burst of confetti. Use the :guilabel:`Celebrate Exports` preference to
show it on the first export only (the default), on every export, or never.

.. _export_social_media_ref:

Social Media Quick Reference
-----------------------------

The table below shows the recommended :guilabel:`Target` and :guilabel:`Video Profile` settings for common
social media platforms. Select these in the **Simple** tab of the Export dialog.

.. list-table::
   :widths: 20 22 30 28
   :header-rows: 1

   * - Platform
     - Target
     - Video Profile
     - Notes
   * - YouTube (landscape)
     - ``YouTube``
     - ``FHD 1080p 30 fps``
     - Use ``YouTube (4K)`` for 4K
   * - YouTube Shorts (vertical)
     - ``YouTube Shorts``
     - ``FHD Vertical 1080p 30 fps``
     - Up to 60 fps
   * - TikTok (vertical)
     - ``TikTok``
     - ``FHD Vertical 1080p 30 fps``
     - Up to 60 fps
   * - Instagram Reels (vertical)
     - ``Instagram Reels``
     - ``FHD Vertical 1080p 30 fps``
     - Up to 60 fps
   * - Instagram (landscape/square)
     - ``Instagram``
     - ``FHD 1080p 30 fps``
     - Square (1:1) also available
   * - Snapchat (vertical)
     - ``Snapchat``
     - ``FHD Vertical 1080p 30 fps``
     - Up to 60 fps
   * - Facebook
     - ``Facebook``
     - ``FHD 1080p 30 fps``
     - Square and vertical also available
   * - LinkedIn (landscape)
     - ``LinkedIn``
     - ``FHD 1080p 30 fps``
     - Square and 4:5 portrait also available
   * - Twitter / X
     - ``Twitter / X``
     - ``FHD 1080p 30 fps``
     - Vertical also available
   * - Vimeo
     - ``Vimeo``
     - ``FHD 1080p 30 fps``
     - Use High quality setting

.. _export_hardware_accel_ref:

Hardware-Accelerated Export
----------------------------

OpenShot supports GPU-accelerated video encoding on supported hardware, dramatically reducing export times.
Hardware-accelerated targets are shown with a badge in the :guilabel:`Target` dropdown. Select the
appropriate target for your hardware:

.. table::
   :widths: 35 20 45

   =====================================  ============  =============================================
   Target (Export Dialog)                 Badge         Requires
   =====================================  ============  =============================================
   ``MP4 (h.264 nv)``                     NVENC         NVIDIA GPU (Kepler or newer)
   ``MP4 (h.264 va)``                     VA-API        Linux with AMD or Intel GPU (VAAPI driver)
   ``MP4 (h.264 qsv)``                    QSV           Intel GPU with Quick Sync Video
   ``MP4 (h.264 videotoolbox)``           VideoToolbox  macOS with Apple or Intel GPU
   ``MP4 (h.264 dx)``                     DirectX       Windows with DirectX-compatible GPU
   ``MP4 (HEVC va)``                      VA-API        Linux VA-API — produces smaller HEVC files
   =====================================  ============  =============================================

MKV variants (``MKV (h.264 nv)``, ``MKV (h.264 va)``, etc.) are also available for each accelerator.
If none of these targets appear or export fails, your system either lacks the required driver or the
hardware encoder is not supported — fall back to the standard ``MP4 (h.264 + AAC)`` target, which uses
the CPU-based ``libx264`` encoder and works on all systems.
