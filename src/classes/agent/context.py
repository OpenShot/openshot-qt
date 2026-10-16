"""
 @file
 @brief Compact, read-only timeline context for editing agents.

Intervals are half-open seconds. Frame spans are one-based, inclusive/exclusive.
Source frames use reader FPS; keyframe coordinates use project FPS and include trim.

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
import json
import math
from pathlib import Path

from .protocol import CommandError


def _rate(value):
    value = value or {}
    return float(value.get('num', 0)) / float(value.get('den', 1) or 1)


def _timecode(seconds):
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    secs, millis = divmod(millis, 1000)
    return '{:02d}:{:02d}:{:02d}.{:03d}'.format(hours, minutes, secs, millis)


def _round_frame(value):
    """Match native std::llround for nonnegative frame coordinates."""
    return math.floor(value + 0.5)


def _interval(start, end, fps=None, native_bounds=False):
    result = {'start': round(start, 6), 'end': round(end, 6),
              'timecodes': [_timecode(start), _timecode(end)]}
    if fps:
        quantize = _round_frame if native_bounds else lambda value: math.ceil(value - 1e-8)
        result['frames'] = [quantize(start * fps) + 1, quantize(end * fps) + 1]
    return result


def _value(data, field, frame, default):
    value = data.get(field, default)
    if isinstance(value, dict):
        import openshot
        keyframe = openshot.Keyframe()
        keyframe.SetJson(json.dumps(value))
        return keyframe.GetValue(frame)
    return value


def _remapped(data):
    points = data.get('time', {}).get('Points', [])
    return bool(points and not (len(points) == 1 and points[0].get('co') == {'X': 1, 'Y': 1}))


def overview(app, start=0, end=None, layer=None, limit=100, offset=0):
    """Return bounded context without native property dumps or media payloads."""
    project = app.project
    clips = list(project.get('clips') or [])
    transitions = list(project.get('effects') or [])
    duration = max([0] + [float(c.get('position', 0)) + max(0, float(c.get('end', 0)) - float(c.get('start', 0))) for c in clips])
    end = duration if end is None else end
    for key, value in [('start', start), ('end', end)]:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise CommandError('invalid_argument', key + ' must be finite nonnegative seconds.')
    if end < start:
        raise CommandError('invalid_argument', 'end must be >= start (timeline seconds).')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise CommandError('invalid_argument', 'limit must be an integer from 1 to 500.')
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise CommandError('invalid_argument', 'offset must be a nonnegative integer.')
    layers = project.get('layers') or []
    track_names = {item['number']: item.get('label') or item.get('name') or 'Track {}'.format(index + 1)
                   for index, item in enumerate(sorted(layers, key=lambda item: item['number']))}
    if layer is not None and layer not in [item['number'] for item in layers]:
        raise CommandError('invalid_layer', 'Unknown layer; inspect tracks in timeline overview.')
    fps = _rate(project.get('fps'))
    files = {item['id']: item for item in project.get('files') or []}
    ordered = sorted([(c, 'clip') for c in clips] + [(c, 'transition') for c in transitions],
                     key=lambda pair: (-pair[0].get('layer', 0), pair[0].get('position', 0), pair[0].get('id', '')))
    tracks = {}
    for item, kind in ordered:
        tracks.setdefault(item.get('layer'), []).append((item, kind))
    matching = []
    for number, items in tracks.items():
        if layer is not None and layer != number:
            continue
        for index, (item, kind) in enumerate(items):
            position = float(item.get('position', 0))
            trim = float(item.get('start', 0))
            finish = position + max(0, float(item.get('end', 0)) - trim)
            if finish <= start or position >= end:
                continue
            matching.append((number, items, index, item, kind, position, trim, finish))
    rows = []
    for number, items, index, item, kind, position, trim, finish in matching[offset:offset + limit]:
        visible_start, visible_end = max(start, position), min(end, finish)
        reader = item.get('reader') or {}
        file = files.get(item.get('file_id'), {})
        source_fps = _rate(reader.get('fps') or file.get('fps'))
        # The native timeline rounds clip position and trim separately. Requested
        # viewport bounds select frame timestamps by ceil; continuous seconds
        # remain unchanged and are distinct from these rendered coordinates.
        clip_first = _round_frame(position * fps) + 1
        clip_end = _round_frame(finish * fps) + 1
        visible_first = max(clip_first, math.ceil(start * fps - 1e-8) + 1)
        visible_frame_end = min(clip_end, math.ceil(end * fps - 1e-8) + 1)
        keyframe_frame = visible_first - clip_first + _round_frame(trim * fps) + 1
        row = {'id': item.get('id'), 'kind': kind, 'layer': number, 'sequence': index + 1,
               'name': item.get('title') or item.get('name') or Path(item.get('file_path') or item.get('path') or file.get('path') or '').name,
               'timeline': _interval(position, finish, fps, native_bounds=True),
               'visible': _interval(visible_start, visible_end, fps)}
        row['visible']['frames'] = [visible_first, max(visible_first, visible_frame_end)]
        if item.get('file_id'):
            row['file_id'] = item['file_id']
        if kind == 'clip':
            remapped = _remapped(item)
            row['source'] = {'trim': _interval(trim, float(item.get('end', trim)), source_fps),
                             'mapping': 'time_remapped' if remapped else 'linear', 'fps': source_fps or None}
            if not remapped:
                row['source']['visible'] = _interval(trim + visible_start - position, trim + visible_end - position, source_fps)
            else:
                row['source']['note'] = 'Time remapping is active; visible source frames are not inferred. Inspect clip get ID time.'
            audio = _value(item, 'has_audio', keyframe_frame, -1)
            video = _value(item, 'has_video', keyframe_frame, -1)
            row['at_visible_start'] = {
                'keyframe_frame': keyframe_frame,
                'timeline_frame': visible_first,
                'sample_seconds': round((visible_first - 1) / fps, 9),
                'has_rendered_frame': visible_first < visible_frame_end,
                'has_audio': bool(reader.get('has_audio', file.get('has_audio', False))) if audio == -1 else bool(audio),
                'has_video': bool(reader.get('has_video', file.get('has_video', False))) if video == -1 else bool(video),
                'volume': _value(item, 'volume', keyframe_frame, 1)}
            row['effects'] = [{'id': effect.get('id'), 'type': effect.get('class_name') or effect.get('type')} for effect in item.get('effects', [])]
        neighbors = {}
        for label, neighbor_index in [('previous', index - 1), ('next', index + 1)]:
            if 0 <= neighbor_index < len(items):
                neighbor = items[neighbor_index][0]
                nstart = float(neighbor.get('position', 0))
                nend = nstart + max(0, float(neighbor.get('end', 0)) - float(neighbor.get('start', 0)))
                gap = position - nend if label == 'previous' else nstart - finish
                neighbors[label] = {'id': neighbor.get('id'), 'gap_seconds': round(gap, 6)}
        row['neighbors'] = neighbors
        rows.append(row)
    return {'revision': app.updates.data_version, 'duration': round(duration, 6),
            'profile': {key: project.get(key) for key in ('width', 'height', 'fps')},
            'range': _interval(start, end, fps),
            'units': {'intervals': 'seconds, end exclusive', 'frames': 'one-based [first, end-exclusive]; timeline clip boundaries use native nearest-frame rounding; viewport selects frame timestamps; source frames describe continuous source intervals at reader FPS, not decoder sampling',
                      'keyframes': 'one-based project-FPS frame including source trim', 'neighbors': 'same-track chronological items; negative gap means overlap'},
            'counts': {'files': len(files), 'clips': len(clips), 'transitions': len(transitions), 'effects': sum(len(c.get('effects', [])) for c in clips)},
            'tracks': [{'layer': item['number'], 'name': track_names[item['number']], 'items': len(tracks.get(item['number'], []))} for item in sorted(layers, key=lambda x: -x['number']) if layer is None or layer == item['number']],
            'items': rows, 'pagination': {'offset': offset, 'limit': limit, 'total': len(matching),
                                         'next_offset': offset + limit if offset + limit < len(matching) else None}}


def view(app, params):
    """Text and JSON share the bounded timeline model; neither decodes media."""
    data = overview(app, **{key: params[key] for key in ('start', 'end', 'layer', 'limit', 'offset') if key in params})
    if not params.get('all_tracks') and params.get('layer') is None:
        data['tracks'] = [track for track in data['tracks'] if track['items']]
    detail = params.get('detail', 'clips')
    if detail == 'summary':
        data.pop('items')
    elif detail == 'clips':
        data['items'] = [
            {'id': row['id'], 'kind': row['kind'], 'name': row['name'], 'layer': row['layer'],
             'timeline': [row['timeline']['start'], row['timeline']['end']],
             'source': [row.get('source', {}).get('trim', {}).get('start'), row.get('source', {}).get('trim', {}).get('end')],
             'streams': row.get('at_visible_start', {}), 'effects': row.get('effects', []),
             'neighbors': row.get('neighbors', {})}
            for row in data['items']]
    if params.get('format', 'text') == 'json':
        return data
    fps = data['profile']['fps']
    lines = ['Timeline revision {} | {}x{} | {}/{} fps | {:.3f}–{:.3f}s'.format(
        data['revision'], data['profile']['width'], data['profile']['height'], fps['num'], fps['den'], data['range']['start'], data['range']['end'])]
    for track in data['tracks']:
        lines.append('{} (layer {}, {} items)'.format(track['name'], track['layer'], track['items']))
        for row in data.get('items', []):
            if row['layer'] != track['layer']:
                continue
            timeline = row['timeline']
            start, end = (timeline['start'], timeline['end']) if isinstance(timeline, dict) else timeline
            source = row.get('source')
            if isinstance(source, dict):
                source = [source.get('trim', {}).get('start'), source.get('trim', {}).get('end')]
            streams = row.get('streams', row.get('at_visible_start', {}))
            audio = 'muted' if not streams.get('has_audio') or streams.get('volume') == 0 else 'gain={:.3g}'.format(streams.get('volume', 1))
            name = ' '.join(str(row['name']).split())[:100]
            text = '  {}  {:8.3f}–{:8.3f}  {}'.format(row['id'], start, end, name)
            if source and source[0] is not None:
                text += '  source {:.3f}–{:.3f}  {}'.format(*source, audio)
            gap = row.get('neighbors', {}).get('previous', {}).get('gap_seconds')
            if gap:
                text += '  {} {:.3f}s'.format('gap' if gap > 0 else 'overlap', abs(gap))
            lines.append(text)
            if detail == 'full':
                lines.append('    '+json.dumps({k: v for k, v in row.items() if k not in ('name', 'id', 'kind', 'layer')}, separators=(',', ':')))
    if data['pagination']['next_offset'] is not None:
        lines.append('More items: --offset {}'.format(data['pagination']['next_offset']))
    lines.append('Seconds; ends exclusive. Use --format json --detail full for frame coordinates and exact metadata.')
    return {'format': 'text', 'text': '\n'.join(lines), 'revision': data['revision']}
