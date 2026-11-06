"""Real application checks for immediate text, shared assets, keyboard focus and persistence."""
import copy
import importlib
import json
import os
import shutil
import sys
import tempfile
import traceback
import unittest

root = tempfile.mkdtemp(prefix="openshot-easy-text-")
original_expanduser = os.path.expanduser
os.path.expanduser = lambda path: root if path == "~" else original_expanduser(path)
from classes.app import OpenShotApp
from classes import info, version
version.get_current_Version = lambda: None
from classes.query import Clip, File
from qt_api import QTimer, Qt, QPoint, QPointF, QT_API, QImage, QTextCursor, QDialog
QTest = importlib.import_module({"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API] + ".QtTest").QTest
app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("send_metrics", False)
checks = unittest.TestCase()
passed = False


def verify():
    global passed
    try:
        window = app.window
        window.activateWindow()
        QTest.qWait(100)
        if not window.isActiveWindow() and hasattr(app, "setActiveWindow"):
            # Headless X servers have no window manager to grant activation.
            app.setActiveWindow(window)
        controller = window.direct_text
        button = window.timelineToolbar.widgetForAction(window.actionDirectText)
        checks.assertTrue(button is not None and window.videoToolbar.widgetForAction(window.actionDirectText) is None)
        checks.assertIn(window.actionText, window.menuTitle.actions())
        checks.assertEqual(window.timelineToolbar.widgetForAction(window.actionAddMarker).toolButtonStyle(), Qt.ToolButtonIconOnly)
        initial_clips, initial_files = len(Clip.filter()), len(File.filter())
        history_count = len(app.updates.actionHistory)
        initial_layers = copy.deepcopy(app.project.get("layers"))
        window.timeline.setFocus()
        preview_size = window.videoPreview.size()
        window.actionText.trigger()
        checks.assertTrue(controller.draft is not None and controller.editor.hasFocus())
        # The formatting bar floats over the preview instead of resizing it.
        bar = controller.toolbar
        checks.assertTrue(bar.isVisible() and bar.parentWidget() is window.videoPreview)
        checks.assertEqual(window.videoPreview.size(), preview_size)
        text_rect = controller.proxy.sceneBoundingRect().toAlignedRect()
        checks.assertFalse(bar.geometry().intersects(text_rect))
        checks.assertTrue(window.videoPreview.rect().contains(bar.geometry()))
        bar.place(bar.geometry())
        checks.assertEqual(bar.geometry().bottom(), window.videoPreview.height() - 9, "Bar moves below text it would cover")
        controller.update_geometry()
        checks.assertIs(app.focusWidget(), controller.view, "Real key events must reach the text view")
        # Edit mode never paints transform handles under the text box.
        from unittest.mock import patch
        with patch.object(type(window.videoPreview), "drawTransformHandler") as handles:
            window.videoPreview.repaint()
        checks.assertEqual(handles.call_count, 0, "Transform handles painted beneath the text editor")
        # The preview's zoom/pan hint never covers the editor or handles.
        from qt_api import QHelpEvent, QEvent

        def tooltip_shown(widget):
            event = QHelpEvent(QEvent.ToolTip, QPoint(5, 5), widget.mapToGlobal(QPoint(5, 5)))
            with patch("windows.video_widget.QToolTip.hideText") as hidden:
                app.sendEvent(widget, event)
            return not hidden.called
        checks.assertFalse(tooltip_shown(window.videoPreview), "Preview tooltip covers the text editor")
        checks.assertFalse(tooltip_shown(controller.view.viewport()), "Preview tooltip covers the text editor")
        if os.environ.get("OPENSHOT_TEXT_SCREENSHOT_DIR"):
            QTest.qWait(300)
            window.grab().save(os.path.join(os.environ["OPENSHOT_TEXT_SCREENSHOT_DIR"], "easy-text-draft.png"))
        # Tt adds a real, selected clip and asset at once, with text selected.
        checks.assertTrue(len(Clip.filter()) == initial_clips + 1 and len(File.filter()) == initial_files + 1)
        checks.assertIn(controller.clip_id, window.selected_clips)
        checks.assertEqual(controller.editor.textCursor().selectedText(), "Text")
        QTest.keyClicks(controller.editor, "Discard me")
        QTest.keyClick(controller.editor, Qt.Key_Escape)
        checks.assertTrue(controller.draft is None and window.timeline.hasFocus())
        checks.assertTrue(len(Clip.filter()) == initial_clips and len(File.filter()) == initial_files)
        checks.assertTrue(len(app.updates.actionHistory) == history_count and not app.updates.redoHistory)
        checks.assertEqual(app.project.get("layers"), initial_layers)

        QTest.mouseClick(button, Qt.LeftButton)
        checks.assertIs(app.focusWidget(), controller.view, "Clicking Tt must not leave focus on the button")
        QTest.keyClicks(controller.editor, "Hello")
        QTest.keyClick(controller.editor, Qt.Key_Return, Qt.ShiftModifier)
        QTest.keyClicks(controller.editor, "world")
        checks.assertIsNotNone(controller.draft)
        controller.toolbar.size.setValue(72)
        window.timeline.setFocus()
        QTest.qWait(50)
        checks.assertEqual(File.filter()[-1].data["text"], "Text", "Focus loss committed typing")
        controller.editor.setFocus()
        QTest.keyClick(controller.editor, Qt.Key_Return)
        checks.assertTrue(controller.draft is None and window.timeline.hasFocus())
        checks.assertTrue(len(Clip.filter()) == initial_clips + 1 and len(File.filter()) == initial_files + 1)
        first = Clip.filter()[-1]
        asset = File.get(id=first.data["file_id"])
        checks.assertTrue(asset.data["type"] == "QtTextReader" and not asset.data["path"])
        checks.assertEqual(asset.data["text"], "Hello\nworld")
        checks.assertEqual(first.data["direct_text"]["font_size"], 72)
        checks.assertEqual(first.data["reader"]["type"], "QtTextReader")
        created_id, asset_id = first.id, asset.id
        # Creation and typing are one undo step.
        app.updates.undo()
        checks.assertTrue(Clip.get(id=created_id) is None and File.get(id=asset_id) is None)
        app.updates.redo()
        checks.assertTrue(Clip.get(id=created_id) and File.get(id=asset_id))

        # Double-clicking the text edits it; clicking outside keeps the typing
        # and returns to transform mode without the formatting bar.
        clip_data = Clip.get(id=created_id).data
        style = clip_data["direct_text"]
        center = controller.geometry(clip_data).map(QPointF(style["width"] / 2, style["height"] / 2)).toPoint()
        QTest.mouseDClick(window.videoPreview, Qt.LeftButton, Qt.NoModifier, center)
        checks.assertTrue(controller.clip_id == created_id and controller.toolbar.isVisible())
        checks.assertEqual(controller.editor.textCursor().selectedText(), "Hello\u2029world", "Double-click selects all text")
        controller.editor.moveCursor(QTextCursor.End)
        QTest.keyClicks(controller.editor, " again")
        inside = controller.view.mapFromScene(controller.proxy.sceneBoundingRect().center())
        QTest.mouseClick(controller.view.viewport(), Qt.LeftButton, Qt.NoModifier, inside)
        checks.assertIsNotNone(controller.draft, "Clicks inside the text keep editing")
        outside = QPoint(5, window.videoPreview.height() - 5)
        QTest.mouseClick(controller.view.viewport(), Qt.LeftButton, Qt.NoModifier, outside)
        checks.assertTrue(controller.draft is None and not controller.toolbar.isVisible())
        checks.assertEqual(File.get(id=asset_id).data["text"], "Hello\nworld again")
        checks.assertIn(created_id, window.selected_clips)
        checks.assertTrue(window.videoPreview.transforming_clip and window.videoPreview.transforming_clip.id == created_id)
        # Like any clip, the selection survives the playhead leaving and returning.
        with patch.object(type(window.videoPreview), "drawTransformHandler") as handles:
            window.videoPreview.repaint()
        checks.assertEqual(handles.call_count, 1, "Transform mode shows handles after editing")
        fps = app.project.get("fps")
        for frame in (round(30 * fps["num"] / fps["den"]), 1):
            window.SeekSignal.emit(frame, True)
            QTest.qWait(100)
            checks.assertTrue(window.videoPreview.transforming_clip and window.videoPreview.transforming_clip.id == created_id, "Seeking cleared the text clip's transform selection")
        with patch.object(type(window.videoPreview), "drawTransformHandler") as handles:
            window.videoPreview.repaint()
        checks.assertEqual(handles.call_count, 1, "Seeking cleared the text clip's transform handles")
        checks.assertFalse(tooltip_shown(window.videoPreview), "Preview tooltip covers transform handles")
        app.updates.undo()
        checks.assertEqual(File.get(id=asset_id).data["text"], "Hello\nworld")

        # The clip menu has one Text submenu near the bottom, under Slice.
        from unittest.mock import patch
        app.clipboard().setText("")  # offscreen platforms start without clipboard data
        with patch("windows.views.timeline.StyledContextMenu.show_at", lambda menu, pos: menu):
            menu = window.timeline.ShowClipMenu(created_id)
        titles = [a.text().replace("&", "") for a in menu.actions()]
        checks.assertTrue("Edit Text" not in titles and titles.count("Text") == 1)
        text_index = titles.index("Text")
        checks.assertTrue(titles.index("Speed") < text_index < titles.index("Properties"))
        if "Slice" in titles:
            checks.assertEqual(text_index, titles.index("Slice") + 1)
        text_menu = menu.actions()[text_index].menu()
        checks.assertEqual([a.text() for a in text_menu.actions()], ["Edit Text", "Edit Style…", "Reset Style"])
        text_menu.actions()[0].trigger()
        checks.assertTrue(controller.clip_id == created_id and controller.toolbar.isVisible())
        checks.assertEqual(controller.editor.textCursor().selectedText(), "Hello\u2029world", "Edit Text selects all text")
        checks.assertIs(app.focusWidget(), controller.view, "Edit Text is ready to type")
        controller.cancel(return_focus=True)
        with patch("windows.text_style.TextStyleDialog.exec_", return_value=0) as style_dialog:
            text_menu.actions()[1].trigger()
        checks.assertEqual(style_dialog.call_count, 1)

        # Next Marker stops on the last clip's final frame; Tt continues after it
        # on the same track instead of stacking a new track over that frame.
        checks.assertEqual(window.actionText.shortcut().toString(), "Shift+T")
        first = Clip.get(id=created_id)
        first_end = first.data["position"] + first.data["end"] - first.data["start"]
        window.SeekSignal.emit(window.timeline_sync.GetLastFrame(), True)
        QTest.qWait(100)
        window.timeline.setFocus()
        QTest.keyClick(window.timeline, Qt.Key_T, Qt.ShiftModifier)
        following = Clip.get(id=controller.clip_id)
        checks.assertTrue(following and following.id != created_id)
        checks.assertEqual(following.data["layer"], first.data["layer"])
        checks.assertLess(abs(following.data["position"] - first_end), 1e-6)
        QTest.keyClick(controller.editor, Qt.Key_Escape)
        checks.assertTrue(Clip.get(id=following.id) is None and window.timeline.hasFocus())
        window.SeekSignal.emit(1, True)
        QTest.qWait(100)

        # Text above the highest occupied track adds a track; Escape removes it.
        layers_before = copy.deepcopy(app.project.get("layers"))
        QTest.mouseClick(button, Qt.LeftButton)
        checks.assertEqual(len(app.project.get("layers")), len(layers_before) + 1)
        controller.toolbar.size.setFocus()
        QTest.keyClick(controller.toolbar.size, Qt.Key_Escape)
        checks.assertTrue(controller.draft is None and window.timeline.hasFocus())
        checks.assertEqual(app.project.get("layers"), layers_before)
        QTest.mouseClick(button, Qt.LeftButton)
        QTest.keyClicks(controller.editor, "Another title")
        controller.toolbar.size.setFocus()
        QTest.keyClick(controller.toolbar.size, Qt.Key_Return)
        checks.assertEqual(len(app.project.get("layers")), len(layers_before) + 1)
        app.updates.undo()
        checks.assertEqual(app.project.get("layers"), layers_before)
        checks.assertEqual(len(File.filter()), initial_files + 1)

        # The same addClip path used by a Project Files drag creates an instance.
        window.timeline.addClip(asset_id, QPointF(12.0, 0), first.data["layer"], call_manual_move=False)
        instances = Clip.filter(file_id=asset_id)
        checks.assertEqual(len(instances), 2)
        original_transforms = {c.id: {k: copy.deepcopy(c.data[k]) for k in ("position", "scale_x", "rotation")}
                               for c in instances}
        window.timeline.AddSelectionJS(created_id, "clip", True)
        window.timeline.setFocus()
        QTest.qWait(100)
        checks.assertTrue(controller.draft is None and window.timeline.hasFocus())
        QTest.keyClick(window.timeline, Qt.Key_Right, Qt.ControlModifier)
        checks.assertTrue(controller.draft is None and window.timeline.hasFocus())
        window.timeline.AddSelectionJS(created_id, "clip", True)
        QTest.keyClick(window.timeline, Qt.Key_Return)
        checks.assertTrue(controller.draft is not None and controller.editor.hasFocus())
        controller.editor.selectAll()
        QTest.keyClicks(controller.editor, "Shared title")
        QTest.keyClick(controller.editor, Qt.Key_Return)
        checks.assertEqual(File.get(id=asset_id).data["text"], "Shared title")
        for clip in Clip.filter(file_id=asset_id):
            checks.assertEqual(clip.data["direct_text"]["text"], "Shared title")
            checks.assertEqual(clip.data["reader"]["text"], "Shared title")
            checks.assertTrue(all(clip.data[k] == v for k, v in original_transforms[clip.id].items()))
        engine_clip = next(c for c in json.loads(window.timeline_sync.timeline.Json())["clips"] if c["id"] == created_id)
        engine_reader = engine_clip["reader"]
        while engine_reader.get("type") == "FrameMapper":
            engine_reader = engine_reader["reader"]
        checks.assertEqual(engine_reader["text"], "Shared title")
        app.updates.undo()
        checks.assertEqual(File.get(id=asset_id).data["text"], "Hello\nworld")
        checks.assertTrue(all(c.data["reader"]["text"] == "Hello\nworld" for c in Clip.filter(file_id=asset_id)))
        app.updates.redo()
        controller.begin(created_id)
        controller.editor.selectAll()
        QTest.keyClicks(controller.editor, "Cancel changes")
        QTest.keyClick(controller.editor, Qt.Key_Escape)
        checks.assertEqual(File.get(id=asset_id).data["text"], "Shared title")
        checks.assertTrue(len(Clip.filter(file_id=asset_id)) == 2 and window.timeline.hasFocus())

        # Entering typing after a double-click must end any preview drag.
        from qt_api import QCoreApplication, QMouseEvent
        window.SeekSignal.emit(1, True)
        QTest.qWait(100)
        before_rotation = copy.deepcopy(Clip.get(id=created_id).data["rotation"])
        preview = window.videoPreview
        preview.mouse_pressed = True
        preview.mouse_dragging = True
        preview.transform_mode = "rotation"
        preview.rotation_drag_value = 386
        point = controller.geometry(Clip.get(id=created_id).data).map(QPointF(100, 20)).toPoint()
        QTest.mouseDClick(preview, Qt.LeftButton, pos=point)
        checks.assertTrue(controller.draft is not None and not preview.mouse_pressed)
        QCoreApplication.sendEvent(preview, QMouseEvent(QEvent.MouseMove, QPointF(point),
                                  Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        QTest.keyClick(controller.editor, Qt.Key_Return)
        for offset in (20, 70, 130):
            QCoreApplication.sendEvent(preview, QMouseEvent(QEvent.MouseMove, QPointF(point) + QPointF(offset, 30),
                                      Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        checks.assertEqual(Clip.get(id=created_id).data["rotation"], before_rotation)
        checks.assertTrue(not preview.mouse_pressed and not preview.mouse_dragging)

        # Cached Project Files and timeline previews are text on opaque black.
        source, _, _ = window.files_model._thumbnail_source_for_file(File.get(id=asset_id))
        image = QImage(source)
        checks.assertTrue(not image.isNull() and image.pixelColor(image.width() // 2, 0).name() == "#000000")
        checks.assertEqual(image.pixelColor(image.width() // 2, 0).alpha(), 255)
        # Rounded corners match the mask used for ordinary media thumbnails.
        checks.assertEqual(image.pixelColor(0, 0).alpha(), 0)
        expected_ratio = info.LIST_ICON_SIZE.width() / info.LIST_ICON_SIZE.height()
        checks.assertLess(abs(image.width() / image.height() - expected_ratio), 0.02)
        checks.assertTrue(not controller.toolbar.bold.icon().isNull() and not controller.toolbar.italic.icon().isNull())
        checks.assertFalse(controller.toolbar.color.text())
        from unittest.mock import patch
        from windows.color_picker import ColorPicker
        controller.begin(created_id)
        with patch("windows.text_style.ColorPicker", wraps=ColorPicker) as picker:
            controller.toolbar.pick_color()
            checks.assertEqual(picker.call_count, 1)
            controller.toolbar.color_picker.reject()
        controller.cancel(return_focus=True)
        checks.assertTrue(window.timeline.clip_painter._direct_text_thumbnail_path(Clip.get(id=created_id)))
        os.remove(source)
        checks.assertTrue(os.path.exists(window.files_model._thumbnail_source_for_file(File.get(id=asset_id))[0]))

        # Project Files offers Edit Text / Duplicate with the Edit Title icons.
        from unittest.mock import patch
        from qt_api import QContextMenuEvent
        from windows.views.menu import StyledContextMenu
        from windows.text_style import TextStyleDialog
        view, model = window.filesView, window.filesView.model()
        row = next(r for r in range(model.rowCount()) if model.data(model.index(r, 5)) == asset_id)
        point = view.visualRect(model.index(row, 0)).center()
        menus = []
        with patch.object(StyledContextMenu, "show_at", autospec=True, side_effect=lambda menu, *a: menus.append(menu)):
            view.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Mouse, point, view.mapToGlobal(point)))
        actions = {a.text(): a for a in menus[-1].actions()}
        checks.assertTrue(not actions["Edit Text…"].icon().isNull() and not actions["Duplicate"].icon().isNull())
        checks.assertEqual(actions["Duplicate"].icon().cacheKey(), window.actionDuplicate.icon().cacheKey())

        # Duplicate opens Edit Text on a copy, ready to type; Cancel adds nothing.
        files_before = len(File.filter())
        with patch.object(TextStyleDialog, "exec_", return_value=0):
            actions["Duplicate"].trigger()
        checks.assertEqual(len(File.filter()), files_before)

        def type_copy(dialog):
            checks.assertEqual(dialog.editor.textCursor().selectedText(), "Shared title", "Duplicate is ready to type")
            checks.assertTrue(dialog.editor.hasFocus() or not dialog.isVisible())
            # On HiDPI screens the preview is drawn at device pixels, not stretched.
            with patch.object(dialog.preview, "devicePixelRatioF", return_value=2.0):
                dialog.render_preview()
            pixmap = dialog.preview.pixmap()
            shown = pixmap.width() / pixmap.devicePixelRatio()
            checks.assertTrue(pixmap.devicePixelRatio() == 2.0 and pixmap.width() > 1.9 * shown)
            checks.assertLessEqual(shown, dialog.preview.width() - 24)
            dialog.toolbar.alignment.button(0).click()
            checks.assertTrue(dialog.style()["alignment"] == "left" and not dialog.toolbar.more.isVisible())
            dialog.editor.insertPlainText("Independent")
            QTest.keyClick(dialog.editor, Qt.Key_Return, Qt.ControlModifier)
            checks.assertEqual(dialog.result(), QDialog.Accepted, "Ctrl+Enter applies the dialog")
            checks.assertEqual(dialog.editor.toPlainText(), "Independent")
            return 1
        with patch.object(TextStyleDialog, "exec_", new=type_copy):
            duplicate = controller.duplicate_file(asset_id)
        checks.assertTrue(duplicate.id != asset_id and len(File.filter()) == files_before + 1)
        checks.assertEqual(File.get(id=duplicate.id).data["text"], "Independent")
        checks.assertEqual(File.get(id=duplicate.id).data["name"], "Independent")
        checks.assertEqual(File.get(id=duplicate.id).data["direct_text"]["alignment"], "left")
        checks.assertEqual(File.get(id=asset_id).data["text"], "Shared title")
        app.updates.undo()
        checks.assertIsNone(File.get(id=duplicate.id), "Duplicating is one undo step")
        app.updates.redo()
        # Unchanged text keeps a distinguishable name.
        with patch.object(TextStyleDialog, "exec_", return_value=1):
            same = controller.duplicate_file(asset_id)
        checks.assertTrue(same.data["text"] == "Shared title" and same.data["name"].endswith("(copy)"))
        app.updates.undo()

        # Edit Text changes the source in place.
        def edit(dialog):
            dialog.editor.setPlainText("Edited copy")
            return 1
        with patch.object(TextStyleDialog, "exec_", new=edit):
            controller.edit_file(duplicate.id)
        checks.assertEqual(File.get(id=duplicate.id).data["text"], "Edited copy")
        checks.assertEqual(len(File.filter()), files_before + 1)

        # Several selected texts: Edit Style changes only what was changed,
        # on all of them, and keeps each text's own words in one undo step.
        from qt_api import QItemSelectionModel
        selection = window.files_model.selection_model
        selection.clearSelection()
        for fid in (asset_id, duplicate.id):
            r = next(r for r in range(model.rowCount()) if model.data(model.index(r, 5)) == fid)
            selection.select(model.index(r, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)
        menus.clear()
        with patch.object(StyledContextMenu, "show_at", autospec=True, side_effect=lambda menu, *a: menus.append(menu)):
            view.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Mouse, point, view.mapToGlobal(point)))
        actions = {a.text(): a for a in menus[-1].actions()}
        checks.assertTrue("Edit Style…" in actions and "Edit Text…" not in actions, list(actions))
        kept = {fid: File.get(id=fid).data["direct_text"]["alignment"] for fid in (asset_id, duplicate.id)}
        checks.assertNotEqual(kept[asset_id], kept[duplicate.id], "Differing styles must survive a shared edit")

        def restyle(dialog):
            checks.assertTrue(not dialog.editor.isEnabled() and dialog.editor.toPlainText() == "Shared title")
            checks.assertEqual(dialog.windowTitle(), "Edit Style")
            dialog.toolbar.size.setValue(77)
            return 1
        with patch.object(TextStyleDialog, "exec_", new=restyle):
            actions["Edit Style…"].trigger()
        for fid, words in ((asset_id, "Shared title"), (duplicate.id, "Edited copy")):
            data = File.get(id=fid).data
            checks.assertEqual(data["direct_text"]["font_size"], 77, data["direct_text"])
            checks.assertTrue(data["text"] == words and data["direct_text"]["alignment"] == kept[fid])
        app.updates.undo()
        checks.assertNotEqual(File.get(id=duplicate.id).data["direct_text"]["font_size"], 77)
        checks.assertNotEqual(File.get(id=asset_id).data["direct_text"]["font_size"], 77)
        app.updates.redo()
        selection.clearSelection()

        # The same on the timeline: Text > Edit Style on several selected text
        # clips styles all of their sources and keeps the selection.
        controller.arm()
        QTest.qWait(300)
        QTest.keyClicks(controller.editor, "Second")
        QTest.keyClick(controller.editor, Qt.Key_Return)
        QTest.qWait(300)
        second_id = controller.last_clip_id
        pair = (created_id, second_id)
        for i, cid in enumerate(pair):
            window.timeline.AddSelectionJS(cid, "clip", i == 0)
        QTest.qWait(100)
        timeline = window.timeline
        target = next(r for r, c, _ in timeline.geometry.iter_clips(viewport=False) if c.id == created_id).center().toPoint()

        def recolor(dialog):
            checks.assertTrue(not dialog.editor.isEnabled() and dialog.windowTitle() == "Edit Style")
            dialog.style_changed("color", "#ff00ff00")
            return 1

        def choose_edit_style(menu, pos):
            text_menu = next(a.menu() for a in menu.actions() if a.text().replace("&", "") == "Text")
            next(a for a in text_menu.actions() if a.text() == "Edit Style…").trigger()
        with patch.object(TextStyleDialog, "exec_", new=recolor), \
                patch.object(StyledContextMenu, "show_at", new=choose_edit_style):
            QTest.mousePress(timeline, Qt.RightButton, Qt.NoModifier, target)
            QTest.mouseRelease(timeline, Qt.RightButton, Qt.NoModifier, target)
        QTest.qWait(200)
        checks.assertEqual([Clip.get(id=cid).data["direct_text"]["color"] for cid in pair], ["#ff00ff00"] * 2, "Edit Style on the timeline styles every selected text clip")
        checks.assertLessEqual(set(pair), set(window.selected_clips), "Edit Style kept only one clip selected")
        checks.assertTrue(all(selected for _, c, selected in timeline.geometry.iter_clips(viewport=False) if c.id in pair))
        app.updates.undo()
        checks.assertNotEqual(Clip.get(id=second_id).data["direct_text"]["color"], "#ff00ff00")
        window.timeline.ClearAllSelections()

        # Native Clip JSON reload and frame generation need no text file.
        import openshot
        data = copy.deepcopy(Clip.get(id=created_id).data)
        native = openshot.Clip()
        native.SetJson(json.dumps(data))
        native.Open()
        frame = native.GetFrame(1)
        checks.assertTrue(frame.GetWidth() > 0 and native.Reader().Name() == "QtTextReader")
        native.Close()
        # Export a real lossless video frame from the native timeline.
        frame = window.timeline_sync.timeline.GetFrame(1)
        export_path = os.path.join(root, "text.mov")
        writer = openshot.FFmpegWriter(export_path)
        writer.SetVideoOptions(True, "png", openshot.Fraction(30, 1), frame.GetWidth(), frame.GetHeight(),
                               openshot.Fraction(1, 1), False, False, 2000000)
        writer.Open()
        writer.WriteFrame(frame)
        writer.Close()
        decoded = openshot.FFmpegReader(export_path)
        decoded.Open()
        checks.assertEqual(decoded.GetFrame(1).GetPixelsBytes(), frame.GetPixelsBytes())
        decoded.Close()
        # A project frame rate change re-keys text readers to the new frames; Undo restores them.
        import openshot as native
        original_fps = copy.deepcopy(app.project.get("fps"))
        window.actionProfile_trigger(native.Profile(os.path.join(info.PROFILES_PATH, "01280x0720p0060_16-09")))
        checks.assertEqual(app.project.get("fps"), {"num": 60, "den": 1})
        checks.assertEqual(File.get(id=asset_id).data["fps"], {"num": 60, "den": 1})
        checks.assertTrue(all(c.data["reader"]["fps"] == {"num": 60, "den": 1} for c in Clip.filter(file_id=asset_id)))
        app.updates.undo()
        checks.assertEqual(app.project.get("fps"), original_fps)
        checks.assertEqual(File.get(id=asset_id).data["fps"], original_fps)
        checks.assertTrue(all(c.data["reader"]["fps"] == original_fps for c in Clip.filter(file_id=asset_id)))
        project_path = os.path.join(root, "text.osp")
        app.project.save(project_path)
        with open(project_path) as stream:
            saved = json.load(stream)
        checks.assertTrue(all(not f.get("path") for f in saved["files"] if f.get("type") == "QtTextReader"))
        shutil.rmtree(os.path.splitext(project_path)[0] + "_assets", ignore_errors=True)
        app.project.load(project_path, interactive=False)
        checks.assertEqual(File.get(id=asset_id).data["text"], "Shared title")
        checks.assertEqual(len(Clip.filter(file_id=asset_id)), 2)
        checks.assertIsNone(controller.draft)
        if os.environ.get("OPENSHOT_TEXT_SCREENSHOT_DIR"):
            QTest.qWait(300)
            window.grab().save(os.path.join(os.environ["OPENSHOT_TEXT_SCREENSHOT_DIR"], "easy-text-committed.png"))
        passed = True
        print("TEXT_WORKFLOW_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()


checks.assertTrue(app.gui())
QTimer.singleShot(2500, verify)
app.exec_()
sys.exit(0 if passed else 1)
