"""Focused Qt binding regressions, runnable without loading native libopenshot."""

import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

import qt_api
from qt_api import (QApplication, QComboBox, QCoreApplication, QEvent,
                    QPoint, QPointF, QRectF, QSizeF, Qt, QWidget)
from classes import tabstops


def load_method(relative_path, name):
    # Exercise the production method with real Qt geometry without importing
    # a libopenshot build linked to a potentially different Qt major version.
    path = Path(__file__).resolve().parents[1] / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"))
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.parse("")
    module.body = [method]
    namespace = dict(vars(qt_api))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


class SentryQtCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def delete_widget(self, widget):
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(qt_api.isdeleted(widget))

    def test_deferred_tab_order_skips_deleted_control(self):
        root = QWidget()
        first, removed, last = [QComboBox(root) for _ in range(3)]
        with patch.object(tabstops.QTimer, "singleShot") as timer:
            tabstops.apply_explicit_tab_order_later(
                [first, removed, last], root, include_hidden=True)
        self.delete_widget(removed)
        with patch.object(tabstops, "safe_set_tab_order") as order:
            timer.call_args[0][1]()
        order.assert_called_once_with(first, last)
        self.delete_widget(root)

    def test_deferred_tab_order_abandons_deleted_root(self):
        root = QWidget()
        widgets = [QComboBox(root), QComboBox(root)]
        with patch.object(tabstops.QTimer, "singleShot") as timer:
            tabstops.apply_explicit_tab_order_later(widgets, root)
        self.delete_widget(root)
        with patch.object(tabstops, "safe_set_tab_order") as order:
            timer.call_args[0][1]()
        order.assert_not_called()

    def test_tab_order_without_root_skips_deleted_control(self):
        widget = QComboBox()
        self.delete_widget(widget)
        tabstops.apply_explicit_tab_order([widget])

    def test_tab_order_preserves_hidden_and_disabled_filters(self):
        root = QWidget()
        widget = QComboBox(root)
        widget.hide()
        self.assertFalse(tabstops._is_focusable(widget, root, False, False))
        self.assertTrue(tabstops._is_focusable(widget, root, True, False))
        widget.setEnabled(False)
        self.assertFalse(tabstops._is_focusable(widget, root, True, False))
        self.assertTrue(tabstops._is_focusable(widget, root, True, True))
        self.delete_widget(root)

    def test_cursor_normalizes_integer_and_floating_points(self):
        update = load_method("windows/views/timeline_backend/qwidget/base.py", "_updateCursor")
        for point in (QPoint(4, 5), QPointF(4.25, 5.75)):
            with self.subTest(point=point):
                def contains(pos):
                    self.assertIsInstance(pos, QPointF)
                    self.assertEqual(pos, QPointF(point))
                    return QRectF(0, 0, 10, 10).contains(pos)
                widget = types.SimpleNamespace(
                    _fixed_cursor=None, geometry=types.SimpleNamespace(ensure=lambda: None),
                    playhead_time_editor=True,
                    _playhead_time_panel_rect=lambda: types.SimpleNamespace(contains=contains),
                    setCursor=Mock())
                update(widget, point)
                widget.setCursor.assert_called_once_with(Qt.IBeamCursor)

    def test_crop_origin_normalizes_integer_point(self):
        check = load_method("windows/video_widget.py", "checkTransformMode")
        def contains(pos):
            self.assertIsInstance(pos, QPointF)
            return QRectF(0, 0, 10, 10).contains(pos)
        widget = types.SimpleNamespace(
            transform=True, transforming_effect=True,
            transforming_effect_object=types.SimpleNamespace(info=types.SimpleNamespace(class_name="Crop")),
            cropOriginHandleScreen=types.SimpleNamespace(contains=contains),
            cursors={"hand": Qt.OpenHandCursor}, rotateCursor=lambda cursor, *args: cursor,
            mouse_dragging=True, transform_mode=None, setCursor=Mock())
        check(widget, 0, 0, 0, types.SimpleNamespace(pos=lambda: QPoint(4, 5)))
        self.assertEqual(widget.hover_transform_mode, "origin")
        self.assertEqual(widget.transform_mode, "origin")
        widget.setCursor.assert_called_once_with(Qt.OpenHandCursor)

    def test_wheel_zoom_supports_position_and_legacy_pos(self):
        wheel = load_method("windows/video_widget.py", "wheelEvent")
        for modern in (False, True):
            with self.subTest(modern=modern):
                event = types.SimpleNamespace(accept=Mock(), angleDelta=lambda: QPoint(0, 128))
                anchor = QPointF(25.25, 30.5) if modern else QPoint(25, 30)
                setattr(event, "position" if modern else "pos", lambda: anchor)
                widget = types.SimpleNamespace(
                    zoom=2.0, width=lambda: 100, height=lambda: 100,
                    centeredViewport=lambda *args: QRectF(0, 0, 100, 100),
                    resize_button=Mock(), update=Mock())
                widget._clamp_pan = lambda: (widget.pan_x, widget.pan_y)
                with patch.object(QCoreApplication, "instance", return_value=types.SimpleNamespace(
                        keyboardModifiers=lambda: Qt.NoModifier)):
                    wheel(widget, event)
                self.assertEqual(widget.zoom, 2.125)
                self.assertAlmostEqual(widget.pan_x, (50 - anchor.x()) * 0.0625)
                self.assertAlmostEqual(widget.pan_y, (50 - anchor.y()) * 0.0625)
                widget.update.assert_called_once_with()
                event.accept.assert_called_once_with()

    def test_round_join_alias_is_usable_and_preserved(self):
        join = Qt.RoundJoin
        pen = qt_api.QPen()
        pen.setJoinStyle(join)
        self.assertEqual(pen.joinStyle(), join)
        qt_api._patch_enums_for_qt6()
        self.assertEqual(Qt.RoundJoin, join)

    def test_keep_anchor_alias_selects_caption_text(self):
        document = qt_api.QTextDocument("caption text")
        cursor = qt_api.QTextCursor(document)
        cursor.setPosition(0)
        cursor.setPosition(7, qt_api.QTextCursor.KeepAnchor)
        self.assertEqual(cursor.selectedText(), "caption")
        alias = qt_api.QTextCursor.KeepAnchor
        qt_api._patch_enums_for_qt6()
        self.assertEqual(qt_api.QTextCursor.KeepAnchor, alias)

    def test_edit_key_pressed_alias_is_accepted_by_item_view(self):
        view = qt_api.QTableView()
        model = qt_api.QStandardItemModel(1, 1)
        view.setModel(model)
        model.setData(model.index(0, 0), "value")
        view.setCurrentIndex(model.index(0, 0))
        trigger = qt_api.QAbstractItemView.EditKeyPressed
        self.assertTrue(view.edit(model.index(0, 0), trigger, None))
        qt_api._patch_enums_for_qt6()
        self.assertEqual(qt_api.QAbstractItemView.EditKeyPressed, trigger)
        self.delete_widget(view)


if __name__ == "__main__":
    unittest.main()
