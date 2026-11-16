# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression coverage for portable copies, close safety, names and encoder policy."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests import test_agent_cli
from classes.agent.protocol import CommandError


class WorkflowTests(unittest.TestCase):
    setUpClass = classmethod(test_agent_cli.EditingTests.setUpClass.__func__)
    setUp = test_agent_cli.EditingTests.setUp
    tearDown = test_agent_cli.EditingTests.tearDown
    call = test_agent_cli.EditingTests.call
    add_clip = test_agent_cli.EditingTests.add_clip

    def test_rename_legacy_clip_and_undo(self):
        clip = self.add_clip()
        from classes.query import Clip
        obj = Clip.get(id=clip['id'])
        obj.data.pop('title', None)
        self.app.project._data['clips'][0].pop('title', None)
        changed = self.call('clip.set', id=clip['id'], values={'title': 'A useful name'})
        self.assertEqual(changed['title'], 'A useful name')
        self.assertEqual(self.call('clip.get', id=clip['id'])['title'], 'A useful name')
        self.call('history.undo')
        self.assertNotEqual(self.call('clip.get', id=clip['id']).get('title'), 'A useful name')
        with self.assertRaises(CommandError):
            self.call('clip.set', id=clip['id'], values={'title': 123})

    def test_text_id_is_usable_in_batch_and_legacy_ref_survives(self):
        result = self.service.execute('edit.apply', {'commands': [
            {'method': 'text.add', 'as': 'label', 'params': {'text': 'Hello', 'layer': self.layer}},
            {'method': 'clip.set', 'params': {'id': {'$ref': 'label.id'}, 'values': {'title': 'Caption'}}},
            {'method': 'clip.set', 'params': {'id': {'$ref': 'label.clip.id'}, 'values': {'position': 2}}}]})
        text = result['data'][0]
        self.assertEqual(text['id'], text['clip']['id'])
        self.assertEqual(result['refs']['label']['id'], result['refs']['label']['clip']['id'])
        self.assertEqual(self.call('clip.get', id=text['id'])['position'], 2)

    def test_collect_preserves_live_project_and_colliding_filenames(self):
        self.add_clip()
        other = Path(self.temp.name) / 'other'
        other.mkdir()
        second = other / Path(self.path).name
        second.write_bytes(Path(self.path).read_bytes())
        f = self.call('file.import', path=str(second))
        self.call('clip.add', file_id=f['id'], layer=self.layer, position=3)
        before = copy.deepcopy(self.app.project._data)
        status = self.call('session.status')
        dest = Path(self.temp.name) / 'portable'
        result = self.call('project.collect', directory=str(dest), name='movie.osp')
        self.assertEqual(before, self.app.project._data)
        self.assertEqual(status, self.call('session.status'))
        self.assertEqual(result['copied_assets'], 2)
        saved = json.loads((dest / 'movie.osp').read_text())
        paths = [f['path'] for f in saved['files']]
        self.assertEqual(len(set(paths)), 2)
        self.assertTrue(all((dest / p).is_file() for p in paths))
        self.assertEqual(saved['history'], {'undo': [], 'redo': []})
        # The copy opens after its original sources are removed.
        Path(self.path).unlink()
        second.unlink()
        self.call('project.open', path=result['path'], discard=True)
        self.assertEqual(len(self.call('clip.list')), 2)

    def test_collect_missing_media_is_atomic_and_never_overwrites(self):
        self.add_clip()
        dest = Path(self.temp.name) / 'portable'
        Path(self.path).unlink()
        with self.assertRaises(CommandError) as error:
            self.call('project.collect', directory=str(dest))
        self.assertEqual(error.exception.code, 'missing_media')
        self.assertFalse(dest.exists())
        dest.mkdir()
        with self.assertRaises(CommandError) as error:
            self.call('project.collect', directory=str(dest))
        self.assertEqual(error.exception.code, 'already_exists')
        self.assertTrue(dest.exists())

    def test_close_checks_dirty_busy_and_save_before_scheduling_quit(self):
        self.add_clip()
        with patch('qt_api.QTimer.singleShot') as schedule:
            with self.assertRaises(CommandError) as error:
                self.call('session.close')
            self.assertEqual(error.exception.code, 'unsaved_changes')
            schedule.assert_not_called()
            process = Mock()
            process.poll.return_value = None
            self.service.jobs['busy'] = {'process': process}
            with self.assertRaises(CommandError) as error:
                self.call('session.close', discard=True)
            self.assertEqual(error.exception.code, 'busy')
            schedule.assert_not_called()
            self.service.jobs.clear()
            path = str(Path(self.temp.name) / 'saved.osp')
            self.service.mode = 'gui'
            result = self.call('session.close', save=path)
            self.assertTrue(result['closing'])
            self.assertTrue(Path(path).exists())
            self.assertFalse(self.app.project.has_unsaved_changes)
            schedule.assert_called_once()

    def test_gpu_selection_checks_actual_settings_and_reports_fallback(self):
        from classes.agent.exporting import select_encoder
        def spec(policy='auto'):
            return {'encoder_selection': {'automatic': True, 'policy': policy, 'attempts': []},
                    'config': {'mode': 'video_audio', 'format': 'mp4', 'video_codec': 'libx264'},
                    'video': {'vcodec': 'libx264'}, 'validation': {}}
        attempts = []
        def check(candidate):
            codec = candidate['config']['video_codec']
            attempts.append(codec)
            if codec == 'h264_vulkan':
                raise CommandError('incompatible_export', 'Device cannot open this profile')
            return {'validation': {'runtime_checked': True}}
        with patch.dict(os.environ, OPENSHOT_RENDER_BACKEND='vulkan'), patch('openshot.FFmpegWriter.IsValidCodec', return_value=True):
            s = spec()
            select_encoder(s, check)
            self.assertEqual(s['config']['video_codec'], 'h264_nvenc')
            self.assertEqual(attempts, ['h264_vulkan', 'h264_nvenc'])
            self.assertFalse(s['encoder_selection']['attempts'][0]['ok'])
            failed = Mock(side_effect=CommandError('incompatible_export', 'Unavailable'))
            s = spec()
            select_encoder(s, failed)
            self.assertEqual(s['encoder_selection']['selected'], 'libx264')
            with self.assertRaises(CommandError) as error:
                select_encoder(spec('gpu'), failed)
            self.assertEqual(error.exception.code, 'gpu_unavailable')
            s = spec('software')
            never = Mock()
            select_encoder(s, never)
            never.assert_not_called()
            s = spec()
            s['encoder_selection']['automatic'] = False
            select_encoder(s, never)
            never.assert_not_called()

    def test_collect_image_sequence_and_effect_resources(self):
        self.add_clip()
        sequence = Path(self.temp.name) / 'sequence'
        sequence.mkdir()
        for number in (1, 2):
            (sequence / ('frame-%04d.png' % number)).write_bytes(Path(self.path).read_bytes())
        lut = Path(self.temp.name) / 'look.cube'
        lut.write_text('LUT_3D_SIZE 2\n')
        # Collection traverses nested reader and effect paths, not only Project Files.
        self.app.project._data['clips'][0]['effects'] = [
            {'mask_reader': {'path': str(sequence / 'frame-%04d.png')}, 'lut_path': str(lut)}]
        dest = Path(self.temp.name) / 'portable'
        self.call('project.collect', directory=str(dest))
        data = json.loads((dest / 'project.osp').read_text())
        effect = data['clips'][0]['effects'][0]
        for number in (1, 2):
            self.assertTrue((dest / (effect['mask_reader']['path'] % number)).is_file())
        self.assertEqual((dest / effect['lut_path']).read_text(), lut.read_text())

    def test_close_rejects_conflicting_flags_and_failed_save(self):
        with patch('qt_api.QTimer.singleShot') as schedule:
            with self.assertRaises(CommandError):
                self.call('session.close', save=str(Path(self.temp.name) / 'x.osp'), discard=True)
            with self.assertRaises(CommandError):
                self.call('session.close', overwrite=True)
            with patch.object(self.app.project, 'save', side_effect=OSError('Disk full')):
                with self.assertRaises(CommandError) as error:
                    self.call('session.close', save=str(Path(self.temp.name) / 'x.osp'))
            self.assertIn('Disk full', str(error.exception))
            schedule.assert_not_called()

    def test_auto_probes_default_backend_but_respects_explicit_cpu(self):
        from classes.agent.exporting import select_encoder
        def spec():
            return {'encoder_selection': {'automatic': True, 'policy': 'auto', 'attempts': []},
                    'config': {'mode': 'video_audio', 'format': 'mp4', 'video_codec': 'libx264'},
                    'video': {'vcodec': 'libx264'}, 'validation': {}}
        with patch.dict(os.environ, {}, clear=True), patch('openshot.FFmpegWriter.IsValidCodec', return_value=True):
            check = Mock(return_value={'validation': {'runtime_checked': True}})
            s = spec()
            select_encoder(s, check)
            self.assertEqual(s['config']['video_codec'], 'h264_vulkan')
            check.assert_called_once()
        with patch.dict(os.environ, OPENSHOT_RENDER_BACKEND='cpu'):
            check = Mock()
            select_encoder(spec(), check)
            check.assert_not_called()

    def test_legacy_title_batch_undo(self):
        clip = self.add_clip()
        self.app.project._data['clips'][0].pop('title', None)
        self.app.updates.data_version += 1  # Invalidate detached Query cache.
        self.call('edit.apply', commands=[{'method': 'clip.set', 'params': {
            'id': clip['id'], 'values': {'title': 'Legacy renamed'}}}])
        self.assertEqual(self.call('clip.get', id=clip['id'])['title'], 'Legacy renamed')
        self.call('history.undo')
        self.assertFalse(self.call('clip.get', id=clip['id']).get('title'))
