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

.. _preferences_ref:

Preferences
===========

The Preferences window contains many important settings and configuration options for OpenShot. They can be
found in the top menu under **Edit→Preferences**. Many settings will require OpenShot to be restarted after your
changes are applied.

NOTE: Some features such as `Animated Titles` and `external SVG editing` require setting the paths for **Blender** and
**Inkscape** under the General tab. And if you notice audio playback issues, such as audio drift, you many need to
adjust the audio settings under the Preview tab.

General
-------

.. image:: images/preferences-1-general.png

The General tab of the Preferences window allows you to modify the settings that apply to OpenShot as a whole.

.. table::
   :widths: 30 15

   ================================  =============  ===========
   Setting                           Default        Description
   ================================  =============  ===========
   Language                          Default        Choose your preferred language for OpenShot menus and windows  
   Default Theme                     Humanity:Dark  Choose your theme for OpenShot, either Light, Dark or None
   Image Length (seconds)            10.00          How long the image displays on the screen when added to the timeline
   Volume                            75.00          The percentage of the volume of the clip when added to the timeline
   Blender Command (path)            *<blank>*      The path to the binary for Blender
   Advanced Title Editor (path)      *<blank>*      The path to the binary for Inkscape
   Show Export Dialog when Finished  *<checked>*    Displays the Export Video windows after the export is finished
   ================================  =============  ===========

Preview
-------

.. image:: images/preferences-2-preview.png

The Preview tab of the Preferences window allows you to set a **Default Video Profile** for your project, if you have
a preference for a specific editing profile. More about `profiles <profiles.html>`_. Also, you can adjust the
real-time preview audio settings, for example, which audio device and sample rate to use.

.. table::
   :widths: 30 20

   ================================  ==================  ===========
   Setting                           Default             Description
   ================================  ==================  ===========
   Default Video Profile             HD 720P 30 fps      Select the profile for Preview and Export defaults  
   Playback Audio Device             Default             
   Default Audio Sample Rate         44100               
   Default Audio Channels            Stereo (2 Channel)  
   ================================  ==================  ===========

Autosave
--------

.. image:: images/preferences-3-autosave.png

Autosave is a saving function in OpenShot which automatically saves the current changes to your project after
a specific number of minutes, helping to reduce the risk or impact of data loss in case of a crash, freeze
or user error.

Recovery
^^^^^^^^

Before each save, a copy of the current project is created in a recovery folder, to further
reduce the risk of data loss. The recovery folder is located at ``~/.openshot_qt/recovery/`` or
``C:\Users\USERNAME\.openshot_qt\recovery``. If you need to recover a corrupt or broken ``*.osp``
project file, please find the most recent copy in the recovery folder, and copy/paste the file
in your original project folder location (i.e. the folder that contains your broken project), and then
**open** this recovered project file in OpenShot. Many versions of each project are stored in the
recovery folder, and if you still have issues with the recovered ``*.osp`` file, you can repeat this
process with older versions contained in the recovery folder.

Cache
-----

.. image:: images/preferences-4-cache.png

Cache settings can be adjusted to make real-time playback faster or less CPU intensive. The cache is used
to store image and audio data for each frame of video requested. The more frames that are cached, the
smoother the real-time playback will be. However, the more that needs to be cached requires more
CPU to generate the cache. There is a balance, and the default settings provide a generally sane
set of cache values, which should allow most computers to playback video and audio smoothly.

.. table::
   :widths: 36 80

   ================================  ==================
   Setting                           Description
   ================================  ==================
   Cache Mode                        Choose between Memory or Disk caching (memory caching is preferred). Disk caching writes image data to the hard disk for later retrieving, and works best with an SSD.
   Cache Limit (MB)                  How many MB are set aside for cache related data. Larger numbers are not always better, since it takes more CPU to generate more frames to fill the cache.
   Image Format (Disk Only)          Image format to store disk cache image data
   Scale Factor (Disk Only)          Percentage (0.1 to 1.0) to reduce the size of disk based image files stored in the disk cache. Smaller numbers make writing and reading cached image files faster.
   Image Quality (Disk Only)         Quality of the image files used in disk cache. The higher compression can cause more slowness, but results in smaller file sizes.
   Cache Pre-roll: Min Frames:       Minimum # of frames that must be cached before playback begins. The larger the #, the larger the wait before playback begins.
   Cache Pre-roll: Max Frames:       Maximum # of frames that can be cached during playback (in front of the playhead). The larger the #, the more CPU is required to cache ahead - vs display the already cached frames.
   Cache Ahead (Percent):            Between 0.0 and 1.0. This represents how much % we cache ahead of the playhead. For example, 0.5 would cache 50% behind and 50% ahead of the playhead. 0.8 would cache 20% behind and 80% ahead of the playhead.
   Cache Max Frames:                 This is an override on the total allowed frames that can be cached by our caching thread. It is defaulted to 600 frames, but even if you give a huge amount of RAM to OpenShot's cache size, this will override the max # of frames cached. The reason is... sometimes when the preview window is very small, and the cache size is set very high, OpenShot might calculate that we can cache 30,000 frames, or something silly which will take a huge amount of CPU, lagging the system. This setting is designed to clamp the upper limit of the cache to something reasonable... even on systems that give OpenShot huge amounts of RAM to work with.
   ================================  ==================

Debug
-----

.. image:: images/preferences-5-debug.png

Here you can modify how much data should be logged. Normally, *Debug Mode (verbose)* is off.
The default port is 5556. If you want to help improve OpenShot you can enable **Send Anonymous Metrics and Errors**.

Performance
-----------
.. image:: images/preferences-6-performance.png

Please keep in mind that hardware acceleration is experimental at the moment. OpenShot supports both decoding and
encoding acceleration. For more information take a look at our `Github <https://github.com/OpenShot/libopenshot/blob/develop/doc/HW-ACCEL.md>`_.
NOTE: On systems with older graphics cards, hardware acceleration may not always be faster than CPU encoding.

.. TODO Performance settings
  Process Video Frame Rates in Parallel
  OMP Threads = Open Multi-Processing? https://en.wikipedia.org/wiki/OpenMP
  FFmpeg Threads 
        (NB: it states 0=default, but the actually default upon installation is 8 ?)
         Advices is N(cores-1) or N(Threads-1) ?
 Hardware Decoder max width/height  Can be found where? Link to HW manufacturers?
 Use Blender GPU rendering: Default = on?
    (May be default in Blender 2.8? - 
    May work backfire if system has multiple GPUs and high-end GPU recognizes Blender automatically)

Keyboard
--------
.. image:: images/preferences-7-keyboard.png

This is where hotkeys can be seen and re-assigned, as described under 
:ref:`keyboard_shortcut_ref`. 
