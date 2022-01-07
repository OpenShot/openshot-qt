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

Import & Export
===============

Video editing projects (including tracks, clips, and keyframes) can be **imported** and **exported** from OpenShot
Video Editor in widely supported formats (**EDL**: Edit Decision Lists, and **XML**: Final Cut Pro format). For example, if
you start editing a video in a different program (Adobe Premier, Final Cut Pro, etc...), but later need to move all
your edits to OpenShot (or vice versa).

EDL (Edit Decision Lists)
-------------------------
The following features are supported when importing and exporting an EDL file with OpenShot.

.. table::
   :widths: 25

   ====================  ============
   Name                  Description
   ====================  ============
   EDL Format            CMX-3600 (a very widely supported variation)
   Single Track          Only a single track can be imported at a time (this is a limitation of the EDL format)
   Tape Name             Only **AX** and **BL** tape names are currently supported in OpenShot
   Edits (V and A)       Only edits are currently supported (transitions are not yet supported)
   Opacity               Opacity keyframes are supported
   Audio Levels          Volume keyframes are supported
   ====================  ============

.. code-block:: python
   :caption: Example EDL format supported by OpenShot:

    TITLE: Clips - TRACK 5
    FCM: NON-DROP FRAME

    001  BL       V     C        00:00:00:01 00:00:03:17 00:00:00:01 00:00:03:17
    001  AX       V     C        00:00:00:01 00:00:10:01 00:00:03:17 00:00:13:17
    * FROM CLIP NAME: Intro.png

    002  BL       V     C        00:00:00:01 00:00:05:09 00:00:13:17 00:00:18:25
    002  AX       V     C        00:00:00:01 00:00:10:01 00:00:18:25 00:00:28:25
    * FROM CLIP NAME: FileName.mp4
    * OPACITY LEVEL AT 00:00:00:01 IS 0.00%  (REEL AX)
    * OPACITY LEVEL AT 00:00:01:01 IS 100.00%  (REEL AX)
    * OPACITY LEVEL AT 00:00:09:01 IS 100.00%  (REEL AX)
    * OPACITY LEVEL AT 00:00:10:01 IS 0.00%  (REEL AX)

    003  BL       V     C        00:00:00:01 00:00:33:15 00:00:28:25 00:01:02:09
    003  AX       V     C        00:00:14:25 00:00:34:29 00:01:02:09 00:01:22:13
    003  AX       A     C        00:00:14:25 00:00:34:29 00:01:02:09 00:01:22:13
    * FROM CLIP NAME: FileName2.mp4

    004  BL       V     C        00:00:00:01 00:00:26:25 00:01:22:13 00:01:49:07
    004  AX       A     C        00:00:00:01 00:02:20:01 00:01:49:07 00:04:09:07
    * FROM CLIP NAME: Music.wav
    * AUDIO LEVEL AT 00:00:00:01 IS -99.00 DB  (REEL AX A1)
    * AUDIO LEVEL AT 00:00:03:01 IS 0.00 DB  (REEL AX A1)
    * AUDIO LEVEL AT 00:02:17:01 IS 0.00 DB  (REEL AX A1)
    * AUDIO LEVEL AT 00:02:20:01 IS -99.00 DB  (REEL AX A1)

XML (Final Cut Pro format)
--------------------------
The following features are supported when importing and exporting an XML file with OpenShot. This XML format
is supported in many video editors (not just Final Cut Pro). In fact, most commercial video editors have some
support for importing and exporting this same XML format.

.. table::
   :widths: 25

   ====================  ============
   Name                  Description
   ====================  ============
   XML Format            Final Cut Pro format (but most commercial video editors also support this format)
   All Tracks            All video and audio tracks are supported
   Edits                 All clips on all tracks are supported (video, image, and audio files). Transitions are not yet supported.
   Opacity               Opacity keyframes are supported
   Audio Levels          Volume keyframes are supported
   ====================  ============


.. code-block:: xml
    :caption: Example XML format supported by OpenShot (abbreviated):

    <?xml version="1.0" ?>
    <!DOCTYPE xmeml>
    <xmeml version="4">
        <sequence MZ.EditLine="3237704870400" MZ.Sequence.AudioTimeDisplayFormat="200" MZ.Sequence.EditingModeGUID="795454d9-d3c2-429d-9474-923ab13b7017" MZ.Sequence.PreviewFrameSizeHeight="480" MZ.Sequence.PreviewFrameSizeWidth="720" MZ.Sequence.PreviewRenderingClassID="1061109567" MZ.Sequence.PreviewRenderingPresetCodec="1685480224" MZ.Sequence.PreviewRenderingPresetPath="EncoderPresets/SequencePreview/795454d9-d3c2-429d-9474-923ab13b7017/QuickTime DV NTSC.epr" MZ.Sequence.PreviewUseMaxBitDepth="false" MZ.Sequence.PreviewUseMaxRenderQuality="false" MZ.Sequence.VideoTimeDisplayFormat="102" MZ.WorkInPoint="0" MZ.WorkOutPoint="5432902675200" MZ.ZeroPoint="8475667200" Monitor.ProgramZoomIn="0" Monitor.ProgramZoomOut="5432902675200" TL.SQAVDividerPosition="0.5" TL.SQAudioVisibleBase="0" TL.SQHeaderWidth="236" TL.SQHideShyTracks="0" TL.SQTimePerPixel="0.050923888888888894" TL.SQVideoVisibleBase="0" TL.SQVisibleBaseTime="0" explodedTracks="true" id="X3N90QWYU1">
            <uuid>60cb1fb8-7dac-11e9-abb0-f81a67234bcb</uuid>
            <duration>249.215625</duration>
            <rate>
                <timebase>30.0</timebase>
                <ntsc>TRUE</ntsc>
            </rate>
            <name>Clips.xml</name>
            <media>
                <video>
                    <format>
                        <samplecharacteristics>
                            <rate>
                                <timebase>30.0</timebase>
                                <ntsc>TRUE</ntsc>
                            </rate>
                            <codec>...</codec>
                            <width>1280</width>
                            <height>720</height>
                            <anamorphic>FALSE</anamorphic>
                            <pixelaspectratio>NTSC-601</pixelaspectratio>
                            <fielddominance>lower</fielddominance>
                            <colordepth>24</colordepth>
                        </samplecharacteristics>
                    </format>
                    <track MZ.TrackTargeted="0" TL.SQTrackExpanded="0" TL.SQTrackExpandedHeight="25" TL.SQTrackShy="0">
                        <enabled>TRUE</enabled>
                        <locked>FALSE</locked>
                        <clipitem id="XAUWQHBX4K">
                            <name>Title.png</name>
                            <enabled>TRUE</enabled>
                            <duration>300.0</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>TRUE</ntsc>
                            </rate>
                            <start>340.79999999999995</start>
                            <end>640.8</end>
                            <in>0.0</in>
                            <out>300.0</out>
                            <pproTicksIn>0.0</pproTicksIn>
                            <pproTicksOut>76204800000000.0</pproTicksOut>
                            <alphatype>none</alphatype>
                            <pixelaspectratio>square</pixelaspectratio>
                            <anamorphic>FALSE</anamorphic>
                            <file id="FL840TGBJK">
                                <name>Title.png</name>
                                <pathurl>Title.png</pathurl>
                                <rate>
                                    <timebase>30</timebase>
                                    <ntsc>TRUE</ntsc>
                                </rate>
                                <duration>301</duration>
                                <timecode>
                                    <rate>
                                        <timebase>30</timebase>
                                        <ntsc>TRUE</ntsc>
                                    </rate>
                                    <string>00:00:00:00</string>
                                    <frame>0</frame>
                                    <displayformat>NDF</displayformat>
                                    <reel>
                                        <name>AX</name>
                                    </reel>
                                </timecode>
                                <media>
                                    <video>
                                        <samplecharacteristics>
                                            <rate>
                                                <timebase>30</timebase>
                                                <ntsc>TRUE</ntsc>
                                            </rate>
                                            <width>720</width>
                                            <height>480</height>
                                            <anamorphic>FALSE</anamorphic>
                                            <pixelaspectratio>square</pixelaspectratio>
                                            <fielddominance>lower</fielddominance>
                                        </samplecharacteristics>
                                    </video>
                                    <audio>
                                        <samplecharacteristics>
                                            <depth>16</depth>
                                            <samplerate>48000</samplerate>
                                        </samplecharacteristics>
                                        <channelcount>2</channelcount>
                                    </audio>
                                </media>
                            </file>
                            <filter>
                                <effect>
                                    <name>Opacity</name>
                                    <effectid>opacity</effectid>
                                    <effectcategory>motion</effectcategory>
                                    <effecttype>motion</effecttype>
                                    <mediatype>video</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>opacity</parameterid>
                                        <name>opacity</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>100</valuemax>
                                        <value>100</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>100.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                            <labels>
                                <label2>Violet</label2>
                            </labels>
                        </clipitem>
                        <clipitem id="A2ZIIOZCH9">
                            <name>FileName.mp4</name>
                            <enabled>TRUE</enabled>
                            <duration>1558.400001525879</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>TRUE</ntsc>
                            </rate>
                            <start>2214.0</start>
                            <end>3772.400001525879</end>
                            <in>0.0</in>
                            <out>1558.400001525879</out>
                            <pproTicksIn>0.0</pproTicksIn>
                            <pproTicksOut>395858534787597.6</pproTicksOut>
                            <alphatype>none</alphatype>
                            <pixelaspectratio>square</pixelaspectratio>
                            <anamorphic>FALSE</anamorphic>
                            <file id="SG00IW75Y5">
                                <name>FileName.mp4</name>
                                <pathurl>FileName.mp4</pathurl>
                                <rate>
                                    <timebase>30</timebase>
                                    <ntsc>TRUE</ntsc>
                                </rate>
                                <duration>301</duration>
                                <timecode>
                                    <rate>
                                        <timebase>30</timebase>
                                        <ntsc>TRUE</ntsc>
                                    </rate>
                                    <string>00:00:00:00</string>
                                    <frame>0</frame>
                                    <displayformat>NDF</displayformat>
                                    <reel>
                                        <name>AX</name>
                                    </reel>
                                </timecode>
                                <media>
                                    <video>
                                        <samplecharacteristics>
                                            <rate>
                                                <timebase>30</timebase>
                                                <ntsc>TRUE</ntsc>
                                            </rate>
                                            <width>720</width>
                                            <height>480</height>
                                            <anamorphic>FALSE</anamorphic>
                                            <pixelaspectratio>square</pixelaspectratio>
                                            <fielddominance>lower</fielddominance>
                                        </samplecharacteristics>
                                    </video>
                                    <audio>
                                        <samplecharacteristics>
                                            <depth>16</depth>
                                            <samplerate>2</samplerate>
                                        </samplecharacteristics>
                                        <channelcount>48000</channelcount>
                                    </audio>
                                </media>
                            </file>
                            <filter>
                                <effect>
                                    <name>Opacity</name>
                                    <effectid>opacity</effectid>
                                    <effectcategory>motion</effectcategory>
                                    <effecttype>motion</effecttype>
                                    <mediatype>video</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>opacity</parameterid>
                                        <name>opacity</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>100</valuemax>
                                        <value>100</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>100.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                            <labels>
                                <label2>Violet</label2>
                            </labels>
                        </clipitem>
                    </track>
                    <track MZ.TrackTargeted="0" TL.SQTrackExpanded="0" TL.SQTrackExpandedHeight="25" TL.SQTrackShy="0">
                        <enabled>TRUE</enabled>
                        <locked>FALSE</locked>
                        <clipitem id="0E25FKQBWG">
                            <name>Credits.png</name>
                            <enabled>TRUE</enabled>
                            <duration>300.0</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>TRUE</ntsc>
                            </rate>
                            <start>105.6</start>
                            <end>405.59999999999997</end>
                            <in>0.0</in>
                            <out>300.0</out>
                            <pproTicksIn>0.0</pproTicksIn>
                            <pproTicksOut>76204800000000.0</pproTicksOut>
                            <alphatype>none</alphatype>
                            <pixelaspectratio>square</pixelaspectratio>
                            <anamorphic>FALSE</anamorphic>
                            <file id="KTBZK4AR5A">
                                <name>Credits.png</name>
                                <pathurl>Credits.png</pathurl>
                                <rate>
                                    <timebase>30</timebase>
                                    <ntsc>TRUE</ntsc>
                                </rate>
                                <duration>301</duration>
                                <timecode>
                                    <rate>
                                        <timebase>30</timebase>
                                        <ntsc>TRUE</ntsc>
                                    </rate>
                                    <string>00:00:00:00</string>
                                    <frame>0</frame>
                                    <displayformat>NDF</displayformat>
                                    <reel>
                                        <name>AX</name>
                                    </reel>
                                </timecode>
                                <media>
                                    <video>
                                        <samplecharacteristics>
                                            <rate>
                                                <timebase>30</timebase>
                                                <ntsc>TRUE</ntsc>
                                            </rate>
                                            <width>720</width>
                                            <height>480</height>
                                            <anamorphic>FALSE</anamorphic>
                                            <pixelaspectratio>square</pixelaspectratio>
                                            <fielddominance>lower</fielddominance>
                                        </samplecharacteristics>
                                    </video>
                                    <audio>
                                        <samplecharacteristics>
                                            <depth>16</depth>
                                            <samplerate>48000</samplerate>
                                        </samplecharacteristics>
                                        <channelcount>2</channelcount>
                                    </audio>
                                </media>
                            </file>
                            <filter>
                                <effect>
                                    <name>Opacity</name>
                                    <effectid>opacity</effectid>
                                    <effectcategory>motion</effectcategory>
                                    <effecttype>motion</effecttype>
                                    <mediatype>video</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>opacity</parameterid>
                                        <name>opacity</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>100</valuemax>
                                        <value>100</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>100.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                            <labels>
                                <label2>Violet</label2>
                            </labels>
                        </clipitem>
                        <clipitem id="YBPQ8J4LC9">
                            <name>Overlay.png</name>
                            <enabled>TRUE</enabled>
                            <duration>300.0</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>TRUE</ntsc>
                            </rate>
                            <start>564.0</start>
                            <end>864.0</end>
                            <in>0.0</in>
                            <out>300.0</out>
                            <pproTicksIn>0.0</pproTicksIn>
                            <pproTicksOut>76204800000000.0</pproTicksOut>
                            <alphatype>none</alphatype>
                            <pixelaspectratio>square</pixelaspectratio>
                            <anamorphic>FALSE</anamorphic>
                            <file id="MMRR3KIDHF">
                                <name>Overlay.png</name>
                                <pathurl>Overlay.png</pathurl>
                                <rate>
                                    <timebase>30</timebase>
                                    <ntsc>TRUE</ntsc>
                                </rate>
                                <duration>301</duration>
                                <timecode>
                                    <rate>
                                        <timebase>30</timebase>
                                        <ntsc>TRUE</ntsc>
                                    </rate>
                                    <string>00:00:00:00</string>
                                    <frame>0</frame>
                                    <displayformat>NDF</displayformat>
                                    <reel>
                                        <name>AX</name>
                                    </reel>
                                </timecode>
                                <media>
                                    <video>
                                        <samplecharacteristics>
                                            <rate>
                                                <timebase>30</timebase>
                                                <ntsc>TRUE</ntsc>
                                            </rate>
                                            <width>720</width>
                                            <height>480</height>
                                            <anamorphic>FALSE</anamorphic>
                                            <pixelaspectratio>square</pixelaspectratio>
                                            <fielddominance>lower</fielddominance>
                                        </samplecharacteristics>
                                    </video>
                                    <audio>
                                        <samplecharacteristics>
                                            <depth>16</depth>
                                            <samplerate>48000</samplerate>
                                        </samplecharacteristics>
                                        <channelcount>2</channelcount>
                                    </audio>
                                </media>
                            </file>
                            <filter>
                                <effect>
                                    <name>Opacity</name>
                                    <effectid>opacity</effectid>
                                    <effectcategory>motion</effectcategory>
                                    <effecttype>motion</effecttype>
                                    <mediatype>video</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>opacity</parameterid>
                                        <name>opacity</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>100</valuemax>
                                        <value>100</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>0.0</value>
                                        </keyframe>
                                        <keyframe>
                                            <when>31.0</when>
                                            <value>100.0</value>
                                        </keyframe>
                                        <keyframe>
                                            <when>271.0</when>
                                            <value>100.0</value>
                                        </keyframe>
                                        <keyframe>
                                            <when>301.0</when>
                                            <value>0.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                            <labels>
                                <label2>Violet</label2>
                            </labels>
                        </clipitem>
                        <clipitem id="SQ3995OKWV">
                            <name>FileName.mp4</name>
                            <enabled>TRUE</enabled>
                            <duration>603.9999999999999</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>TRUE</ntsc>
                            </rate>
                            <start>1868.0</start>
                            <end>2471.9999999999995</end>
                            <in>444.0</in>
                            <out>1048.0</out>
                            <pproTicksIn>112783104000000.0</pproTicksIn>
                            <pproTicksOut>266208768000000.0</pproTicksOut>
                            <alphatype>none</alphatype>
                            <pixelaspectratio>square</pixelaspectratio>
                            <anamorphic>FALSE</anamorphic>
                            <file id="SG00IW75Y5">
                                <name>FileName.mp4</name>
                                <pathurl>FileName.mp4</pathurl>
                                <rate>
                                    <timebase>30</timebase>
                                    <ntsc>TRUE</ntsc>
                                </rate>
                                <duration>301</duration>
                                <timecode>
                                    <rate>
                                        <timebase>30</timebase>
                                        <ntsc>TRUE</ntsc>
                                    </rate>
                                    <string>00:00:00:00</string>
                                    <frame>0</frame>
                                    <displayformat>NDF</displayformat>
                                    <reel>
                                        <name>AX</name>
                                    </reel>
                                </timecode>
                                <media>
                                    <video>
                                        <samplecharacteristics>
                                            <rate>
                                                <timebase>30</timebase>
                                                <ntsc>TRUE</ntsc>
                                            </rate>
                                            <width>720</width>
                                            <height>480</height>
                                            <anamorphic>FALSE</anamorphic>
                                            <pixelaspectratio>square</pixelaspectratio>
                                            <fielddominance>lower</fielddominance>
                                        </samplecharacteristics>
                                    </video>
                                    <audio>
                                        <samplecharacteristics>
                                            <depth>16</depth>
                                            <samplerate>2</samplerate>
                                        </samplecharacteristics>
                                        <channelcount>48000</channelcount>
                                    </audio>
                                </media>
                            </file>
                            <filter>
                                <effect>
                                    <name>Opacity</name>
                                    <effectid>opacity</effectid>
                                    <effectcategory>motion</effectcategory>
                                    <effecttype>motion</effecttype>
                                    <mediatype>video</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>opacity</parameterid>
                                        <name>opacity</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>100</valuemax>
                                        <value>100</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>100.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                            <labels>
                                <label2>Violet</label2>
                            </labels>
                        </clipitem>
                    </track>
                </video>
                <audio>
                    <numOutputChannels>2</numOutputChannels>
                    <format>
                        <samplecharacteristics>
                            <depth>16</depth>
                            <samplerate>44100</samplerate>
                        </samplecharacteristics>
                    </format>
                    <outputs>
                        <group>
                            <index>1</index>
                            <numchannels>1</numchannels>
                            <downmix>0</downmix>
                            <channel>
                                <index>1</index>
                            </channel>
                        </group>
                        <group>
                            <index>2</index>
                            <numchannels>1</numchannels>
                            <downmix>0</downmix>
                            <channel>
                                <index>2</index>
                            </channel>
                        </group>
                    </outputs>
                    <track MZ.TrackTargeted="1" PannerCurrentValue="0.5" PannerIsInverted="true" PannerName="Balance" PannerStartKeyframe="-91445760000000000,0.5,0,0,0,0,0,0" TL.SQTrackAudioKeyframeStyle="0" TL.SQTrackExpanded="0" TL.SQTrackExpandedHeight="25" TL.SQTrackShy="0" currentExplodedTrackIndex="0" premiereTrackType="Stereo" totalExplodedTrackCount="2">
                        <enabled>TRUE</enabled>
                        <locked>FALSE</locked>
                        <outputchannelindex>1</outputchannelindex>
                        <clipitem id="A2ZIIOZCH9-audio" premiereChannelType="stereo">
                            <name>FileName.mp4</name>
                            <enabled>TRUE</enabled>
                            <duration>1558.400001525879</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>FALSE</ntsc>
                            </rate>
                            <start>2214.0</start>
                            <end>3772.400001525879</end>
                            <in>0.0</in>
                            <out>1558.400001525879</out>
                            <pproTicksIn>0.0</pproTicksIn>
                            <pproTicksOut>395858534787597.6</pproTicksOut>
                            <file id="SG00IW75Y5"/>
                            <sourcetrack>
                                <mediatype>audio</mediatype>
                                <trackindex>1</trackindex>
                            </sourcetrack>
                            <filter>
                                <effect>
                                    <name>Audio Levels</name>
                                    <effectid>audiolevels</effectid>
                                    <effectcategory>audiolevels</effectcategory>
                                    <effecttype>audiolevels</effecttype>
                                    <mediatype>audio</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>level</parameterid>
                                        <name>Level</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>3.98109</valuemax>
                                        <value>1.0</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>1.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                        </clipitem>
                    </track>
                    <track MZ.TrackTargeted="1" PannerCurrentValue="0.5" PannerIsInverted="true" PannerName="Balance" PannerStartKeyframe="-91445760000000000,0.5,0,0,0,0,0,0" TL.SQTrackAudioKeyframeStyle="0" TL.SQTrackExpanded="0" TL.SQTrackExpandedHeight="25" TL.SQTrackShy="0" currentExplodedTrackIndex="0" premiereTrackType="Stereo" totalExplodedTrackCount="2">
                        <enabled>TRUE</enabled>
                        <locked>FALSE</locked>
                        <outputchannelindex>2</outputchannelindex>
                        <clipitem id="SQ3995OKWV-audio" premiereChannelType="stereo">
                            <name>FileName.mp4</name>
                            <enabled>TRUE</enabled>
                            <duration>603.9999999999999</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>FALSE</ntsc>
                            </rate>
                            <start>1868.0</start>
                            <end>2471.9999999999995</end>
                            <in>444.0</in>
                            <out>1048.0</out>
                            <pproTicksIn>112783104000000.0</pproTicksIn>
                            <pproTicksOut>266208768000000.0</pproTicksOut>
                            <file id="SG00IW75Y5"/>
                            <sourcetrack>
                                <mediatype>audio</mediatype>
                                <trackindex>2</trackindex>
                            </sourcetrack>
                            <filter>
                                <effect>
                                    <name>Audio Levels</name>
                                    <effectid>audiolevels</effectid>
                                    <effectcategory>audiolevels</effectcategory>
                                    <effecttype>audiolevels</effecttype>
                                    <mediatype>audio</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>level</parameterid>
                                        <name>Level</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>3.98109</valuemax>
                                        <value>1.0</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>1.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                        </clipitem>
                        <clipitem id="N2D64Q4B9F-audio" premiereChannelType="stereo">
                            <name>The Epic.wav</name>
                            <enabled>TRUE</enabled>
                            <duration>4200.46875</duration>
                            <rate>
                                <timebase>30</timebase>
                                <ntsc>FALSE</ntsc>
                            </rate>
                            <start>3276.0</start>
                            <end>7476.46875</end>
                            <in>0.0</in>
                            <out>4200.46875</out>
                            <pproTicksIn>0.0</pproTicksIn>
                            <pproTicksOut>1066986270000000.0</pproTicksOut>
                            <file id="PTWYH9FRCD">
                                <name>The Epic.wav</name>
                                <pathurl>The Epic.wav</pathurl>
                                <rate>
                                    <timebase>30</timebase>
                                    <ntsc>TRUE</ntsc>
                                </rate>
                                <duration>4196</duration>
                                <timecode>
                                    <rate>
                                        <timebase>30</timebase>
                                        <ntsc>TRUE</ntsc>
                                    </rate>
                                    <string>00;00;00;00</string>
                                    <frame>0</frame>
                                    <displayformat>DF</displayformat>
                                </timecode>
                                <media>
                                    <audio>
                                        <samplecharacteristics>
                                            <depth>16</depth>
                                            <samplerate>44100</samplerate>
                                        </samplecharacteristics>
                                        <channelcount>2</channelcount>
                                    </audio>
                                </media>
                            </file>
                            <sourcetrack>
                                <mediatype>audio</mediatype>
                                <trackindex>2</trackindex>
                            </sourcetrack>
                            <filter>
                                <effect>
                                    <name>Audio Levels</name>
                                    <effectid>audiolevels</effectid>
                                    <effectcategory>audiolevels</effectcategory>
                                    <effecttype>audiolevels</effecttype>
                                    <mediatype>audio</mediatype>
                                    <pproBypass>false</pproBypass>
                                    <parameter authoringApp="OpenShot">
                                        <parameterid>level</parameterid>
                                        <name>Level</name>
                                        <valuemin>0</valuemin>
                                        <valuemax>3.98109</valuemax>
                                        <value>1.0</value>
                                        <keyframe>
                                            <when>1.0</when>
                                            <value>0.0</value>
                                        </keyframe>
                                        <keyframe>
                                            <when>91.0</when>
                                            <value>1.0</value>
                                        </keyframe>
                                        <keyframe>
                                            <when>4111.0</when>
                                            <value>1.0</value>
                                        </keyframe>
                                        <keyframe>
                                            <when>4201.0</when>
                                            <value>0.0</value>
                                        </keyframe>
                                    </parameter>
                                </effect>
                            </filter>
                            <logginginfo>
                                <description/>
                                <scene/>
                                <shottake/>
                                <lognote/>
                                <good/>
                                <originalvideofilename/>
                                <originalaudiofilename/>
                            </logginginfo>
                            <colorinfo>
                                <lut/>
                                <lut1/>
                                <asc_sop/>
                                <asc_sat/>
                                <lut2/>
                            </colorinfo>
                        </clipitem>
                    </track>
                </audio>
            </media>
            <timecode>
                <rate>
                    <timebase>30.0</timebase>
                    <ntsc>TRUE</ntsc>
                </rate>
                <string>00;00;00;01</string>
                <frame>1</frame>
                <displayformat>DF</displayformat>
            </timecode>
        </sequence>
    </xmeml>
