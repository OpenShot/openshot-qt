"""GPU controls must preserve current-session evidence and apply only on restart."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import sys

SOURCE_ROOT = str(Path(__file__).resolve().parents[1])
if SOURCE_ROOT not in sys.path:
    sys.path.insert(0, SOURCE_ROOT)

from qt_api import QApplication
from classes.gpu_settings import apply_gpu_preferences
from classes.gpu_diagnostics import GpuDiagnostics
from windows.views.gpu_performance import GpuStatusBadge


def report():
    device = SimpleNamespace(name='Example GPU', vendor='NVIDIA', type='discrete',
                             driver='test', uuid='test', vulkan_api='1.3',
                             video_decode=True, video_encode=False)
    native = SimpleNamespace(ListGpuDevices=lambda: [device], ActiveGpuDevice=lambda: device,
                             GpuEncoders=lambda: [], VulkanOpenGLPresenter=Mock())
    result = GpuDiagnostics(native, Mock(), {})
    result.probe()
    return result


class GpuPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_restart_settings_and_external_override_precedence(self):
        settings = SimpleNamespace(get={'gpu-mode': 'cpu', 'gpu-device': 'Example GPU'}.get)
        environment = {}
        apply_gpu_preferences(settings, environment)
        self.assertEqual(environment['OPENSHOT_RENDER_BACKEND'], 'cpu')
        self.assertEqual(environment['OPENSHOT_VULKAN_DEVICE'], 'Example GPU')
        environment = {'OPENSHOT_RENDER_BACKEND': 'vulkan', 'OPENSHOT_VULKAN_DEVICE': 'Other GPU'}
        apply_gpu_preferences(settings, environment)
        self.assertEqual(environment['OPENSHOT_RENDER_BACKEND'], 'vulkan')
        self.assertEqual(environment['OPENSHOT_VULKAN_DEVICE'], 'Other GPU')
        environment = {}
        apply_gpu_preferences(SimpleNamespace(get=lambda key: None), environment)
        self.assertEqual(environment, {'OPENSHOT_RENDER_BACKEND': 'vulkan'})

    def test_startup_synchronizes_resolved_preferences_with_native_runtime(self):
        native = SimpleNamespace(ConfigureGpuEnvironment=Mock())
        settings = SimpleNamespace(get={'gpu-mode': 'cpu', 'gpu-device': 'Saved GPU'}.get)
        environment = {'OPENSHOT_VULKAN_DEVICE': 'Launch override'}
        apply_gpu_preferences(settings, environment, native)
        native.ConfigureGpuEnvironment.assert_called_once_with('cpu', 'Launch override')

    def test_green_requires_timeline_presentation_and_keeps_fallback_visible(self):
        diagnostics = report()
        self.assertEqual(diagnostics.user_status()['mode'], 'cpu')
        self.assertIn('not yet used', diagnostics.user_status()['title'])
        thumbnail = diagnostics.register_preview('thumbnail', True, 'available')
        diagnostics.observe_preview(thumbnail, True)
        self.assertEqual(diagnostics.user_status()['mode'], 'cpu')
        timeline = diagnostics.register_preview('timeline', True, 'available')
        diagnostics.observe_preview(timeline, False, 'CPU-backed frame')
        self.assertIn('fallback', diagnostics.user_status()['title'])
        diagnostics.observe_preview(timeline, True)
        state = diagnostics.user_status()
        self.assertEqual(state['mode'], 'gpu')
        self.assertIn('fallback', state['title'])
        diagnostics.environ['OPENSHOT_RENDER_BACKEND'] = 'cpu'
        self.assertEqual(diagnostics.user_status()['mode'], 'cpu')

    def test_detected_device_without_initialization_is_not_reported_ready(self):
        diagnostics = report()
        diagnostics.selected = ''
        state = diagnostics.user_status()
        self.assertFalse(state['ready'])
        self.assertEqual(state['mode'], 'cpu')
        self.assertIn('initialization unavailable', state['title'])

    def test_about_badge_reuses_export_artwork_and_dimensions(self):
        badge = GpuStatusBadge()
        self.assertEqual((badge.width(), badge.height()), (64, 22))
        self.assertTrue(badge.renderers['cpu'].isValid())
        self.assertTrue(badge.renderers['gpu'].isValid())
        badge.set_mode('gpu')
        self.assertEqual(badge.accessibleName(), 'GPU')
        badge.close()
