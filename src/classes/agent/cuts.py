"""
 @file
 @brief Timeline cuts through Query and the caller's existing undo transaction.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
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
import copy
import math

from classes.query import Clip
from .protocol import CommandError


def split_clip(service, params):
    """Keep both halves using the GUI's source-trim slicing semantics.

    Curves retain source coordinates, including time-remapping curves. The caller
    supplies a transaction (EditingService.execute does this for all mutations).
    """
    requested = params['at']
    if isinstance(requested, bool) or not isinstance(requested, (int, float)) or not math.isfinite(requested) or requested < 0:
        raise CommandError('invalid_argument', 'at must be finite nonnegative timeline seconds.', {'path': 'params.at'})
    left = service.obj('clip', params['id'])
    original = copy.deepcopy(left.data)
    layer = next((row for row in service.app.project.get('layers') or [] if row['number'] == original.get('layer')), {})
    if layer.get('lock'):
        raise CommandError('locked_track', 'The clip is on a locked track. Unlock it before splitting.', {'layer': original.get('layer')})
    fps = service.fps()
    at = math.floor(requested * fps + 0.5) / fps
    position, start, end = (float(original.get(key, 0)) for key in ('position', 'start', 'end'))
    finish = position + end - start
    if not position < at < finish:
        raise CommandError('out_of_range', 'The snapped split must be strictly inside the clip; at is timeline seconds.',
                           {'path': 'params.at', 'requested_at': requested, 'at': at, 'timeline_start': position, 'timeline_end': finish})
    boundary = start + at - position
    left_data = copy.deepcopy(original)
    left_data.update(end=boundary, duration=boundary-start)
    right_data = copy.deepcopy(original)
    right_data.pop('id', None)
    right_data.update(position=at, start=boundary, duration=end-boundary)
    for effect in right_data.get('effects', []):
        effect['id'] = service.app.project.generate_id()
    # Parse both complete native clips before either Query distributes an update.
    for data in (left_data, right_data):
        service.validate_timing(data)
        service.native('clip', data)
    right = Clip()
    right.data = right_data
    right.save()
    left.data = {'end': boundary, 'duration': boundary-start}
    left.save()
    return {'left': service.summary('clip', service.obj('clip', left.id).data),
            'right': service.summary('clip', service.obj('clip', right.id).data),
            'at': at, 'requested_at': requested}
