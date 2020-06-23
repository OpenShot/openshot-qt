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

.. _quick_tutorial_ref:
Quick Tutorial
===============

OpenShot is very easy to use, and it has many advanced features.  This tutorial will take you through some basic steps in **under 5 minutes**.  After this tutorial, you will be able to make a simple photo slide-show with music.

Step 1 – Import Photos & Music
-------------------------------
Before we can begin making a video, we need to import files into OpenShot.  Drag and drop a few images (\*.JPG, \*.PNG, etc.) and a music file (\*.MP3, \*. WAV, etc.) from your file manager or desktop to OpenShot.  You can add your :ref:`def-clip` to the timeline as well as the Project Files list.  Be sure to drop the files to where the arrow in the illustration is pointing.

.. image:: images/quick-start-drop-files.jpg

Step 2 – Add Photos to Timeline
--------------------------------
Next, drag each photo to the timeline (as seen in the illustration).  The timeline represents your final video, so arrange your photos in the order you want them to appear in your video.  If you overlap two clips, OpenShot will automatically create a smooth fade transition between them, displayed by blue rounded rectangles between the clips.  Remember, you can rearrange the clips as many times as needed by simply dragging and dropping.  OpenShot uses tracks to layer videos and images. The top most track is the top layer, and the bottom track is the bottom layer. The higher track will always be visible while the lower tracks will only be visible if the higher tracks don't have any clips above them at that point in the timeline.  Also, lower tracks are visible if the clips on the higher tracks are allowing images to pass through them using the Alpha setting.

.. image:: images/quick-start-timeline-drop.jpg

Step 3 – Add Music to Timeline
-------------------------------
To make your photo slide-show more interesting, we need to add some music.  You should have imported a music file in Step 1. Click on the music file, and drag it to the timeline.  If the song is too long, click the right edge of your music clip and drag it to the left to make your clip shorter.

.. image:: images/quick-start-music.jpg

Step 4 – Preview your Project
------------------------------
To preview how your video looks & sounds, click the Play button under the Preview window.  You can also pause, rewind, and fast-forward your video project by clicking the corresponding buttons.

.. image:: images/quick-start-play.jpg

Step 5 - Refine and Adjust Your Video
--------------------------------------
OpenShot has many advanced features to enhance your project.  You can use :ref:`titles` to add a title screen or text to your clips.  :ref:`transitions` will gradually fade one clip to another.  :ref:`animation_ref`s can change the properties of a clip over time.  These changes can be even more refined using the Properties window (Press **CTRL+I** if the Properties windows is not already visible).  For more information, use the menu to the left to find the related topics.

Step 6 – Export your Video
---------------------------
Once you have edited your photo slide-show video, the last step is to export the project.  This will convert your OpenShot project into a single video file.  Using the default settings, the video will work on most media players (such as VLC) or websites (such as YouTube, Vimeo, etc.).

Click the Export Video icon in the top toolbarn (Press CTRL+E or use the **File > Export Video** menu).  Choose from one of the many preset export options, and click the *Export Video* button.  Exporting can take a very long time depending on the length of your project, the video profile that you chose, the quality of the export video and the speed of your computer's Central Processing Unit (CPU).  Please be aware of these factor and be patient as your system creates your video.

.. image:: images/quick-start-export.jpg

In Conclusion
-------------
You should now have a basic understanding of how OpenShot works. Importing, Arranging, Previewing, and Exporting.  Hopefully this tutorial took less than 5 minutes for you to complete. Please read the rest of this guide for a more detailed understanding of OpenShot, and it's advanced features. If you have any questions after reading the rest of this User Guide, join our `Reddit Community <https://www.redit.com/OpenShot>`_ and ask others for help with your issue.  If you still have an issued after joining our Reddit Community and believe that you have a bug in OpenShot, check out our `GitHub Repository <https://www.github.com/OpenShot>`_ and see if your issue is resolved or a patch is in progress.  Enjoy!

Definitions
------------
.. _def-clip_ref:
Clip:
   Each media file you add to the OpenShot timeline is called a clip.
.. _def-project_ref:
Project:
   All of the files, transitions, effects and animations that you make or use within OpenShot.
.. _def-profile_ref:
 Profile:
   A profile is a collection of common video settings (size, frame rate, aspect ratio, etc…).
.. _def-animation_ref:
Animation:
   The technique of making inanimate objects or drawings appear to move in motion pictures or computer graphics.
.. _def-transition_ref:   
Transition:
   A transition is used to gradually fade (or wipe) between two clips.
