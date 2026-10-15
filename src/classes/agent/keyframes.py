"""
 @file
 @brief Curve editing in explicit project-FPS coordinates, through existing Query updates.

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
from collections import Counter
import copy
import difflib
import json
import math

import openshot

from .protocol import CommandError
from .validation import numeric, unknown


def fail(message, path='params', hint=None, **details):
    if hint:
        message += ' ' + hint
    raise CommandError('invalid_keyframe', message, dict(details, path=path, hint=hint))


def curve_paths(data, prefix=''):
    result = []
    if isinstance(data, dict):
        if 'Points' in data:
            return [{'property': prefix, 'point_count': len(data['Points'])}]
        for key, value in data.items():
            if key not in ('reader', 'effects', 'mask_reader'):
                result.extend(curve_paths(value, prefix + '.' + key if prefix else key))
    return result


def property_curve(obj, path):
    parts = path.split('.')
    value = obj.data
    for part in parts:
        if not isinstance(value, dict) or part not in value or part in ('reader', 'effects', 'mask_reader'):
            value = None
            break
        value = value[part]
    if not isinstance(value, dict) or 'Points' not in value:
        choices = [p['property'] for p in curve_paths(obj.data)]
        close = difflib.get_close_matches(path, choices, n=1)
        hint = "Did you mean '{}'?".format(close[0]) if close else 'Run keyframe list ID to discover curve property paths.'
        fail('Not a keyframe property: ' + path, 'params.property', hint, property=path, available=choices)
    return copy.deepcopy(value)


class Coordinates:
    def __init__(self, service, kind, obj, params):
        self.fps = service.fps()
        self.space = params.get('space', 'native')
        self.unit = params.get('unit', 'frames')
        timing = service.obj('clip', obj.parent['id']).data if kind == 'effect' else obj.data
        trim = self.round(timing.get('start', 0) * self.fps)
        position = self.round(timing.get('position', 0) * self.fps)
        self.shift = {'native': 0, 'clip': trim, 'timeline': trim - position}[self.space]
        self.context = {'native_frame_at_clip_start': trim + 1,
                        'timeline_frame_at_clip_start': position + 1,
                        'trim_seconds': timing.get('start', 0),
                        'position_seconds': timing.get('position', 0)}

    @staticmethod
    def round(value):
        return math.floor(value + 0.5)

    def native(self, value, path='params.at'):
        numeric(value, path, integer=self.unit == 'frames')
        frame = value if self.unit == 'frames' else self.round(value * self.fps) + 1
        return int(frame + self.shift)

    def external(self, frame):
        value = frame - self.shift
        return value if self.unit == 'frames' else (value - 1) / self.fps

    def delta(self, value):
        numeric(value, 'params.offset', integer=self.unit == 'frames')
        return value if self.unit == 'frames' else value * self.fps


def selected(points, coords, params):
    start = coords.native(params['start'], 'params.start') if 'start' in params else -math.inf
    end = coords.native(params['end'], 'params.end') if 'end' in params else math.inf
    if end < start:
        fail('Range end must be at or after start; keyframe ranges are inclusive.', 'params.end', start=params.get('start'), end=params.get('end'))
    return [p for p in points if start <= p['co']['X'] <= end]


def evaluated(curve, frame):
    native = openshot.Keyframe()
    native.SetJson(json.dumps(curve))
    return native.GetValue(frame)


def store(service, kind, obj, path, points):
    if not points:
        fail('A curve must retain at least one point.')
    points = sorted(points, key=lambda p: p['co']['X'])
    frames = [p['co']['X'] for p in points]
    if len(frames) != len(set(frames)):
        duplicates = sorted(frame for frame, count in Counter(frames).items() if count > 1)
        fail('Multiple points would occupy the same native frame; no changes applied.',
             hint='Change offset/scale or narrow the range. Use keyframe list to inspect existing points.', frames=duplicates)
    if any(frame < 1 for frame in frames):
        fail('The edit moves points before native frame 1; no changes applied.',
             hint='Increase the target coordinate/offset or choose a later range.', frames=[f for f in frames if f < 1])
    root, *parts = path.split('.')
    value = copy.deepcopy(obj.data[root])
    if parts:
        container = value
        for part in parts[:-1]:
            container = container[part]
        container[parts[-1]] = {'Points': points}
    else:
        value = {'Points': points}
    # Reuse semantic/property validation and native parsing before publishing.
    service.dispatch(kind + '.set', {'id': obj.id, 'values': {root: value}})
    return {'id': obj.id, 'property': path, 'point_count': len(points)}


def command(service, kind, operation, params):
    obj = service.obj(kind, params['id'])
    coords = Coordinates(service, kind, obj, params)
    path = params.get('property')
    if operation == 'list' and not path:
        if 'start' in params or 'end' in params:
            fail('Specify property before filtering a keyframe range.', 'params.property')
        return {'id': obj.id, 'kind': kind, 'properties': curve_paths(obj.data),
                'fps': service.app.project.get('fps'), 'coordinates': coords.context}
    curve = property_curve(obj, path)
    points = curve['Points']
    if operation == 'list':
        result = selected(points, coords, params)
        native_frames = [p['co']['X'] for p in result]
        for point in result:
            point['co']['X'] = coords.external(point['co']['X'])
        return {'id': obj.id, 'property': path, 'space': coords.space, 'unit': coords.unit,
                'fps': service.app.project.get('fps'), 'coordinates': coords.context,
                'native_frames': native_frames, 'points': result}
    if operation == 'set':
        if 'frame' in params:
            if 'at' in params or coords.space != 'native' or coords.unit != 'frames':
                fail('frame is a legacy native-frame coordinate; use at for other coordinates.')
            frame = params['frame']
        elif 'at' in params:
            frame = coords.native(params['at'])
        else:
            fail('set requires at or legacy frame.', 'params.at',
                 'Use --space clip --unit seconds --at 0 for the visible clip start.')
        if frame < 1:
            fail('The requested coordinate resolves to native frame {}; native frames start at 1.'.format(frame),
                 'params.frame' if 'frame' in params else 'params.at',
                 'Use --space clip --unit seconds --at 0 for the visible clip start.',
                 native_frame=frame, coordinates=coords.context)
        numeric(frame, 'params.frame', integer=True, minimum=1)
        point = next((copy.deepcopy(p) for p in points if p['co']['X'] == frame),
                     json.loads(openshot.Keyframe(params['value']).Json())['Points'][0])
        point['co'] = {'X': frame, 'Y': params['value']}
        point['interpolation'] = int({'linear': openshot.LINEAR, 'bezier': openshot.BEZIER,
                                      'constant': openshot.CONSTANT}[params.get('interpolation', 'linear')])
        handles = params.get('handles', {})
        for key in handles:
            if key not in ('handle_left', 'handle_right', 'handle_type'):
                unknown('params.handles', key, ('handle_left', 'handle_right', 'handle_type'))
        point.update(copy.deepcopy(handles))
        points = [p for p in points if p['co']['X'] != frame] + [point]
    elif operation == 'clear':
        if 'value' in params and 'at' in params:
            fail('clear accepts value or at, not both.')
        frame = coords.native(params['at']) if 'at' in params else 1
        if frame < 1:
            fail('The sampling coordinate resolves before native frame 1.', 'params.at',
                 'Use --space clip --unit seconds --at 0 to sample the visible clip start.', coordinates=coords.context)
        value = params['value'] if 'value' in params else evaluated(curve, frame)
        points = json.loads(openshot.Keyframe(value).Json())['Points']
    elif operation in ('remove', 'transform'):
        if operation == 'remove' and 'at' in params:
            if 'start' in params or 'end' in params:
                fail('remove accepts at or start/end, not both.')
            chosen = [p for p in points if p['co']['X'] == coords.native(params['at'])]
        else:
            if operation == 'remove' and not any(k in params for k in ('start', 'end')):
                fail('remove requires at or a range; use clear to remove all animation.', 'params.at')
            chosen = selected(points, coords, params)
        if not chosen:
            fail('No keyframe points match the requested range.',
                 hint='Run keyframe list with the same space/unit; remove edits existing points, not interpolated samples.')
        untouched = [p for p in points if p not in chosen]
        if operation == 'remove':
            points = untouched or json.loads(openshot.Keyframe(evaluated(curve, 1)).Json())['Points']
        else:
            scale = params.get('scale', 1)
            numeric(scale, 'params.scale', minimum=0)
            if scale == 0:
                fail('Time scale must be greater than zero.')
            pivot = coords.native(params['pivot'], 'params.pivot') if 'pivot' in params else chosen[0]['co']['X']
            offset = coords.delta(params.get('offset', 0))
            for point in chosen:
                point['co']['X'] = coords.round(pivot + (point['co']['X'] - pivot) * scale + offset)
            points = untouched + chosen
    elif operation in ('copy', 'paste'):
        if operation == 'copy':
            if 'at' not in params:
                fail('copy requires a destination at coordinate.')
            source = service.obj(kind, params['source_id'])
            source_curve = property_curve(source, params.get('source_property', path))
            source_coords = Coordinates(service, kind, source, params)
            incoming = selected(source_curve['Points'], source_coords, params)
            if not incoming:
                fail('No source points match the requested range.')
            # Anchor the first copied point, not the source trim, at the destination.
            delta = coords.native(params['at']) - incoming[0]['co']['X']
            for point in incoming:
                point['co']['X'] += delta
        else:
            incoming = copy.deepcopy(params['points'])
            if not 1 <= len(incoming) <= 10000:
                fail('paste requires 1..10000 point objects.')
            for index, point in enumerate(incoming):
                if not isinstance(point, dict) or not isinstance(point.get('co'), dict) or 'X' not in point['co']:
                    fail('Each pasted point requires co.X and co.Y.')
                point['co']['X'] = coords.native(point['co']['X'], 'params.points[{}].co.X'.format(index))
        frames = [p['co']['X'] for p in incoming]
        if len(frames) != len(set(frames)):
            fail('Copied/pasted points collide after frame snapping.')
        points = incoming if params['mode'] == 'replace' else [p for p in points if p['co']['X'] not in frames] + incoming
    else:
        fail('Unknown keyframe operation: ' + operation)
    return store(service, kind, obj, path, points)
