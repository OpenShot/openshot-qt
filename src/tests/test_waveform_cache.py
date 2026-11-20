# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.


"""Waveform storage remains compact, portable, and independent of project JSON."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classes import waveform_cache as cache


class WaveformCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'runtime'
        self.mock = patch.object(cache, 'cache_directory', lambda: str(self.directory))
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.clear_memory()
        self.addCleanup(self.clear_memory)

    def clear_memory(self):
        cache._buffers.clear()
        cache._buffer_bytes = 0

    def test_preparation_preserves_channel_and_partial_history_waveforms(self):
        reference = cache.store_samples([.75] * 3)
        data = {
            'files': [{'ui': {'audio_data_channels': [
                {'audio_data': [.25] * 4, 'audio_data_rms': [.125] * 4}]}}],
            'history': {
                'undo': [{'key': ['clips', {'id': 'C1'}, 'ui', 'audio_data'], 'value': reference}],
                'redo': [{'old_values': {'ui': {'audio_data': [.5] * 2}}}]}}
        assets = self.root / 'project_assets' / 'waveforms'
        self.assertIs(cache.prepare(data, str(assets)), data)
        self.assertEqual(len(list(assets.glob('*.wfc'))), 4)
        self.directory = self.root / 'different-user'
        self.clear_memory()
        cache.prepare(data, str(assets), importing=True)
        channel = data['files'][0]['ui']['audio_data_channels'][0]
        self.assertEqual(list(cache.samples(channel['audio_data'])), [.25] * 4)
        self.assertEqual(list(cache.samples(channel['audio_data_rms'])), [.125] * 4)
        self.assertEqual(list(cache.samples(data['history']['undo'][0]['value'])), [.75] * 3)
        redo = data['history']['redo'][0]['old_values']['ui']['audio_data']
        self.assertEqual(list(cache.samples(redo)), [.5] * 2)

    def test_waveform_operations_do_not_visit_keyframe_points(self):
        class Points(list):
            def __iter__(self):
                raise AssertionError('Keyframe points must not be scanned for waveforms')
        data = {'clips': [{'alpha': {'Points': Points([{'co': {'X': 1, 'Y': 0}}])},
                           'ui': {'audio_data': [.25] * 4}}]}
        assets = str(self.root / 'assets')
        cache.externalize(data)
        cache.transfer(data, assets)
        cache.prepare(data, assets)
        self.assertEqual(len(list(Path(assets).glob('*.wfc'))), 1)

    def test_float32_roundtrip_dedup_and_immutable_shared_buffer(self):
        values = [-1.0, 0.0, .000001, .23, 1.0, 4.5]
        ref = cache.store_samples(values)
        self.assertEqual(ref, cache.store_samples(values))
        self.assertEqual(len(list(self.directory.iterdir())), 1)
        self.clear_memory()
        actual = cache.samples(ref)
        for a, b in zip(actual, values):
            self.assertAlmostEqual(a, b)
        self.assertIs(actual, cache.samples(copy.deepcopy(ref)))
        with self.assertRaises(TypeError):
            actual[0] = 2.0

    def test_legacy_history_migration_and_portable_save_as(self):
        original = {'ui': {'audio_data': [.25] * 1000, 'audio_data_rms': [.125] * 1000,
                           'audio_data_rate': 200, 'audio_data_format': 'absolute_peak_v2'}}
        data = {'clips': [copy.deepcopy(original)], 'history': {'undo': [original]}}
        cache.externalize(data)
        self.assertLess(len(json.dumps(data)), 1000)
        ref = data['clips'][0]['ui']['audio_data']
        self.assertEqual(ref, data['history']['undo'][0]['ui']['audio_data'])
        sidecars = self.root / 'project_assets' / 'waveforms'
        cache.transfer(data, str(sidecars))
        # A different machine has only the project JSON and its assets.
        self.directory = self.root / 'other-machine'
        self.clear_memory()
        self.assertEqual(len(cache.samples(ref)), 0)
        cache.transfer(json.loads(json.dumps(data)), str(sidecars), importing=True)
        self.assertEqual(list(cache.samples(ref)), [.25] * 1000)
        save_as = self.root / 'save-as_assets' / 'waveforms'
        cache.transfer(data, str(save_as))
        self.assertEqual(sorted(p.name for p in sidecars.iterdir()),
                         sorted(p.name for p in save_as.iterdir()))

    def test_missing_corrupt_and_invalid_references(self):
        ref = cache.store_samples([.5, .75])
        path = self.directory / (ref['waveform_cache'] + '.wfc')
        path.write_bytes(b'corrupt')
        self.clear_memory()
        self.assertEqual(len(cache.samples(ref)), 0)
        cache.store_samples([.5, .75])  # Regeneration repairs the bad cache.
        self.clear_memory()
        self.assertEqual(list(cache.samples(ref)), [.5, .75])
        path.unlink()
        self.clear_memory()
        self.assertEqual(len(cache.samples(ref)), 0)
        self.assertFalse(cache.is_reference({'waveform_cache': '../outside', 'count': 1}))
        self.assertFalse(cache.is_reference(dict(ref, count=-1)))
        self.assertEqual(len(cache.samples(dict(ref, count=100_000_001))), 0)

    def test_memory_eviction_preserves_disk_and_history(self):
        with patch.object(cache, '_MAX_MEMORY', 16):
            first = cache.store_samples([.25] * 4)
            cache.store_samples([.5] * 4)
            self.assertNotIn(first['waveform_cache'], cache._buffers)
            self.assertEqual(list(cache.samples(first)), [.25] * 4)
            self.assertLessEqual(cache._buffer_bytes, 16)

    def test_oversized_envelope_does_not_bypass_memory_budget(self):
        with patch.object(cache, '_MAX_MEMORY', 16):
            small = cache.store_samples([.25] * 4)
            large = cache.store_samples([.5] * 8)
            self.assertNotIn(large['waveform_cache'], cache._buffers)
            self.assertIn(small['waveform_cache'], cache._buffers)
            self.assertEqual(list(cache.samples(large)), [.5] * 8)
            self.assertLessEqual(cache._buffer_bytes, 16)

    def test_hidden_and_pending_waveforms_remain_distinct(self):
        data = {'clips': [{'ui': {'audio_data': []}}, {'ui': {'audio_data': None}}]}
        before = copy.deepcopy(data)
        cache.externalize(data)
        self.assertEqual(data, before)
        self.assertEqual(cache.sample_count(None), 0)
        self.assertEqual(cache.sample_count(cache.store_samples([1, 2, 3])), 3)

    def test_project_json_write_and_reopen_with_undo_sidecars(self):
        from classes.project_data import ProjectDataStore
        from classes.json_data import JsonDataStore
        project = ProjectDataStore.__new__(ProjectDataStore)
        JsonDataStore.__init__(project)
        data = {'clips': [{'ui': {'audio_data': [.5] * 100}}],
                'history': {'undo': [{'value': {'ui': {'audio_data_rms': [.25] * 100}}}]}}
        path = str(self.root / 'example.osp')
        project.write_to_file(path, data)
        saved = json.loads(Path(path).read_text())
        self.assertNotIn('\n', Path(path).read_text())
        self.assertTrue(cache.is_reference(saved['clips'][0]['ui']['audio_data']))
        self.assertEqual(len(list((self.root / 'example_assets' / 'waveforms').iterdir())), 2)
        self.directory = self.root / 'new-user-cache'
        self.clear_memory()
        reopened = project.read_from_file(path)
        self.assertEqual(list(cache.samples(reopened['clips'][0]['ui']['audio_data'])), [.5] * 100)
        restored = reopened['history']['undo'][0]['value']['ui']['audio_data_rms']
        self.assertEqual(list(cache.samples(restored)), [.25] * 100)

    def test_missing_visible_cache_requests_one_background_rebuild(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from windows.views.timeline_backend.paint.clip import ClipPainter
        ref = cache.store_samples([.5, .75])
        self.clear_memory()
        (self.directory / (ref['waveform_cache'] + '.wfc')).unlink()
        window = SimpleNamespace(Show_Waveform_Triggered=Mock())
        painter = SimpleNamespace(w=window)
        clip = SimpleNamespace(id='clip-1', data={'ui': {'audio_data': ref}})
        with patch('windows.views.timeline_backend.paint.clip.QTimer.singleShot') as timer:
            for _ in range(2):
                self.assertFalse(ClipPainter._draw_waveform(painter, None, clip, None))
            timer.assert_called_once()
            timer.call_args[0][1]()
        window.Show_Waveform_Triggered.assert_called_once_with(['clip-1'])
