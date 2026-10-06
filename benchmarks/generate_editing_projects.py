# @file
# @brief Generate media and projects for editing benchmarks
# @author OpenShot Studios, LLC
#
# @section LICENSE
#
# Copyright (c) 2008-2026 OpenShot Studios, LLC
# (http://www.openshotstudios.com). This file is part of
# OpenShot Video Editor (http://www.openshot.org), an open-source project
# dedicated to delivering high quality video editing and animation solutions
# to the world.
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
#

"""Generate redistributable MP4/MP3 fixtures and OSP projects for manual timings.

Usage: python3 benchmarks/generate_editing_projects.py /tmp/editing-projects
Requires ffmpeg and the same openshot binding used by the application.
"""
import copy
import json
import os
import shutil
# Generate local fixtures using the installed ffmpeg.
import subprocess  # nosec B404
import sys

import openshot

output = os.path.abspath(sys.argv[1])
os.makedirs(output, exist_ok=True)
video = os.path.join(output, "test-pattern.mp4")
audio = os.path.join(output, "sine.mp3")
ffmpeg = shutil.which("ffmpeg")
if ffmpeg is None:
    raise SystemExit("ffmpeg is required to generate editing fixtures")
# Fixed ffmpeg arguments and absolute output paths; no shell interpolation.
# A long GOP makes nonsequential seeks more expensive, without external content.
subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                "testsrc2=size=1280x720:rate=24", "-f", "lavfi", "-i",
                "sine=frequency=440:sample_rate=48000", "-t", "30", "-c:v",
                "libx264", "-preset", "ultrafast", "-g", "240", "-c:a", "aac", video], check=True, shell=False)  # nosec B603
subprocess.run([ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                "sine=frequency=660:sample_rate=48000", "-t", "30", "-c:a",
                "libmp3lame", audio], check=True, shell=False)  # nosec B603
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(root, "src", "settings", "_default.project")) as stream:
    template = json.load(stream)
readers = {}
for index, path in enumerate((video, audio)):
    reader = openshot.FFmpegReader(path)
    reader.Open()
    data = json.loads(reader.Json())
    data.update(id="F%d" % index, media_type="video" if index == 0 else "audio")
    readers[path] = data
    reader.Close()


def clip(path, index, position, start, end, layer):
    native = openshot.Clip(path)
    data = json.loads(native.Json())
    data.update(id="C%d" % index, file_id=readers[path]["id"],
                position=position, start=start, end=end, duration=end-start, layer=layer)
    return data


for name in ("overlapping-av", "long-gop", "many-short", "edit-undo-playback"):
    project = copy.deepcopy(template)
    project["profile"] = "HD 720p 24 fps"
    project["files"] = list(readers.values())
    if name == "many-short":
        project["clips"] = [clip(video if i % 2 == 0 else audio, i,
                                  i * .25, (i % 20) * .5, (i % 20) * .5 + .5,
                                  1000000 + (i % 2) * 1000000) for i in range(100)]
    elif name == "long-gop":
        project["clips"] = [clip(video, 0, 0., 0., 30., 1000000)]
    else:
        project["clips"] = [clip(video if i % 2 == 0 else audio, i,
                                  i * .5, 0., 20., 1000000 + i * 1000000)
                             for i in range(4)]
    path = os.path.join(output, name + ".osp")
    with open(path, "w") as stream:
        json.dump(project, stream, indent=1)
    print(path)
