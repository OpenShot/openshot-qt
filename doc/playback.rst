.. Copyright (c) 2008-2023 OpenShot Studios, LLC
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

.. _playback_ref:

Playback
========
The preview window is where video & audio playback takes place in OpenShot Video Editor. The preview window
utilizes real-time video rendering, caching, re-sampling, and image scaling. This is the primary area for watching
back (and listening to) your edits, giving you the feedback needed to make adjustments. It is also one of the most
costly operations to your CPU, and requires a modern computer and some reasonable assumptions and factors (listed below).

Real-Time Preview
-----------------
Many factors affect how smoothly the **real-time video preview** can playback on your computer. This requires a fast, modern
multi-threaded CPU, lots of RAM (memory), and a modern GPU. We have listed many of the important factors below.

.. table::
   :widths: 22 80

   ==================  ============
   Factor              Description
   ==================  ============
   CPU                 If your CPU is too slow or has too few cores, you will likely experience a slow, choppy preview.
                       We recommend installing OpenShot on fairly modern computer. See :ref:`min_system_req_ref` for
                       more details on the hardware requirements for OpenShot Video Editor.
   Memory              If your available RAM memory is too limited, you will likely see huge drops in real-time
                       performance, and your entire system will lag. We recommend installing additional RAM in your
                       computer, if possible. See :ref:`min_system_req_ref`.
   Cache               Your cache settings in the OpenShot Preferences are very important for determining how many
                       frames to processes in advance. A value too low or too high can cause lag during the real-time
                       video preview. The cache is also related to the available RAM. The higher the cache values, the more
                       RAM and CPU is needed. We recommend experimenting with the Cache Preferences in OpenShot if you are
                       experiencing issues with smooth playback. See :ref:`preferences_cache_ref`.
   Preview Size        The height x width of your preview dock (widget) is very important for smooth real-time previews.
                       The larger the window size, the more pixels must be rendered per frame, and the more CPU and RAM
                       are required. It is recommended to keep reducing the preview window size until you achieve smooth
                       video playback. On a slower computer, the preview window size might need to be very small for
                       real-time previews (i.e. 320 x 240).
   Profile             Your project profile determines which size (width x height) and frame rate (FPS) are used during both
                       playback and exporting. For example, if you are using a FHD 1920x1080 sized profile, you can also choose a
                       smaller profile with the same aspect ratio (``16x9`` in this example), to improve the preview speed
                       on slower computers. See :ref:`profiles_ref` for more information on available profiles.
   FPS (Frame Rate)    The FPS of your project is also very important, and a large factor for smooth video playback. For
                       example, a 60 FPS video must render twice the number of frames, compared to a 30 FPS video. If
                       you are experiencing slow downs in real-time performance, it can be helpful to reduce your project's
                       FPS to a lower value, such as 30 or 24.
   Matching Rates      It is very important to match your source assets FPS and Sample Rate with your Project FPS and Project
                       sample rate. If either rate does not match exactly, it requires lots of additional CPU and RAM for
                       OpenShot to normalize the mismatching rates. This can lead to audio pops, mis-alignments, duplicate frames, and extra
                       lag in the real-time video preview. You can right-click a file and choose :guilabel:`File Properties`, to
                       inspect the source asset rates, and ensure they match your Project settings (shown at the top of OpenShot).
                       See :ref:`file_properties_ref`.
   Source Assets       For example, if you are editing 4K 60 FPS source assets, this is likely going to put a strain on your system. A
                       common solution is using another tool (such as FFmpeg) to create a copy (or proxy) of all your source assets,
                       at a lower resolution (and maybe even a lower FPS). It is recommended to keep these proxy video files
                       in their own folder, separate from the original video files. Once you have completed your video editing with
                       the proxy files, simply copy/paste your `*.osp` project file back into the original folder, and export
                       the higher quality, original files.
   Audio Device        If you are still having issues with audio lag or sync, please verify you are using the correct
                       Audio Device for playback (in the OpenShot Preferences). See :ref:`preferences_preview_ref`. Also,
                       verify your default audio device (on your operating system) is using the same sample rate. On
                       certain operating systems (such as Windows), mismatching sample rates can cause severe audio
                       / video sync problems. Be sure to restart OpenShot after changing the audio device.
   ==================  ============

Audio Troubleshooting
---------------------
If you are still experiencing audio related issues, and the above real-time playback factors did not resolve
your issue, here are some additional troubleshooting steps you can take.

.. table::
   :widths: 22 80

   ==================  ============
   Step                Description
   ==================  ============
   Latest Daily Build  Verify you are running the latest daily build of OpenShot: https://www.openshot.org/download#daily
   Clean Install       See :ref:`preferences_reset_ref` for a clean install
   Audio Device        Check that the Playback Audio Device is set correctly for your sound output under Preferences
                       in the Preview tab. Restart OpenShot after changing the settings. You can also try a different
                       audio device (USB, audio over HDMI from the video card, etc.) to rule out other audio issues.
                       Disable `automatic sound suppression` for voice calls during microphone activity, and disable
                       `Audio Enhancements` under the advanced settings tab of your audio device (not all audio devices
                       have these settings). See :ref:`preferences_preview_ref`.
   Sample Rate         Ensure that the `Default Audio Sample Rate` and `Default Audio Channels` on the Preview tab of the
                       Preferences window match your hardware. You can also check these settings in the operating system
                       control panel (i.e. Windows Sound Control Panel). See :ref:`preferences_preview_ref`.
   Volume              Ensure that the volume does not exceed 100% on overlapping clips (such as an audio track combined
                       with a video track). Lower the volume on individual clips if needed. See :ref:`clip_volume_mixing_ref`.
   Headphones          If you're using headphones, plug them in before starting OpenShot. Launching OpenShot with no
                       speakers, headphones, or valid audio playback device can cause OpenShot to freeze during playback.
   OS Updates          Update your operating system and any pending security updates. Some audio issues, especially
                       audio device specific issues, can be resolved with an operating system update.
   ==================  ============
