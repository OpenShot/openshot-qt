# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Separate missing encoder builds from runtime GPU/driver failures."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from classes.export_settings import encoder_support, preferred_export_codec


def native(compiled, available=()):
    return SimpleNamespace(FFmpegWriter=SimpleNamespace(IsValidCodec=Mock(return_value=compiled)),
                           GpuEncoders=Mock(return_value=list(available)))


class ExportEncoderSupportTests(unittest.TestCase):
    def test_missing_nvenc_is_a_build_issue_and_does_not_probe_driver(self):
        api = native(False)
        backend, supported, reason = encoder_support("h264_nvenc", api, {})
        self.assertEqual(backend, "nvenc")
        self.assertFalse(supported)
        self.assertIn("not included in this FFmpeg build", reason)
        api.GpuEncoders.assert_not_called()

    def test_legacy_nvenc_visibility_still_depends_on_compiled_support(self):
        api = native(True)
        _, supported, reason = encoder_support("h264_nvenc", api, {})
        self.assertTrue(supported)
        self.assertIn("checked when export starts", reason)
        api.GpuEncoders.assert_not_called()

    def test_vulkan_distinguishes_missing_codec_from_failed_runtime_probe(self):
        for compiled, expected in ((False, "not included"), (True, "did not open")):
            with self.subTest(compiled=compiled):
                api = native(compiled)
                _, supported, reason = encoder_support("h264_vulkan", api, {})
                self.assertFalse(supported)
                self.assertIn(expected, reason)
                self.assertEqual(api.GpuEncoders.call_count, int(compiled))

    def test_successful_vulkan_probe_and_failure_are_explicit(self):
        api = native(True, ["h264_vulkan"])
        self.assertTrue(encoder_support("h264_vulkan", api, {})[1])
        api.GpuEncoders.side_effect = RuntimeError("driver unavailable")
        _, supported, reason = encoder_support("h264_vulkan", api, {})
        self.assertFalse(supported)
        self.assertIn("driver unavailable", reason)

    def test_cpu_backend_preserves_legacy_videotoolbox_selection(self):
        api = native(True)
        self.assertTrue(encoder_support("h264_videotoolbox", api, {"OPENSHOT_RENDER_BACKEND": "cpu"})[1])
        api.GpuEncoders.assert_not_called()
        self.assertFalse(encoder_support("h264_videotoolbox", api, {})[1])

    def test_software_encoder_does_not_probe_gpu(self):
        api = native(True)
        backend, supported, reason = encoder_support("libx264", api, {})
        self.assertEqual(backend, "cpu")
        self.assertTrue(supported)
        self.assertIn("CPU", reason)
        api.GpuEncoders.assert_not_called()


class ExportDefaultTests(unittest.TestCase):
    def test_only_working_h264_encoders_are_selected(self):
        candidates = {'libx264', 'h264_nvenc', 'h264_vulkan', 'hevc_vulkan'}
        api = native(True, ['hevc_vulkan', 'h264_nvenc'])
        self.assertEqual(preferred_export_codec(candidates, api, {}), 'h264_nvenc')
        api.GpuEncoders.return_value.append('h264_vulkan')
        self.assertEqual(preferred_export_codec(candidates, api, {}), 'h264_vulkan')
        self.assertEqual(preferred_export_codec({'libx264'}, api, {}), 'libx264')

    def test_cpu_mode_and_failed_probes_use_software(self):
        api = native(True, ['h264_nvenc'])
        candidates = {'libx264', 'h264_nvenc'}
        self.assertEqual(preferred_export_codec(candidates, api, {'OPENSHOT_RENDER_BACKEND': 'cpu'}), 'libx264')
        api.GpuEncoders.assert_not_called()
        api.GpuEncoders.side_effect = RuntimeError('unavailable')
        self.assertEqual(preferred_export_codec(candidates, api, {}), 'libx264')
        self.assertIsNone(preferred_export_codec({'hevc_nvenc'}, api, {}))


class CachedEncoderTests(unittest.TestCase):
    def test_dialog_reads_results_without_entering_the_native_probe(self):
        api = native(True)
        api.GpuEncoders.side_effect = AssertionError('GUI must not probe hardware')
        checking = dict(state='checking', encoders=())
        self.assertTrue(encoder_support('h264_vulkan', api, {}, checking)[1])
        self.assertIn('Checking', encoder_support('h264_vulkan', api, {}, checking)[2])
        self.assertEqual(preferred_export_codec({'libx264', 'h264_vulkan'}, api, {}, checking), 'libx264')
        ready = dict(state='ready', encoders=('h264_vulkan',))
        self.assertTrue(encoder_support('h264_vulkan', api, {}, ready)[1])
        self.assertFalse(encoder_support('h264_nvenc', api, {}, ready)[1])
        self.assertEqual(preferred_export_codec({'libx264', 'h264_vulkan'}, api, {}, ready), 'h264_vulkan')
        api.GpuEncoders.assert_not_called()

    def test_failed_discovery_is_distinct_from_an_encoder_that_failed_to_open(self):
        api = native(True)
        failed = encoder_support('h264_vulkan', api, {}, dict(state='failed', encoders=()))
        empty = encoder_support('h264_vulkan', api, {}, dict(state='ready', encoders=()))
        self.assertFalse(failed[1]); self.assertFalse(empty[1])
        self.assertIn('could not be verified', failed[2])
        self.assertIn('did not open', empty[2])
        api.GpuEncoders.assert_not_called()
