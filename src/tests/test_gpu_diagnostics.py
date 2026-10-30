"""GPU capability evidence must never be mistaken for observed acceleration."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from classes.gpu_diagnostics import GpuDiagnostics


def native_api():
    device = SimpleNamespace(name="Test GPU", vendor="NVIDIA", type="discrete",
                             driver="test driver", uuid="test-uuid", vulkan_api="1.3.290",
                             video_decode=True, video_encode=True)
    return SimpleNamespace(VulkanOpenGLPresenter=Mock(), ListGpuDevices=Mock(return_value=[device]),
                           ActiveGpuDevice=Mock(return_value=device),
                           GpuEncoders=Mock(return_value=["h264_nvenc"]),
                           VulkanFrameReadbackCount=Mock(return_value=3))


class GpuDiagnosticsTests(unittest.TestCase):
    def test_copy_is_short_and_keeps_fallback_without_verbose_evidence(self):
        report = GpuDiagnostics(native_api(), Mock(), {})
        report.probe()
        key = report.register_preview("timeline", True, "available")
        report.observe_preview(key, True)
        self.assertEqual(len(report.copy_lines()), 3)
        report.observe_preview(key, False, "Qt/OpenGL and Vulkan selected different GPUs")
        copied = report.copy_lines()
        self.assertEqual(len(copied), 4)
        self.assertIn("Vulkan: 1.3.290", copied[3])
        self.assertEqual(copied[1], "Preview: GPU acceleration worked, but CPU fallback also occurred")
        self.assertEqual(copied[2], "Fallback reason: Display and video processing selected different GPUs")
        self.assertIn("different GPUs", copied[2])
        self.assertNotIn("native draws", "\n".join(copied))
        self.assertNotIn("h264_nvenc", "\n".join(copied))
        self.assertIn("h264_nvenc", "\n".join(report.report_lines()))

    def test_capabilities_do_not_claim_acceleration(self):
        report = GpuDiagnostics(native_api(), Mock(), {})
        report.probe()
        report.register_preview("timeline", True, "presenter available")
        self.assertIn("not yet observed", report.brief())
        self.assertNotIn("active", report.brief())
        text = "\n".join(report.report_lines())
        self.assertIn("h264_nvenc", text)
        self.assertIn("Vulkan API: 1.3.290", text)
        self.assertIn("encode=True", text)
        self.assertIn("do not establish hardware decoding or encoding", text)

    def test_fallback_after_native_rendering_stays_visible_and_logs_are_bounded(self):
        logger = Mock()
        report = GpuDiagnostics(native_api(), logger, {})
        report.probe()
        key = report.register_preview("timeline", True, "available")
        report.observe_preview(key, True)
        self.assertIn("active", report.brief())
        for _ in range(100):
            report.observe_preview(key, False, "Qt/OpenGL and Vulkan selected different GPUs")
        self.assertIn("CPU fallback", report.brief())
        self.assertEqual(report.snapshot()["previews"][0]["cpu_draws"], 100)
        self.assertIn("different GPUs", "\n".join(report.report_lines()))
        # Capabilities, selection, first native draw, first fallback. No frame spam.
        self.assertEqual(logger.info.call_count, 4)
        report.log_summary()
        report.log_summary()
        self.assertEqual(logger.info.call_count, 5)

    def test_cpu_build_does_not_claim_that_no_gpu_exists(self):
        report = GpuDiagnostics(SimpleNamespace(), Mock(), {})
        report.probe()
        self.assertIn("information unavailable", report.brief())
        self.assertIn("API unavailable", report.brief())
        self.assertNotIn("no GPU", report.brief())
        self.assertIn("not checked", "\n".join(report.report_lines()))

    def test_cpu_override_does_not_probe_encoders_or_claim_gpu_is_active(self):
        native = native_api()
        report = GpuDiagnostics(native, Mock(), {"OPENSHOT_RENDER_BACKEND": "cpu"})
        report.probe()
        native.GpuEncoders.assert_not_called()
        self.assertIn("CPU rendering requested", report.brief())
        self.assertIn("not checked", "\n".join(report.report_lines()))

    def test_failed_probe_preserves_device_and_error_without_claiming_acceleration(self):
        native = native_api()
        native.ActiveGpuDevice.side_effect = RuntimeError("vkCreateDevice failed")
        report = GpuDiagnostics(native, Mock(), {})
        report.probe()
        self.assertIn("Test GPU", report.brief())
        self.assertIn("Vulkan unavailable", report.brief())
        self.assertIn("vkCreateDevice failed", "\n".join(report.report_lines()))
        self.assertIn("Hardware encoders that opened: not checked", "\n".join(report.report_lines()))
        native.GpuEncoders.assert_not_called()

    def test_preview_disabled_reason_is_preserved(self):
        report = GpuDiagnostics(native_api(), Mock(), {})
        report.probe()
        report.register_preview("timeline", False, "Qt could not create an OpenGL context")
        self.assertIn("CPU preview selected", report.brief())
        self.assertIn("OpenGL context", "\n".join(report.report_lines()))

    def test_pending_probe_does_not_run_from_about_reads(self):
        native = native_api()
        report = GpuDiagnostics(native, Mock(), {})
        self.assertIn("checking", report.brief())
        report.report_lines()
        native.ListGpuDevices.assert_not_called()
        native.GpuEncoders.assert_not_called()

    def test_older_helper_fields_are_reported_as_unknown(self):
        native = native_api()
        del native.ListGpuDevices.return_value[0].vulkan_api
        del native.ListGpuDevices.return_value[0].video_encode
        report = GpuDiagnostics(native, Mock(), {})
        report.probe()
        text = "\n".join(report.report_lines())
        self.assertIn("Vulkan API: not reported", text)
        self.assertIn("encode=not reported", text)
