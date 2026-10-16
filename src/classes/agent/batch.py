"""
 @file
 @brief Named result references for commands sharing an UpdateManager transaction.

This resolves command inputs only; Query and UpdateManager remain responsible
for generating IDs, distributing JSON changes, and recording undo/redo.

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
import difflib
import re

from .protocol import CommandError


def method_name(method):
    # Public command paths use the CLI group spelling; keep legacy RPC spelling.
    if isinstance(method, str) and method.startswith('effects.'):
        return 'effect.' + method[len('effects.'):]
    return method


def validate_entries(commands, mutations):
    names = set()
    for index, entry in enumerate(commands):
        path = 'params.commands[{}]'.format(index)
        if not isinstance(entry, dict):
            raise CommandError('validation_error', path + ': expected a command object.')
        extra = set(entry) - {'method', 'params', 'as'}
        if extra:
            raise CommandError('validation_error', path + ': unknown fields ' + ', '.join(sorted(extra)) + '. Allowed: method, params, as.')
        method = method_name(entry.get('method'))
        if not isinstance(method, str) or method not in mutations:
            choices = sorted(m.replace('effect.', 'effects.', 1) for m in mutations)
            matches = difflib.get_close_matches(str(entry.get('method')), choices, n=1)
            hint = ' Did you mean {}?'.format(matches[0]) if matches else ''
            raise CommandError('validation_error', path + '.method: unknown mutation ' + repr(entry.get('method')) + '.' + hint,
                               {'path': path + '.method', 'allowed': choices, 'completed': 0})
        if not isinstance(entry.get('params'), dict):
            raise CommandError('validation_error', path + '.params: expected an argument object.')
        if 'as' in entry:
            name = entry['as']
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name):
                raise CommandError('validation_error', path + '.as: use a name starting with a letter, followed by up to 63 letters, digits or underscores.')
            if name in names:
                raise CommandError('validation_error', path + '.as: duplicate result name ' + name)
            names.add(name)


def resolve(value, results, path='params'):
    if isinstance(value, dict):
        if '$ref' in value:
            ref = value['$ref']
            if len(value) != 1 or not isinstance(ref, str):
                raise CommandError('validation_error', path + ': a reference must be exactly {"$ref":"name.id"}.')
            parts = ref.split('.')
            current = results
            for part in parts:
                if not isinstance(current, dict) or part not in current:
                    raise CommandError('invalid_reference', path + ': cannot resolve ' + repr(ref) + '. Reference a field of an earlier named result, e.g. {"$ref":"media.id"}.',
                                       {'path': path, 'reference': ref, 'available_names': list(results)})
                current = current[part]
            return copy.deepcopy(current)
        return {k: resolve(v, results, path + '.' + k) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, results, '{}[{}]'.format(path, i)) for i, v in enumerate(value)]
    return value
