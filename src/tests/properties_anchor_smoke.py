"""Open the real clip context menu and preserve its edge through dock layout."""
import copy
import importlib
import os
import tempfile
import traceback

root = tempfile.mkdtemp(prefix="openshot-properties-anchor-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root if path == "~" else original_expanduser(path)
from classes.app import OpenShotApp
from classes.query import Clip
from classes.direct_text import default_text, new_text_clip
from qt_api import QApplication, QCursor, QPoint, QTimer, Qt, QT_API

QTest = importlib.import_module({"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API] + ".QtTest").QTest
app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
passed = False


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
        clip.data = new_text_clip(default_text(640, 360), root, 60.0,
                                  app.project.get("layers")[-1]["number"], 10.0)
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
        assert not window.dockProperties.isVisible()
        triggered = []

        def choose_properties():
            menu = QApplication.activePopupWidget()
            assert menu is not None, "Clip context menu did not open"
            action = next(a for a in menu.actions() if a.text() == window.actionProperties.text())
            # Moving into the menu must not replace the original edge anchor.
            QCursor.setPos(menu.mapToGlobal(menu.actionGeometry(action).center()))
            QTest.mouseClick(menu, Qt.LeftButton, pos=menu.actionGeometry(action).center())
            triggered.append(True)

        QTimer.singleShot(100, choose_properties)
        timeline.ShowClipMenu(clip.id)
        QTest.qWait(600)
        assert triggered and window.dockProperties.isVisible()
        assert timeline.mapToGlobal(QPoint(0, 0)).x() > initial_origin + 100, "Fixture did not shift timeline"
        assert abs(edge().x() - before.x()) <= 1, (before.x(), edge().x())
        assert timeline.pixels_per_second == initial_zoom
        assert Clip.get(id=clip.id).data == original

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
        assert abs(edge().x() - playhead_x) <= 1, (playhead_x, edge().x())
        assert timeline.pixels_per_second == initial_zoom

        # A keyboard open at time zero can only clamp to the new left edge.
        timeline.current_frame = 1
        timeline.set_scroll_left(0.0)
        window.actionProperties.trigger()
        QTest.qWait(600)
        assert timeline.h_scroll_offset == 0.0, timeline.h_scroll_offset
        assert timeline.scrollbar_position[0] == 0.0
        assert Clip.get(id=clip.id).data == original

        # Explicit timeline input takes control before the settling timer fires.
        timeline.begin_properties_layout_change((60.0, before.x()))
        QTest.mouseClick(timeline, Qt.LeftButton,
                         pos=QPoint(timeline.track_name_width + 10, timeline.ruler_height // 2))
        assert timeline._properties_layout_anchor is None
        timeline.begin_properties_layout_change((60.0, before.x()))
        timeline.zoomIn()
        assert timeline._properties_layout_anchor is None
        user_scroll = timeline.h_scroll_offset
        QTest.qWait(600)
        assert abs(timeline.h_scroll_offset - user_scroll) <= 1, (user_scroll, timeline.h_scroll_offset)
        passed = True
        print("PROPERTIES_ANCHOR_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()


assert app.gui()
QTimer.singleShot(4000, verify)
app.exec_()
raise SystemExit(0 if passed else 1)
