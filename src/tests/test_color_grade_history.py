"""Undo regression coverage for modeless Color Grade editors and dock lifecycles."""
import copy
import types
import sys
import unittest
from unittest.mock import Mock, patch

from qt_api import QColor, QDockWidget, QEvent, QMainWindow, QMouseEvent, QStandardItem, Qt
from classes import updates as updates_module
from classes.updates import UpdateManager
from windows import color_grade_editor
from windows.views import properties_tableview
from tests import test_live_property_updates as live_tests


class EditorHarness(types.SimpleNamespace):
    """Weak-referenceable receiver for real Qt signals."""


class ColorGradeHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        live_tests.LivePropertyUpdateTests.setUpClass()
        cls.qt_app = live_tests.LivePropertyUpdateTests.app
        if not hasattr(cls.qt_app, "_tr"):
            cls.qt_app._tr = lambda text: text

    def setUp(self):
        self.qt_errors = []
        patcher = patch.object(sys, "excepthook", side_effect=lambda *args: self.qt_errors.append(args))
        patcher.start()
        self.addCleanup(patcher.stop)
        model, view, effect, app, item, value = live_tests.LivePropertyUpdateTests.make_editor(self)
        view = EditorHarness(**vars(view))
        self.model, self.view, self.effect, self.app = model, view, effect, app
        self.item, self.value = item, value
        app.theme_manager = None
        self.updates = app.updates = UpdateManager()
        self.window = app.window = QMainWindow()
        for name in ("refreshFrameSignal", "txtPropertyFilter", "IgnoreUpdates", "verifySelections",
                     "actionUndo_trigger", "actionRedo_trigger"):
            setattr(self.window, name, Mock())
        self.window.addDocks = lambda docks, area: [self.window.addDockWidget(area, dock) for dock in docks]
        self.window.show()
        self.pending_timers = []
        for target, name, replacement in (
            (properties_tableview, "get_app", lambda: app),
            (updates_module, "get_app", lambda: app),
            (color_grade_editor, "get_app", lambda: app),
        ):
            patcher = patch.object(target, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        from windows.models import properties_model
        for patcher in (
            patch.object(properties_model, "get_app", return_value=app),
            patch.object(properties_tableview.Effect, "get", side_effect=lambda **kw: self.effect),
            patch.object(properties_tableview, "record_feedback_changes"),
            patch.object(properties_tableview.QTimer, "singleShot", side_effect=lambda ms, fn: self.pending_timers.append(fn)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        effect.data["class_name"] = "ColorGrade"
        effect.data["curve_all"] = color_grade_editor.default_curve_data()
        label, curve_item = QStandardItem("Curve"), QStandardItem("Curve")
        label.setData(("curve_all", {"type": "colorgrade_curve", "closest_point_x": 1, "previous_point_x": 1,
                                  "object_id": None, "curve": copy.deepcopy(effect.data["curve_all"])}))
        curve_item.setData(item.data())
        model.model.appendRow([label, curve_item])
        self.curve_item = curve_item
        model.update_item = Mock()
        self.saved_data = copy.deepcopy(effect.data)
        effect.save = lambda: self.updates.update(["effects", {"id": "effect"}], copy.deepcopy(effect.data))

        def apply(action):
            if action.key[0] == "effects":
                action.set_old_values(copy.deepcopy(self.saved_data))
                self.saved_data = copy.deepcopy(action.values)
                effect.data = copy.deepcopy(action.values)
        self.updates.add_listener(types.SimpleNamespace(changed=apply))
        self.updates.add_listener(model)
        view.win = self.window
        view.transaction_id = None
        view.original_data_map = {}
        view.update_in_progress = False
        view.mouse_pressed = False
        view.live_property_session = None
        view.live_property_cache_paused = False
        view.live_property_playback_cache_state = None
        view.current_selection = [{"id": "effect", "type": "effect"}]
        view.color_grade_curve_dialogs = set()
        view.selected_item = item
        view._place_curve_dialog_near_index = Mock()
        names = (
            "_update_live_property_preview _update_property_preview _update_color_grade_preview_meta "
            "value_updated_wrapper start_transaction finalize_transaction cancel_transaction _restore_original_objects "
            "begin_live_property_session accept_live_property_session cancel_live_property_session "
            "preview_live_property_value preview_curve_property_value _resolve_live_property_item "
            "_wheels_drag_started _wheels_drag_finished start_property_change start_curve_property_change "
            "finish_property_change pause_live_property_caching resume_live_property_caching _is_playing "
            "_activate_color_grade_wheels_session _find_color_grade_wheels_item _find_property_value_item "
            "_auto_connect_color_grade_wheels_dock _reconnect_color_grade_wheels_session "
            "_update_color_grade_wheels_enabled _set_color_grade_wheels_unbound _disabled_color_grade_wheels_data "
            "_selection_is_color_grade _ensure_color_grade_wheels_dock_attached _color_grade_wheels_visibility_changed "
            "_close_color_grade_editors _open_wheels_editor _open_curve_editor select_item _sync_curve_edit_frame "
            "property_model_refreshed _sync_color_grade_editors_to_current_frame _sync_color_grade_wheels_dock_from_model"
        )
        for name in names.split():
            setattr(view, name, types.MethodType(getattr(properties_tableview.PropertiesTableView, name), view))
        # Production connects itemChanged to the table's transaction wrapper.
        # Preview text updates must not be mistaken for user property edits.
        model.model.itemChanged.connect(view.value_updated_wrapper)
        dock = view.color_grade_wheels_dock = QDockWidget("Color Wheels", self.window)
        panel = view.color_grade_wheels_panel = color_grade_editor.ColorGradeWheelsPanel(value, 20, dock)
        dock.setWidget(panel)
        self.window.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.hide()
        panel.wheelsChanged.connect(view.preview_live_property_value)
        panel.dragStarted.connect(view._wheels_drag_started)
        panel.dragFinished.connect(view._wheels_drag_finished)
        dock.visibilityChanged.connect(view._color_grade_wheels_visibility_changed)
        self.addCleanup(self.close_widgets)

    def close_widgets(self):
        self.view._close_color_grade_editors()
        self.view.color_grade_wheels_dock.blockSignals(True)
        self.window.close()
        self.window.deleteLater()
        self.assertEqual(self.qt_errors, [], "Unhandled exception in a Qt slot")

    def drain_timers(self):
        while self.pending_timers:
            self.pending_timers.pop(0)()

    def open_wheels(self, via_properties=False):
        if via_properties:
            self.view._open_wheels_editor(self.model.model.item(0, 0).data())
        else:
            self.view.color_grade_wheels_dock.show()
        self.drain_timers()

    def assert_history_available(self):
        self.assertFalse(self.updates.ignore_history)
        self.assertIsNone(self.updates.transaction_id)
        count = len(self.updates.actionHistory)
        self.updates.update(["position"], 12)
        self.assertEqual(len(self.updates.actionHistory), count + 1)
        self.updates.undo()
        self.assertEqual(len(self.updates.actionHistory), count)
        self.updates.redo()
        self.assertEqual(len(self.updates.actionHistory), count + 1)

    def drag_wheel(self):
        panel = self.view.color_grade_wheels_panel
        panel.dragStarted.emit()
        for amount in (0.2, 0.4, 0.8):
            panel.rows["global"]._on_input_changed("amount", amount)
        panel.dragFinished.emit()

    def open_curve(self):
        self.view.selected_item = self.curve_item
        self.view._open_curve_editor(self.model.model.item(1, 0).data(), self.model.model.index(1, 1))
        return next(iter(self.view.color_grade_curve_dialogs))

    def test_open_close_reopen_via_properties_or_dock_keeps_unrelated_edits_undoable(self):
        for via_properties in (False, True):
            with self.subTest(via_properties=via_properties):
                self.open_wheels(via_properties)
                self.assert_history_available()
                self.view.color_grade_wheels_dock.close()
                self.assertIsNone(self.view.live_property_session)
                self.assert_history_available()
                self.open_wheels(via_properties)
                self.assert_history_available()
                self.view.color_grade_wheels_dock.close()

    def test_each_drag_is_one_undo_step_with_unrelated_edits_between_drags(self):
        self.open_wheels()
        before = copy.deepcopy(self.effect.data)
        self.drag_wheel()
        self.assertEqual(len(self.updates.actionHistory), 1)
        after = copy.deepcopy(self.effect.data)
        self.assertNotEqual(before, after)
        self.updates.undo()
        self.assertEqual(self.effect.data, before)
        self.updates.redo()
        self.assertEqual(self.effect.data, after)
        self.assert_history_available()
        self.drag_wheel()
        self.assertEqual(len(self.updates.actionHistory), 3)
        self.assertNotEqual(self.updates.actionHistory[0].transaction, self.updates.actionHistory[2].transaction)
        self.assert_history_available()

    def test_discrete_wheel_actions_and_color_picker_do_not_leave_history_disabled(self):
        self.open_wheels(True)
        row = self.view.color_grade_wheels_panel.rows["global"]
        for action in (row._insert_keyframe, row.reset_to_neutral,
                       lambda: row._insert_slider_keyframe("amount")):
            action()
            self.assert_history_available()
        # The picker callback does not emit dragStarted/dragFinished.
        with patch.object(color_grade_editor, "ColorPicker") as picker:
            row.pick_color()
            picker.call_args.kwargs["callback"](QColor("red"))
        self.assert_history_available()

    def test_curves_with_and_without_wheels_keep_history_available_between_changes(self):
        for wheels in (False, True):
            with self.subTest(wheels=wheels):
                if wheels:
                    self.open_wheels()
                dialog = self.open_curve()
                self.assert_history_available()
                count = len(self.updates.actionHistory)
                before = copy.deepcopy(self.effect.data)
                dialog._toggle_enabled()
                self.assertEqual(len(self.updates.actionHistory), count + 1)
                after = copy.deepcopy(self.effect.data)
                self.assertNotEqual(before, after)
                self.updates.undo()
                self.assertEqual(self.effect.data, before)
                self.updates.redo()
                self.assertEqual(self.effect.data, after)
                self.assert_history_available()
                dialog.close()
                self.view.color_grade_curve_dialogs.discard(dialog)
                self.assert_history_available()

    def test_selection_clear_and_change_finish_interrupted_curve_without_wheels(self):
        for selection in ([], [{"id": "clip", "type": "clip"}]):
            with self.subTest(selection=selection):
                dialog = self.open_curve()
                dialog.changeStarted.emit()
                self.assertTrue(self.updates.ignore_history)
                count = len(self.updates.actionHistory)
                self.view.select_item(selection)
                self.assertEqual(len(self.updates.actionHistory), count + 1)
                self.assertFalse(self.view.live_property_cache_paused)
                self.assert_history_available()
                self.view.color_grade_curve_dialogs.discard(dialog)

    def test_close_curve_or_wheels_during_edit_releases_transaction(self):
        dialog = self.open_curve()
        dialog.changeStarted.emit()
        dialog.close()
        self.assert_history_available()
        self.open_wheels()
        self.view.color_grade_wheels_panel.dragStarted.emit()
        self.view.color_grade_wheels_dock.close()
        self.assertIsNone(self.view.live_property_session)
        self.assert_history_available()

    def test_obscured_tab_keeps_binding_but_explicit_hide_ends_it(self):
        self.open_wheels()
        session = self.view.live_property_session
        # Qt emits visibilityChanged(False) for an obscured dock tab without
        # explicitly hiding the dock. Exercise that signal separately from hide().
        self.view.color_grade_wheels_dock.visibilityChanged.emit(False)
        self.assertIs(self.view.live_property_session, session)
        self.assert_history_available()
        self.view.color_grade_wheels_dock.hide()
        self.assertIsNone(self.view.live_property_session)
        self.assert_history_available()

    def test_missing_effect_at_drag_end_still_releases_history(self):
        self.open_wheels()
        self.view.color_grade_wheels_panel.dragStarted.emit()
        self.effect = None
        self.view.color_grade_wheels_panel.dragFinished.emit()
        self.assert_history_available()

    def test_color_view_layout_then_properties_launch_and_scopes_only(self):
        metrics = types.ModuleType("classes.metrics")
        metrics.track_metric_session = Mock()
        metrics.track_metric_screen = Mock()
        with patch.dict(sys.modules, {"classes.metrics": metrics}):
            from windows.main_window import MainWindow
        window = self.window
        window.propertyTableView = self.view
        for name in ("dockProperties", "dockVideo", "dockTimeline", "dockLumaWaveform",
                     "dockHistogram", "dockVectorscope", "dockAudio"):
            dock = QDockWidget(name, window)
            window.addDockWidget(Qt.TopDockWidgetArea, dock)
            setattr(window, name, dock)
        for name in ("_set_active_custom_view_id", "_set_active_builtin_view", "style_dock_widgets"):
            setattr(window, name, Mock())
        for name in ("getDocks", "removeDocks", "floatDocks", "showDocks"):
            setattr(window, name, types.MethodType(getattr(MainWindow, name), window))
        # Exercise the actual Color View layout, including dock removal/showing.
        MainWindow.actionColor_Grade_View_trigger(window)
        self.drain_timers()
        self.assertIsNotNone(self.view.live_property_session)
        self.assert_history_available()
        self.drag_wheel()
        self.assert_history_available()
        self.view.color_grade_wheels_dock.hide()
        self.assert_history_available()  # Scope docks remain open.
        self.open_wheels(True)
        self.assert_history_available()
        # Switching layouts with an existing session must also remain safe.
        MainWindow.actionColor_Grade_View_trigger(window)
        self.drain_timers()
        self.assert_history_available()

    def test_unbound_dock_and_cancelled_idle_session_do_not_suppress_history(self):
        self.view.current_selection = []
        self.open_wheels()
        self.assertIsNone(self.view.live_property_session)
        self.assertFalse(self.view.color_grade_wheels_panel.isEnabled())
        self.assert_history_available()
        self.view.select_item([{"id": "effect", "type": "effect"}])
        self.drain_timers()
        self.view.cancel_live_property_session()
        self.assert_history_available()

    def test_cancel_interrupted_curve_restores_original_and_history(self):
        dialog = self.open_curve()
        before = copy.deepcopy(self.effect.data)
        dialog.changeStarted.emit()
        changed = copy.deepcopy(before["curve_all"])
        changed["enabled"]["Points"][0]["co"]["Y"] = 0
        dialog.curve_widget().curveChanged.emit(changed)
        self.assertNotEqual(self.effect.data, before)
        self.view._close_color_grade_editors(commit_changes=False)
        self.assertEqual(self.effect.data, before)
        self.assertEqual(self.updates.actionHistory, [])
        self.assert_history_available()

    def test_model_rebuild_rebinds_wheels_after_undo_without_suppressing_history(self):
        self.open_wheels()
        self.drag_wheel()
        self.updates.undo()
        old_item = self.item
        label, new_item = QStandardItem("Wheels"), QStandardItem("Wheels")
        metadata = self.model.model.item(0, 0).data()[1]
        metadata["wheels"] = copy.deepcopy(self.effect.data["wheels"])
        label.setData(("wheels", metadata))
        new_item.setData(old_item.data())
        self.model.ignore_update_signal = True
        self.model.model.setItem(0, 0, label)
        self.model.model.setItem(0, 1, new_item)
        self.model.ignore_update_signal = False
        self.view.property_model_refreshed()
        self.assertIs(self.view.live_property_session["item"], new_item)
        self.assert_history_available()
        self.drag_wheel()
        self.assert_history_available()

    def test_curve_mouse_drags_keep_one_transaction_per_gesture(self):
        self.assert_curve_drags(((0.8, 0.8, -1), (0.2, 0.2, 1)))

    def test_curve_corner_drags_keep_one_transaction_per_gesture(self):
        self.assert_curve_drags(((1.0, 1.0, -1), (0.0, 0.0, 1)))

    def assert_curve_drags(self, points):
        dialog = self.open_curve()
        widget = dialog.curve_widget()
        widget.resize(300, 300)
        states = [copy.deepcopy(self.effect.data)]
        for index, (x, y, direction) in enumerate(points):
            with self.subTest(drag=index):
                pos = widget._point_to_screen({"x": x, "y": y})
                widget.mousePressEvent(QMouseEvent(
                    QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                transaction = self.view.transaction_id
                self.assertIsNotNone(transaction)
                for step in range(1, 31):
                    pos = widget._point_to_screen({"x": x, "y": y + direction * step / 200})
                    widget.mouseMoveEvent(QMouseEvent(
                        QEvent.MouseMove, pos, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
                    self.assertEqual(self.view.transaction_id, transaction)
                    self.assertTrue(self.updates.ignore_history)
                    self.assertEqual(len(self.updates.actionHistory), index)
                widget.mouseReleaseEvent(QMouseEvent(
                    QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
                self.assertEqual(len(self.updates.actionHistory), index + 1)
                self.assertFalse(self.updates.ignore_history)
                states.append(copy.deepcopy(self.effect.data))
        for state in reversed(states[:-1]):
            self.updates.undo()
            self.assertEqual(self.effect.data, state)
        for state in states[1:]:
            self.updates.redo()
            self.assertEqual(self.effect.data, state)

    def test_curve_release_after_clip_restores_native_effects(self):
        """A full clip restore can replace effects while Properties stays selected."""
        import json
        import openshot
        from windows.models import properties_model

        reader = openshot.DummyReader(openshot.Fraction(24, 1), 320, 180, 44100, 2, 30)
        clip = openshot.Clip()
        clip.Reader(reader)
        clip.Id("clip")
        clip.End(10)
        native_effect = openshot.EffectInfo().CreateEffect("ColorGrade")
        native_effect.Id("effect")
        clip.AddEffect(native_effect)
        timeline = openshot.Timeline(320, 180, openshot.Fraction(24, 1), 44100, 2, openshot.LAYOUT_STEREO)
        timeline.AddClip(clip)
        self.window.timeline_sync = types.SimpleNamespace(timeline=timeline)
        self.window.CaptionTextLoaded = Mock()
        self.window.txtPropertyFilter.text.return_value = "Curve: All"
        self.model.selected = [(timeline.GetClipEffect("effect"), "effect")]
        self.model.selected_ids = [("effect", "effect")]
        self.model.selected_parent = clip
        self.model.new_item = True
        self.model.previous_filter = None
        self.model.items = {}
        self.model.filter_base_properties = []
        self.model.parent.property_model_refreshed = self.view.property_model_refreshed
        self.model.update_model = types.MethodType(properties_model.PropertiesModel.update_model, self.model)
        # Keep the production identity of the preview payload for changed().
        self.effect.save = lambda: self.updates.update(["effects", {"id": "effect"}], self.effect.data)

        def apply_native(action):
            key = action.key
            if key[0] == "effects":
                key = ["clips", {"id": "clip"}, "effects", {"id": "effect"}]
            timeline.ApplyJsonDiff(json.dumps([{"type": action.type, "key": key, "value": action.values}]))
        self.updates.add_listener(types.SimpleNamespace(changed=apply_native), 0)
        self.model.update_model("Curve: All")
        item, meta = self.view._find_property_value_item("curve_all", "colorgrade_curve")
        self.view.selected_item = item
        self.view._open_curve_editor(("curve_all", meta), self.model.model.index(item.row(), 1))
        dialog = next(iter(self.view.color_grade_curve_dialogs))
        widget = dialog.curve_widget()
        widget.resize(300, 300)

        # This is the effects portion of a full clip undo payload. libopenshot
        # rebuilds the effect list; the old borrowed effect is now detached.
        self.updates.update(["clips", {"id": "clip"}], {"effects": [json.loads(native_effect.Json())]})
        for y in (0.7, 0.4):
            pos = widget._point_to_screen({"x": 1.0, "y": widget._evaluated_nodes()[-1]["y"]})
            widget.mousePressEvent(QMouseEvent(
                QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
            pos = widget._point_to_screen({"x": 1.0, "y": y})
            widget.mouseMoveEvent(QMouseEvent(
                QEvent.MouseMove, pos, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            preview_y = widget._evaluated_nodes()[-1]["y"]
            self.assertAlmostEqual(preview_y, y, delta=0.005)
            widget.mouseReleaseEvent(QMouseEvent(
                QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
            self.assertAlmostEqual(widget._evaluated_nodes()[-1]["y"], preview_y)
            self.assertEqual(self.model.selected[0][0].this, timeline.GetClipEffect("effect").this)

        # Rebuilding the effect list can also remove then restore the selection.
        # Rows must be rebuilt, rather than reusing deleted QStandardItems.
        self.updates.update(["clips", {"id": "clip"}], {"effects": []})
        self.assertEqual(self.model.selected, [])
        self.assertEqual(self.model.model.rowCount(), 0)
        self.updates.update(["clips", {"id": "clip"}], {"effects": [json.loads(native_effect.Json())]})
        self.assertEqual(self.model.selected[0][0].this, timeline.GetClipEffect("effect").this)
        self.assertIsNotNone(self.view._find_property_value_item("curve_all", "colorgrade_curve")[0])

    def test_native_selection_refresh_uses_active_ids_not_pending_selection(self):
        """A queued UI selection must not retarget an editor's active model."""
        from windows.models import properties_model
        old = Mock()
        old.Id.side_effect = AssertionError("Do not dereference a replaced native object")
        current = Mock()
        parent = object()
        current.ParentClip.return_value = parent
        timeline = Mock()
        timeline.GetClipEffect.return_value = current
        self.window.timeline_sync = types.SimpleNamespace(timeline=timeline)
        self.model.selected = [(old, "effect")]
        self.model.selected_ids = [("effect", "effect")]
        self.model.next_selection = [{"id": "other", "type": "clip"}]
        properties_model.PropertiesModel._refresh_selected_objects(self.model)
        self.assertEqual(self.model.selected, [(current, "effect")])
        self.assertIs(self.model.selected_parent, parent)
        timeline.GetClipEffect.assert_called_once_with("effect")
        timeline.GetClip.assert_not_called()

    def test_selection_timeout_records_and_clears_native_ids(self):
        from windows.models import properties_model
        effect = Mock()
        effect.Id.return_value = "effect"
        timeline = Mock()
        timeline.GetClipEffect.return_value = effect
        self.window.timeline_sync = types.SimpleNamespace(timeline=timeline)
        self.window.preview_thread = Mock()
        self.model.update_frame = Mock()
        self.model.selected = []
        self.model.next_selection = [{"id": "effect", "type": "effect"}]
        properties_model.PropertiesModel.update_item_timeout(self.model)
        self.assertEqual(self.model.selected_ids, [("effect", "effect")])
        self.model.next_selection = []
        properties_model.PropertiesModel.update_item_timeout(self.model)
        self.assertEqual(self.model.selected_ids, [])
        self.assertEqual(self.model.selected, [])
