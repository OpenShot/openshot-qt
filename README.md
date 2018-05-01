## Copyright

 Copyright (c) 2008-2018 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.

## Instructions

OpenShot Video Editor 2.x supports Linux, Mac, and Windows. But due to 
the many dependencies required to run OpenShot, we recommend using an 
installer for your operating system. Please visit 
http://www.openshot.org/download/ to find your correct installer.

## Documentation

Documentation for OpenShot 2.x can be generated with Doxygen, a popular
command-line application for scanning source code and generating readable
documentation. OpenShot contains a Doxygen input file (Doxyfile.in), but
you must first install the following Python filter for Doxygen: doxypy.
Then, run the following command:

    $ doxygen Doxyfile.in

## Dependencies

Although installers are much easier to use, if you must build from 
source, here are some tips: 

OpenShot 2.x is programmed in Python, and thus does not need
to be compiled to run.  However, be sure you have the following 
dependencies in order to run OpenShot successfully: 

1) Python 3.0+ (http://www.python.org)
2) PyQt5 (http://www.riverbankcomputing.co.uk/software/pyqt/download5)
3) libopenshot: OpenShot Library (http://www.openshot.org)
4) FFmpeg or Libav (http://www.ffmpeg.org/ or http://libav.org/)
5) GCC build tools (or MinGW on Windows)

To run OpenShot from the command line, use the following syntax:
(be sure the change the path to match the install location of OpenShot)

    $ cd /home/USER/openshot_qt
    $ python3 src/launch.py

## How to install

If you would like to install OpenShot, use this command:

    $ sudo python3 setup.py install

Installing OpenShot using this command does a few extra things that
the build wizard doesn't do.  It adds MIME Types, adds an icon to your
Application menu, registers icons, adds a /usr/bin/openshot command, and
copies all the code files to the /site-packages/ folder.

## Tutorial

Here is a tutorial of the current development features:

#### Do you have a help manual?
1) Yes, go to http://www.openshotusers.com/help/en/

#### How do I add media to my project?
1) Drag and drop videos or music files from gnome into the "Project Files" tree.
2) Click the File / Import Files... menu
3) Click the "Import Files" icon on the toolbar (at the top of the screen)

#### How do I add media to my timeline?
1) Click on any file in your "Project Files" tree, and drag it onto the timeline (at the bottom of the screen)

#### How do I position clips on my timeline?
1) Simply click on any clips already on the timeline, and drag them to their new location
2) Use the magnet icon to have your clips magically stick to their closest neighbor clips.

#### How do I trim / un-trim clips
1) Click and drag the edge of the clip to it's new location.

#### The audio / video is out of sync. What can I do?
1) This is usually related to a bug in libopenshot or FFmpeg.  To resolve this, re-encode the video using the ffmpeg command line tool.
2) Here is an example command to convert a folder full of Canon MTS files to MP4:
    $ find '/home/jonathan/Desktop/Caveman Movie/Videos' -iname "*.MTS" -exec ffmpeg -i {} -acodec libfaac -ab 128k -ac 2 
    -r 60 -vcodec mpeg4 -f mp4 -y -sameq {}.mp4 \;
3) Usually the reason the A/V are out of sync is related to the frame rate (i.e. the -r parameter on the ffmpeg command).
Try a variety of frame rates and OpenShot project types to find one that doesn't have A/V sync issues. Some common rates are:  -r 29.97  -r 25  -r 30  -r 60


## Websites

- http://www.openshot.org/  (Official website and blog)
- https://github.com/OpenShot/openshot-qt (source code and issue tracker)
- http://freshmeat.net/projects/openshot-video-editor/
- https://sourceforge.net/projects/openshotvideo/
- https://www.ohloh.net/p/openshot-video-editor/
- http://launchpad.net/openshot/

## Report a bug

You can file an Issue in the OpenShot/openshot-qt project on Github https://github.com/OpenShot/openshot-qt/issues. Make sure to add plenty of detail about the issue and logs if possible.

## Translations

https://translations.launchpad.net/openshot

## Ask a question  

You can ask any question you have here https://github.com/OpenShot/openshot-qt/issues.

## Contributing

If you would like to help reporting issues or commit fixes to the project please see our [contributor guidelines](CONTRIBUTING.md).
