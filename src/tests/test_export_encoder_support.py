"""Separate missing encoder builds from runtime GPU/driver failures."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from classes.export_settings import encoder_support


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
