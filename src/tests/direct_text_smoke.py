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
from qt_api import QTimer, Qt, QPointF, QT_API, QImage
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
        window.actionText.trigger()
        assert controller.draft is not None and controller.editor.hasFocus()
        assert app.focusWidget() is controller.view, "Real key events must reach the text view"
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

        # Standalone editor edits a source without needing any timeline use.
        controller.duplicate_file(asset_id)
        duplicate = next(f for f in File.filter() if f.id != asset_id)
        from windows.text_style import TextStyleDialog
        dialog = TextStyleDialog(duplicate.data["direct_text"], window)
        dialog.editor.setPlainText("Independent")
        from unittest.mock import patch
        with patch("windows.text_style.TextStyleDialog", return_value=dialog), patch.object(dialog, "exec_", return_value=1):
            controller.edit_file(duplicate.id)
        assert File.get(id=duplicate.id).data["text"] == "Independent"
        assert File.get(id=asset_id).data["text"] == "Shared title"

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
