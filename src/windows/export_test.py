#!/usr/bin/env python3

""" 
 @file
 @brief This file tests exporting a video in a specific format/codec
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE
 
 Copyright (c) 2008-2014 OpenShot Studios, LLC
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
 """

import openshot
import os, sys


# Write test video to this path
EXPORT_TESTS = os.path.join(os.path.expanduser("~"), ".openshot_qt", "tests")

# Check for the correct # of arguments
if len(sys.argv) != 15:
	print("Error: %s is not the correct # of arguments (15 expected)" % len(sys.argv))
	exit()
	
print("Params:")
print(sys.argv)
	
# Get video params from the arguments passed to this script
format = sys.argv[1]
codec = sys.argv[2]
fps = openshot.Fraction(int(sys.argv[3]), int(sys.argv[4]))
width = int(sys.argv[5])
height = int(sys.argv[6])
pixel_ratio = openshot.Fraction(int(sys.argv[7]), int(sys.argv[8]))
bitrate = int(sys.argv[9])

# Get audio params
audio_codec = sys.argv[10]
sample_rate = int(sys.argv[11])
channels = int(sys.argv[12])
channel_layout = int(sys.argv[13])
audio_bitrate = int(sys.argv[14])


# Determine final exported file path
export_file_path = os.path.join(EXPORT_TESTS, "test.%s" % format)
print("Test Export to %s" % export_file_path)

# Create FFmpegWriter
w = openshot.FFmpegWriter(export_file_path);

# Set Audio & Video Options
w.SetVideoOptions(True, codec, fps, width, height, pixel_ratio, False, False, bitrate);
w.SetAudioOptions(True, audio_codec, sample_rate, channels, channel_layout, audio_bitrate);

w.DisplayInfo()

# Open the writer
w.Open();

for frame_number in range(30):
	# Create empty frame
	f = openshot.Frame(frame_number, width, height, "#ffffff")
	f.AddColor(width, height, "#ffffff")
	
	# Write some test frames
	w.WriteFrame(f)

# Close writer
w.Close()
	
# Success if we reached this line succesfully
print("*SUCCESS*")

