"""
 @file
 @brief Unit tests for choosing and feeding the experimental Vulkan preview
 @author Jonathan Thomas <jonathan@openshot.org>

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

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import openshot
from qt_api import QImage

from windows.preview_thread import PreviewParent
from windows.video_widget import gpu_preview_enabled, gpu_preview_status
from windows import video_widget


GPU_OPENSHOT = SimpleNamespace(VulkanOpenGLPresenter=object)
CPU_OPENSHOT = SimpleNamespace()
WIDGETS = SimpleNamespace(QOpenGLWidget=object)


def has_opengl():
    return True


class OpenGLAvailabilityTests(unittest.TestCase):
    def test_created_context_must_support_shader_programs(self):
        application = SimpleNamespace(instance=lambda: object(), platformName=lambda: "windows")
        for version, expected in (((1, 1), False), ((2, 0), True), ((4, 6), True)):
            with self.subTest(version=version):
                context = Mock()
                context.create.return_value = True
                context.format.return_value.version.return_value = version
                with patch.object(video_widget.QtWidgets, "QApplication", application), \
                        patch.object(video_widget.QtGui, "QOpenGLContext", return_value=context):
                    self.assertEqual(video_widget.opengl_available(), expected)


class GpuPreviewEnabledTests(unittest.TestCase):
    def test_missing_binding_and_failed_context_have_distinct_reasons(self):
        check = Mock(return_value=False)
        enabled, reason = gpu_preview_status(CPU_OPENSHOT, "pyqt5", WIDGETS, {}, check)
        self.assertFalse(enabled)
        self.assertIn("binding", reason)
        check.assert_not_called()
        enabled, reason = gpu_preview_status(GPU_OPENSHOT, "pyqt5", WIDGETS, {}, check)
        self.assertFalse(enabled)
        self.assertIn("OpenGL", reason)
        check.assert_called_once_with()

    def test_cpu_override_reports_reason_without_context_probe(self):
        check = Mock()
        enabled, reason = gpu_preview_status(
            GPU_OPENSHOT, "pyqt5", WIDGETS, {"OPENSHOT_RENDER_BACKEND": "cpu"}, check)
        self.assertFalse(enabled)
        self.assertEqual(reason, "OPENSHOT_RENDER_BACKEND=cpu")
        check.assert_not_called()

    def test_gpu_build_under_pyqt5_uses_native_preview(self):
        self.assertTrue(gpu_preview_enabled(GPU_OPENSHOT, "pyqt5", WIDGETS, {}, has_opengl))
        self.assertTrue(gpu_preview_enabled(
            GPU_OPENSHOT, "pyqt5", WIDGETS, {"OPENSHOT_RENDER_BACKEND": "vulkan"}, has_opengl))

    def test_cpu_display_override_does_not_probe_opengl(self):
        check = Mock()
        environment = {"OPENSHOT_RENDER_BACKEND": "vulkan", "OPENSHOT_PRESENTATION_BACKEND": "cpu"}
        enabled, reason = gpu_preview_status(GPU_OPENSHOT, "pyqt5", WIDGETS, environment, check)
        self.assertFalse(enabled)
        self.assertIn("Vulkan processing remains enabled", reason)
        self.assertEqual(environment["OPENSHOT_RENDER_BACKEND"], "vulkan")
        check.assert_not_called()

    def test_missing_opengl_keeps_widget_preview(self):
        self.assertFalse(gpu_preview_enabled(GPU_OPENSHOT, "pyqt5", WIDGETS, {}, lambda: False))

    def test_cpu_build_keeps_widget_preview(self):
        self.assertFalse(gpu_preview_enabled(CPU_OPENSHOT, "pyqt5", WIDGETS, {}, has_opengl))

    def test_cpu_backend_keeps_widget_preview_in_gpu_build(self):
        self.assertFalse(gpu_preview_enabled(
            GPU_OPENSHOT, "pyqt5", WIDGETS, {"OPENSHOT_RENDER_BACKEND": "cpu"}, has_opengl))

    def test_other_qt_bindings_keep_widget_preview(self):
        self.assertFalse(gpu_preview_enabled(GPU_OPENSHOT, "pyqt6", WIDGETS, {}, has_opengl))
        self.assertFalse(gpu_preview_enabled(GPU_OPENSHOT, "pyqt5", SimpleNamespace(), {}, has_opengl))


class SourcePreviewPresentationTests(unittest.TestCase):
    def _preview(self, presenter, request="current"):
        player = Mock()
        player.Mode.return_value = openshot.PLAYBACK_PAUSED
        player.Speed.return_value = 0
        video_preview = SimpleNamespace(gpu_presenter=presenter, present=Mock())
        worker = SimpleNamespace(player=player, videoPreview=video_preview,
                                 _preview_image_request=request)
        return SimpleNamespace(worker=worker), video_preview

    def test_native_frame_goes_to_gpu_presenter(self):
        presenter = Mock()
        preview, video_preview = self._preview(presenter)
        frame = openshot.Frame()
        PreviewParent.present_source_preview(preview, "current", frame)
        presenter.Present.assert_called_once_with(frame)
        video_preview.present.assert_not_called()

    def test_image_uses_widget_presentation(self):
        presenter = Mock()
        preview, video_preview = self._preview(presenter)
        image = QImage(2, 2, QImage.Format_RGBA8888)
        PreviewParent.present_source_preview(preview, "current", image)
        video_preview.present.assert_called_once_with(image)
        presenter.Present.assert_not_called()

    def test_superseded_request_is_ignored(self):
        presenter = Mock()
        preview, video_preview = self._preview(presenter, request="newer")
        PreviewParent.present_source_preview(preview, "current", openshot.Frame())
        presenter.Present.assert_not_called()
        video_preview.present.assert_not_called()


if __name__ == "__main__":
    unittest.main()
