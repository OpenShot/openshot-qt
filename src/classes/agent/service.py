"""Editing commands backed by existing Query objects and UpdateManager."""
import copy
import json
import math
from pathlib import Path
import uuid
import time
from collections import OrderedDict

import openshot
from classes.query import File, Clip, Transition, Effect
from .protocol import CommandError

OBJECTS = {'file': File, 'clip': Clip, 'transition': Transition, 'effect': Effect}
MUTATIONS = {k + '.' + op for k in OBJECTS for op in ('add', 'set', 'remove')} | {'file.import'}
MUTATIONS -= {'file.add', 'file.set'}
MUTATIONS |= {k + '.keyframe.set' for k in ('clip', 'transition', 'effect')}
MUTATIONS |= {'clip.fade', 'clip.split', 'project.profile', 'project.profile.set'}


def finite(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < minimum:
        raise CommandError('invalid_argument', name + ' must be finite and >= ' + str(minimum))
    return value


def existing(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise CommandError('not_found', 'File does not exist: ' + str(path))
    return str(path)


def output_path(path, suffix, overwrite=False):
    path = Path(path).expanduser().resolve()
    if path.suffix.lower() != suffix:
        raise CommandError('invalid_argument', 'Output must end with ' + suffix)
    if not path.parent.is_dir():
        raise CommandError('not_found', 'Output parent directory must exist: ' + str(path.parent))
    if path.exists() and not overwrite:
        raise CommandError('already_exists', 'Output already exists: ' + str(path) + ('. Use project save PATH --overwrite to replace it.' if suffix == '.osp' else '. Choose a new output path.'))
    return str(path)


class EditingService:
    def __init__(self, app, session_id, mode):
        self.app, self.session_id, self.mode = app, session_id, mode
        self.jobs = {}
        self.operations = OrderedDict()

    def status(self):
        return {'session_id': self.session_id, 'mode': self.mode, 'protocol': 1,
                'project': self.app.project.current_filepath,
                'revision': self.app.updates.data_version,
                'dirty': self.app.project.has_unsaved_changes,
                'can_undo': bool(self.app.updates.actionHistory),
                'can_redo': bool(self.app.updates.redoHistory)}

    def execute(self, method, params, operation_id=None):
        tracked = isinstance(method, str) and (method in MUTATIONS or method.startswith('effects.') and method.split('.')[-1] in ('add', 'set', 'remove') or method in ('edit.apply', 'project.save', 'project.open', 'history.undo', 'history.redo', 'export.start', 'export.cancel'))
        if not tracked:
            return self._execute(method, params)
        operation_id = operation_id or uuid.uuid4().hex
        record = {'id': operation_id, 'method': method, 'started': time.time(),
                  'revision_before': self.app.updates.data_version, 'state': 'running'}
        self.operations[operation_id] = record
        try:
            result = self._execute(method, params)
            result['operation_id'] = operation_id
            record.update(state='completed', result=copy.deepcopy(result))
            return result
        except Exception as exc:
            detail = getattr(exc, 'details', None)
            detail = dict(detail or {}) if isinstance(detail, (dict, type(None))) else {'cause': detail}
            detail['operation_id'] = operation_id
            record.update(state='failed', error={'code': getattr(exc, 'code', 'command_failed'), 'message': str(exc), 'details': detail})
            raise CommandError(record['error']['code'], str(exc), detail)
        finally:
            record.update(revision_after=self.app.updates.data_version, finished=time.time())
            if len(json.dumps(record)) > 262144:
                record.pop('result', None)
                record['result_omitted'] = 'Result exceeded the 256 KiB operation record limit; inspect current objects.'
            while len(self.operations) > 100 or sum(len(json.dumps(r)) for r in self.operations.values()) > 4*1024*1024:
                self.operations.popitem(last=False)

    def _execute(self, method, params):
        if not isinstance(method, str) or not isinstance(params, dict):
            raise CommandError('invalid_request', 'Expected method string and params object.')
        from .batch import method_name
        method = method_name(method)
        from .validation import arguments
        arguments(method, params)
        if method == 'edit.apply':
            commands = params.get('commands')
            if not isinstance(commands, list) or not 1 <= len(commands) <= 256:
                raise CommandError('invalid_argument', 'Provide 1..256 commands.')
            from .batch import validate_entries, method_name
            validate_entries(commands, MUTATIONS)
            commands = [dict(entry, method=method_name(entry['method'])) for entry in commands]
            expected = params.get('expect_revision')
            if expected is not None and expected != self.app.updates.data_version:
                raise CommandError('revision_conflict', 'Project changed; inspect and rebuild the batch.', self.status())
        else:
            commands = [{'method': method, 'params': params}]
        # Preflight against a detached project and private UpdateManager. No GUI or
        # engine listeners receive data until every operation passes validation.
        if method == 'edit.apply':
            self.preflight(commands)
        old_transaction = self.app.updates.transaction_id
        transaction = uuid.uuid4().hex
        self.app.updates.transaction_id = transaction
        results = []
        named = {}
        from .batch import resolve
        try:
            for entry in commands:
                resolved = resolve(entry['params'], named) if method == 'edit.apply' else entry['params']
                arguments(entry['method'], resolved)
                result = self.dispatch(entry['method'], resolved)
                if 'as' in entry:
                    named[entry['as']] = result
                if entry['method'].split('.')[0] in OBJECTS and entry['method'] in MUTATIONS and isinstance(result, dict) and 'id' in result:
                    result = self.summary(entry['method'].split('.')[0], result)
                results.append(dict(result, ref=entry['as']) if 'as' in entry and isinstance(result, dict) else result)
        except Exception as exc:
            details = {'revision': self.app.updates.data_version, 'transaction_id': transaction,
                       'completed': len(results), 'results': results}
            if isinstance(exc, CommandError):
                details['cause'] = exc.details
                raise CommandError(exc.code, str(exc), details)
            raise CommandError('command_failed', str(exc), details)
        finally:
            self.app.updates.transaction_id = old_transaction
            if self.app.window and (method in MUTATIONS or method == 'edit.apply'):
                self.app.window.refreshFrameSignal.emit()
        response = {'revision': self.app.updates.data_version, 'transaction_id': transaction,
                    'data': results if method == 'edit.apply' else results[0]}
        if named:
            response['refs'] = {name: {'id': value['id']} if isinstance(value, dict) and 'id' in value else value
                                for name, value in named.items()}
        return response

    def preflight(self, commands):
        from classes.updates import UpdateManager
        from classes.query import QueryObject
        from .validation import arguments
        project, updates = self.app.project, self.app.updates
        shadow = copy.copy(project)
        shadow._data = copy.deepcopy(project._data)
        private_updates = UpdateManager()
        private_updates.add_listener(shadow)
        named = {}
        from .batch import resolve
        try:
            self.app.project, self.app.updates = shadow, private_updates
            QueryObject._cache_version = None
            for index, entry in enumerate(commands):
                try:
                    params = resolve(entry['params'], named)
                    arguments(entry['method'], params)
                    result = self.dispatch(entry['method'], params)
                    if 'as' in entry:
                        named[entry['as']] = result
                except Exception as exc:
                    detail = getattr(exc, 'details', None) or {}
                    path = 'params.commands[{}]'.format(index)
                    if isinstance(detail, dict) and detail.get('path'):
                        path += '.' + detail['path']
                    raise CommandError(getattr(exc, 'code', 'validation_error'),
                                       'Batch command {} ({}): {} No edits were applied.'.format(index, entry['method'], exc),
                                       {'path': path, 'command_index': index, 'completed': 0,
                                        'revision': updates.data_version, 'cause': detail})
        finally:
            self.app.project, self.app.updates = project, updates
            QueryObject._cache_version = None
            QueryObject._cache = {}

    @staticmethod
    def summary(kind, data):
        keys = ('id', 'name', 'title', 'path', 'media_type', 'type', 'class_name', 'file_id',
                'layer', 'position', 'start', 'end', 'duration', 'width', 'height', 'fps')
        if kind == 'effect':
            keys = ('id', 'name', 'type', 'class_name')
        result = {key: data[key] for key in keys if key in data}
        command = 'effects' if kind == 'effect' else kind
        result['inspect'] = 'openshot-cli {} get {}'.format(command, data['id'])
        return result

    def obj(self, kind, object_id):
        obj = OBJECTS[kind].get(id=object_id)
        if obj is None or obj.id != object_id:
            raise CommandError('not_found', kind + ' ID not found: ' + str(object_id))
        obj.data = copy.deepcopy(obj.data)
        return obj

    def layer(self, value):
        if value not in [item['number'] for item in self.app.project.get('layers')]:
            raise CommandError('invalid_layer', 'Unknown layer number; use project get to inspect layers.')
        return value

    def dispatch(self, method, p):
        if method == 'operation.list':
            return [{k: v for k, v in row.items() if k not in ('result', 'error')} for row in reversed(list(self.operations.values()))]
        if method == 'operation.get':
            if p['id'] not in self.operations:
                raise CommandError('not_found', 'Operation is not retained in this session. Inspect operation list and current project state.')
            return copy.deepcopy(self.operations[p['id']])
        if method == 'timeline.view' and p.get('format', 'image' if p.get('output') else 'text') != 'image':
            if p.get('output'):
                raise CommandError('invalid_argument', '--output is for --format image. Text/JSON views write to stdout.')
            from .context import view
            return view(self.app, p)
        if method == 'clip.split':
            from .cuts import split_clip
            return split_clip(self, p)
        if method == 'timeline.overview':
            from .context import overview
            return overview(self.app, **p)
        if method == 'clip.fade':
            obj = self.obj('clip', p['id'])
            fps = self.fps()
            fade_in = finite(p.get('fade_in', 0), 'fade_in')
            fade_out = finite(p.get('fade_out', 0), 'fade_out')
            nearest = lambda seconds: math.floor(seconds * fps + 0.5)
            trim = nearest(obj.data['start'])
            position = obj.data['position']
            first = trim + 1
            last = (nearest(position + obj.data['end'] - obj.data['start'])
                    - nearest(position) + trim)
            in_frames, out_frames = nearest(fade_in), nearest(fade_out)
            if not in_frames and not out_frames:
                raise CommandError('invalid_range', 'Specify --in or --out of at least one project frame ({:.6f}s).'.format(1/fps))
            if in_frames + out_frames > last - first:
                raise CommandError('invalid_range', 'Fade durations must fit between the first and last visible clip frames ({:.6f}s).'.format(max(0, (last-first)/fps)))
            value = finite(p.get('value', 1), 'value')
            curve = openshot.Keyframe(value)
            curve.AddPoint(first, 0 if in_frames else value, openshot.LINEAR)
            if in_frames:
                curve.AddPoint(first + in_frames, value, openshot.LINEAR)
            if out_frames:
                curve.AddPoint(last - out_frames, value, openshot.LINEAR)
                curve.AddPoint(last, 0, openshot.LINEAR)
            return self.dispatch('clip.set', {'id': obj.id, 'values': {p.get('property', 'alpha'): json.loads(curve.Json())}})
        if method == 'session.status':
            return self.status()
        if method == 'session.show':
            from .host import show_session
            return show_session(self.app)
        if method == 'session.stop':
            if self.mode != 'headless':
                raise CommandError('unsupported', 'Close GUI sessions in the editor.')
            self.require_clean(p)
            if any(job['process'].poll() is None for job in self.jobs.values()):
                raise CommandError('busy', 'Cancel or finish active exports before stopping.')
            from qt_api import QTimer
            QTimer.singleShot(100, self.app.quit)
            return {'stopping': True}
        if method == 'project.get':
            data = self.app.project
            return dict(self.status(), **{k: data.get(k) for k in ('width', 'height', 'fps', 'profile', 'sample_rate', 'channels', 'layers')},
                        counts={'files': len(data.get('files') or []), 'clips': len(data.get('clips') or []),
                                'transitions': len(data.get('effects') or []),
                                'effects': sum(len(c.get('effects', [])) for c in data.get('clips') or [])})
        if method == 'project.open':
            self.require_clean(p)
            path = existing(p['path'])
            if self.app.window:
                self.app.window.open_project(path, clear_thumbnails=False, interactive=False)
            else:
                self.app.project.load(path, clear_thumbnails=False, interactive=False)
                self.app.updates.load_history(self.app.project)
            return self.dispatch('project.get', {})
        if method == 'project.save':
            path = output_path(p['path'], '.osp', p.get('overwrite', False))
            self.app.updates.save_history(self.app.project, self.app.get_settings().get("history-limit"))
            self.app.project.save(path)
            if self.app.window:
                self.app.window.SetWindowTitle()
            return {'path': path}
        if method in ('project.profile', 'project.profile.set'):
            from .profiles import apply
            return apply(self, p)
        if method == 'project.profile.get':
            from .profiles import current
            return current(self.app.project)
        if method.startswith('profile.'):
            from .profiles import command
            return command(method, p, self)
        if method in ('history.undo', 'history.redo'):
            getattr(self.app.updates, method.split('.')[1])()
            return self.status()
        if method == 'effect.types':
            from .catalog import effect_types
            return effect_types()
        if method == 'effect.describe':
            from .catalog import describe_effect
            return describe_effect(p['type'], p.get('property'))
        if method.startswith('export.'):
            from .render import export_command
            return export_command(self, method.split('.', 1)[1], p)
        if method == 'timeline.view':
            if not p.get('output'):
                raise CommandError('invalid_argument', 'Image timeline view requires --output NEW.png.')
            if p.get('layer') is not None:
                raise CommandError('unsupported', '--layer currently filters text/JSON views. Image mode fits used tracks.')
            p = {k: v for k, v in p.items() if k not in ('format', 'detail', 'layer', 'limit', 'offset')}
        if method.startswith('timeline.') or method in ('file.thumbnail', 'file.strip'):
            from .render import inspect_command
            return inspect_command(self, method, p)
        kind, _, operation = method.partition('.')
        if kind not in OBJECTS:
            raise CommandError('unknown_method', 'Unknown command: ' + method)
        if operation == 'list':
            keys = ('id', 'name', 'title', 'path', 'media_type', 'type', 'class_name', 'file_id', 'layer', 'position', 'start', 'end', 'duration')
            objects = OBJECTS[kind].filter()
            if kind == 'effect':
                from .catalog import effect_types
                descriptions = {e['class_name']: e['description'] for e in effect_types()}
                result = []
                for obj in objects:
                    item = self.summary(kind, obj.data)
                    item['clip_id'] = obj.parent['id']
                    item['description'] = descriptions.get(obj.data.get('class_name') or obj.data.get('type'), '')
                    result.append(item)
                return result
            return [{k: o.data[k] for k in keys if k in o.data} for o in objects]
        if operation == 'keyframe.set':
            obj = self.obj(kind, p['id'])
            name = p['property']
            if not isinstance(obj.data.get(name), dict) or 'Points' not in obj.data[name]:
                raise CommandError('invalid_property', 'Property does not support keyframes; use properties.')
            frame = p['frame']
            if not isinstance(frame, int) or frame < 1:
                raise CommandError('invalid_frame', 'Keyframe coordinate must be an integer >= 1.')
            value = p['value']
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise CommandError('invalid_argument', 'Keyframe value must be a finite number.')
            curve = openshot.Keyframe()
            curve.SetJson(json.dumps(obj.data[name]))
            modes = {'linear': openshot.LINEAR, 'bezier': openshot.BEZIER, 'constant': openshot.CONSTANT}
            if p.get('interpolation', 'linear') not in modes:
                raise CommandError('invalid_argument', 'Interpolation must be linear, bezier, or constant.')
            curve.AddPoint(frame, value, modes[p.get('interpolation', 'linear')])
            return self.dispatch(kind + '.set', {'id': obj.id, 'values': {name: json.loads(curve.Json())}})
        if operation in ('get', 'remove', 'set', 'properties'):
            obj = self.obj(kind, p['id'])
            if operation == 'get':
                return obj.data
            if operation == 'remove':
                if kind == 'file' and any(c.data.get('file_id') == obj.id or c.data.get('reader', {}).get('id') == obj.id for c in Clip.filter()):
                    raise CommandError('in_use', 'Remove clips referencing this file first.')
                if kind == 'effect':
                    parent = self.obj('clip', obj.parent['id'])
                    parent.data = {'effects': [e for e in parent.data.get('effects', []) if e['id'] != obj.id]}
                    parent.save()
                else:
                    obj.delete()
                return {'removed': obj.id}
            if operation == 'properties':
                frame = p.get('frame', 1)
                finite(frame, 'frame', 1)
                native = self.native(kind, obj.data)
                return json.loads(native.PropertiesJSON(frame))
            values = p.get('values')
            if not isinstance(values, dict) or not values:
                raise CommandError('invalid_argument', 'values must be a non-empty JSON object.')
            from .validation import properties
            properties(kind, obj.data, values, self.native(kind, obj.data))
            values = copy.deepcopy(values)
            protected = {'id', 'reader', 'file_id', 'effects', 'type', 'class_name', 'path'}
            for key in values:
                if key not in obj.data or key in protected:
                    raise CommandError('invalid_property', 'Unknown or protected property: ' + key + '; inspect get/properties.')
            for key, value in list(values.items()):
                if isinstance(obj.data.get(key), dict) and 'Points' in obj.data[key] and isinstance(value, (int, float)):
                    if not math.isfinite(value):
                        raise CommandError('invalid_argument', 'Property values must be finite.')
                    values[key] = json.loads(openshot.Keyframe(float(value)).Json())
            merged = dict(obj.data, **values)
            self.validate_timing(merged, kind)
            if kind == 'clip' and merged.get('file_id'):
                source = self.obj('file', merged['file_id'])
                if source.data.get('media_type') != 'image' and merged['end'] > source.data['duration'] + 1e-6:
                    from .validation import fail
                    fail('params.values.end', 'a source out-point <= {}'.format(source.data['duration']), merged['end'])
            self.native(kind, merged)  # Parse before distributing to native/UI listeners.
            if 'start' in merged and 'end' in merged:
                values = dict(values, duration=merged['end'] - merged['start'])
            obj.data = values
            obj.save()
            return self.obj(kind, obj.id).data
        if method == 'file.import':
            path = existing(p['path'])
            found = File.get(path=path)
            if found:
                return found.data
            reader = openshot.Clip.CreateReader(path, False)
            if not reader:
                raise CommandError('invalid_media', 'No reader for ' + path)
            reader.Open()
            try:
                data = json.loads(reader.Json())
            finally:
                reader.Close()
            from classes.image_types import get_media_type
            data.update(path=path, name=Path(path).name)
            data['media_type'] = get_media_type(data)
            obj = File()
            obj.data = data
            obj.save()
            return obj.data
        if method == 'clip.add':
            file = self.obj('file', p['file_id'])
            native = openshot.Clip(file.absolute_path())
            try:
                data = json.loads(native.Json())
            finally:
                native.Close()
            start = p.get('start', 0)
            end = p.get('end', 10 if file.data.get('media_type') == 'image' else file.data['duration'])
            data.update(file_id=file.id, reader=copy.deepcopy(file.data), layer=self.layer(p['layer']),
                        position=p.get('position', 0), start=start, end=end, duration=end-start)
            self.validate_timing(data)
            if file.data.get('media_type') != 'image' and end > file.data['duration'] + 1e-6:
                raise CommandError('out_of_range', 'Clip end exceeds source duration.')
            if p.get('audio_only'):
                data['has_video'] = json.loads(openshot.Keyframe(0.0).Json())
            data['volume'] = json.loads(openshot.Keyframe(finite(p.get('volume', 1), 'volume')).Json())
            obj = Clip()
            obj.data = data
            obj.save()
            return obj.data
        if method == 'transition.add':
            duration = finite(p.get('duration', 1), 'duration', 1 / self.fps())
            reader = openshot.QtImageReader(existing(p['mask']))
            reader.Open()
            try:
                reader_data = json.loads(reader.Json())
            finally:
                reader.Close()
            brightness = openshot.Keyframe(-1.0 if p.get('reverse') else 1.0)
            brightness.AddPoint(round(duration*self.fps()) + 1, 1.0 if p.get('reverse') else -1.0, openshot.BEZIER)
            data = {'type': 'Mask', 'title': 'Transition', 'layer': self.layer(p['layer']),
                    'position': finite(p.get('position', 0), 'position'), 'start': 0, 'end': duration,
                    'duration': duration, 'reader': reader_data, 'replace_image': False,
                    'brightness': json.loads(brightness.Json()), 'contrast': json.loads(openshot.Keyframe(3.0).Json())}
            self.native('transition', data)
            obj = Transition()
            obj.data = data
            obj.save()
            return obj.data
        if method == 'effect.add':
            clip = self.obj('clip', p['clip_id'])
            from .catalog import resolve_effect
            effect_type = resolve_effect(p['type'])['class_name']
            effect = openshot.EffectInfo().CreateEffect(effect_type)
            if effect is None:
                raise CommandError('invalid_effect', 'Unknown effect type; use effects list.')
            effect.Id(self.app.project.generate_id())
            data = json.loads(effect.Json())
            clip.data = {'effects': clip.data.get('effects', []) + [data]}
            clip.save()
            return data
        raise CommandError('unknown_method', 'Unknown command: ' + method)

    def require_clean(self, params):
        if self.app.project.has_unsaved_changes and not params.get('discard'):
            raise CommandError('unsaved_changes', 'Save the project first, or explicitly pass --discard.')

    def fps(self):
        rate = self.app.project.get('fps')
        return rate['num'] / rate['den']

    def validate_timing(self, data, kind='clip'):
        for key in ('start', 'end', 'position'):
            if key in data:
                finite(data[key], key)
        if 'start' in data and 'end' in data and (data['end'] < data['start'] or (kind != 'effect' and data['end'] == data['start'])):
            raise CommandError('invalid_range', 'end must be greater than start (exclusive).')
        if 'layer' in data and kind != 'effect':
            self.layer(data['layer'])

    @staticmethod
    def native(kind, data):
        native = openshot.Clip() if kind == 'clip' else openshot.EffectInfo().CreateEffect(data.get('class_name') or data.get('type', 'Mask'))
        if native is None:
            raise CommandError('invalid_effect', 'Unrecognized effect class.')
        native.SetJson(json.dumps(data, allow_nan=False))
        return native
