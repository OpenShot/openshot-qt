# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""GPU capability evidence must never be mistaken for observed acceleration."""
from types import SimpleNamespace
import unittest
import threading
import json
import unittest.mock
from unittest.mock import Mock

from classes.gpu_diagnostics import GpuDiagnostics


def native_api():
    device = SimpleNamespace(name="Test GPU", vendor="NVIDIA", type="discrete",
                             driver="test driver", uuid="test-uuid", vulkan_api="1.3.290",
                             video_decode=True, video_encode=True)
    return SimpleNamespace(VulkanOpenGLPresenter=Mock(), ListGpuDevices=Mock(return_value=[device]),
                           ActiveGpuDevice=Mock(return_value=device),
                           GpuEncoders=Mock(return_value=["h264_nvenc"]),
                           VulkanFrameReadbackCount=Mock(return_value=3),
                           VulkanUploadFailureCount=Mock(return_value=0))


class GpuDiagnosticsTests(unittest.TestCase):
    def test_lost_device_removes_vulkan_encoders_without_probing_again(self):
        api = native_api()
        api.GpuEncoders.return_value = ['h264_vulkan', 'hevc_vulkan', 'h264_vaapi']
        api.VulkanDeviceLost = Mock(return_value=False)
        report = GpuDiagnostics(api, Mock(), {})
        report.probe()
        self.assertIn('h264_vulkan', report.encoder_capabilities()['encoders'])
        api.VulkanDeviceLost.return_value = True
        self.assertEqual(report.encoder_capabilities(), dict(state='ready', encoders=('h264_vaapi',)))
        api.GpuEncoders.assert_called_once()

    def test_export_can_read_capabilities_while_driver_probe_is_blocked(self):
        from classes.export_settings import encoder_support, preferred_export_codec, cached_encoder_capabilities
        entered, release = threading.Event(), threading.Event()
        api = native_api()
        api.FFmpegWriter = SimpleNamespace(IsValidCodec=Mock(return_value=True))
        def probe():
            entered.set()
            release.wait(5)
            return ['h264_vulkan']
        api.GpuEncoders.side_effect = probe
        report = GpuDiagnostics(api, Mock(), {})
        report.start_probe()
        try:
            self.assertTrue(entered.wait(2))
            cached = cached_encoder_capabilities(SimpleNamespace(gpu_diagnostics=report))
            self.assertEqual(cached['state'], 'checking')
            self.assertTrue(encoder_support('h264_vulkan', api, {}, cached)[1])
            self.assertEqual(preferred_export_codec({'libx264', 'h264_vulkan'}, api, {}, cached), 'libx264')
            api.GpuEncoders.assert_called_once_with()
        finally:
            release.set()
            report.probe_thread.join(2)
        self.assertEqual(report.encoder_capabilities(), dict(state='ready', encoders=('h264_vulkan',)))

    def test_additional_encoder_probes_use_writer_results_not_compiled_names(self):
        api = native_api()
        writer = Mock()
        writer.Test.side_effect = [json.dumps(dict(ok=True)), json.dumps(dict(ok=False))]
        api.FFmpegWriter = Mock(return_value=writer)
        api.FFmpegWriter.IsValidCodec.side_effect = lambda codec: codec in ('h264_qsv', 'h264_amf')
        api.Fraction = lambda num, den: (num, den)
        report = GpuDiagnostics(api, Mock(), {})
        report.probe()
        self.assertEqual(report.encoder_capabilities()['encoders'], ('h264_nvenc', 'h264_qsv'))
        self.assertEqual(writer.Test.call_count, 2)

    def test_copy_reports_capability_independently_of_preview_activity(self):
        report = GpuDiagnostics(native_api(), Mock(), {})
        report.probe()
        initial = report.copy_lines()
        self.assertEqual(initial[1], "GPU Support: Available")
        key = report.register_preview("timeline", True, "available")
        report.observe_preview(key, True)
        self.assertEqual(report.copy_lines(), initial)
        report.observe_preview(key, False, "Qt/OpenGL and Vulkan selected different GPUs")
        copied = report.copy_lines()
        self.assertEqual(copied, initial)
        self.assertIn("Vulkan: 1.3.290", copied[2])
        self.assertEqual(copied[1], "GPU Support: Available")
        self.assertFalse(any(line.startswith("Fallback reason:") for line in copied))
        self.assertNotIn("native draws", "\n".join(copied))
        self.assertNotIn("h264_nvenc", "\n".join(copied))
        self.assertIn("h264_nvenc", "\n".join(report.report_lines()))

    def test_copy_names_gpu_debug_switches(self):
        report = GpuDiagnostics(native_api(), Mock(), {"OPENSHOT_GPU_DEBUG": "1",
                                                       "OPENSHOT_PRESENTATION_SYNC": "wait"})
        report.probe()
        self.assertEqual(report.copy_lines()[-1],
                         "Debug settings: OPENSHOT_GPU_DEBUG=1, OPENSHOT_PRESENTATION_SYNC=wait")
        quiet = GpuDiagnostics(native_api(), Mock(), {})
        quiet.probe()
        self.assertNotIn("Debug settings", "\n".join(quiet.copy_lines()))

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

    def test_cpu_backed_frames_while_warming_up_are_not_reported(self):
        logger = Mock()
        native = native_api()
        report = GpuDiagnostics(native, logger, {})
        report.probe()
        key = report.register_preview("timeline", True, "available")
        calls = logger.info.call_count
        for _ in range(10):
            report.observe_preview(key, False, "Frame is CPU-backed (decode, rendering, or an effect required CPU pixels)")
        preview = report.snapshot()["previews"][0]
        self.assertEqual(preview["cpu_draws"], 10)
        self.assertEqual(preview["fallback_reasons"], [])
        self.assertEqual(logger.info.call_count, calls)
        self.assertEqual(report.copy_lines()[1],
                         "GPU Support: Available")
        self.assertFalse(any(line.startswith("Fallback reason:") for line in report.copy_lines()))
        # After the warm-up the same reason is a real fallback.
        report.observe_preview(key, False, "Frame is CPU-backed (decode, rendering, or an effect required CPU pixels)")
        self.assertEqual(len(report.snapshot()["previews"][0]["fallback_reasons"]), 1)
        self.assertEqual(logger.info.call_count, calls + 1)
        # Other reasons are reported immediately.
        other = report.register_preview("source", True, "available")
        report.observe_preview(other, False, "Submit presentation transfer: VK_ERROR_DEVICE_LOST")
        self.assertEqual(logger.info.call_count, calls + 3)

    def test_upload_failures_are_reported(self):
        native = native_api()
        native.VulkanUploadFailureCount.return_value = 7
        report = GpuDiagnostics(native, Mock(), {})
        report.probe()
        self.assertEqual(report.snapshot()["upload_failures"], 7)
        self.assertIn("GPU image upload failures (session): 7", "\n".join(report.report_lines()))

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
        self.assertIn("GPU Support: CPU mode explicitly selected", report.copy_lines())
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
        self.assertIn("GPU Support: Unavailable", report.copy_lines())
        self.assertIn("GPU initialization: ActiveGpuDevice: vkCreateDevice failed", report.copy_lines())
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


class GpuDeviceLostTests(unittest.TestCase):
    def test_device_loss_clears_gpu_frames_once_and_keeps_editing(self):
        from qt_api import QApplication
        from tests.qt_test_app import get_or_create_app, ensure_app_state
        app, _ = get_or_create_app(lambda: QApplication([]))
        ensure_app_state(app, dict)
        from windows import main_window
        window = SimpleNamespace(timeline_sync=SimpleNamespace(timeline=Mock()), refreshFrameSignal=Mock(),
                                 statusBar=Mock())
        diagnostics = Mock()
        fake_app = SimpleNamespace(_tr=lambda text: text, gpu_diagnostics=diagnostics)
        with unittest.mock.patch.object(main_window, "get_app", return_value=fake_app):
            main_window.MainWindow.gpu_device_lost(window)
            main_window.MainWindow.gpu_device_lost(window)
        window.timeline_sync.timeline.ClearAllCache.assert_called_once_with(True)
        window.refreshFrameSignal.emit.assert_called_once_with()
        window.statusBar.showMessage.assert_called_once()
        self.assertIn("CPU", window.statusBar.showMessage.call_args[0][0])
        diagnostics.event.assert_called_once()
