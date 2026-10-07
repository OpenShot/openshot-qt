"""Timeline cuts through Query and the caller's existing undo transaction."""
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
