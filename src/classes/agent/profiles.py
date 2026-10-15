"""
 @file
 @brief Installed, source-derived and portable project profiles using libopenshot.

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
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import openshot
from classes import info
from .protocol import CommandError
from .validation import fail, numeric

FIELDS = {'description', 'width', 'height', 'fps', 'pixel_ratio', 'display_ratio',
          'progressive', 'spherical', 'pixel_format'}
MATCH_FIELDS = ('width', 'height', 'fps', 'pixel_ratio', 'display_ratio', 'progressive', 'spherical')


def validate(data):
    if not isinstance(data, dict):
        fail('profile', 'a profile JSON object', data)
    for key in data:
        if key not in FIELDS:
            from .validation import unknown
            unknown('profile', key, FIELDS)
    for key in ('width', 'height'):
        numeric(data.get(key), 'profile.'+key, integer=True, minimum=1, maximum=16384)
    for key in ('fps', 'pixel_ratio', 'display_ratio'):
        value = data.get(key)
        if not isinstance(value, dict) or set(value) != {'num', 'den'}:
            fail('profile.'+key, '{"num": positive integer, "den": positive integer}', value)
        for part in ('num', 'den'):
            numeric(value[part], 'profile.'+key+'.'+part, integer=True, minimum=1, maximum=10000000)
    for key in ('progressive', 'spherical'):
        if not isinstance(data.get(key), bool):
            fail('profile.'+key, 'a boolean', data.get(key))
    numeric(data.get('pixel_format', 0), 'profile.pixel_format', integer=True, minimum=0)
    if not isinstance(data.get('description'), str) or not data['description'].strip():
        fail('profile.description', 'a nonempty description', data.get('description'))
    result = copy.deepcopy(data)
    for key in ('fps', 'pixel_ratio', 'display_ratio'):
        fraction = Fraction(result[key]['num'], result[key]['den'])
        result[key] = {'num': fraction.numerator, 'den': fraction.denominator}
    native = openshot.Profile()
    native.SetJson(json.dumps(result))
    return json.loads(native.Json())


def catalogue(search=None):
    rows = []
    for origin, folder in [('user', info.USER_PROFILES_PATH), ('builtin', info.PROFILES_PATH)]:
        for path in sorted(Path(folder).glob('*')):
            if not path.is_file():
                continue
            try:
                data = json.loads(openshot.Profile(str(path)).Json())
                if search and search.casefold() not in (path.name+' '+data['description']).casefold():
                    continue
                rows.append(dict(data, id=origin+':'+path.name, origin=origin))
            except (RuntimeError, ValueError):
                continue
    return rows


def get(identifier):
    matches = [row for row in catalogue() if identifier in (row['id'], row['description'])]
    if len(matches) != 1:
        raise CommandError('profile_not_found' if not matches else 'ambiguous_profile',
                           'Select an exact profile ID from profile list; descriptions may not be unique.',
                           {'requested': identifier, 'matches': [r['id'] for r in matches]})
    return matches[0]


def settings(row):
    return {key: value for key, value in row.items() if key in FIELDS}


def current(project):
    data = project._data if hasattr(project, '_data') else project
    result = dict(data.get('profile_settings') or {})
    result.update({key: copy.deepcopy(data[key]) for key in ('width', 'height', 'fps', 'pixel_ratio', 'display_ratio')})
    result.update(description=data['profile'])
    result.setdefault('progressive', True)
    result.setdefault('spherical', False)
    result.setdefault('pixel_format', 0)
    result = validate(result)
    exact = [r['id'] for r in catalogue() if not differences(result, r)]
    return dict(result, id=exact[0] if exact else 'project', matching_ids=exact, portable=True)


def differences(source, candidate):
    result = {}
    for key in MATCH_FIELDS:
        a, b = source.get(key), candidate.get(key)
        if key in ('fps', 'pixel_ratio', 'display_ratio') and a and b:
            equal = a['num'] * b['den'] == b['num'] * a['den']
        else:
            equal = a == b
        if not equal:
            result[key] = {'source': a, 'candidate': b}
    return result


def from_file(file):
    data = file.data
    if data.get('media_type') == 'image' or data.get('has_single_image') or not data.get('has_video'):
        raise CommandError('not_video', 'A moving-video source is required for profile matching; images and audio do not define project FPS.')
    # Album art in audio files also has a nominal video stream but no video FPS.
    fps = data.get('fps', {})
    if not fps.get('num') or not fps.get('den'):
        raise CommandError('not_video', 'Source does not declare a usable video frame rate.')
    pixel = data.get('pixel_ratio') or {'num': 1, 'den': 1}
    ratio = Fraction(data['width'] * pixel['num'], data['height'] * pixel['den'])
    result = {'width': data['width'], 'height': data['height'], 'fps': fps,
              'pixel_ratio': pixel, 'display_ratio': {'num': ratio.numerator, 'den': ratio.denominator},
              'progressive': not data.get('interlaced_frame', False),
              'spherical': bool(data.get('spherical', False)), 'pixel_format': 0}
    digest = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:10]
    result['description'] = 'Source {}x{} {}/{} fps {}'.format(data['width'], data['height'], fps['num'], fps['den'], digest)
    return validate(result)


def match(file, limit=10):
    numeric(limit, 'params.limit', integer=True, minimum=1, maximum=100)
    source = from_file(file)
    rows = []
    for candidate in catalogue():
        diff = differences(source, candidate)
        score = sum({'width': 4, 'height': 4, 'fps': 8, 'progressive': 8}.get(key, 2) for key in diff)
        distance = abs(candidate['width']-source['width']) + abs(candidate['height']-source['height'])
        rows.append((score, distance, dict(candidate, exact=not diff, differences=diff)))
    rows.sort(key=lambda row: (row[0], row[1], row[2]['id']))
    return {'file_id': file.id, 'source_profile': source,
            'exact_ids': [r[2]['id'] for r in rows if r[2]['exact']],
            'matches': [row[2] for row in rows[:limit]],
            'note': 'FPS is the reader-declared rate; variable-frame-rate timing is not inferred. Near matches are never applied automatically.'}


def resolve(service, params):
    identifier = params.get('id') or params.get('profile')
    choices = sum(bool(v) for v in (identifier, params.get('from_file'), params.get('values'), params.get('width')))
    if choices != 1:
        raise CommandError('invalid_argument', 'Choose one profile ID, --from-file FILE_ID, --json profile, or --width/--height.')
    if identifier:
        return settings(current(service.app.project) if identifier == 'project' else get(identifier))
    if params.get('from_file'):
        result = match(service.obj('file', params['from_file']))
        if result['exact_ids']:
            return settings(get(result['exact_ids'][0]))
        if not params.get('create_custom'):
            raise CommandError('no_exact_profile', 'No exact installed profile. Inspect profile match; use --create-custom to embed the source profile in the project.', result)
        return result['source_profile']
    if params.get('values'):
        data = dict(settings(current(service.app.project)), **params['values'])
        if 'description' not in params['values']:
            data['description'] = 'Custom '+hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]
        return validate(data)
    width, height = params.get('width'), params.get('height')
    fps = {'num': params.get('fps_num', 30), 'den': params.get('fps_den', 1)}
    for row in catalogue():
        if row['width'] == width and row['height'] == height and row['fps']['num']*fps['den'] == fps['num']*row['fps']['den'] and row['progressive'] and row['pixel_ratio']['num'] == row['pixel_ratio']['den']:
            return settings(row)
    raise CommandError('unsupported_profile', 'No exact installed width/height/FPS match. Use profile list, --from-file, or --json for a custom profile.')


def apply(service, params):
    profile = resolve(service, params)
    updates, project = service.app.updates, service.app.project
    # FPS conversion in ProjectDataStore uses the same conversion/scaler as the
    # GUI. Checkpoint affected arrays first so undo is exact even after rounding.
    arrays = ('clips', 'effects', 'markers', 'files')
    before = {key: copy.deepcopy(project.get(key) or []) for key in arrays}
    for key in arrays:
        updates.update([key], before[key])
    updates.update(['profile_settings'], profile)
    for key in ('profile', 'width', 'height', 'display_ratio', 'pixel_ratio', 'fps'):
        updates.update([key], profile['description'] if key == 'profile' else profile[key])
    # Keep the final converted arrays explicit in the transaction for deterministic
    # redo, and synchronize durations after the existing trim-grid conversion.
    for key in ('clips', 'effects'):
        for item in project.get(key) or []:
            if 'start' in item and 'end' in item:
                item['duration'] = item['end'] - item['start']
    for key in arrays:
        updates.update([key], copy.deepcopy(project.get(key) or []))
    return current(project)


def command(method, params, service=None):
    if method == 'profile.get':
        return get(params['id'])
    if method == 'profile.match':
        return match(service.obj('file', params['file_id']), params.get('limit', 10))
    rows = catalogue(params.get('search'))
    limit, offset = params.get('limit', 50), params.get('offset', 0)
    numeric(limit, 'params.limit', integer=True, minimum=1, maximum=500)
    numeric(offset, 'params.offset', integer=True, minimum=0)
    return {'profiles': rows[offset:offset+limit], 'total': len(rows),
            'next_offset': offset+limit if offset+limit < len(rows) else None}
