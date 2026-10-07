"""
 @file
 @brief This file converts project data from one FPS to a new FPS (adjusting precisions, trims, and positions)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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


def change_profile(clips, new_profile):
    """Snap timing to the new grid while preserving nonempty clips and joins.

    Only repair boundaries which touched before conversion, on the same layer
    and between the same kind of object. Intentional gaps/overlaps are edits,
    not rounding errors. A run of one-frame clips may need to grow when the
    new FPS is lower: never erase a clip to keep the original total duration.
    """
    frame_time = new_profile.info.fps.den / new_profile.info.fps.num
    groups = {}
    for clip in clips:
        if 'start' in clip and 'end' in clip:
            key = (clip.get('layer'), clip.get('type'))
            groups.setdefault(key, []).append(clip)

    joins = []
    for group in groups.values():
        ordered = sorted(group, key=lambda clip: clip['position'])
        for previous, current in zip(ordered, ordered[1:]):
            right = previous['position'] + previous['end'] - previous['start']
            if abs(current['position'] - right) < 1e-7:
                joins.append((previous, current))

    def snap(seconds):
        return round(seconds / frame_time) * frame_time

    for clip in clips:
        nonempty = clip.get('end', 0) > clip.get('start', 0)
        clip['position'] = snap(clip['position'])
        if 'start' in clip:
            clip['start'] = snap(clip['start'])
        if 'end' in clip:
            clip['end'] = snap(clip['end'])
            if nonempty and 'start' in clip:
                clip['end'] = max(clip['end'], clip['start'] + frame_time)

    for previous, current in joins:
        duration = snap(current['position'] - previous['position'])
        if duration >= frame_time - 1e-7:
            previous['end'] = snap(previous['start'] + duration)
        else:
            current['position'] = snap(previous['position'] + previous['end'] - previous['start'])

    for clip in clips:
        if 'start' in clip and 'end' in clip:
            clip['duration'] = clip['end'] - clip['start']
    return clips
