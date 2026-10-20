"""
 @file
 @brief Profile persistence, grouped history, text inspection and export resolution.

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
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classes.agent.protocol import CommandError


class ProfileExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        isolate_preferences(self)
        from classes.agent.service import EditingService
        from qt_api import QImage, QColor
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        self.service = EditingService(self.app, 'profile-test', 'headless')
        self.temp = tempfile.TemporaryDirectory()
        image = QImage(80, 40, QImage.Format_ARGB32)
        image.fill(QColor('red'))
        self.path = str(Path(self.temp.name)/'source.png')
        image.save(self.path)
        self.file = self.call('file.import', path=self.path)
        self.layer = self.app.project.get('layers')[0]['number']

    def tearDown(self):
        self.temp.cleanup()

    def call(self, method, **params):
        return self.service.execute(method, params)['data']

    def clip(self):
        return self.call('clip.add', file_id=self.file['id'], layer=self.layer, position=.013, start=.012, end=2.117)

    def test_preset_discovery_skips_unsafe_xml_and_keeps_standard_doctype(self):
        from classes.agent import exporting
        builtin = Path(self.temp.name) / 'builtin'
        user = Path(self.temp.name) / 'user'
        builtin.mkdir()
        user.mkdir()
        (builtin / 'valid.xml').write_text(
            '<!DOCTYPE openshot-export-option>'
            '<openshot-export-option><title>Valid preset</title></openshot-export-option>')
        (user / 'entity.xml').write_text(
            '<!DOCTYPE openshot-export-option [<!ENTITY title "Expanded entity">]>'
            '<openshot-export-option><title>&title;</title></openshot-export-option>')
        (user / 'broken.xml').write_text('<not-valid')
        with patch.object(exporting.info, 'EXPORT_PRESETS_PATH', str(builtin)), \
             patch.object(exporting.info, 'USER_PRESETS_PATH', str(user)):
            rows = exporting.presets()
        self.assertEqual([(row['id'], row['title']) for row in rows],
                         [('builtin:valid', 'Valid preset')])

    def test_profile_retimes_populated_project_and_undo_is_exact(self):
        clip = self.clip()
        self.call('clip.keyframe.set', id=clip['id'], property='volume', frame=17, value=.4)
        before = copy.deepcopy(self.app.project._data)
        result = self.call('project.profile.set', id='builtin:01280x0720p0024_16-09')
        self.assertEqual(result['fps']['num'], 24)
        changed = copy.deepcopy(self.app.project._data)
        self.assertNotEqual(changed['clips'], before['clips'])
        self.call('history.undo')
        for key in ('clips', 'effects', 'files', 'markers', 'profile', 'profile_settings', 'fps'):
            self.assertEqual(self.app.project._data[key], before[key], key)
        self.call('history.redo')
        for key in ('clips', 'effects', 'files', 'markers', 'profile', 'profile_settings', 'fps'):
            self.assertEqual(self.app.project._data[key], changed[key], key)

    def test_custom_profile_reopens_portably(self):
        self.clip()
        profile = self.call('project.profile.set', values={
            'description': 'Portable odd size', 'width': 1234, 'height': 678,
            'fps': {'num': 24000, 'den': 1001}, 'display_ratio': {'num': 617, 'den': 339},
            'progressive': False, 'spherical': True})
        path = str(Path(self.temp.name)/'custom.osp')
        self.call('project.save', path=path)
        self.call('project.open', path=path)
        reopened = self.call('project.profile.get')
        self.assertEqual(profile, reopened)
        self.call('history.undo')
        self.assertEqual(self.call('project.profile.get')['fps']['num'], 30)

    def test_history_soft_limit_keeps_large_transaction_after_reopen(self):
        clip = self.clip()
        before = self.call('clip.get', id=clip['id'])
        self.call('edit.apply', commands=[{'method': 'clip.set', 'params': {'id': clip['id'], 'values': {'position': i/30}}} for i in range(130)])
        settings = self.app.get_settings()
        original_get = settings.get
        with patch.object(settings, 'get', side_effect=lambda key: 1 if key == 'history-limit' else original_get(key)):
            path = str(Path(self.temp.name)/'history.osp')
            self.call('project.save', path=path)
        self.assertEqual(len(self.app.project.get('history')['undo']), 130)
        self.call('project.open', path=path)
        self.call('history.undo')
        self.assertEqual({key: self.call('clip.get', id=clip['id'])[key] for key in before}, before)
        self.call('history.redo')
        self.assertAlmostEqual(self.call('clip.get', id=clip['id'])['position'], 129/30)
        self.app.updates.save_history(self.app.project, 0)
        self.assertEqual(self.app.project.get('history'), {'undo': [], 'redo': []})

    def test_profile_match_and_no_silent_nearest(self):
        from classes.query import File
        file = File.get(id=self.file['id'])
        file.data.update(media_type='video', has_video=True, has_single_image=False, width=1280, height=720,
                         fps={'num': 24, 'den': 1}, pixel_ratio={'num': 1, 'den': 1})
        file.save()
        result = self.call('profile.match', file_id=file.id)
        self.assertIn('builtin:01280x0720p0024_16-09', result['exact_ids'])
        self.call('project.profile.set', from_file=file.id)
        file.data.update(width=1234); file.save()
        with self.assertRaises(CommandError) as error:
            self.call('project.profile.set', from_file=file.id)
        self.assertEqual(error.exception.code, 'no_exact_profile')
        self.call('project.profile.set', from_file=file.id, create_custom=True)
        self.assertEqual(self.call('project.profile.get')['width'], 1234)

    def test_export_catalogue_routes_through_session(self):
        rows = self.call('export.preset.list', search='h.264')
        self.assertTrue(rows)
        row = self.call('export.preset.get', id=rows[0]['id'])
        self.assertEqual(row['id'], rows[0]['id'])
        self.assertIn('config_fields', self.call('export.capabilities'))

    def test_export_resolution_changes_only_snapshot_and_validates_options(self):
        self.clip()
        from classes.agent.exporting import resolve
        before = copy.deepcopy(self.app.project._data)
        output = str(Path(self.temp.name)/'out.mp4')
        spec = resolve(self.service, {'output': output, 'preset': 'builtin:format_mp4_x264',
                                     'profile': 'builtin:01280x0720p0024_16-09', 'quality': 'med',
                                     'config': {'video_options': {'preset': 'fast'}}})
        self.assertEqual(spec['profile']['fps']['num'], 24)
        self.assertEqual(spec['config']['quality_mode'], 'crf')
        self.assertEqual(spec['config']['video_bitrate'], 23)
        self.assertEqual(self.app.project._data, before)
        for config in ({'video_codex': 'typo'}, {'channels': '2'}, {'hardware': {'nonsense': 1}}, {'video_codec': 'missing_encoder'}):
            with self.assertRaises(CommandError):
                resolve(self.service, {'output': output, 'config': config})
        self.assertFalse(Path(output).exists())

    def test_export_validate_opens_the_engine_without_writing(self):
        self.clip()
        output = Path(self.temp.name)/'out.mp4'
        result = self.call('export.validate', output=str(output), profile='builtin:00640x0360p0030_16-09')
        self.assertTrue(result['validation']['runtime_checked'])
        self.assertFalse(output.exists())

        output = Path(self.temp.name)/'song.mp3'
        with self.assertRaises(CommandError) as error:
            self.call('export.validate', output=str(output), profile='builtin:00640x0360p0030_16-09',
                      config={'mode': 'audio', 'format': 'mp3', 'audio_codec': 'aac'})
        self.assertEqual(error.exception.code, 'incompatible_export')
        self.assertEqual(error.exception.details['cause']['path'], 'params.config.audio_codec')
        self.assertIn('MP3', str(error.exception))
        self.assertFalse(output.exists())

        result = self.call('export.validate', output=str(output), profile='builtin:00640x0360p0030_16-09',
                           config={'mode': 'audio', 'format': 'mp3', 'audio_codec': 'libmp3lame'})
        self.assertTrue(result['validation']['runtime_checked'])

    def test_text_view_and_operation_recovery(self):
        clip = self.clip()
        text = self.call('timeline.view')['text']
        self.assertIn(clip['id'], text)
        self.assertIn('source', text)
        overview = self.call('timeline.view', format='json', detail='clips')
        self.assertEqual(overview['items'][0]['id'], clip['id'])
        result = self.service.execute('clip.set', {'id': clip['id'], 'values': {'volume': .5}}, operation_id='known-operation')
        self.assertEqual(result['operation_id'], 'known-operation')
        self.assertEqual(self.call('operation.get', id='known-operation')['result'], result)
        with self.assertRaises(CommandError) as error:
            self.call('clip.set', id=clip['id'], values={'volum': 1})
        operation = self.call('operation.get', id=error.exception.details['operation_id'])
        self.assertEqual(operation['state'], 'failed')
        self.assertIn('volume', operation['error']['message'])
