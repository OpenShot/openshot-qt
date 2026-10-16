"""
 @file
 @brief Behavioral coverage for command discovery, framing and native editing sessions.

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
import contextlib
import io
import json
from pathlib import Path
import subprocess  # nosec B404 - Launch controlled local processes without a shell.
import sys
import tempfile
import unittest

from cli import build_parser, normalize_help
from classes.agent.protocol import CommandError, decode, dimensions, encode


class HelpTests(unittest.TestCase):
    def test_every_command_has_offline_help(self):
        import argparse
        def visit(parser, path):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(SystemExit) as result:
                    build_parser().parse_args(path + ['--help'])
            self.assertEqual(result.exception.code, 0)
            self.assertIn('usage:', output.getvalue())
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for name, child in action.choices.items():
                        visit(child, path + [name])
        visit(build_parser(), [])

    def test_consistent_help_and_effect_routing(self):
        for args in (['help'], ['clip', 'help'], ['clip', 'add', 'help'], ['effects', 'help']):
            self.assertEqual(normalize_help(args)[-1], '--help')
        args = build_parser().parse_args(normalize_help(['effects', 'audiovisualization', 'help', '--property', 'background']))
        self.assertEqual(args.method, 'effect.describe')
        self.assertEqual(args.type, 'audiovisualization')
        self.assertEqual(args.property, 'background')
        self.assertEqual(build_parser().parse_args(['effects', 'list']).method, 'effect.types')
        self.assertEqual(build_parser().parse_args(['effects', 'instances']).method, 'effect.list')

    def test_help_does_not_import_native_dependencies(self):
        from tests.agent_test_support import subprocess_environment
        script = """import cli, sys
try:
    cli.main(['--help'])
except SystemExit as exc:
    assert exc.code == 0
assert 'openshot' not in sys.modules
assert 'qt_api' not in sys.modules
"""
        result = subprocess.run([sys.executable, '-c', script], capture_output=True,  # nosec B603 - Fixed test executable and argument array; no shell.
                                env=subprocess_environment())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fragmented_and_multiple_messages(self):
        packet = encode({'method': 'clip.get', 'params': {'id': 'abc'}})
        buffer = bytearray(packet[:3])
        self.assertIsNone(decode(buffer))
        buffer.extend(packet[3:] + encode({'ok': True}))
        self.assertEqual(decode(buffer)['method'], 'clip.get')
        self.assertEqual(decode(buffer), {'ok': True})
        self.assertEqual(buffer, bytearray())

    def test_limits_reject_before_allocating(self):
        for size in [(1000000, 10), (4096, 4096), (0, 10)]:
            with self.assertRaises(CommandError):
                dimensions(*size)

    def test_export_wait_success_failure_and_timeout(self):
        from unittest.mock import patch
        from classes.agent.waiting import wait_for_export
        running = {'data': {'job_id': 'job', 'state': 'running'}}
        completed = {'data': {'job_id': 'job', 'state': 'completed'}}
        clock = [0]
        def sleep(seconds):
            clock[0] += seconds
        with patch('classes.agent.waiting.time.monotonic', side_effect=lambda: clock[0]), patch('classes.agent.waiting.time.sleep', side_effect=sleep):
            calls = []
            def request(*args):
                calls.append(args)
                return completed
            result = wait_for_export({}, running, request, 30, 10)
            self.assertEqual(result['wait']['status_requests'], 1)
            self.assertEqual(calls[0][1:3], ('export.status', {'job_id': 'job'}))
            with self.assertRaises(CommandError) as error:
                wait_for_export({}, running, request, 30, 0)
            self.assertEqual(error.exception.code, 'wait_timeout')
            self.assertEqual(error.exception.details['job_id'], 'job')
            with self.assertRaises(CommandError) as error:
                wait_for_export({}, {'data': {'job_id': 'job', 'state': 'failed', 'error': 'encoder failed'}}, request, 30, 10)
            self.assertEqual(error.exception.code, 'export_failed')


class EditingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        isolate_preferences(self)
        from classes.agent.service import EditingService
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        self.service = EditingService(self.app, 'test-session', 'headless')
        self.temp = tempfile.TemporaryDirectory()
        from qt_api import QImage, QColor
        from classes.agent.render import image_format
        image = QImage(64, 36, image_format())
        image.fill(QColor('red'))
        self.path = str(Path(self.temp.name)/'red.png')
        image.save(self.path)
        self.layer = self.app.project.get('layers')[0]['number']

    def tearDown(self):
        self.temp.cleanup()

    def call(self, method, **params):
        return self.service.execute(method, params)['data']

    def add_clip(self):
        file = self.call('file.import', path=self.path)
        return self.call('clip.add', file_id=file['id'], layer=self.layer, end=2)

    def test_show_rejects_offscreen_without_changing_project(self):
        if self.app.platformName().lower() not in ('offscreen', 'minimal'):
            self.skipTest('Requires a headless Qt backend')
        clip = self.add_clip()
        before = self.call('session.status')
        with self.assertRaises(CommandError) as error:
            self.call('session.show')
        self.assertEqual(error.exception.code, 'display_unavailable')
        self.assertEqual(self.call('session.status'), before)
        self.assertEqual(self.call('clip.get', id=clip['id'])['id'], clip['id'])
        self.assertIsNone(self.app.window)

    def test_query_edits_undo_redo_and_batch_failure(self):
        clip = self.add_clip()
        self.call('clip.set', id=clip['id'], values={'position': 3})
        self.assertEqual(self.call('clip.get', id=clip['id'])['position'], 3)
        self.call('history.undo')
        self.assertEqual(self.call('clip.get', id=clip['id'])['position'], 0)
        self.call('history.redo')
        self.assertEqual(self.call('clip.get', id=clip['id'])['position'], 3)
        with self.assertRaises(CommandError) as error:
            self.call('edit.apply', commands=[
                {'method': 'clip.set', 'params': {'id': clip['id'], 'values': {'position': 4}}},
                {'method': 'clip.remove', 'params': {'id': 'missing'}},
            ])
        self.assertEqual(error.exception.details['completed'], 0)
        self.assertEqual(self.call('clip.get', id=clip['id'])['position'], 3)
        with self.assertRaises(CommandError):
            self.call('edit.apply', expect_revision=-1, commands=[{'method': 'clip.remove', 'params': {'id': clip['id']}}])
        self.call('clip.remove', id=clip['id'])
        self.call('history.undo')
        self.assertEqual(self.call('clip.get', id=clip['id'])['id'], clip['id'])

    def test_insert_undo_redo(self):
        clip = self.add_clip()
        self.call('history.undo')
        self.assertEqual(self.call('clip.list'), [])
        self.call('history.redo')
        self.assertEqual(self.call('clip.list')[0]['id'], clip['id'])

    def test_named_batch_creates_and_reverts_all_objects(self):
        result = self.service.execute('edit.apply', {'commands': [
            {'method': 'file.import', 'as': 'media', 'params': {'path': self.path}},
            {'method': 'clip.add', 'as': 'shot', 'params': {'file_id': {'$ref': 'media.id'}, 'layer': self.layer, 'end': 3}},
            {'method': 'clip.fade', 'params': {'id': {'$ref': 'shot.id'}, 'fade_in': 0.5, 'fade_out': 0.5}},
            {'method': 'effects.add', 'as': 'look', 'params': {'clip_id': {'$ref': 'shot.id'}, 'type': 'Saturation'}},
            {'method': 'effect.set', 'params': {'id': {'$ref': 'look.id'}, 'values': {'saturation': 1.2}}},
        ]})
        clip_id = result['refs']['shot']['id']
        clip = self.call('clip.get', id=clip_id)
        self.assertEqual(clip['effects'][0]['id'], result['refs']['look']['id'])
        self.assertEqual(clip['alpha']['Points'][-1]['co']['Y'], 0)
        self.call('history.undo')
        self.assertEqual(self.call('clip.list'), [])
        self.assertEqual(self.call('file.list'), [])
        self.call('history.redo')
        self.assertEqual(self.call('clip.get', id=clip_id), clip)

    def test_batch_split_references_and_undo(self):
        clip = self.add_clip()
        result = self.service.execute('edit.apply', {'commands': [
            {'method': 'clip.split', 'as': 'cut', 'params': {'id': clip['id'], 'at': 1}},
            {'method': 'clip.set', 'params': {'id': {'$ref': 'cut.right.id'}, 'values': {'volume': 0.2}}},
        ]})
        right = result['refs']['cut']['right']['id']
        self.assertAlmostEqual(self.call('clip.get', id=right)['volume']['Points'][0]['co']['Y'], 0.2)
        self.call('history.undo')
        self.assertEqual(len(self.call('clip.list')), 1)
        self.assertEqual(self.call('clip.get', id=clip['id'])['end'], 2)

    def test_batch_profile_preflight_and_history(self):
        commands = [
            {'method': 'project.profile', 'params': {'width': 1280, 'height': 720, 'fps_num': 24}},
            {'method': 'file.import', 'as': 'media', 'params': {'path': self.path}},
            {'method': 'clip.add', 'params': {'file_id': {'$ref': 'media.id'}, 'layer': self.layer, 'end': 3}},
        ]
        before = json.dumps(self.app.project._data, sort_keys=True)
        calls = []
        class Watcher:
            def changed(self, action):
                calls.append(action)
        watcher = Watcher()
        self.app.updates.add_listener(watcher)
        try:
            with self.assertRaises(CommandError):
                self.call('edit.apply', commands=commands + [{'method': 'clip.remove', 'params': {'id': 'missing'}}])
            self.assertEqual(json.dumps(self.app.project._data, sort_keys=True), before)
            self.assertEqual(calls, [])
            self.call('edit.apply', commands=commands)
            self.assertEqual(self.service.fps(), 24)
            self.call('history.undo')
            self.assertEqual(self.service.fps(), 30)
            self.assertEqual(self.call('clip.list'), [])
            self.call('history.redo')
            self.assertEqual(self.service.fps(), 24)
            self.assertEqual(len(self.call('clip.list')), 1)
        finally:
            self.app.updates.disconnect_listener(watcher)

    def test_invalid_reference_and_fade_do_not_change_project(self):
        before = json.dumps(self.app.project._data, sort_keys=True)
        revision = self.app.updates.data_version
        for tail in [
            {'method': 'clip.add', 'params': {'file_id': {'$ref': 'typo.id'}, 'layer': self.layer}},
            {'method': 'file.import', 'as': 'media', 'params': {'path': self.path}},
        ]:
            with self.assertRaises(CommandError):
                self.call('edit.apply', commands=[{'method': 'file.import', 'as': 'media', 'params': {'path': self.path}}, tail])
            self.assertEqual(json.dumps(self.app.project._data, sort_keys=True), before)
            self.assertEqual(self.app.updates.data_version, revision)
        clip = self.add_clip()
        self.call('clip.set', id=clip['id'], values={'start': 10, 'end': 13})
        self.call('clip.fade', id=clip['id'], fade_in=0.5, fade_out=0.5)
        native = self.service.native('clip', self.call('clip.get', id=clip['id']))
        self.assertEqual(native.alpha.GetValue(301), 0)
        self.assertEqual(native.alpha.GetValue(316), 1)
        self.assertEqual(native.alpha.GetValue(390), 0)
        revision = self.app.updates.data_version
        with self.assertRaises(CommandError):
            self.call('clip.fade', id=clip['id'], fade_in=5)
        self.assertEqual(self.app.updates.data_version, revision)

    def test_fade_ends_on_native_last_frame_with_unsnapped_timing(self):
        clip = self.add_clip()
        self.call('clip.set', id=clip['id'], values={'position': 0.02, 'start': 0.01, 'end': 0.1})
        self.call('clip.fade', id=clip['id'], fade_out=1/30)
        native = self.service.native('clip', self.call('clip.get', id=clip['id']))
        self.assertEqual(native.alpha.GetValue(1), 1)
        self.assertEqual(native.alpha.GetValue(2), 0)

    def test_profile_and_native_render(self):
        self.call('project.profile', width=1280, height=720, fps_num=24, fps_den=1)
        self.assertEqual(self.call('project.get')['fps'], {'num': 24, 'den': 1})
        self.call('history.undo')
        self.assertEqual(self.call('project.get')['fps'], {'num': 30, 'den': 1})
        self.call('history.redo')
        self.assertEqual(self.call('project.get')['fps'], {'num': 24, 'den': 1})
        self.add_clip()
        output = str(Path(self.temp.name)/'frame.png')
        result = self.call('timeline.thumbnail', frame=1, width=160, height=90, output=output)
        self.assertEqual(result['tiles'][0]['seconds'], 0)
        from qt_api import QImage
        image = QImage(output)
        self.assertEqual((image.width(), image.height()), (160, 90))
        self.assertGreater(image.pixelColor(80, 45).red(), 200)
        with self.assertRaises(CommandError):
            self.call('timeline.strip', start=0, end=2, width=4096, height=4096, count=64, output=str(Path(self.temp.name)/'large.png'))

    def test_invalid_properties_never_reach_listeners(self):
        clip = self.add_clip()
        calls = []
        class Watcher:
            def changed(self, action):
                calls.append(action)
        watcher = Watcher()
        self.app.updates.add_listener(watcher)
        revision = self.app.updates.data_version
        cases = [
            ({'volum': 0.5}, 'params.values.volum'),
            ({'volume': 'quiet'}, 'params.values.volume'),
            ({'position': True}, 'params.values.position'),
            ({'alpha': 2}, 'params.values.alpha'),
            ({'has_video': 4}, 'params.values.has_video'),
            ({'duration': 3}, 'params.values.duration'),
            ({'volume': {'Points': [{'co': {'X': 0, 'Y': 1}}]}}, 'params.values.volume.Points[0].co.X'),
            ({'volume': {'Points': [{'co': {'X': 1, 'Y': float('nan')}}]}}, 'params.values.volume.Points[0].co.Y'),
            ({'volume': {'Points': [{'co': {'X': 1, 'Y': 1}, 'interpolation': 7}]}}, 'params.values.volume.Points[0].interpolation'),
        ]
        try:
            for values, expected_path in cases:
                with self.subTest(values=values):
                    with self.assertRaises(CommandError) as error:
                        self.call('clip.set', id=clip['id'], values=values)
                    self.assertIn(expected_path, str(error.exception))
                    self.assertEqual(self.app.updates.data_version, revision)
                    self.assertEqual(calls, [])
            with self.assertRaises(CommandError):
                self.call('edit.apply', commands=[
                    {'method': 'clip.set', 'params': {'id': clip['id'], 'values': {'position': 4}}},
                    {'method': 'clip.set', 'params': {'id': clip['id'], 'values': {'volum': 1}}},
                ])
            self.assertEqual(calls, [])
            self.assertEqual(self.app.updates.data_version, revision)
        finally:
            self.app.updates.disconnect_listener(watcher)

    def test_scalar_and_individual_keyframes(self):
        clip = self.add_clip()
        self.call('clip.set', id=clip['id'], values={'volume': 0.5, 'has_video': 0})
        result = self.call('clip.get', id=clip['id'])
        self.assertEqual(result['volume']['Points'][0]['co']['Y'], 0.5)
        self.call('clip.keyframe.set', id=clip['id'], property='volume', frame=31, value=1.0)
        result = self.call('clip.get', id=clip['id'])
        self.assertEqual([p['co']['X'] for p in result['volume']['Points']], [1, 31])
        with self.assertRaises(CommandError):
            self.call('clip.set', id=clip['id'], values={'position': 2}, typo=True)

    def test_real_timeline_snapshot_is_read_only(self):
        clip = self.add_clip()
        revision = self.app.updates.data_version
        listeners = list(self.app.updates.updateListeners)
        result = self.call('timeline.view', start=0.5, end=1.5, width=640,
                           output=str(Path(self.temp.name)/'timeline.png'))
        self.assertEqual(result['renderer'], 'qwidget')
        self.assertEqual(result['tracks'], [self.layer])
        self.assertEqual(result['width'], 640)
        self.assertEqual(self.app.updates.data_version, revision)
        self.assertEqual(self.app.updates.updateListeners, listeners)
        self.assertIsNone(self.app.window)
        self.assertEqual(self.call('clip.get', id=clip['id'])['position'], 0)
        with self.assertRaises(CommandError):
            self.call('timeline.view', start=0, end=100, pixels_per_second=1000,
                      output=str(Path(self.temp.name)/'too-wide.png'))

    def test_effect_help_matches_installed_engine(self):
        result = self.call('effect.describe', type='audio_visualization')
        self.assertEqual(result['class_name'], 'AudioVisualization')
        self.assertIn('podcast', result['details'])
        self.assertIn('background', result['properties'])
        self.assertTrue(result['properties']['background']['choices'])
        self.assertTrue(self.call('effect.types')[0]['description'])

    def test_effect_and_transition_roundtrip(self):
        clip = self.add_clip()
        effect = self.call('effect.add', clip_id=clip['id'], type='Blur')
        self.assertEqual(self.call('effect.get', id=effect['id'])['id'], effect['id'])
        self.call('effect.set', id=effect['id'], values={'horizontal_radius': 2})
        attached = self.call('effect.list')[0]
        self.assertEqual(attached['clip_id'], clip['id'])
        self.assertNotIn('duration', attached)
        self.call('effect.remove', id=effect['id'])
        self.call('history.undo')
        self.assertEqual(len(self.call('effect.list')), 1)
        transition = self.call('transition.add', mask=self.path, layer=self.layer, duration=1)
        self.assertTrue(self.call('transition.properties', id=transition['id'], frame=1))
        self.call('transition.remove', id=transition['id'])
        self.assertEqual(self.call('transition.list'), [])


if __name__ == '__main__':
    unittest.main()
