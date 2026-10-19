"""Real application checks for immediate text, shared assets, keyboard focus and persistence."""
import copy
import importlib
import json
import os
import shutil
import sys
import tempfile
import traceback

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
        assert button is not None and window.videoToolbar.widgetForAction(window.actionDirectText) is None
        assert window.actionText in window.menuTitle.actions()
        assert window.timelineToolbar.widgetForAction(window.actionAddMarker).toolButtonStyle() == Qt.ToolButtonIconOnly
        initial_clips, initial_files = len(Clip.filter()), len(File.filter())
        history_count = len(app.updates.actionHistory)
        initial_layers = copy.deepcopy(app.project.get("layers"))
        window.timeline.setFocus()
        preview_size = window.videoPreview.size()
        window.actionText.trigger()
        assert controller.draft is not None and controller.editor.hasFocus()
        # The formatting bar floats over the preview instead of resizing it.
        bar = controller.toolbar
        assert bar.isVisible() and bar.parentWidget() is window.videoPreview
        assert window.videoPreview.size() == preview_size
        text_rect = controller.proxy.sceneBoundingRect().toAlignedRect()
        assert not bar.geometry().intersects(text_rect)
        assert window.videoPreview.rect().contains(bar.geometry())
        bar.place(bar.geometry())
        assert bar.geometry().bottom() == window.videoPreview.height() - 9, "Bar moves below text it would cover"
        controller.update_geometry()
        assert app.focusWidget() is controller.view, "Real key events must reach the text view"
        # Edit mode never paints transform handles under the text box.
        from unittest.mock import patch
        with patch.object(type(window.videoPreview), "drawTransformHandler") as handles:
            window.videoPreview.repaint()
        assert handles.call_count == 0, "Transform handles painted beneath the text editor"
        # The preview's zoom/pan hint never covers the editor or handles.
        from qt_api import QHelpEvent, QEvent

        def tooltip_shown(widget):
            event = QHelpEvent(QEvent.ToolTip, QPoint(5, 5), widget.mapToGlobal(QPoint(5, 5)))
            with patch("windows.video_widget.QToolTip.hideText") as hidden:
                app.sendEvent(widget, event)
            return not hidden.called
        assert not tooltip_shown(window.videoPreview), "Preview tooltip covers the text editor"
        assert not tooltip_shown(controller.view.viewport()), "Preview tooltip covers the text editor"
        if os.environ.get("OPENSHOT_TEXT_SCREENSHOT_DIR"):
            QTest.qWait(300)
            window.grab().save(os.path.join(os.environ["OPENSHOT_TEXT_SCREENSHOT_DIR"], "easy-text-draft.png"))
        # Tt adds a real, selected clip and asset at once, with text selected.
        assert len(Clip.filter()) == initial_clips + 1 and len(File.filter()) == initial_files + 1
        assert controller.clip_id in window.selected_clips
        assert controller.editor.textCursor().selectedText() == "Text"
        QTest.keyClicks(controller.editor, "Discard me")
        QTest.keyClick(controller.editor, Qt.Key_Escape)
        assert controller.draft is None and window.timeline.hasFocus()
        assert len(Clip.filter()) == initial_clips and len(File.filter()) == initial_files
        assert len(app.updates.actionHistory) == history_count and not app.updates.redoHistory
        assert app.project.get("layers") == initial_layers

        QTest.mouseClick(button, Qt.LeftButton)
        assert app.focusWidget() is controller.view, "Clicking Tt must not leave focus on the button"
        QTest.keyClicks(controller.editor, "Hello")
        QTest.keyClick(controller.editor, Qt.Key_Return, Qt.ShiftModifier)
        QTest.keyClicks(controller.editor, "world")
        assert controller.draft is not None
        controller.toolbar.size.setValue(72)
        window.timeline.setFocus()
        QTest.qWait(50)
        assert File.filter()[-1].data["text"] == "Text", "Focus loss committed typing"
        controller.editor.setFocus()
        QTest.keyClick(controller.editor, Qt.Key_Return)
        assert controller.draft is None and window.timeline.hasFocus()
        assert len(Clip.filter()) == initial_clips + 1 and len(File.filter()) == initial_files + 1
        first = Clip.filter()[-1]
        asset = File.get(id=first.data["file_id"])
        assert asset.data["type"] == "QtTextReader" and not asset.data["path"]
        assert asset.data["text"] == "Hello\nworld"
        assert first.data["direct_text"]["font_size"] == 72
        assert first.data["reader"]["type"] == "QtTextReader"
        created_id, asset_id = first.id, asset.id
        # Creation and typing are one undo step.
        app.updates.undo()
        assert Clip.get(id=created_id) is None and File.get(id=asset_id) is None
        app.updates.redo()
        assert Clip.get(id=created_id) and File.get(id=asset_id)

        # Double-clicking the text edits it; clicking outside keeps the typing
        # and returns to transform mode without the formatting bar.
        clip_data = Clip.get(id=created_id).data
        style = clip_data["direct_text"]
        center = controller.geometry(clip_data).map(QPointF(style["width"] / 2, style["height"] / 2)).toPoint()
        QTest.mouseDClick(window.videoPreview, Qt.LeftButton, Qt.NoModifier, center)
        assert controller.clip_id == created_id and controller.toolbar.isVisible()
        assert controller.editor.textCursor().selectedText() == "Hello\u2029world", "Double-click selects all text"
        controller.editor.moveCursor(QTextCursor.End)
        QTest.keyClicks(controller.editor, " again")
        inside = controller.view.mapFromScene(controller.proxy.sceneBoundingRect().center())
        QTest.mouseClick(controller.view.viewport(), Qt.LeftButton, Qt.NoModifier, inside)
        assert controller.draft is not None, "Clicks inside the text keep editing"
        outside = QPoint(5, window.videoPreview.height() - 5)
        QTest.mouseClick(controller.view.viewport(), Qt.LeftButton, Qt.NoModifier, outside)
        assert controller.draft is None and not controller.toolbar.isVisible()
        assert File.get(id=asset_id).data["text"] == "Hello\nworld again"
        assert created_id in window.selected_clips
        assert window.videoPreview.transforming_clip and window.videoPreview.transforming_clip.id == created_id
        # Like any clip, the selection survives the playhead leaving and returning.
        with patch.object(type(window.videoPreview), "drawTransformHandler") as handles:
            window.videoPreview.repaint()
        assert handles.call_count == 1, "Transform mode shows handles after editing"
        fps = app.project.get("fps")
        for frame in (round(30 * fps["num"] / fps["den"]), 1):
            window.SeekSignal.emit(frame, True)
            QTest.qWait(100)
            assert window.videoPreview.transforming_clip and window.videoPreview.transforming_clip.id == created_id, \
                "Seeking cleared the text clip's transform selection"
        with patch.object(type(window.videoPreview), "drawTransformHandler") as handles:
            window.videoPreview.repaint()
        assert handles.call_count == 1, "Seeking cleared the text clip's transform handles"
        assert not tooltip_shown(window.videoPreview), "Preview tooltip covers transform handles"
        app.updates.undo()
        assert File.get(id=asset_id).data["text"] == "Hello\nworld"

        # The clip menu has one Text submenu near the bottom, under Slice.
        from unittest.mock import patch
        app.clipboard().setText("")  # offscreen platforms start without clipboard data
        with patch("windows.views.timeline.StyledContextMenu.show_at", lambda menu, pos: menu):
            menu = window.timeline.ShowClipMenu(created_id)
        titles = [a.text().replace("&", "") for a in menu.actions()]
        assert "Edit Text" not in titles and titles.count("Text") == 1
        text_index = titles.index("Text")
        assert titles.index("Speed") < text_index < titles.index("Properties")
        if "Slice" in titles:
            assert text_index == titles.index("Slice") + 1
        text_menu = menu.actions()[text_index].menu()
        assert [a.text() for a in text_menu.actions()] == ["Edit Text", "Edit Style…"]
        text_menu.actions()[0].trigger()
        assert controller.clip_id == created_id and controller.toolbar.isVisible()
        assert controller.editor.textCursor().selectedText() == "Hello\u2029world", "Edit Text selects all text"
        assert app.focusWidget() is controller.view, "Edit Text is ready to type"
        controller.cancel(return_focus=True)
        with patch("windows.text_style.TextStyleDialog.exec_", return_value=0) as style_dialog:
            text_menu.actions()[1].trigger()
        assert style_dialog.call_count == 1

        # Next Marker stops on the last clip's final frame; Tt continues after it
        # on the same track instead of stacking a new track over that frame.
        assert window.actionText.shortcut().toString() == "Shift+T"
        first = Clip.get(id=created_id)
        first_end = first.data["position"] + first.data["end"] - first.data["start"]
        window.SeekSignal.emit(window.timeline_sync.GetLastFrame(), True)
        QTest.qWait(100)
        window.timeline.setFocus()
        QTest.keyClick(window.timeline, Qt.Key_T, Qt.ShiftModifier)
        following = Clip.get(id=controller.clip_id)
        assert following and following.id != created_id
        assert following.data["layer"] == first.data["layer"]
        assert abs(following.data["position"] - first_end) < 1e-6
        QTest.keyClick(controller.editor, Qt.Key_Escape)
        assert Clip.get(id=following.id) is None and window.timeline.hasFocus()
        window.SeekSignal.emit(1, True)
        QTest.qWait(100)

        # Text above the highest occupied track adds a track; Escape removes it.
        layers_before = copy.deepcopy(app.project.get("layers"))
        QTest.mouseClick(button, Qt.LeftButton)
        assert len(app.project.get("layers")) == len(layers_before) + 1
        controller.toolbar.size.setFocus()
        QTest.keyClick(controller.toolbar.size, Qt.Key_Escape)
        assert controller.draft is None and window.timeline.hasFocus()
        assert app.project.get("layers") == layers_before
        QTest.mouseClick(button, Qt.LeftButton)
        QTest.keyClicks(controller.editor, "Another title")
        controller.toolbar.size.setFocus()
        QTest.keyClick(controller.toolbar.size, Qt.Key_Return)
        assert len(app.project.get("layers")) == len(layers_before) + 1
        app.updates.undo()
        assert app.project.get("layers") == layers_before
        assert len(File.filter()) == initial_files + 1

        # The same addClip path used by a Project Files drag creates an instance.
        window.timeline.addClip(asset_id, QPointF(12.0, 0), first.data["layer"], call_manual_move=False)
        instances = Clip.filter(file_id=asset_id)
        assert len(instances) == 2
        second = next(c for c in instances if c.id != created_id)
        original_transforms = {c.id: {k: copy.deepcopy(c.data[k]) for k in ("position", "scale_x", "rotation")}
                               for c in instances}
        window.timeline.AddSelectionJS(created_id, "clip", True)
        window.timeline.setFocus()
        QTest.qWait(100)
        assert controller.draft is None and window.timeline.hasFocus()
        QTest.keyClick(window.timeline, Qt.Key_Right, Qt.ControlModifier)
        assert controller.draft is None and window.timeline.hasFocus()
        window.timeline.AddSelectionJS(created_id, "clip", True)
        QTest.keyClick(window.timeline, Qt.Key_Return)
        assert controller.draft is not None and controller.editor.hasFocus()
        controller.editor.selectAll()
        QTest.keyClicks(controller.editor, "Shared title")
        QTest.keyClick(controller.editor, Qt.Key_Return)
        assert File.get(id=asset_id).data["text"] == "Shared title"
        for clip in Clip.filter(file_id=asset_id):
            assert clip.data["direct_text"]["text"] == "Shared title"
            assert clip.data["reader"]["text"] == "Shared title"
            assert all(clip.data[k] == v for k, v in original_transforms[clip.id].items())
        engine_clip = next(c for c in json.loads(window.timeline_sync.timeline.Json())["clips"] if c["id"] == created_id)
        engine_reader = engine_clip["reader"]
        while engine_reader.get("type") == "FrameMapper":
            engine_reader = engine_reader["reader"]
        assert engine_reader["text"] == "Shared title"
        app.updates.undo()
        assert File.get(id=asset_id).data["text"] == "Hello\nworld"
        assert all(c.data["reader"]["text"] == "Hello\nworld" for c in Clip.filter(file_id=asset_id))
        app.updates.redo()
        controller.begin(created_id)
        controller.editor.selectAll()
        QTest.keyClicks(controller.editor, "Cancel changes")
        QTest.keyClick(controller.editor, Qt.Key_Escape)
        assert File.get(id=asset_id).data["text"] == "Shared title"
        assert len(Clip.filter(file_id=asset_id)) == 2 and window.timeline.hasFocus()

        # Entering typing after a double-click must end any preview drag.
        from qt_api import QCoreApplication, QMouseEvent, QEvent
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
        assert controller.draft is not None and not preview.mouse_pressed
        QCoreApplication.sendEvent(preview, QMouseEvent(QEvent.MouseMove, QPointF(point),
                                  Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        QTest.keyClick(controller.editor, Qt.Key_Return)
        for offset in (20, 70, 130):
            QCoreApplication.sendEvent(preview, QMouseEvent(QEvent.MouseMove, QPointF(point) + QPointF(offset, 30),
                                      Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        assert Clip.get(id=created_id).data["rotation"] == before_rotation
        assert not preview.mouse_pressed and not preview.mouse_dragging

        # Cached Project Files and timeline previews are text on opaque black.
        source, name, _ = window.files_model._thumbnail_source_for_file(File.get(id=asset_id))
        image = QImage(source)
        assert not image.isNull() and image.pixelColor(image.width() // 2, 0).name() == "#000000"
        assert image.pixelColor(image.width() // 2, 0).alpha() == 255
        # Rounded corners match the mask used for ordinary media thumbnails.
        assert image.pixelColor(0, 0).alpha() == 0
        expected_ratio = info.LIST_ICON_SIZE.width() / info.LIST_ICON_SIZE.height()
        assert abs(image.width() / image.height() - expected_ratio) < 0.02
        assert not controller.toolbar.bold.icon().isNull() and not controller.toolbar.italic.icon().isNull()
        assert not controller.toolbar.color.text()
        from unittest.mock import patch
        from windows.color_picker import ColorPicker
        controller.begin(created_id)
        with patch("windows.text_style.ColorPicker", wraps=ColorPicker) as picker:
            controller.toolbar.pick_color()
            assert picker.call_count == 1
            controller.toolbar.color_picker.reject()
        controller.cancel(return_focus=True)
        assert window.timeline.clip_painter._direct_text_thumbnail_path(Clip.get(id=created_id))
        os.remove(source)
        assert os.path.exists(window.files_model._thumbnail_source_for_file(File.get(id=asset_id))[0])

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
        assert not actions["Edit Text…"].icon().isNull() and not actions["Duplicate"].icon().isNull()
        assert actions["Duplicate"].icon().cacheKey() == window.actionDuplicate.icon().cacheKey()

        # Duplicate opens Edit Text on a copy, ready to type; Cancel adds nothing.
        files_before = len(File.filter())
        with patch.object(TextStyleDialog, "exec_", return_value=0):
            actions["Duplicate"].trigger()
        assert len(File.filter()) == files_before

        def type_copy(dialog):
            assert dialog.editor.textCursor().selectedText() == "Shared title", "Duplicate is ready to type"
            assert dialog.editor.hasFocus() or not dialog.isVisible()
            # On HiDPI screens the preview is drawn at device pixels, not stretched.
            with patch.object(dialog.preview, "devicePixelRatioF", return_value=2.0):
                dialog.render_preview()
            pixmap = dialog.preview.pixmap()
            shown = pixmap.width() / pixmap.devicePixelRatio()
            assert pixmap.devicePixelRatio() == 2.0 and pixmap.width() > 1.9 * shown
            assert shown <= dialog.preview.width() - 24
            dialog.toolbar.alignment.button(0).click()
            assert dialog.style()["alignment"] == "left" and not dialog.toolbar.more.isVisible()
            dialog.editor.insertPlainText("Independent")
            QTest.keyClick(dialog.editor, Qt.Key_Return, Qt.ControlModifier)
            assert dialog.result() == QDialog.Accepted, "Ctrl+Enter applies the dialog"
            assert dialog.editor.toPlainText() == "Independent"
            return 1
        with patch.object(TextStyleDialog, "exec_", new=type_copy):
            duplicate = controller.duplicate_file(asset_id)
        assert duplicate.id != asset_id and len(File.filter()) == files_before + 1
        assert File.get(id=duplicate.id).data["text"] == "Independent"
        assert File.get(id=duplicate.id).data["name"] == "Independent"
        assert File.get(id=duplicate.id).data["direct_text"]["alignment"] == "left"
        assert File.get(id=asset_id).data["text"] == "Shared title"
        app.updates.undo()
        assert File.get(id=duplicate.id) is None, "Duplicating is one undo step"
        app.updates.redo()
        # Unchanged text keeps a distinguishable name.
        with patch.object(TextStyleDialog, "exec_", return_value=1):
            same = controller.duplicate_file(asset_id)
        assert same.data["text"] == "Shared title" and same.data["name"].endswith("(copy)")
        app.updates.undo()

        # Edit Text changes the source in place.
        def edit(dialog):
            dialog.editor.setPlainText("Edited copy")
            return 1
        with patch.object(TextStyleDialog, "exec_", new=edit):
            controller.edit_file(duplicate.id)
        assert File.get(id=duplicate.id).data["text"] == "Edited copy"
        assert len(File.filter()) == files_before + 1

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
        assert "Edit Style…" in actions and "Edit Text…" not in actions, list(actions)
        kept = {fid: File.get(id=fid).data["direct_text"]["alignment"] for fid in (asset_id, duplicate.id)}
        assert kept[asset_id] != kept[duplicate.id], "Differing styles must survive a shared edit"

        def restyle(dialog):
            assert not dialog.editor.isEnabled() and dialog.editor.toPlainText() == "Shared title"
            assert dialog.windowTitle() == "Edit Style"
            dialog.toolbar.size.setValue(77)
            return 1
        with patch.object(TextStyleDialog, "exec_", new=restyle):
            actions["Edit Style…"].trigger()
        for fid, words in ((asset_id, "Shared title"), (duplicate.id, "Edited copy")):
            data = File.get(id=fid).data
            assert data["direct_text"]["font_size"] == 77, data["direct_text"]
            assert data["text"] == words and data["direct_text"]["alignment"] == kept[fid]
        app.updates.undo()
        assert File.get(id=duplicate.id).data["direct_text"]["font_size"] != 77
        assert File.get(id=asset_id).data["direct_text"]["font_size"] != 77
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
            assert not dialog.editor.isEnabled() and dialog.windowTitle() == "Edit Style"
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
        assert [Clip.get(id=cid).data["direct_text"]["color"] for cid in pair] == ["#ff00ff00"] * 2, \
            "Edit Style on the timeline styles every selected text clip"
        assert set(pair) <= set(window.selected_clips), "Edit Style kept only one clip selected"
        assert all(selected for _, c, selected in timeline.geometry.iter_clips(viewport=False) if c.id in pair)
        app.updates.undo()
        assert Clip.get(id=second_id).data["direct_text"]["color"] != "#ff00ff00"
        window.timeline.ClearAllSelections() if hasattr(window.timeline, "ClearAllSelections") else None

        # Native Clip JSON reload and frame generation need no text file.
        import openshot
        data = copy.deepcopy(Clip.get(id=created_id).data)
        native = openshot.Clip()
        native.SetJson(json.dumps(data))
        native.Open()
        frame = native.GetFrame(1)
        assert frame.GetWidth() > 0 and native.Reader().Name() == "QtTextReader"
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
        assert decoded.GetFrame(1).GetPixelsBytes() == frame.GetPixelsBytes()
        decoded.Close()
        # A project frame rate change re-keys text readers to the new frames; Undo restores them.
        import openshot as native
        original_fps = copy.deepcopy(app.project.get("fps"))
        window.actionProfile_trigger(native.Profile(os.path.join(info.PROFILES_PATH, "01280x0720p0060_16-09")))
        assert app.project.get("fps") == {"num": 60, "den": 1}
        assert File.get(id=asset_id).data["fps"] == {"num": 60, "den": 1}
        assert all(c.data["reader"]["fps"] == {"num": 60, "den": 1} for c in Clip.filter(file_id=asset_id))
        app.updates.undo()
        assert app.project.get("fps") == original_fps
        assert File.get(id=asset_id).data["fps"] == original_fps
        assert all(c.data["reader"]["fps"] == original_fps for c in Clip.filter(file_id=asset_id))
        project_path = os.path.join(root, "text.osp")
        app.project.save(project_path)
        with open(project_path) as stream:
            saved = json.load(stream)
        assert all(not f.get("path") for f in saved["files"] if f.get("type") == "QtTextReader")
        shutil.rmtree(os.path.splitext(project_path)[0] + "_assets", ignore_errors=True)
        app.project.load(project_path, interactive=False)
        assert File.get(id=asset_id).data["text"] == "Shared title"
        assert len(Clip.filter(file_id=asset_id)) == 2
        assert controller.draft is None
        if os.environ.get("OPENSHOT_TEXT_SCREENSHOT_DIR"):
            QTest.qWait(300)
            window.grab().save(os.path.join(os.environ["OPENSHOT_TEXT_SCREENSHOT_DIR"], "easy-text-committed.png"))
        passed = True
        print("TEXT_WORKFLOW_PASSED", flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()


assert app.gui()
QTimer.singleShot(2500, verify)
app.exec_()
sys.exit(0 if passed else 1)
