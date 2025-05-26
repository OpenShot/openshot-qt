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


def remove_gaps(clips, new_profile):
    project_fps_num = new_profile.info.fps.num
    project_fps_den = new_profile.info.fps.den
    FRAME_DURATION = project_fps_den / project_fps_num  # Duration of one frame

    # Define a tolerance in frames (e.g., 1 to 3 frames)
    max_gap_tolerance = 3 * FRAME_DURATION
    min_gap_tolerance = 1 / 10000  # Tiny tolerance for floating-point drift

    def snap_to_new_fps_grid(time_in_seconds):
        # Snap the time to the nearest frame boundary based on the FPS grid
        return round(time_in_seconds / FRAME_DURATION) * FRAME_DURATION

    # Sort clips by position to ensure we handle them in order
    clips.sort(key=lambda x: x['position'])

    # Iterate over the clips and adjust tiny gaps (by modifying the "end" attribute)
    for i in range(1, len(clips)):
        current_clip = clips[i]
        previous_clip = clips[i - 1]
        if 'start' not in current_clip or 'start' not in previous_clip:
            continue
        if 'end' not in current_clip or 'end' not in previous_clip:
            continue

        # Calculate the right edge of the previous clip
        previous_clip_right_edge = snap_to_new_fps_grid(previous_clip['position'] + (previous_clip['end'] - previous_clip['start']))

        # Calculate the gap between the current clip's position and the end of the previous clip
        gap = current_clip['position'] - previous_clip_right_edge

        # Fix tiny gaps or overlaps within the tolerance range (1-3 frames) by adjusting the "end" of the previous clip
        if min_gap_tolerance < abs(gap) < max_gap_tolerance:
            # Adjust the "end" of the previous clip to fill the gap
            previous_clip['end'] += gap  # Extend the end trim by the gap size

        # Ensure that the adjusted "end" is snapped to the grid
        previous_clip['end'] = snap_to_new_fps_grid(previous_clip['end'])

    return clips

def change_profile(clips, new_profile):
    """Adjust all clip-like objects to use project FPS precision, adjusting 'end' trim
    (if needed) to close any tiny (1 to 3 frame) gaps."""
    project_fps_num = new_profile.info.fps.num
    project_fps_den = new_profile.info.fps.den

    def snap_to_new_fps_grid(time_in_seconds):
        frame_time = project_fps_den / project_fps_num
        return round(time_in_seconds / frame_time) * frame_time

    for clip in clips:
        # Update position, start, and end to the new profile's FPS grid
        clip['position'] = snap_to_new_fps_grid(clip['position'])
        if 'start' in clip:
            clip['start'] = snap_to_new_fps_grid(clip['start'])
        if 'end' in clip:
            clip['end'] = snap_to_new_fps_grid(clip['end'])

    # After snapping to the new grid, remove gaps by adjusting the "end" attribute
    return remove_gaps(clips, new_profile)
