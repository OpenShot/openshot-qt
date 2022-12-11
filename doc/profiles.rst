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

.. _profiles_ref:

Profiles
========

A video profile is a collection of common video settings (*size, frame rate, aspect ratio*). Profiles are used
during editing, previewing, and exporting to provide a quick way to switch between common combinations of
these settings.

If you often use the same profile, you can set a default profile:
:guilabel:`Edit→Preferences→Preview`.

Project Profile
---------------

The project profile is used when previewing your project and editing. The default project profile is ``HD 720p 30fps``.
It is best practice to always switch to your target profile before you begin editing. For example, if you are targeting
1080p 30fps, switch to that profile before you begin editing your project. For a full list of included profiles
see :ref:`profile_list_ref`.

.. image:: images/profiles.jpg

==  ==================  ============
#   Name                Description
==  ==================  ============
1   Title Bar           The title bar of OpenShot displays the current profile
2   Profile Button      Launch the profiles dialog
3   Choose Profile      Select a profile for editing and preview
==  ==================  ============

Export Profile
--------------

The export profile always defaults to your current project profile, but can be changed to target different profiles.

.. image:: images/export-profiles.jpg

==  ==================  ============
#   Name                Description
==  ==================  ============
1   Choose Profile      Select a profile for export
==  ==================  ============

Custom Profile
--------------
Although OpenShot has more than 70 profiles (:ref:`profile_list_ref`) included in OpenShot, you can also create
your own custom profiles. Create a new file in the ``~/.openshot_qt/profiles/`` or
``C:\Users\USERNAME\.openshot_qt\profiles`` folder. Use the following text as your template (i.e. copy and
paste this into the new file):

.. code-block:: python

    description=Custom Profile Name
    frame_rate_num=30000
    frame_rate_den=1001
    width=1280
    height=720
    progressive=1
    sample_aspect_num=1
    sample_aspect_den=1
    display_aspect_num=16
    display_aspect_den=9

.. table::
   :widths: 24 60

   ======================  ============
   Profile Property        Description
   ======================  ============
   description             The friendly name of the profile (this is what OpenShot displays in the user interface)
   frame_rate_num          The frame rate numerator. All frame rates are expressed as fractions. For example, ``30 FPS == 30/1``.
   frame_rate_den          The frame rate denominator. All frame rates are expressed as fractions. For example, ``29.97 FPS == 30,000/1001``.
   width                   The number of horizontal pixels in the image. By reversing the values for `width` and `height`, you can create a vertical profile.
   height                  The number of vertical pixels in the image
   progressive             ```(0 or 1)``` If 1, both even and odd rows of pixels are used. If 0, only odd or even rows of pixels are used.
   sample_aspect_num       The numerator of the **SAR** (sample/pixel shape aspect ratio), ``1:1`` ratio would represent a square pixel, ``2:1`` ratio would represent a ``2x1`` rectangle pixel shape, etc...
   sample_aspect_den       The denominator of the **SAR** (sample/pixel shape aspect ratio)
   display_aspect_num      The numerator of the **DAR** (display aspect ratio), ``(width/height) X (sample aspect ratio)``. This is the final ratio of the image displayed on screen, reduced to the smallest fraction possible (common ratios are 16:9 for wide formats, 4:3 for legacy television formats).
   display_aspect_den      The denominator of the **DAR** (display aspect ratio)
   ======================  ============

Once you restart OpenShot, you will see your custom profile appear in the list of Profiles.

.. _preset_list_ref:

Preset List
-----------

OpenShot includes a large list of common profiles and their associated video export settings (``video codec``,
``audio codec``, ``audio channels``, ``audio sample rate``, etc...), which targets specific websites and devices.

All Formats
^^^^^^^^^^^

AVI (h.264)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             avi
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

AVI (mpeg2)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             avi
   Video Codec              mpeg2video
   Audio Codec              mp2
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

AVI (mpeg4)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             avi
   Video Codec              mpeg4
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

GIF (animated)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             gif
   Video Codec              gif
   Audio Codec              N/A
   Audio Channels           N/A
   Audio Channel Layout     N/A
   Sample Rate              N/A
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      N/A
   Audio Bitrate (med)      N/A
   Audio Bitrate (high)     N/A
   Profiles                 All
   =======================  ============

MKV (av1)
~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              libaom-av1
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      50 crf
   Video Bitrate (med)      23 crf
   Video Bitrate (high)     1 crf
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MKV (h.264 dx)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              h264_dxva2
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MKV (h.264 nv)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              h264_nvenc
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MKV (h.264 qsv)
~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              h264_qsv
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MKV (h.264 videotoolbox)
~~~~~~~~~~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              h264_videotoolbox
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MKV (h.264)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MKV (h.265)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              libx265
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      50 crf
   Video Bitrate (med)      23 crf
   Video Bitrate (high)     0 crf
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MOV (h.264)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mov
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MOV (mpeg2)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mov
   Video Codec              mpeg2video
   Audio Codec              mp2
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MOV (mpeg4)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mov
   Video Codec              mpeg4
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP3 (audio only)
~~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp3
   Video Codec              N/A
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      N/A
   Video Bitrate (med)      N/A
   Video Bitrate (high)     N/A
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (AV1 rav1e)
~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              librav1e
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      200 qp
   Video Bitrate (med)      100 qp
   Video Bitrate (high)     50 qp
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (AV1 svt)
~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libsvtav1
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      60 qp
   Video Bitrate (med)      50 qp
   Video Bitrate (high)     30 qp
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (HEVC va)
~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              hevc_vaapi
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (Xvid)
~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libxvid
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.264 dx)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              h264_dxva2
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.264 nv)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              h264_nvenc
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.264 qsv)
~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              h264_qsv
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.264 va)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              h264_vaapi
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.264 va)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mkv
   Video Codec              h264_vaapi
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.264 videotoolbox)
~~~~~~~~~~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              h264_videotoolbox
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.264)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (h.265)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx265
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      50 crf
   Video Bitrate (med)      23 crf
   Video Bitrate (high)     0 crf
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MP4 (mpeg4)
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              mpeg4
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

MPEG (mpeg2)
~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mpeg
   Video Codec              mpeg2video
   Audio Codec              mp2
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

OGG (theora/flac)
~~~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             ogg
   Video Codec              libtheora
   Audio Codec              flac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

OGG (theora/vorbis)
~~~~~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             ogg
   Video Codec              libtheora
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

WEBM (AV1 aom)
~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             webm
   Video Codec              libaom-av1
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      50 crf
   Video Bitrate (med)      35 crf
   Video Bitrate (high)     10 crf
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

WEBM (vp9)
~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             webm
   Video Codec              libvpx-vp9
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      50 crf
   Video Bitrate (med)      30 crf
   Video Bitrate (high)     5 crf
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

WEBM (vp9) lossless
~~~~~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             webm
   Video Codec              libvpx-vp9
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      50 crf
   Video Bitrate (med)      23 crf
   Video Bitrate (high)     0 crf
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

WEBM (vpx)
~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             webm
   Video Codec              libvpx
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

WEBP (vp9 va)
~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             webm
   Video Codec              vp9_vaapi
   Audio Codec              libopus
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

Device
^^^^^^

Apple TV
~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (high)     5 Mb/s
   Audio Bitrate (high)     256 kb/s
   Profiles                 HD 720p 30 fps
   =======================  ============

Chromebook
~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             webm
   Video Codec              libvpx
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 All
   =======================  ============

Nokia nHD
~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             avi
   Video Codec              libxvid
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      1 Mb/s
   Video Bitrate (med)      3 Mb/s
   Video Bitrate (high)     5 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 Mobile 360p
   =======================  ============

Xbox 360
~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             avi
   Video Codec              libxvid
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      2 Mb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     8 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 | DV/DVD Widescreen NTSC
                            | HD 1080p 29.97 fps
                            | HD 720p 29.97 fps
   =======================  ============

Web
^^^

Flickr-HD
~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mov
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 | HD 1080p 25 fps
                            | HD 1080p 29.97 fps
                            | HD 720p 25 fps
                            | HD 720p 29.97 fps
   =======================  ============

Instagram
~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      3.5 Mb/s
   Video Bitrate (high)     5.50 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 | HD 1080p 25 fps
                            | HD 1080p 30 fps
                            | HD 720p 25 fps
                            | HD 720p 30 fps
                            | HD Vertical 1080p 30 fps
                            | HD Vertical 720p 30 fps
   =======================  ============

Metacafe
~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              mpeg4
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              44100
   Video Bitrate (low)      2 Mb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     8 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 VGA NTSC
   =======================  ============

Picasa
~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              44100
   Video Bitrate (low)      2 Mb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     8 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 VGA NTSC
   =======================  ============

Twitter
~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      1.7 Mb/s
   Video Bitrate (high)     3.5 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 | HD 1080p 25 fps
                            | HD 1080p 30 fps
                            | HD 720p 25 fps
                            | HD 720p 30 fps
                            | HD Vertical 1080p 30 fps
                            | HD Vertical 720p 30 fps
   =======================  ============

Vimeo
~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      2 Mb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     8 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 | VGA NTSC
                            | VGA Widescreen NTSC
   =======================  ============

Vimeo-HD
~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      4 Mb/s
   Video Bitrate (med)      8 Mb/s
   Video Bitrate (high)     12 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 | HD 1080p 23.98 fps
                            | HD 1080p 24 fps
                            | HD 1080p 25 fps
                            | HD 1080p 29.97 fps
                            | HD 1080p 30 fps
                            | HD 720p 23.98 fps
                            | HD 720p 24 fps
                            | HD 720p 25 fps
                            | HD 720p 29.97 fps
                            | HD 720p 30 fps
   =======================  ============

Wikipedia
~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             ogg
   Video Codec              libtheora
   Audio Codec              libvorbis
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      384 kb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     15.00 Mb/s
   Audio Bitrate (low)      96 kb/s
   Audio Bitrate (med)      128 kb/s
   Audio Bitrate (high)     192 kb/s
   Profiles                 QVGA 29.97 fps
   =======================  ============

YouTube HD
~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      8 Mb/s
   Video Bitrate (med)      10 Mb/s
   Video Bitrate (high)     12 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 | HD 1080p 23.98 fps
                            | HD 1080p 24 fps
                            | HD 1080p 25 fps
                            | HD 1080p 29.97 fps
                            | HD 1080p 30 fps
                            | HD 1080p 50 fps
                            | HD 1080p 59.94 fps
                            | HD 1080p 60 fps
   =======================  ============

YouTube HD (2K)
~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      16 Mb/s
   Video Bitrate (med)      20 Mb/s
   Video Bitrate (high)     24 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 | 2.5K QHD 1440p 23.98 fps
                            | 2.5K QHD 1440p 24 fps
                            | 2.5K QHD 1440p 25 fps
                            | 2.5K QHD 1440p 29.97 fps
                            | 2.5K QHD 1440p 30 fps
                            | 2.5K QHD 1440p 50 fps
                            | 2.5K QHD 1440p 59.94 fps
                            | 2.5K QHD 1440p 60 fps
   =======================  ============

YouTube HD (4K)
~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      45 Mb/s
   Video Bitrate (med)      56 Mb/s
   Video Bitrate (high)     68 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 | 4K UHD 2160p 23.98 fps
                            | 4K UHD 2160p 24 fps
                            | 4K UHD 2160p 25 fps
                            | 4K UHD 2160p 29.97 fps
                            | 4K UHD 2160p 30 fps
                            | 4K UHD 2160p 50 fps
                            | 4K UHD 2160p 59.94 fps
                            | 4K UHD 2160p 60 fps
   =======================  ============

YouTube Standard
~~~~~~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              libmp3lame
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      2 Mb/s
   Video Bitrate (med)      5 Mb/s
   Video Bitrate (high)     8 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      256 kb/s
   Audio Bitrate (high)     320 kb/s
   Profiles                 | HD 720p 23.98 fps
                            | HD 720p 24 fps
                            | HD 720p 25 fps
                            | HD 720p 29.97 fps
                            | HD 720p 30 fps
                            | HD 720p 50 fps
                            | HD 720p 59.94 fps
                            | HD 720p 60 fps
                            | VGA NTSC
                            | VGA Widescreen NTSC
   =======================  ============

DVD
^^^

DVD-NTSC
~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             dvd
   Video Codec              mpeg2video
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      1 Mb/s
   Video Bitrate (med)      3 Mb/s
   Video Bitrate (high)     5 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      192 kb/s
   Audio Bitrate (high)     256 kb/s
   Profiles                 | DV/DVD NTSC
                            | DV/DVD Widescreen NTSC
   =======================  ============

DVD-PAL
~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             dvd
   Video Codec              mpeg2video
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      1 Mb/s
   Video Bitrate (med)      3 Mb/s
   Video Bitrate (high)     5 Mb/s
   Audio Bitrate (low)      128 kb/s
   Audio Bitrate (med)      192 kb/s
   Audio Bitrate (high)     256 kb/s
   Profiles                 | DV/DVD PAL
                            | DV/DVD Widescreen PAL
   =======================  ============

Blu-Ray/AVCHD
^^^^^^^^^^^^^

AVCHD Disks
~~~~~~~~~~~

.. table::
   :widths: 26 80

   =======================  ============
   Attribute                Description
   =======================  ============
   Video Format             mp4
   Video Codec              libx264
   Audio Codec              aac
   Audio Channels           2
   Audio Channel Layout     Stereo
   Sample Rate              48000
   Video Bitrate (low)      15 Mb/s
   Video Bitrate (high)     40 Mb/s
   Audio Bitrate (low)      256 kb/s
   Audio Bitrate (high)     256 kb/s
   Profiles                 | HD 1080i 25 fps
                            | HD 1080i 30 fps
                            | HD 1080p 25 fps
   =======================  ============

.. _profile_list_ref:

Profile List
------------

OpenShot includes a large list of common profiles.

Definitions
^^^^^^^^^^^

- **FPS**: Frames Per Second
- **DAR**: Display Aspect Ratio (i.e. 1920:1080 reduces to 16:9 aspect ratio)
- **SAR**: Sample Aspect Ratio (i.e. 1:1 ratio == square pixel, 2:1 horizontal rectangular pixel). The SAR directly affects the display aspect ratio. For example, a 4:3 video can be displayed as 16:9, if it uses rectangular pixels.

=====================================  ======  ======  ======  ======  ======  ==========
Profile Name                           Width   Height  FPS     DAR     SAR     Interlaced
=====================================  ======  ======  ======  ======  ======  ==========
1024x576 16:9 PAL                      1024    576     25.00   16:9    1:1     No
2.5K QHD 1440p 23.98 fps               2560    1440    23.98   16:9    1:1     No
2.5K QHD 1440p 24 fps                  2560    1440    24.00   16:9    1:1     No
2.5K QHD 1440p 25 fps                  2560    1440    25.00   16:9    1:1     No
2.5K QHD 1440p 29.97 fps               2560    1440    29.97   16:9    1:1     No
2.5K QHD 1440p 30 fps                  2560    1440    30.00   16:9    1:1     No
2.5K QHD 1440p 50 fps                  2560    1440    50.00   16:9    1:1     No
2.5K QHD 1440p 59.94 fps               2560    1440    59.94   16:9    1:1     No
2.5K QHD 1440p 60 fps                  2560    1440    60.00   16:9    1:1     No
384x288 4:3 PAL                        384     288     25.00   4:3     1:1     No
4K UHD 2160p 23.98 fps                 3840    2160    23.98   16:9    1:1     No
4K UHD 2160p 24 fps                    3840    2160    24.00   16:9    1:1     No
4K UHD 2160p 25 fps                    3840    2160    25.00   16:9    1:1     No
4K UHD 2160p 29.97 fps                 3840    2160    29.97   16:9    1:1     No
4K UHD 2160p 30 fps                    3840    2160    30.00   16:9    1:1     No
4K UHD 2160p 50 fps                    3840    2160    50.00   16:9    1:1     No
4K UHD 2160p 59.94 fps                 3840    2160    59.94   16:9    1:1     No
4K UHD 2160p 60 fps                    3840    2160    60.00   16:9    1:1     No
512x288 16:9 PAL                       512     288     25.00   16:9    1:1     No
768x576 4:3 PAL                        768     576     25.00   4:3     1:1     No
CIF 15 fps                             352     288     15.00   4:3     59:54   No
CIF NTSC                               352     288     29.97   4:3     10:11   No
CIF PAL                                352     288     25.00   4:3     59:54   No
CVD NTSC                               480     352     29.97   4:3     20:11   Yes
CVD PAL                                576     352     25.00   4:3     59:27   Yes
DV/DVD NTSC                            720     480     29.97   4:3     8:9     Yes
DV/DVD PAL                             720     576     25.00   4:3     16:15   Yes
DV/DVD Widescreen NTSC                 720     480     29.97   16:9    32:27   Yes
DV/DVD Widescreen PAL                  720     576     25.00   16:9    64:45   Yes
DV/DVD Widescreen PAL (Anamorphic)     720     576     25.00   16:9    64:45   No
HD 1080i 25 fps                        1920    1080    25.00   16:9    1:1     Yes
HD 1080i 29.97 fps                     1920    1080    29.97   16:9    1:1     Yes
HD 1080i 30 fps                        1920    1080    30.00   16:9    1:1     Yes
HD 1080p 23.98 fps                     1920    1080    23.98   16:9    1:1     No
HD 1080p 24 fps                        1920    1080    24.00   16:9    1:1     No
HD 1080p 25 fps                        1920    1080    25.00   16:9    1:1     No
HD 1080p 29.97 fps                     1920    1080    29.97   16:9    1:1     No
HD 1080p 30 fps                        1920    1080    30.00   16:9    1:1     No
HD 1080p 50 fps                        1920    1080    50.00   16:9    1:1     No
HD 1080p 59.94 fps                     1920    1080    59.94   16:9    1:1     No
HD 1080p 60 fps                        1920    1080    60.00   16:9    1:1     No
HD 720p 23.98 fps                      1280    720     23.98   16:9    1:1     No
HD 720p 24 fps                         1280    720     24.00   16:9    1:1     No
HD 720p 25 fps                         1280    720     25.00   16:9    1:1     No
HD 720p 29.97 fps                      1280    720     29.97   16:9    1:1     No
HD 720p 30 fps                         1280    720     30.00   16:9    1:1     No
HD 720p 50 fps                         1280    720     50.00   16:9    1:1     No
HD 720p 59.94 fps                      1280    720     59.94   16:9    1:1     No
HD 720p 60 fps                         1280    720     60.00   16:9    1:1     No
HD Vertical 1080p 30 fps               1080    1920    30.00   9:16    1:1     No
HD Vertical 720p 30 fps                720     1280    30.00   9:16    1:1     No
HDV 1080 25i 1920x1080                 1920    1080    25.00   16:9    1:1     Yes
HDV 1080 25p 1920x1080                 1920    1080    25.00   16:9    1:1     No
HDV 1440x1080i 25 fps                  1440    1080    25.00   16:9    4:3     Yes
HDV 1440x1080i 29.97 fps               1440    1080    29.97   16:9    4:3     Yes
HDV 1440x1080p 25 fps                  1440    1080    25.00   16:9    4:3     No
HDV 1440x1080p 29.97 fps               1440    1080    29.97   16:9    4:3     No
HDV 720 24p                            1280    720     24.00   16:9    1:1     No
Mobile 360p                            320     240     29.97   4:3     1:1     No
NTSC 23.98 fps                         720     486     23.98   4:3     8:9     No
NTSC 29.97 fps                         720     486     29.97   4:3     8:9     Yes
QCIF 15 fps                            176     144     15.00   4:3     59:54   No
QCIF NTSC                              176     144     29.97   4:3     10:11   No
QCIF PAL                               176     144     25.00   4:3     59:54   No
QVGA 15 fps                            320     240     15.00   4:3     1:1     No
QVGA 29.97 fps                         320     240     29.97   4:3     1:1     No
QVGA Widescreen 29.97 fps              426     240     29.97   16:9    1:1     No
SVCD NTSC                              480     480     29.97   4:3     15:11   Yes
SVCD PAL                               480     576     25.00   4:3     59:36   Yes
SVCD Widescreen NTSC                   480     480     29.97   16:9    20:11   Yes
SVCD Widescreen PAL                    480     576     25.00   16:9    59:27   Yes
VCD NTSC                               352     240     29.97   4:3     10:11   No
VCD PAL                                352     288     25.00   4:3     59:54   No
VGA NTSC                               640     480     29.97   4:3     1:1     No
VGA Widescreen NTSC                    854     480     29.97   16:9    1:1     No
=====================================  ======  ======  ======  ======  ======  ==========
