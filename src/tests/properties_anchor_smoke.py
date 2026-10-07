# @file
# @brief Exercise Properties dock positioning in the real application
# @author OpenShot Studios, LLC
#
# @section LICENSE
#
# Copyright (c) 2008-2026 OpenShot Studios, LLC
# (http://www.openshotstudios.com). This file is part of
# OpenShot Video Editor (http://www.openshot.org), an open-source project
# dedicated to delivering high quality video editing and animation solutions
# to the world.
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
#

"""Open the real clip context menu and preserve its edge through dock layout."""
import copy
import importlib
import os
import json
import openshot
import tempfile
import traceback
import unittest

root = tempfile.mkdtemp(prefix="openshot-properties-anchor-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root if path == "~" else original_expanduser(path)
from classes.app import OpenShotApp
from classes import version
# UI workflow checks must not depend on the external update service.
version.get_current_Version = lambda: None
from classes.query import Clip
from qt_api import QApplication, QCursor, QImage, QPoint, QTimer, Qt, QT_API

QTest = importlib.import_module({"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API] + ".QtTest").QTest
app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
passed = False
checks = unittest.TestCase()


def verify():
    global passed
    try:
        window = app.window
        window.resize(1440, 900)
        for dock in window.getDocks():
            if dock not in (window.dockTimeline, window.dockVideo):
                dock.hide()
        window.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        window.addDockWidget(Qt.LeftDockWidgetArea, window.dockProperties)
        window.dockProperties.hide()
        window.dockProperties.setMinimumWidth(300)
        QTest.qWait(500)
        timeline = window.timeline
        clip = Clip()
        # Exercise ordinary media: dock anchoring must work without text support.
        image = QImage(640, 360, QImage.Format_RGBA8888)
        image.fill(Qt.white)
        image_path = os.path.join(root, "anchor.png")
        checks.assertTrue(image.save(image_path), 'image.save(image_path)')
        native_clip = openshot.Clip(image_path)
        clip.data = json.loads(native_clip.Json())
        clip.data.update(position=60.0, start=0.0, end=10.0, duration=10.0,
                         layer=app.project.get("layers")[-1]["number"])
        clip.save()
        window.selected_items = [{"id": clip.id, "type": "clip"}]
        timeline.zoom_factor = 10.0
        timeline.delayed_resize_callback()
        timeline.set_scroll_left(100.0 / timeline.scrollbar_position[2])
        QTest.qWait(500)
        timeline.end_properties_layout_change()
        original = copy.deepcopy(Clip.get(id=clip.id).data)

        def edge():
            timeline.geometry.ensure()
            rect = timeline.geometry.calc_item_rect(Clip.get(id=clip.id), viewport=True)
            return timeline.mapToGlobal(QPoint(round(rect.left()), round(rect.center().y())))

        before = edge()
        initial_origin = timeline.mapToGlobal(QPoint(0, 0)).x()
        initial_zoom = timeline.pixels_per_second
        QCursor.setPos(before)
        app.clipboard().setText("Properties anchor fixture")
        checks.assertTrue(not window.dockProperties.isVisible(), 'not window.dockProperties.isVisible()')
        triggered = []

        def choose_properties():
            menu = QApplication.activePopupWidget()
            checks.assertTrue(menu is not None, "Clip context menu did not open")
            action = next(a for a in menu.actions() if a.text() == window.actionProperties.text())
            # Moving into the menu must not replace the original edge anchor.
            QCursor.setPos(menu.mapToGlobal(menu.actionGeometry(action).center()))
            QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
            triggered.append(True)

        QTimer.singleShot(100, choose_properties)
        timeline.ShowClipMenu(clip.id)
        QTest.qWait(600)
        checks.assertTrue(triggered and window.dockProperties.isVisible(), 'triggered and window.dockProperties.isVisible()')
        checks.assertTrue(timeline.mapToGlobal(QPoint(0, 0)).x() > initial_origin + 100, "Fixture did not shift timeline")
        checks.assertTrue(abs(edge().x() - before.x()) <= 1, (before.x(), edge().x()))
        checks.assertTrue(timeline.pixels_per_second == initial_zoom, 'timeline.pixels_per_second == initial_zoom')
        checks.assertTrue(Clip.get(id=clip.id).data == original, 'Clip.get(id=clip.id).data == original')

        # Hide uses the playhead fallback. Repeated dock layout passes must keep
        # the same screen anchor after the delayed scrollbar normalization.
        timeline.current_frame = round(60.0 * timeline.fps_float) + 1
        playhead_x = edge().x()
        window.dockProperties.hide()
        QTest.qWait(20)
        window.resize(1480, 900)
        QTest.qWait(20)
        window.resize(1440, 900)
        QTest.qWait(600)
        checks.assertTrue(abs(edge().x() - playhead_x) <= 1, (playhead_x, edge().x()))
        checks.assertTrue(timeline.pixels_per_second == initial_zoom, 'timeline.pixels_per_second == initial_zoom')

        # A keyboard open at time zero can only clamp to the new left edge.
        timeline.current_frame = 1
        timeline.set_scroll_left(0.0)
        window.actionProperties.trigger()
        QTest.qWait(600)
        checks.assertTrue(timeline.h_scroll_offset == 0.0, timeline.h_scroll_offset)
        checks.assertTrue(timeline.scrollbar_position[0] == 0.0, 'timeline.scrollbar_position[0] == 0.0')
        checks.assertTrue(Clip.get(id=clip.id).data == original, 'Clip.get(id=clip.id).data == original')

        # Explicit timeline input takes control before the settling timer fires.
        timeline.begin_properties_layout_change((60.0, before.x()))
        QTest.mouseClick(timeline, Qt.LeftButton,
                         pos=QPoint(timeline.track_name_width + 10, timeline.ruler_height // 2))
        checks.assertTrue(timeline._properties_layout_anchor is None, 'timeline._properties_layout_anchor is None')
        timeline.begin_properties_layout_change((60.0, before.x()))
        timeline.zoomIn()
        checks.assertTrue(timeline._properties_layout_anchor is None, 'timeline._properties_layout_anchor is None')
        user_scroll = timeline.h_scroll_offset
        QTest.qWait(600)
        checks.assertTrue(abs(timeline.h_scroll_offset - user_scroll) <= 1, (user_scroll, timeline.h_scroll_offset))

        # Opening Properties from inside a clip at zero cannot preserve the
        # cursor's screen position when the dock covers it. Keep the start visible.
        window.dockProperties.hide()
        QTest.qWait(600)
        timeline.end_properties_layout_change()
        clip = Clip.get(id=clip.id)
        clip.data["position"] = 0.0
        clip.save()
        timeline.current_frame = 1
        timeline.set_scroll_left(0.0)
        QTest.qWait(500)
        original = copy.deepcopy(Clip.get(id=clip.id).data)
        click_pos = edge() + QPoint(30, 0)
        QCursor.setPos(click_pos)
        triggered.clear()
        QTimer.singleShot(100, choose_properties)
        timeline.ShowClipMenu(clip.id)
        QTest.qWait(600)
        checks.assertTrue(triggered and window.dockProperties.isVisible())
        viewport_left = timeline.mapToGlobal(QPoint(timeline.track_name_width, 0)).x()
        checks.assertLess(click_pos.x(), viewport_left, "Fixture must cover the old cursor position")
        checks.assertEqual(timeline.h_scroll_offset, 0.0)
        checks.assertLessEqual(abs(edge().x() - viewport_left), 1)
        checks.assertEqual(Clip.get(id=clip.id).data, original)
        passed = True
        print("PROPERTIES_ANCHOR_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        # Qt6 quit() closes windows first; skip the unsaved-changes prompt.
        app.project.has_unsaved_changes = False
        app.quit()


checks.assertTrue(app.gui(), 'app.gui()')
QTimer.singleShot(4000, verify)
app.exec_()
raise SystemExit(0 if passed else 1)
