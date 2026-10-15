"""
 @file
 @brief Deterministic selectors and per-clip expansion into the existing batch engine.

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

from classes.query import Clip
from .batch import method_name, validate_entries
from .protocol import CommandError
from .validation import numeric, unknown


def select(service, selector):
    allowed = ('ids', 'layer', 'start', 'end', 'file_id', 'effect', 'all')
    if not selector:
        raise CommandError('invalid_selection', 'Provide selection filters, or explicitly use {"all":true}.')
    for key in selector:
        if key not in allowed:
            unknown('params.selection', key, allowed)
    if 'all' in selector and (selector['all'] is not True or len(selector) != 1):
        raise CommandError('invalid_selection', 'all must be true and cannot combine with filters.')
    ids = selector.get('ids')
    if ids is not None and (not isinstance(ids, list) or not ids or
                            any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids))):
        raise CommandError('invalid_selection', 'ids must be a nonempty array of unique clip IDs.')
    if 'layer' in selector:
        numeric(selector['layer'], 'params.selection.layer', integer=True)
        service.layer(selector['layer'])
    for key in ('start', 'end'):
        if key in selector:
            numeric(selector[key], 'params.selection.' + key, minimum=0)
    if 'end' in selector and selector['end'] <= selector.get('start', 0):
        raise CommandError('invalid_selection', 'Selection end must be greater than start (exclusive).')
    if 'file_id' in selector:
        if not isinstance(selector['file_id'], str):
            raise CommandError('invalid_selection', 'file_id must be an imported file ID.')
        service.obj('file', selector['file_id'])
    effect = None
    if 'effect' in selector:
        if not isinstance(selector['effect'], str):
            raise CommandError('invalid_selection', 'effect must be a class name or alias.')
        from .catalog import resolve_effect
        effect = resolve_effect(selector['effect'])['class_name']
    clips = Clip.filter()
    if ids is not None:
        missing = sorted(set(ids) - {c.id for c in clips})
        if missing:
            raise CommandError('not_found', 'Selected clip IDs do not exist.', {'ids': missing})
    rows = []
    for obj in clips:
        c = obj.data
        if ids is not None and obj.id not in ids:
            continue
        if 'layer' in selector and c['layer'] != selector['layer']:
            continue
        if 'file_id' in selector and c.get('file_id') != selector['file_id']:
            continue
        if 'start' in selector and c['position'] + c['end'] - c['start'] <= selector['start']:
            continue
        if 'end' in selector and c['position'] >= selector['end']:
            continue
        if effect and not any((e.get('class_name') or e.get('type')) == effect for e in c.get('effects', [])):
            continue
        rows.append(c)
    rows.sort(key=lambda c: (c['position'], c['layer'], c['id']))
    if len(rows) > 256:
        raise CommandError('selection_limit', 'Selection exceeds 256 clips; narrow the filters.')
    locked = {r['number'] for r in service.app.project.get('layers') if r.get('lock')}
    return {'ids': [c['id'] for c in rows], 'clips': [dict(service.summary('clip', c), locked=c['layer'] in locked) for c in rows],
            'count': len(rows), 'revision': service.app.updates.data_version}


def expand(service, selection, templates, mutations):
    if not isinstance(templates, list) or not 1 <= len(templates) <= 256:
        raise CommandError('invalid_argument', 'Provide 1..256 command templates.')
    validate_entries(templates, mutations)
    if not selection['ids']:
        raise CommandError('empty_selection', 'No clips match the selection; no edits applied.')
    if len(selection['ids']) * len(templates) > 256:
        raise CommandError('batch_limit', 'Bulk expansion exceeds 256 commands; narrow the selection or templates.')
    if any(c['locked'] for c in selection['clips']):
        raise CommandError('locked_track', 'Selection includes clips on locked tracks; no edits applied.')
    commands = []
    for index, clip_id in enumerate(selection['ids']):
        names = {t['as']: 'clip{}_result{}'.format(index, n)
                 for n, t in enumerate(templates) if 'as' in t}
        def local_refs(value):
            if isinstance(value, dict):
                if '$ref' in value and isinstance(value['$ref'], str):
                    name, separator, suffix = value['$ref'].partition('.')
                    if name not in names:
                        raise CommandError('invalid_reference', 'Unknown template reference ' + repr(name) + '; references must name a result in the same per-clip template.',
                                           {'reference': value['$ref'], 'available_names': list(names)})
                    return dict(value, **{'$ref': names[name] + separator + suffix})
                return {k: local_refs(v) for k, v in value.items()}
            if isinstance(value, list):
                return [local_refs(v) for v in value]
            return value
        for template in templates:
            entry = local_refs(copy.deepcopy(template))
            method = method_name(entry['method'])
            params = entry['params']
            if method.startswith('clip.') and method != 'clip.add':
                target = 'id'
            elif method == 'effect.add':
                target = 'clip_id'
            elif method.startswith('effect.') and isinstance(params.get('id'), dict) and '$ref' in params['id']:
                target = None
            else:
                raise CommandError('invalid_template', 'Bulk templates support existing clip mutations, effect.add, and effect mutations referencing an earlier named result.')
            if target:
                if target in params:
                    raise CommandError('invalid_template', 'Omit ' + target + '; bulk supplies the selected clip ID.')
                params[target] = clip_id
            if 'as' in entry:
                entry['as'] = names[entry['as']]
            commands.append(entry)
    return commands


def adjust(service, params):
    obj = service.obj('clip', params['id'])
    values = params['values']
    if not values:
        raise CommandError('invalid_argument', 'Supply at least one relative adjustment.')
    updates = {}
    for name, adjustment in values.items():
        if not isinstance(adjustment, dict) or not adjustment or set(adjustment) - {'add', 'multiply'}:
            raise CommandError('invalid_argument', 'Each adjustment needs add and/or multiply: ' + name)
        add, multiply = adjustment.get('add', 0), adjustment.get('multiply', 1)
        numeric(add, 'params.values.' + name + '.add')
        numeric(multiply, 'params.values.' + name + '.multiply')
        value = copy.deepcopy(obj.data.get(name))
        if isinstance(value, dict) and 'Points' in value:
            for point in value['Points']:
                point['co']['Y'] = point['co']['Y'] * multiply + add
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            value = value * multiply + add
        else:
            raise CommandError('invalid_property', 'Relative adjustments require a numeric property or curve: ' + name)
        updates[name] = value
    return service.dispatch('clip.set', {'id': obj.id, 'values': updates})
