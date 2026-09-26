"""
 @file
 @brief This file contains unit tests for Optimize Preview menu rendering
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

import os
import sys
import types
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QObject
from qt_api import QAction, QApplication

from tests.qt_test_app import get_or_create_app
from windows.views.menu import StyledContextMenu
from windows.views.optimized_preview_menu import populate_optimized_preview_menu


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])

    def _tr(self, text):
        return text


class DummyWindow(QObject):
    def __init__(self, states=None, has_proxy=None):
        super().__init__()
        self._selected_files = [types.SimpleNamespace(id="F1", data={"id": "F1", "media_type": "video"})]
        self._states = states or {"F1": "none"}
        self._has_proxy = has_proxy or {"F1": False}
        self.proxy_service = types.SimpleNamespace(
            get_proxy_state=lambda file_obj: self._states.get(file_obj.id, "none"),
            has_proxy_reader=lambda file_obj: self._has_proxy.get(file_obj.id, False),
        )
        self.actionOptimizedPreviewCreate = QAction("Optimize Video", self)
        self.actionOptimizedPreviewUseExisting = QAction("Link to Existing...", self)
        self.actionOptimizedPreviewRemove = QAction("Unlink", self)
        self.actionOptimizedPreviewCancel = QAction("Cancel", self)
        self.actionOptimizedPreviewDeleteAndUnlink = QAction("Delete && Unlink", self)

    def selected_files(self):
        return list(self._selected_files)


class OptimizedPreviewMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls._owns_app = get_or_create_app(DummyApp)

    def test_populate_menu_adds_cancel_for_running_jobs(self):
        win = DummyWindow(states={"F1": "running"}, has_proxy={"F1": False})
        menu = StyledContextMenu("Optimize Preview")

        populate_optimized_preview_menu(win, menu)

        texts = [action.text().replace("&&", "&") for action in menu.actions() if action.text()]
        self.assertEqual(texts[0], "Cancel")
        self.assertNotIn("Optimize Video", texts)
        self.assertFalse(win.actionOptimizedPreviewCreate.isEnabled())
        self.assertTrue(win.actionOptimizedPreviewCancel.isEnabled())

    def test_populate_menu_shows_unlink_actions_when_proxy_exists(self):
        win = DummyWindow(states={"F1": "ready"}, has_proxy={"F1": True})
        menu = StyledContextMenu("Optimize Preview")

        populate_optimized_preview_menu(win, menu)

        texts = [action.text().replace("&&", "&") for action in menu.actions() if action.text()]
        self.assertIn("Optimize Video", texts)
        self.assertIn("Unlink", texts)
        self.assertIn("Delete & Unlink", texts)
        self.assertTrue(win.actionOptimizedPreviewRemove.isEnabled())

    def test_populate_menu_hides_remove_when_no_proxy_exists(self):
        win = DummyWindow(states={"F1": "none"}, has_proxy={"F1": False})
        menu = StyledContextMenu("Optimize Preview")

        populate_optimized_preview_menu(win, menu)

        texts = [action.text().replace("&&", "&") for action in menu.actions() if action.text()]
        self.assertNotIn("Unlink", texts)
        self.assertNotIn("Delete & Unlink", texts)

    def test_populate_menu_enables_locate_existing_for_multi_selection(self):
        win = DummyWindow(states={"F1": "none", "F2": "none"}, has_proxy={"F1": False, "F2": False})
        win._selected_files = [
            types.SimpleNamespace(id="F1", data={"id": "F1", "media_type": "video"}),
            types.SimpleNamespace(id="F2", data={"id": "F2", "media_type": "video"}),
        ]
        menu = StyledContextMenu("Optimize Preview")

        populate_optimized_preview_menu(win, menu)

        self.assertTrue(win.actionOptimizedPreviewUseExisting.isEnabled())

    def test_populate_menu_keeps_optimize_video_label_for_mixed_selection(self):
        win = DummyWindow(states={"F1": "ready", "F2": "none"}, has_proxy={"F1": True, "F2": False})
        win._selected_files = [
            types.SimpleNamespace(id="F1", data={"id": "F1", "media_type": "video"}),
            types.SimpleNamespace(id="F2", data={"id": "F2", "media_type": "video"}),
        ]
        menu = StyledContextMenu("Optimize Preview")

        populate_optimized_preview_menu(win, menu)

        self.assertEqual(win.actionOptimizedPreviewCreate.text(), "Optimize Video")

    def test_add_menu_hides_for_non_video_selection(self):
        from windows.views.optimized_preview_menu import add_optimized_preview_menu

        win = DummyWindow()
        win._selected_files = [types.SimpleNamespace(id="A1", data={"id": "A1", "media_type": "audio"})]
        menu = StyledContextMenu("Root")

        result = add_optimized_preview_menu(win, menu)

        self.assertIsNone(result)

    def test_populate_menu_targets_only_video_subset(self):
        win = DummyWindow(states={"F1": "none"}, has_proxy={"F1": False})
        win._selected_files = [
            types.SimpleNamespace(id="A1", data={"id": "A1", "media_type": "audio"}),
            types.SimpleNamespace(id="F1", data={"id": "F1", "media_type": "video"}),
        ]
        menu = StyledContextMenu("Optimize Preview")

        populate_optimized_preview_menu(win, menu)

        self.assertEqual(win._optimized_preview_target_file_ids, ["F1"])
