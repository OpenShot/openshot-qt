"""Validate untrusted command data before it enters OpenShot's update listeners.

Native property min/max values often describe GUI slider ranges, not legal engine
ranges (e.g. scale > 1 and volume > 1 are valid). Enforce enums and structural
contracts, plus explicitly known semantic bounds; expose other ranges as metadata.
"""
import difflib
import json
import math

from .protocol import CommandError


def fail(path, expected, value, hint=None):
    received = repr(value)
    if len(received) > 160:
        received = received[:157] + '...'
    message = '{}: expected {}; received {}.'.format(path, expected, received)
    if hint:
        message += ' ' + hint
    raise CommandError('validation_error', message, {
        'path': path, 'expected': expected, 'received': received, 'hint': hint})


def unknown(path, key, choices):
    close = difflib.get_close_matches(key, choices, n=1)
    hint = "Did you mean '{}'?".format(close[0]) if close else 'Allowed fields: ' + ', '.join(sorted(choices))
    fail(path + '.' + key, 'a supported field', key, hint)


def numeric(value, path, integer=False, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        fail(path, 'a finite ' + ('integer' if integer else 'number'), value, 'Use a JSON number, not a quoted string, null, or boolean.')
    if integer and int(value) != value:
        fail(path, 'an integer', value)
    if minimum is not None and value < minimum:
        fail(path, 'a number >= ' + str(minimum), value)
    if maximum is not None and value > maximum:
        fail(path, 'a number <= ' + str(maximum), value)


def json_value(value, path='$', depth=0):
    if depth > 32:
        fail(path, 'JSON nesting of at most 32 levels', '<nested data>')
    if isinstance(value, float) and not math.isfinite(value):
        fail(path, 'a finite JSON number', value)
    if isinstance(value, dict):
        for key, child in value.items():
            json_value(child, path + '.' + key, depth+1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            json_value(child, '{}[{}]'.format(path, index), depth+1)


def arguments(method, params):
    # Keep CLI argument definitions as the single source of command names/fields.
    # No parsing or side effects here; programmatic RPC calls get the same contract.
    import argparse
    from cli import build_parser
    if not hasattr(arguments, '_commands'):
        commands = {}
        def walk(parser):
            operation = parser.get_default('method')
            if operation:
                commands[operation] = [a for a in parser._actions if not isinstance(a, (argparse._HelpAction, argparse._SubParsersAction))]
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for child in action.choices.values():
                        walk(child)
        walk(build_parser())
        arguments._commands = commands
    actions = arguments._commands.get('project.profile.set' if method == 'project.profile' else method)
    if actions is None:
        fail('method', 'a supported command', method, 'Run openshot-cli --help to discover commands.')
    allowed = {a.dest for a in actions}
    for key in params:
        if key not in allowed:
            unknown('params', key, allowed)
    for action in actions:
        key = action.dest
        if key not in params:
            if action.required:
                fail('params.' + key, 'a required argument', '<missing>', 'Run openshot-cli ' + method.replace('effect.', 'effects.', 1).replace('.', ' ') + ' help.')
            continue
        value = params[key]
        path = 'params.' + key
        if key in ('values', 'commands', 'config'):
            expected = list if key == 'commands' else dict
            if not isinstance(value, expected):
                fail(path, 'a JSON object' if expected is dict else 'a JSON array', value)
        elif isinstance(action, argparse._StoreTrueAction):
            if not isinstance(value, bool):
                fail(path, 'a boolean', value)
        elif action.type is int:
            numeric(value, path, integer=True)
            if not isinstance(value, int):
                fail(path, 'a JSON integer', value)
        elif action.type:
            numeric(value, path)
        elif not isinstance(value, str) or not value:
            fail(path, 'a non-empty string', value)
        if action.choices and value not in action.choices:
            fail(path, 'one of ' + repr(action.choices), value)
    json_value(params, 'params')


def scalar(value, metadata, path, property_name):
    numeric(value, path, integer=metadata.get('type') == 'int')
    choices = [c['value'] for c in metadata.get('choices', [])]
    if choices and value not in choices:
        fail(path, 'one of ' + repr(choices), value,
             '; '.join('{}={}'.format(c['value'], c['name']) for c in metadata['choices']))
    if property_name in ('alpha',):
        numeric(value, path, minimum=0, maximum=1)
    if property_name in ('volume', 'scale_x', 'scale_y'):
        numeric(value, path, minimum=0)


def curve(value, metadata, path, property_name):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        scalar(value, metadata, path, property_name)
        return
    if not isinstance(value, dict):
        fail(path, 'a number (constant) or {"Points":[...]}', value,
             'For example {"volume":0.5}; use keyframe set to edit one point.')
    for key in value:
        if key != 'Points':
            unknown(path, key, ['Points'])
    points = value.get('Points')
    if not isinstance(points, list) or not 1 <= len(points) <= 10000:
        fail(path + '.Points', 'an array containing 1..10000 points', points)
    previous = 0
    for index, point in enumerate(points):
        base = '{}.Points[{}]'.format(path, index)
        if not isinstance(point, dict):
            fail(base, 'a point object', point)
        allowed = {'co', 'handle_left', 'handle_right', 'handle_type', 'interpolation'}
        for key in point:
            if key not in allowed:
                unknown(base, key, allowed)
        co = point.get('co')
        if not isinstance(co, dict) or set(co) != {'X', 'Y'}:
            fail(base + '.co', 'an object with exactly X and Y', co,
                 'Example: {"co":{"X":1,"Y":0.5},"interpolation":1}. X is a 1-based frame.')
        numeric(co['X'], base + '.co.X', integer=True, minimum=1)
        if co['X'] <= previous:
            fail(base + '.co.X', 'a frame strictly greater than the preceding point', co['X'], 'Sort points by X and remove duplicate frames.')
        previous = co['X']
        scalar(co['Y'], metadata, base + '.co.Y', property_name)
        for key in ('interpolation', 'handle_type'):
            if key in point:
                numeric(point[key], base + '.' + key, integer=True, minimum=0, maximum=2)
        for key in ('handle_left', 'handle_right'):
            if key in point:
                handle = point[key]
                if not isinstance(handle, dict) or set(handle) != {'X', 'Y'}:
                    fail(base + '.' + key, 'an object with X and Y', handle)
                for axis in ('X', 'Y'):
                    numeric(handle[axis], base + '.' + key + '.' + axis)


def structure(value, template, path, metadata=None, property_name=''):
    metadata = metadata or {}
    if isinstance(template, dict) and 'Points' in template:
        curve(value, metadata, path, property_name)
    elif isinstance(template, dict):
        if not isinstance(value, dict):
            fail(path, 'a JSON object', value)
        for key in value:
            if key not in template:
                unknown(path, key, template)
        for key in template:
            if key not in value:
                fail(path + '.' + key, 'a required nested field (nested objects replace, not merge)', '<missing>')
            structure(value[key], template[key], path + '.' + key, property_name=property_name)
    elif isinstance(template, bool):
        if not isinstance(value, bool):
            fail(path, 'a JSON boolean', value)
    elif isinstance(template, (int, float)):
        scalar(value, metadata, path, property_name)
    elif isinstance(template, str):
        if not isinstance(value, str):
            fail(path, 'a string', value)
    elif isinstance(template, list):
        # Structural collections need dedicated editing commands.
        fail(path, 'a property editable through its dedicated command', value, 'Use effect add/remove for clip effects.')
    elif value is not None:
        fail(path, 'null', value)


def properties(kind, current, values, native):
    if not isinstance(values, dict) or not values:
        fail('params.values', 'a non-empty JSON object', values)
    metadata = json.loads(native.PropertiesJSON(1))
    protected = {'id', 'reader', 'file_id', 'effects', 'type', 'class_name', 'path', 'duration'}
    for name, value in values.items():
        path = 'params.values.' + name
        if name not in current:
            unknown('params.values', name, set(current)-protected)
        meta = metadata.get(name, {})
        if name in protected or meta.get('readonly'):
            fail(path, 'an editable property', value, 'This field is derived or structural; use add/remove or start/end instead.')
        structure(value, current[name], path, meta, name)
