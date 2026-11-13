"""
 @file
 @brief CLI clip-menu presets share the editor's logic, validation, and undo history.

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
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from classes.agent.protocol import CommandError


class AgentClipPresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        isolate_preferences(self)
        from classes.agent.service import EditingService
        from qt_api import QImage, QColor
        from classes.agent.render import image_format
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        self.service = EditingService(self.app, 'test-presets', 'headless')
        self.temp = tempfile.TemporaryDirectory()
        image = QImage(64, 36, image_format())
        image.fill(QColor('red'))
        path = str(Path(self.temp.name) / 'red.png')
        image.save(path)
        self.file = self.call('file.import', path=path)
        self.layer = self.app.project.get('layers')[0]['number']
        self.clip = self.call('clip.add', file_id=self.file['id'], layer=self.layer, position=3, start=0, end=4)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, method, **params):
        return self.service.execute(method, params)['data']

    def data(self, clip_id=None):
        return self.service.obj('clip', clip_id or self.clip['id']).data

    def points(self, prop, clip_id=None):
        return [(p['co']['X'], p['co']['Y']) for p in self.data(clip_id)[prop]['Points']]

    def test_motion_presets_match_menu_zones_and_undo(self):
        before = copy.deepcopy(self.data())
        self.call('clip.motion', id=self.clip['id'], preset='slide-in-left')
        self.assertEqual(self.points('location_x'), [(1, -1.0), (31, 0.0)])
        self.call('clip.motion', id=self.clip['id'], preset='pulse', at=5)
        self.assertEqual([x for x, _ in self.points('scale_x')], [1, 61, 76, 91])  # Pulse from 2s into the clip.
        self.call('clip.motion', id=self.clip['id'], preset='wipe-out-left')
        mask = [e for e in self.data()['effects'] if e['class_name'] == 'Mask']
        self.assertEqual(len(mask), 1)
        self.assertEqual(mask[0]['ui-menu'], 'motion')
        self.assertTrue(mask[0]['reader']['path'].endswith('wipe_left_to_right.svg'))
        self.call('clip.motion', id=self.clip['id'], preset='none')
        self.assertEqual(self.data()['effects'], [])
        for _ in range(4):
            self.service.execute('history.undo', {})
        self.assertEqual(self.data(), before)

    def test_relative_motion_keeps_a_placed_clip_anchored(self):
        import openshot
        self.call('clip.set', id=self.clip['id'], values={'gravity': openshot.GRAVITY_TOP_RIGHT, 'location_x': -0.05})
        for preset in ('slide-in-left', 'pulse', 'bounce-out'):
            self.call('clip.motion', id=self.clip['id'], preset=preset)
            self.assertEqual(self.data()['gravity'], openshot.GRAVITY_TOP_RIGHT, preset)
        self.assertAlmostEqual(self.points('location_x')[-1][1], -0.05, places=5)
        self.call('clip.motion', id=self.clip['id'], preset='cam-push-in')
        self.assertEqual(self.data()['gravity'], openshot.GRAVITY_CENTER)  # Camera frames from the center.

    def test_look_presets_replace_remove_and_reset(self):
        self.call('clip.look', id=self.clip['id'], effect='ColorGrade', preset='warm_up')
        self.call('clip.look', id=self.clip['id'], effect='ColorGrade', preset='boost_color')
        self.call('clip.look', id=self.clip['id'], effect='Glow', preset='neon')
        self.assertEqual([e['class_name'] for e in self.data()['effects']], ['ColorGrade', 'Glow'])
        glow = self.data()['effects'][1]
        self.assertEqual((glow['ui-menu'], glow['color']['blue']['Points'][0]['co']['Y']), ('look', 255))
        self.call('clip.look', id=self.clip['id'], effect='Glow', preset='none')
        self.assertEqual([e['class_name'] for e in self.data()['effects']], ['ColorGrade'])
        self.call('clip.look', id=self.clip['id'], effect='all', preset='none')
        self.assertEqual(self.data()['effects'], [])
        for effect, preset in (('Glow', 'warm_up'), ('all', 'neon')):
            with self.assertRaises(CommandError):
                self.call('clip.look', id=self.clip['id'], effect=effect, preset=preset)

    def test_speed_freeze_reset_and_repeat(self):
        self.call('clip.speed', id=self.clip['id'], mode='forward', factor=2)
        self.assertAlmostEqual(self.data()['end'], 2)
        self.call('clip.speed', id=self.clip['id'], mode='reset')
        self.assertAlmostEqual(self.data()['end'], 10)  # Default image length.
        self.call('clip.speed', id=self.clip['id'], mode='freeze', at=4, duration=2)
        self.assertAlmostEqual(self.data()['end'], 12)
        self.assertIn((31, 31), self.points('time'))
        self.assertIn((91, 31), self.points('time'))
        self.call('clip.speed', id=self.clip['id'], mode='reset')
        self.call('clip.repeat', id=self.clip['id'], passes=3, pattern='pingpong')
        self.assertAlmostEqual(self.data()['end'], 30)
        for params in ({'mode': 'forward'}, {'mode': 'reverse', 'factor': 2}, {'mode': 'freeze', 'at': 1, 'duration': 1},
                       {'mode': 'freeze', 'at': 4}):
            with self.assertRaises(CommandError):
                self.call('clip.speed', id=self.clip['id'], **params)

    def test_bulk_motion_is_one_undo_step(self):
        other = self.call('clip.add', file_id=self.file['id'], layer=self.layer, position=8, start=0, end=4)
        before = copy.deepcopy(self.app.project._data['clips'])
        self.service.execute('edit.bulk', {'selection': {'all': True},
                                           'commands': [{'method': 'clip.motion', 'params': {'preset': 'cam-push-in'}}]})
        self.assertEqual([x for x, _ in self.points('scale_x', other['id'])], [1, 121])
        self.assertAlmostEqual(self.points('scale_x', other['id'])[1][1], 1.2, places=5)
        self.service.execute('history.undo', {})
        self.assertEqual(self.app.project._data['clips'], before)

    def test_locked_track_and_invalid_preset_are_rejected(self):
        with self.assertRaises(CommandError):
            self.call('clip.motion', id=self.clip['id'], preset='moonwalk')
        self.app.project._data['layers'][0]['lock'] = True
        with self.assertRaises(CommandError) as error:
            self.call('clip.motion', id=self.clip['id'], preset='flash')
        self.assertEqual(error.exception.code, 'locked_track')

    def test_waveform_show_hide_and_redraw_after_speed(self):
        path = str(Path(self.temp.name) / 'tone.wav')
        with wave.open(path, 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b''.join(struct.pack('<h', int(15000*math.sin(i*2*math.pi*440/8000))) for i in range(24000)))
        audio = self.call('file.import', path=path)
        clip = self.call('clip.add', file_id=audio['id'], layer=self.layer, start=0, end=3)
        from classes.waveform_cache import samples
        self.call('clip.waveform', id=clip['id'])
        shown = self.data(clip['id'])['ui']
        self.assertGreater(max(samples(shown['audio_data'])), .1)
        self.call('clip.speed', id=clip['id'], mode='forward', factor=2)
        self.assertNotEqual(self.data(clip['id'])['ui']['waveform_token'], shown['waveform_token'])
        self.call('clip.waveform', id=clip['id'], hide=True)
        self.assertEqual(self.data(clip['id'])['ui']['audio_data'], [])
        with self.assertRaises(CommandError):
            self.call('clip.waveform', id=self.clip['id'])
