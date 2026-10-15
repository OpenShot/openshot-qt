"""
 @file
 @brief Native curve behavior and transactional safety for keyframe and bulk edits.

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
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import openshot

from classes.agent.protocol import CommandError
from classes.agent.service import EditingService


class KeyframeBulkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        from qt_api import QImage, QColor
        isolate_preferences(self)
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        self.service = EditingService(self.app, 'keyframe-bulk-test', 'headless')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        image = QImage(64, 36, QImage.Format_ARGB32)
        image.fill(QColor('red'))
        self.path = str(Path(self.temp.name) / 'red.png')
        image.save(self.path)
        self.file = self.call('file.import', path=self.path)
        self.layer = self.app.project.get('layers')[0]['number']
        self.clip = self.add_clip(position=5, start=2, end=8)

    def call(self, method, **params):
        return self.service.execute(method, params)['data']

    def add_clip(self, **params):
        return self.call('clip.add', file_id=self.file['id'], layer=self.layer, **params)

    def key(self, operation, **params):
        params.setdefault('id', self.clip['id'])
        params.setdefault('property', 'volume')
        return self.call('clip.keyframe.' + operation, **params)

    def native(self, object_id=None, name='volume'):
        data = self.call('clip.get', id=object_id or self.clip['id'])
        curve = openshot.Keyframe()
        curve.SetJson(json.dumps(data[name]))
        return curve

    def state(self):
        return (copy.deepcopy(self.app.project._data), self.app.updates.data_version,
                copy.deepcopy([a.json() for a in self.app.updates.actionHistory]),
                copy.deepcopy([a.json() for a in self.app.updates.redoHistory]),
                self.app.project.has_unsaved_changes)

    def test_trimmed_clip_coordinates_round_trip_and_evaluation(self):
        self.key('set', space='clip', unit='seconds', at=0, value=0)
        self.key('set', space='timeline', unit='seconds', at=6, value=1)
        self.assertAlmostEqual(self.native().GetValue(76), .5)
        native = self.key('list')['points']
        self.assertEqual([p['co']['X'] for p in native], [1, 61, 91])
        clip_points = self.key('list', space='clip', unit='frames', start=1)['points']
        self.assertEqual([p['co']['X'] for p in clip_points], [1, 31])
        timeline_points = self.key('list', space='timeline', unit='seconds', start=5)['points']
        self.assertEqual([p['co']['X'] for p in timeline_points], [5, 6])
        other = self.add_clip(position=12, start=2, end=8)
        self.key('paste', id=other['id'], space='clip', unit='frames', points=clip_points, mode='replace')
        self.assertEqual(self.native(other['id']).GetValue(76), self.native().GetValue(76))

    def test_fractional_fps_snaps_once_and_keeps_time_remapped_curve_coordinates(self):
        self.app.project._data['fps'] = {'num': 24000, 'den': 1001}
        self.call('clip.set', id=self.clip['id'], values={'time': 10})
        self.key('set', space='clip', unit='seconds', at=1.001, value=.25)
        points = self.key('list')['points']
        self.assertEqual(points[-1]['co']['X'], 73)  # trim 48 + elapsed 24 + 1
        self.assertAlmostEqual(self.native().GetValue(73), .25)
        self.assertAlmostEqual(self.key('list', space='clip', unit='seconds')['points'][-1]['co']['X'], 1.001)

    def test_nested_effect_properties_preserve_siblings_and_parent_timing(self):
        effect = self.call('effect.add', clip_id=self.clip['id'], type='ChromaKey')
        before = self.call('effect.get', id=effect['id'])
        self.call('effects.keyframe.set', id=effect['id'], property='color.red', space='clip', at=31, value=200)
        after = self.call('effect.get', id=effect['id'])
        self.assertEqual(after['color']['green'], before['color']['green'])
        self.assertEqual(after['color']['blue'], before['color']['blue'])
        self.assertEqual(after['color']['red']['Points'][-1]['co'], {'X': 91, 'Y': 200})
        curve = openshot.Keyframe(); curve.SetJson(json.dumps(after['color']['red']))
        self.assertEqual(curve.GetValue(91), 200)
        self.call('history.undo')
        self.assertEqual(self.call('effect.get', id=effect['id']), before)
        self.call('history.redo')
        self.assertEqual(self.call('effect.get', id=effect['id']), after)

    def test_bezier_handles_and_constant_interpolation_are_native(self):
        self.key('clear', value=0)
        handles = {'handle_left': {'X': .2, 'Y': .9}, 'handle_right': {'X': .7, 'Y': .1}, 'handle_type': 1}
        self.key('set', frame=31, value=1, interpolation='bezier', handles=handles)
        point = self.key('list')['points'][-1]
        for name, value in handles.items():
            self.assertEqual(point[name], value)
        self.assertGreater(self.native().GetValue(16), 0)
        self.assertLess(self.native().GetValue(16), 1)
        self.key('set', frame=31, value=.8, interpolation='constant')
        self.assertEqual(self.key('list')['points'][-1]['handle_left'], handles['handle_left'])
        self.assertEqual(self.native().GetValue(30), 0)
        self.assertAlmostEqual(self.native().GetValue(31), .8)

    def test_preview_exposes_midpoint_pause_without_changing_history(self):
        self.key('clear', value=0)
        self.key('set', frame=31, value=.5, interpolation='bezier')
        self.key('set', frame=61, value=1, interpolation='bezier')
        before = self.state()
        result = self.key('preview', start=1, end=61, count=4)
        self.assertEqual(self.state(), before)
        samples = {row['native_frame']: row for row in result['samples']}
        self.assertTrue({30, 31, 32}.issubset(samples))
        middle = samples[31]
        peak = max(abs(row['outgoing_rate']) for row in samples.values())
        self.assertLess(middle['incoming_rate'], peak * .1)
        self.assertLess(middle['outgoing_rate'], peak * .1)
        self.assertEqual(result['rate_unit'], 'property units per second')
        self.key('set', frame=31, value=.5, interpolation='linear')
        self.key('set', frame=61, value=1, interpolation='linear')
        middle = self.key('preview', at=31)['samples'][0]
        self.assertAlmostEqual(middle['incoming_rate'], .5)
        self.assertAlmostEqual(middle['outgoing_rate'], .5)

    def test_preview_constant_jump_and_invalid_ranges(self):
        self.key('clear', value=0)
        self.key('set', frame=31, value=1, interpolation='constant')
        jump = self.key('preview', at=31)['samples'][0]
        self.assertEqual(jump['incoming_rate'], 30)
        self.assertEqual(jump['outgoing_rate'], 0)
        before = self.state()
        for params in ({'at': 1, 'end': 2}, {'start': 0}, {'start': 3, 'end': 2},
                       {'count': 1}, {'count': 257}):
            with self.subTest(params=params), self.assertRaises(CommandError):
                self.key('preview', **params)
        self.assertEqual(self.state(), before)

    def test_preview_coordinates_for_clip_nested_effect_and_transition(self):
        effect = self.call('effect.add', clip_id=self.clip['id'], type='ChromaKey')
        transition = self.call('transition.add', mask=self.path, layer=self.layer, position=5, duration=2)
        for kind, obj, prop in [('clip', self.clip, 'volume'), ('effects', effect, 'color.red'),
                                ('transition', transition, 'brightness')]:
            self.call(kind + '.keyframe.set', id=obj['id'], property=prop,
                      space='clip', unit='seconds', at=0, value=0)
            self.call(kind + '.keyframe.set', id=obj['id'], property=prop,
                      space='clip', unit='seconds', at=1, value=1)
            before = self.state()
            result = self.call(kind + '.keyframe.preview', id=obj['id'], property=prop,
                               space='timeline', unit='seconds', at=5.5)
            row = result['samples'][0]
            self.assertEqual(row['at'], 5.5)
            self.assertAlmostEqual(row['value'], .5)
            self.assertAlmostEqual(row['incoming_rate'], 1)
            self.assertEqual(self.state(), before)

    def test_named_easing_shapes_incoming_segment_and_preserves_neighbors(self):
        from classes.easing import easing_presets
        self.key('clear', value=0)
        self.key('set', frame=31, value=.5)
        self.key('set', frame=61, value=1)
        before = self.key('list')['points']
        for name, control, _ in easing_presets():
            with self.subTest(preset=name):
                self.key('set', frame=31, value=.5, easing=name)
                points = self.key('list')['points']
                self.assertEqual(points[0]['handle_right'], {'X': control[0], 'Y': control[1]})
                self.assertEqual(points[1]['handle_left'], {'X': control[2], 'Y': control[3]})
                self.assertEqual(points[1]['handle_right'], before[1]['handle_right'])
                self.assertEqual(points[2], before[2])
                samples = self.key('preview', start=1, end=31)
                self.assertEqual(samples['samples'][0]['value'], 0)
                self.assertEqual(samples['samples'][-1]['value'], .5)
        self.key('set', frame=31, value=.5, easing='ease-in')
        self.assertLess(self.key('preview', at=16)['samples'][0]['value'], .25)
        self.key('set', frame=31, value=.5, easing='ease-out')
        self.assertGreater(self.key('preview', at=16)['samples'][0]['value'], .25)
        self.call('history.undo')
        self.assertLess(self.key('preview', at=16)['samples'][0]['value'], .25)

    def test_preview_fractional_fps_and_sample_limit(self):
        self.app.project._data['fps'] = {'num': 24000, 'den': 1001}
        self.key('clear', value=0)
        self.key('set', frame=25, value=1)
        result = self.key('preview', at=13)
        self.assertEqual(result['fps'], {'num': 24000, 'den': 1001})
        self.assertAlmostEqual(result['samples'][0]['outgoing_rate'], 1000 / 1001)
        points = [{'co': {'X': 1 + i * 4, 'Y': i / 400}, 'interpolation': 1}
                  for i in range(400)]
        self.key('paste', points=points, mode='replace')
        before = self.state()
        with self.assertRaisesRegex(CommandError, '1024'):
            self.key('preview')
        self.assertEqual(self.state(), before)
        self.assertLessEqual(self.key('preview', start=1, end=40)['sample_count'], 1024)

    def test_shared_gui_preset_labels_and_controls_are_unchanged(self):
        from classes.easing import keyframe_bezier_presets
        from windows.views import menu
        from windows.views.timeline_backend.qwidget import keyframe
        app = SimpleNamespace(_tr=lambda text: 'translated:' + text)
        expected = keyframe_bezier_presets(app._tr)
        self.assertEqual(len(expected), 28)
        self.assertEqual(expected[0], (.25, .1, .25, 1., 'translated:Ease (Default)'))
        with patch.object(menu, 'get_app', return_value=app):
            self.assertEqual(menu.keyframe_bezier_presets(), expected)
        with patch.object(keyframe, 'get_app', return_value=app):
            self.assertEqual(keyframe.KeyframeMixin._keyframe_bezier_presets(None), expected)

    def test_easing_validation_and_batch_preflight_are_atomic(self):
        self.key('clear', value=0)
        before = self.state()
        for params in ({'frame': 1, 'easing': 'ease'},
                       {'frame': 31, 'easing': 'ease', 'interpolation': 'linear'},
                       {'frame': 31, 'easing': 'ease', 'handles': {}},
                       {'frame': 31, 'easing': 'ease-typo'}):
            with self.subTest(params=params), self.assertRaises(CommandError):
                self.key('set', value=1, **params)
            self.assertEqual(self.state(), before)
        commands = [{'method': 'clip.keyframe.set',
                     'params': {'id': self.clip['id'], 'property': 'volume',
                                'frame': 31, 'value': 1, 'easing': 'ease-out'}}]
        self.call('edit.apply', commands=commands, dry_run=True)
        self.assertEqual(self.state(), before)
        self.call('edit.apply', commands=commands)
        self.assertGreater(self.key('preview', at=16)['samples'][0]['value'], .5)
        self.call('history.undo')
        self.assertEqual(self.key('list')['points'][0]['co']['Y'], 0)

    def test_remove_last_point_and_clear_keep_editable_base(self):
        self.key('clear', value=.4)
        self.key('remove', at=1)
        self.assertEqual(len(self.key('list')['points']), 1)
        self.assertAlmostEqual(self.native().GetValue(100), .4)
        self.key('set', frame=31, value=1)
        self.assertAlmostEqual(self.native().GetValue(16), .7)
        self.key('clear', at=16)
        self.assertAlmostEqual(self.native().GetValue(100), .7)
        self.key('set', frame=31, value=.2)
        self.assertAlmostEqual(self.native().GetValue(31), .2)

    def test_range_transform_collision_rejected_and_handles_preserved(self):
        self.key('set', frame=31, value=.2, interpolation='bezier', handles={'handle_left': {'X': .1, 'Y': .8}})
        self.key('set', frame=61, value=.8)
        original = self.key('list')['points']
        self.key('transform', start=31, end=61, offset=30, scale=2)
        moved = self.key('list')['points']
        self.assertEqual([p['co']['X'] for p in moved], [1, 61, 121])
        self.assertEqual(moved[1]['handle_left'], original[1]['handle_left'])
        self.call('history.undo')
        self.assertEqual(self.key('list')['points'], original)
        before = self.state()
        for params in ({'start': 31, 'end': 31, 'offset': -30}, {'start': 31, 'offset': -200}, {'scale': 0}, {'scale': .001}):
            with self.subTest(params=params), self.assertRaises(CommandError):
                self.key('transform', **params)
            self.assertEqual(self.state(), before)

    def test_copy_between_trimmed_clips_with_explicit_merge_or_replace(self):
        self.key('set', space='clip', at=1, value=.2)
        self.key('set', space='clip', at=31, value=.8)
        other = self.add_clip(position=20, start=4, end=10)
        self.key('copy', id=other['id'], source_id=self.clip['id'], space='clip', start=1, end=31, at=1, mode='merge')
        points = self.key('list', id=other['id'])['points']
        self.assertEqual([p['co']['X'] for p in points], [1, 121, 151])
        self.assertAlmostEqual(self.native(other['id']).GetValue(136), .5)
        self.key('copy', id=other['id'], source_id=self.clip['id'], space='clip', start=1, end=31, at=31, mode='replace')
        self.assertEqual([p['co']['X'] for p in self.key('list', id=other['id'])['points']], [151, 181])

    def test_invalid_curves_never_publish_or_change_history(self):
        before = self.state()
        listener = Mock()
        self.app.updates.add_listener(listener)
        self.addCleanup(self.app.updates.disconnect_listener, listener)
        invalid = [
            ('set', {'at': 0, 'value': 1}),
            ('set', {'at': 1.5, 'value': 1}),
            ('set', {'at': 1, 'value': float('nan')}),
            ('set', {'at': 1, 'value': 1, 'handles': {'handle_left': {'X': 'bad', 'Y': 0}}}),
            ('set', {'frame': 1, 'at': 1, 'value': 1}),
            ('set', {'at': 1, 'value': 1, 'property': 'reader.path'}),
            ('paste', {'points': [{'co': {'X': 1, 'Y': 0}}, {'co': {'X': 1, 'Y': 1}}], 'mode': 'merge'}),
            ('paste', {'points': [{'co': {'X': 1, 'Y': 0}, 'interpolation': 9}], 'mode': 'replace'}),
            ('set', {'at': 1, 'value': 2, 'property': 'alpha'}),
            ('remove', {}),
            ('clear', {'space': 'timeline', 'unit': 'seconds', 'at': 0}),
        ]
        for op, params in invalid:
            with self.subTest(op=op, params=params), self.assertRaises(CommandError):
                self.key(op, **params)
            self.assertEqual(self.state(), before)
        listener.changed.assert_not_called()

    def test_selection_filters_intersect_and_boundaries_are_half_open(self):
        second = self.add_clip(position=11, end=2)
        self.call('effect.add', clip_id=self.clip['id'], type='Saturation')
        selection = self.call('edit.select', selection={'layer': self.layer, 'start': 10, 'end': 11, 'file_id': self.file['id'], 'effect': 'saturation'})
        self.assertEqual(selection['ids'], [self.clip['id']])
        self.assertEqual(self.call('edit.select', selection={'start': 11})['ids'], [second['id']])
        before = self.state()
        self.call('edit.select', selection={'all': True})
        self.assertEqual(self.state(), before)
        for selector in ({}, {'all': False}, {'ids': [self.clip['id'], 'missing']}, {'layer': 999}, {'start': 4, 'end': 4}, {'unknown': 1}):
            with self.subTest(selector=selector), self.assertRaises(CommandError):
                self.call('edit.select', selection=selector)

    def test_bulk_effects_keyframes_and_relative_adjustments_one_undo(self):
        self.add_clip(position=15, start=4, end=10)
        before = copy.deepcopy(self.app.project._data)
        templates = [
            {'method': 'clip.adjust', 'params': {'values': {'position': {'add': 2}, 'volume': {'multiply': .5}}}},
            {'method': 'effects.add', 'as': 'look', 'params': {'type': 'Saturation'}},
            {'method': 'effects.keyframe.set', 'params': {'id': {'$ref': 'look.id'}, 'property': 'saturation', 'space': 'clip', 'at': 1, 'value': 0}},
            {'method': 'effects.keyframe.set', 'params': {'id': {'$ref': 'look.id'}, 'property': 'saturation', 'space': 'clip', 'at': 31, 'value': 1.2}},
        ]
        result = self.service.execute('edit.bulk', {'selection': {'all': True}, 'commands': templates})
        self.assertEqual(len(result['selected_ids']), 2)
        after = copy.deepcopy(self.app.project._data)
        for old, clip in zip(before['clips'], after['clips']):
            self.assertEqual(clip['position'], old['position'] + 2)
            self.assertEqual(clip['volume']['Points'][0]['co']['Y'], .5)
            curve = openshot.Keyframe(); curve.SetJson(json.dumps(clip['effects'][0]['saturation']))
            self.assertAlmostEqual(curve.GetValue(round(clip['start']*30)+16), .6)
        self.assertNotEqual(after['clips'][0]['effects'][0]['id'], after['clips'][1]['effects'][0]['id'])
        self.call('history.undo')
        self.assertEqual(self.app.project._data['clips'], before['clips'])
        self.call('history.redo')
        self.assertEqual(self.app.project._data['clips'], after['clips'])

    def test_dry_runs_and_failed_bulk_have_no_listener_or_history_effects(self):
        self.add_clip(position=15, end=2)
        before = self.state()
        listener = Mock()
        self.app.updates.add_listener(listener)
        self.addCleanup(self.app.updates.disconnect_listener, listener)
        templates = [{'method': 'clip.adjust', 'params': {'values': {'position': {'add': 1}}}}]
        result = self.call('edit.bulk', selection={'all': True}, commands=templates, dry_run=True)
        self.assertEqual(result['command_count'], 2)
        self.assertEqual(result['selected_ids'], [c['id'] for c in before[0]['clips']])
        self.call('edit.apply', commands=[{'method': 'clip.set', 'params': {'id': self.clip['id'], 'values': {'volume': .1}}}], dry_run=True)
        # First selected clip can move left by ten seconds only if it starts late enough.
        with self.assertRaises(CommandError):
            self.call('edit.bulk', selection={'all': True}, commands=[{'method': 'clip.adjust', 'params': {'values': {'end': {'add': -3}}}}])
        self.assertEqual(self.state(), before)
        listener.changed.assert_not_called()

    def test_revision_lock_empty_selection_and_expansion_limits(self):
        templates = [{'method': 'clip.set', 'params': {'values': {'volume': .2}}}]
        before = self.state()
        with self.assertRaises(CommandError):
            self.call('edit.bulk', selection={'all': True}, commands=templates, expect_revision=-1)
        with self.assertRaises(CommandError):
            self.call('edit.bulk', selection={'start': 1000}, commands=templates)
        self.assertEqual(self.state(), before)
        self.app.project._data['layers'][0]['lock'] = True
        with self.assertRaises(CommandError) as error:
            self.call('edit.bulk', selection={'all': True}, commands=templates)
        self.assertEqual(error.exception.code, 'locked_track')
        self.app.project._data['layers'][0]['lock'] = False
        self.add_clip(end=2)
        before = self.state()
        with self.assertRaises(CommandError) as error:
            self.call('edit.bulk', selection={'all': True}, commands=templates * 129)
        self.assertEqual(error.exception.code, 'batch_limit')
        self.assertEqual(self.state(), before)

    def test_relative_changes_preserve_curve_shape_and_reject_invalid_results(self):
        self.key('set', frame=31, value=.2, interpolation='bezier', handles={'handle_left': {'X': .2, 'Y': .8}})
        original = self.key('list')['points']
        sample = self.native().GetValue(16)
        self.call('clip.adjust', id=self.clip['id'], values={'volume': {'multiply': 2, 'add': .1}})
        updated = self.key('list')['points']
        self.assertAlmostEqual(self.native().GetValue(16), sample * 2 + .1)
        self.assertEqual(updated[1]['handle_left'], original[1]['handle_left'])
        before = self.state()
        with self.assertRaises(CommandError):
            self.call('clip.adjust', id=self.clip['id'], values={'position': {'add': -100}})
        self.assertEqual(self.state(), before)

    def test_bulk_animation_save_reopen_and_undo_redo(self):
        self.add_clip(position=20, start=4, end=8)
        def animation_state():
            keys = ('id', 'start', 'end', 'position', 'location_x', 'volume', 'effects')
            return [{k: copy.deepcopy(c[k]) for k in keys} for c in self.app.project.get('clips')]
        before = animation_state()
        templates = [
            {'method': 'clip.keyframe.set', 'params': {'property': 'location_x', 'space': 'clip', 'at': 1, 'value': -1}},
            {'method': 'clip.keyframe.set', 'params': {'property': 'location_x', 'space': 'clip', 'at': 31, 'value': 0, 'interpolation': 'bezier'}},
        ]
        self.call('edit.bulk', selection={'all': True}, commands=templates)
        changed = animation_state()
        path = str(Path(self.temp.name) / 'animation.osp')
        self.call('project.save', path=path)
        self.call('project.open', path=path)
        self.assertEqual(animation_state(), changed)
        self.call('history.undo')
        self.assertEqual(animation_state(), before)
        self.call('history.redo')
        self.assertEqual(animation_state(), changed)

    def test_noninteractive_load_ignores_obsolete_resource_but_checks_reader(self):
        effect = self.call('effect.add', clip_id=self.clip['id'], type='ChromaKey')
        path = Path(self.temp.name) / 'legacy.osp'
        self.call('project.save', path=str(path))
        data = json.loads(path.read_text())
        effect = data['clips'][0]['effects'][0]
        effect['resource'] = '/missing/obsolete-mask.svg'
        effect['mask_reader'] = {'type': 'QtImageReader', 'path': self.path}
        path.write_text(json.dumps(data))
        self.call('project.open', path=str(path))
        self.assertNotIn('resource', self.app.project.get('clips')[0]['effects'][0])
        effect['mask_reader']['path'] = '/missing/real-mask.svg'
        path.write_text(json.dumps(data))
        before = self.state()
        with self.assertRaises(CommandError):
            self.call('project.open', path=str(path))
        self.assertEqual(self.state(), before)

    def test_bulk_gui_refresh_is_coalesced_and_restored_on_runtime_failure(self):
        window = SimpleNamespace(IgnoreUpdates=SimpleNamespace(emit=Mock()), refreshFrameSignal=SimpleNamespace(emit=Mock()))
        self.app.window = window
        self.addCleanup(setattr, self.app, 'window', None)
        self.call('edit.bulk', selection={'all': True}, commands=[{'method': 'clip.set', 'params': {'values': {'volume': .2}}}] * 3)
        self.assertEqual(window.IgnoreUpdates.emit.call_args_list[0].args, (True, True))
        self.assertEqual(window.IgnoreUpdates.emit.call_args_list[-1].args, (False, True))
        # The real IgnoreUpdates(False) callback performs the final refresh.
        window.refreshFrameSignal.emit.assert_not_called()
        window.IgnoreUpdates.emit.reset_mock()
        dispatch = self.service.dispatch
        calls = []
        def fail_during_commit(method, params):
            if method == 'clip.set':
                calls.append(method)
                if len(calls) == 4:  # two preflight calls, then one committed edit
                    raise RuntimeError('simulated engine listener failure')
            return dispatch(method, params)
        before = copy.deepcopy(self.app.project.get('clips'))
        with patch.object(self.service, 'dispatch', side_effect=fail_during_commit), self.assertRaises(CommandError) as error:
            self.call('edit.apply', commands=[{'method': 'clip.set', 'params': {'id': self.clip['id'], 'values': {'volume': .3}}}] * 2)
        self.assertEqual(error.exception.details['completed'], 1)
        self.assertEqual(window.IgnoreUpdates.emit.call_args_list[-1].args, (False, True))
        self.app.window = None
        self.call('history.undo')
        self.assertEqual(self.app.project.get('clips'), before)

    def test_same_keyframe_workflow_for_clips_effects_and_transitions(self):
        effect = self.call('effect.add', clip_id=self.clip['id'], type='Saturation')
        transition = self.call('transition.add', mask=self.path, layer=self.layer, position=5, duration=2)
        owners = [('clip', self.clip['id'], 'volume'), ('effects', effect['id'], 'saturation'),
                  ('transition', transition['id'], 'brightness')]
        for kind, owner_id, name in owners:
            with self.subTest(kind=kind):
                prefix = kind + '.keyframe.'
                discovery = self.call(prefix + 'list', id=owner_id)
                self.assertIn(name, [row['property'] for row in discovery['properties']])
                params = {'id': owner_id, 'property': name, 'space': 'clip', 'unit': 'seconds'}
                self.call(prefix + 'clear', **params, value=0)
                self.call(prefix + 'set', **params, at=0, value=0)
                self.call(prefix + 'set', **params, at=1, value=1)
                points = self.call(prefix + 'list', **params, start=0)['points']
                self.assertEqual([p['co'] for p in points], [{'X': 0, 'Y': 0}, {'X': 1, 'Y': 1}])
                self.call(prefix + 'transform', **params, start=1, end=1, offset=.5)
                self.assertEqual(self.call(prefix + 'list', **params, start=1)['points'][0]['co']['X'], 1.5)
                self.call(prefix + 'remove', **params, at=1.5)
                self.assertEqual(len(self.call(prefix + 'list', **params, start=0)['points']), 1)
                self.call(prefix + 'paste', **params, points=points, mode='replace')
                self.assertEqual(self.call(prefix + 'list', **params)['points'], points)

    def test_keyframe_errors_explain_property_and_coordinate_corrections(self):
        before = self.state()
        with self.assertRaises(CommandError) as error:
            self.key('set', property='volum', at=1, value=0)
        self.assertIn("Did you mean 'volume'?", str(error.exception))
        self.assertEqual(error.exception.details['cause']['path'], 'params.property')
        with self.assertRaises(CommandError) as error:
            self.key('set', space='timeline', unit='seconds', at=0, value=0)
        self.assertIn('native frame', str(error.exception))
        self.assertIn('--space clip --unit seconds --at 0', str(error.exception))
        self.assertIn('coordinates', error.exception.details['cause'])
        with self.assertRaises(CommandError) as error:
            self.key('remove', at=1000)
        self.assertIn('not interpolated samples', str(error.exception))
        self.assertEqual(self.state(), before)

    def test_batch_rechecks_revision_after_gui_event_pump(self):
        old_transaction = self.app.updates.transaction_id
        observed = []
        def emit(ignore, wait):
            if ignore:
                observed.append(self.app.updates.transaction_id)
                self.app.updates.data_version += 1
        self.app.window = SimpleNamespace(ignore_updates=False, IgnoreUpdates=SimpleNamespace(emit=emit))
        self.addCleanup(setattr, self.app, 'window', None)
        original = self.call('clip.get', id=self.clip['id'])
        with self.assertRaises(CommandError) as error:
            self.call('edit.apply', commands=[{'method': 'clip.set', 'params': {'id': self.clip['id'], 'values': {'volume': .1}}}])
        self.assertEqual(error.exception.code, 'revision_conflict')
        self.assertEqual(observed, [old_transaction])
        self.assertEqual(self.app.updates.transaction_id, old_transaction)
        self.assertEqual(self.call('clip.get', id=self.clip['id']), original)

    def test_64_clip_256_command_animation_batch_and_single_undo(self):
        import time
        for index in range(63):
            self.add_clip(position=index * .5, start=index % 4, end=index % 4 + 3)
        before = copy.deepcopy(self.app.project.get('clips'))
        templates = [
            {'method': 'clip.keyframe.set', 'params': {'property': 'location_x', 'space': 'clip', 'at': 1, 'value': -1}},
            {'method': 'clip.keyframe.set', 'params': {'property': 'location_x', 'space': 'clip', 'at': 31, 'value': 0}},
            {'method': 'clip.keyframe.set', 'params': {'property': 'alpha', 'space': 'clip', 'at': 1, 'value': 0}},
            {'method': 'clip.keyframe.set', 'params': {'property': 'alpha', 'space': 'clip', 'at': 31, 'value': 1}},
        ]
        started = time.monotonic()
        result = self.call('edit.bulk', selection={'all': True}, commands=templates)
        print('64 clips / 256 commands: {:.3f}s including preflight'.format(time.monotonic() - started))
        self.assertEqual(len(result), 256)
        for clip in self.app.project.get('clips'):
            for name, expected in [('location_x', -.5), ('alpha', .5)]:
                curve = openshot.Keyframe(); curve.SetJson(json.dumps(clip[name]))
                self.assertAlmostEqual(curve.GetValue(round(clip['start'] * 30) + 16), expected)
        after = copy.deepcopy(self.app.project.get('clips'))
        self.call('history.undo')
        self.assertEqual(self.app.project.get('clips'), before)
        self.call('history.redo')
        self.assertEqual(self.app.project.get('clips'), after)

    def test_bulk_template_references_cannot_escape_the_selected_clip(self):
        self.add_clip(position=20, end=2)
        before = self.state()
        with self.assertRaises(CommandError) as error:
            self.call('edit.bulk', selection={'all': True}, commands=[
                {'method': 'effects.add', 'as': 'look', 'params': {'type': 'Saturation'}},
                {'method': 'effects.set', 'params': {'id': {'$ref': 'clip0_result0.id'}, 'values': {'saturation': .5}}},
            ])
        self.assertEqual(error.exception.code, 'invalid_reference')
        self.assertEqual(self.state(), before)

    def test_long_template_names_stay_valid_after_per_clip_expansion(self):
        name = 'result' + 'x' * 58
        self.call('edit.bulk', selection={'all': True}, commands=[
            {'method': 'effects.add', 'as': name, 'params': {'type': 'Saturation'}},
            {'method': 'effects.set', 'params': {'id': {'$ref': name + '.id'}, 'values': {'saturation': .5}}},
        ])
        effect = self.call('clip.get', id=self.clip['id'])['effects'][0]
        self.assertEqual(effect['saturation']['Points'][0]['co']['Y'], .5)

    def test_nested_curve_boolean_is_not_treated_as_unchanged_numeric_value(self):
        effect = self.call('effect.add', clip_id=self.clip['id'], type='ChromaKey')
        self.call('effects.keyframe.set', id=effect['id'], property='color.red', at=1, value=1)
        color = self.call('effect.get', id=effect['id'])['color']
        color['red']['Points'][0]['co']['Y'] = True
        before = self.state()
        with self.assertRaises(CommandError) as error:
            self.call('effect.set', id=effect['id'], values={'color': color})
        self.assertIn('color.red.Points[0].co.Y', str(error.exception))
        self.assertEqual(self.state(), before)
