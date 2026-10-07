"""Native timeline waveform inspection stays bounded and never edits the project."""
import copy
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave


class SnapshotWaveformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from classes.agent.service import EditingService
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        self.service = EditingService(self.app, 'waveform-test', 'headless')
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'tone.wav')
        with wave.open(self.path, 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b''.join(struct.pack('<h', int(15000*math.sin(i*2*math.pi*440/8000))) for i in range(24000)))
        self.file = self.call('file.import', path=self.path)
        self.clip = self.call('clip.add', file_id=self.file['id'], start=1, end=2,
                              layer=self.app.project.get('layers')[0]['number'])

    def tearDown(self):
        self.temp.cleanup()

    def call(self, method, **params):
        return self.service.execute(method, params)['data']

    def test_waveform_snapshot_private_cache_and_trim(self):
        from windows.views.timeline_backend.qwidget.snapshot import render_timeline_snapshot, snapshot_clips
        before = copy.deepcopy(self.app.project._data)
        revision = self.app.updates.data_version
        result = render_timeline_snapshot(str(Path(self.temp.name)/'wave.png'), start=.25, end=.75,
                                          width=640, mode='waveforms')
        self.assertEqual(result['waveforms']['generated_sources'], 1)
        self.assertEqual(result['generated_thumbnails'], 0)
        self.assertEqual(result['image_bytes'], Path(result['path']).stat().st_size)
        self.assertEqual(result['items'][0]['source_start'], 1)
        self.assertEqual(result['items'][0]['timeline_end'], 1)
        clips, metrics = snapshot_clips('waveforms', 0, 1, 30)
        self.assertEqual(metrics['cache_hits'], 1)
        self.assertTrue(any(clips[0].data['ui']['audio_data']))
        self.assertEqual(self.app.project._data, before)
        self.assertEqual(self.app.updates.data_version, revision)

    def test_volume_is_applied_without_contaminating_source_cache(self):
        from windows.views.timeline_backend.qwidget.snapshot import snapshot_clips
        audible, _ = snapshot_clips("waveforms", 0, 1, 30)
        self.assertGreater(max(audible[0].data["ui"]["audio_data"]), .1)
        self.call("clip.set", id=self.clip["id"], values={"volume": 0})
        muted, metrics = snapshot_clips("waveforms", 0, 1, 30)
        self.assertEqual(metrics["cache_hits"], 1)
        self.assertEqual(max(muted[0].data["ui"]["audio_data"]), 0)

    def test_disabled_audio_and_stale_clip_cache(self):
        from windows.views.timeline_backend.qwidget.snapshot import snapshot_clips
        from classes.query import Clip
        clip = Clip.get(id=self.clip['id'])
        clip.data.setdefault('ui', {})['audio_data'] = [.9] * 600
        clip.save()
        self.call('clip.set', id=self.clip['id'], values={'has_audio': 0})
        disabled, _ = snapshot_clips('waveforms', 0, 1, 30)
        self.assertEqual(max(disabled[0].data['ui']['audio_data']), 0)
        self.call('clip.set', id=self.clip['id'], values={'has_audio': -1, 'volume': .25})
        refreshed, _ = snapshot_clips('waveforms', 0, 1, 30)
        self.assertGreater(max(refreshed[0].data['ui']['audio_data']), .01)
        self.assertLess(max(refreshed[0].data['ui']['audio_data']), .2)

    def test_time_mapping_identity_and_reversal_sample_origin(self):
        import json
        import openshot
        from classes.query import File
        from windows.views.timeline_backend.qwidget.snapshot import snapshot_clips
        file = File.get(id=self.file['id'])
        # Synthetic raw source impulses isolate mapping from audio decoding.
        impulse = [0.0] * 600
        impulse[20] = .75
        file.data['ui'] = {'audio_data': impulse, 'audio_data_rms': impulse,
                           'audio_data_rate': 200, 'audio_data_format': 'absolute_peak_v2'}
        file.save()
        curve = openshot.Keyframe()
        curve.AddPoint(1, 1, openshot.LINEAR)
        curve.AddPoint(91, 91, openshot.LINEAR)
        self.call('clip.set', id=self.clip['id'], values={'time': json.loads(curve.Json())})
        mapped, _ = snapshot_clips('waveforms', 0, 1, 30)
        self.assertEqual(mapped[0].data['ui']['audio_data'], impulse)
        reverse = openshot.Keyframe()
        reverse.AddPoint(1, 91, openshot.LINEAR)
        reverse.AddPoint(91, 1, openshot.LINEAR)
        self.call('clip.set', id=self.clip['id'], values={'time': json.loads(reverse.Json())})
        mapped, _ = snapshot_clips('waveforms', 0, 1, 30)
        self.assertEqual(mapped[0].data['ui']['audio_data'][580], .75)

    def test_thumbnails_mode_does_not_remove_project_cache(self):
        from windows.views.timeline_backend.qwidget.snapshot import snapshot_clips
        from classes.query import Clip
        clip = Clip.get(id=self.clip['id'])
        clip.data.setdefault('ui', {})['audio_data'] = [.1, .2]
        clip.save()
        before = copy.deepcopy(self.app.project._data)
        clips, _ = snapshot_clips('thumbnails', 0, 1, 30)
        self.assertNotIn('audio_data', clips[0].data['ui'])
        self.assertEqual(self.app.project._data, before)

    def test_long_source_rejected_before_decode(self):
        from windows.views.timeline_backend.qwidget.snapshot import snapshot_clips
        from classes.query import File
        file = File.get(id=self.file['id'])
        file.data['duration'] = 601
        file.save()
        with self.assertRaisesRegex(ValueError, 'whole source'):
            snapshot_clips('waveforms', 0, 1, 30)
