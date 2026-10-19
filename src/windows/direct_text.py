"""In-preview text editing. Graphics proxy mapping preserves caret/IME at rotation."""
import copy
import json

from qt_api import (
    Qt, QEvent, QGraphicsScene, QGraphicsView, QTextEdit, QFrame, QPalette,
    QColor, QAbstractButton,
    QTextCursor, QRectF, QPointF, QObject, QTimer, QImage, QPixmap, QRunnable, QThreadPool, pyqtSignal,
)
from classes.app import get_app
from classes import info
from classes.query import Clip, Track, File
from classes.direct_text import default_text, apply_text, new_text_clip, text_document, save_text_asset, TEXT_ANIMATED, evaluated_text_style, set_text_keyframe


class SnapshotSignals(QObject):
    ready = pyqtSignal(object, int, str)


class SnapshotTask(QRunnable):
    """Worker owns all readers; canceled generations never touch UI/native preview."""
    def __init__(self, data, frame, width, height, generation, canceled):
        super().__init__()
        self.data, self.frame, self.width, self.height = data, frame, width, height
        self.generation, self.canceled = generation, canceled
        self.signals = SnapshotSignals()

    def run(self):
        if self.canceled.is_set():
            return
        import openshot
        native = None
        try:
            data = self.data
            fps = data["fps"]
            native = openshot.Timeline(data["width"], data["height"],
                                       openshot.Fraction(fps["num"], fps["den"]),
                                       data["sample_rate"], data["channels"], data["channel_layout"])
            native.SetJson(json.dumps(data))
            if self.canceled.is_set():
                return
            native.SetMaxSize(self.width, self.height)
            native.Open()
            frame = native.GetFrame(self.frame)
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(),
                           frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
            if not self.canceled.is_set():
                self.signals.ready.emit(image, self.generation, "")
        except Exception as exc:
            if not self.canceled.is_set():
                self.signals.ready.emit(None, self.generation, str(exc))
        finally:
            if native is not None:
                try:
                    native.Close()
                except Exception:
                    # Reader destruction must not unwind across QRunnable.run.
                    pass


class TextPreviewView(QGraphicsView):
    """Paint the established native transform handles above the caret layer."""
    def __init__(self, owner):
        super().__init__(owner.preview)
        self.owner = owner

    def mousePressEvent(self, event):
        owner = self.owner
        if owner is not None and owner.draft is not None:
            point = owner.proxy.mapFromScene(self.mapToScene(event.pos()))
            if not owner.proxy.contains(point):
                # Clicking away keeps the text and returns to transform mode.
                event.accept()
                owner.finish(commit=True)
                return
        super().mousePressEvent(event)

    def drawForeground(self, painter, rect):
        owner = self.owner
        if owner is None or owner.draft is None:
            return
        painter.save()
        painter.setTransform(owner.proxy.sceneTransform())
        from qt_api import QPen
        painter.setBrush(Qt.NoBrush)
        border = float(owner.draft.get("border_width", 0))
        if border:
            painter.setPen(QPen(QColor(owner.draft.get("border_color", "#ffffff")), border))
            painter.drawRect(QRectF(border / 2, border / 2,
                                   owner.draft["width"] - border, owner.draft["height"] - border))
        painter.restore()
        # Typing and clip transforms are separate modes. Show the text box,
        # without presenting resize/rotation handles that are inactive here.
        painter.save()
        painter.setTransform(owner.proxy.sceneTransform())
        pen = QPen(QColor("#66baff"), 1, Qt.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(0, 0, owner.draft["width"], owner.draft["height"]))
        painter.restore()


class TextEditor(QTextEdit):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setAcceptRichText(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setContentsMargins(0, 0, 0, 0)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAccessibleName(get_app()._tr("Edit Text"))

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride:
            # Native text selection, clipboard and undo belong to this editor.
            # File actions remain available without committing the draft.
            file_keys = (Qt.Key_S, Qt.Key_O, Qt.Key_N, Qt.Key_Q, Qt.Key_E)
            if not (event.key() in file_keys and event.modifiers() & Qt.ControlModifier):
                event.accept()
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.owner.discard()
            event.accept()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.owner.finish(commit=True)
            event.accept()
            return
        super().keyPressEvent(event)


class DirectTextController(QObject):
    def __init__(self, window, preview):
        super().__init__(window)
        self.window = window
        self.preview = preview
        self.armed = False
        self.generation = 0
        self.snapshot_cancel = None
        self.clip_id = None
        self.draft = None
        self.original = None
        self._gui_ready = False
        self._closed = False
        self.reveal_timer = QTimer(self)
        self.reveal_timer.setSingleShot(True)
        self.reveal_timer.timeout.connect(self.reveal_created_clip)
        self.committing = False
        # Tt commits a real clip at once; the typing commit joins that undo step.
        self.created_clip_id = self.create_transaction = None
        self.return_widget = None
        get_app().updates.add_listener(self)

    def _ensure_gui(self):
        if self._gui_ready:
            return
        self._gui_ready = True
        window, preview = self.window, self.preview
        self.snapshot_pool = QThreadPool(self)
        self.snapshot_pool.setMaxThreadCount(1)
        self.view = TextPreviewView(self)
        self.scene = QGraphicsScene(self.view)
        self.view.setScene(self.scene)
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setStyleSheet("background: transparent; border: none;")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.editor = TextEditor(self)
        self.backdrop = self.scene.addPixmap(QPixmap())
        self.backdrop.setZValue(-1)
        self.proxy = self.scene.addWidget(self.editor)
        self.view.hide()
        preview.installEventFilter(self)
        self.view_port = self.view.viewport()
        self.editor.textChanged.connect(self.grow_document)
        from windows.text_style import TextStyleToolbar
        # Floats over the preview so showing it never resizes the video.
        self.toolbar = TextStyleToolbar(self, preview)
        self.toolbar.hide()
        window.PlaySignal.connect(self.cancel)
        window.SeekSignal.connect(self.cancel)

    def arm(self):
        """Create a selected text clip at the playhead, ready for typing."""
        import openshot
        if "document_layout" not in json.loads(openshot.QtTextReader().Json()):
            from qt_api import QMessageBox
            QMessageBox.information(self.window, get_app()._tr("Add Text"),
                                    get_app()._tr("Text editing requires an updated libopenshot library."))
            return
        self.cancel()
        self.window.PauseSignal.emit()
        self.create()

    def apply_property(self, clip_id, key, value):
        """Properties dock entry point; semantic changes never add keyframes."""
        key = key.removeprefix("direct_text.") if hasattr(key, "removeprefix") else key.replace("direct_text.", "", 1)
        if key not in ("text", "font_family", "font_size", "color", "background", "alignment", "width", "font_bold", "font_italic"):
            return False
        clip = Clip.get(id=clip_id)
        if not clip or not clip.data.get("direct_text"):
            return False
        track = Track.get(number=clip.data["layer"])
        if track and track.data.get("lock", False):
            return False
        if key in ("font_bold", "font_italic"):
            value = bool(value)
        style = copy.deepcopy(self.draft if self.clip_id == clip_id and self.draft else clip.data["direct_text"])
        if key in ("font_size", "width"):
            value = max(8 if key == "font_size" else 64, min(1000 if key == "font_size" else 8192, int(value)))
        if key == "alignment" and value not in ("left", "center", "right"):
            return False
        if key in ("color", "background") and not QColor(value).isValid():
            return False
        if self.clip_id == clip_id and self.draft:
            style["text"] = self.editor.toPlainText()
        style[key] = value
        if self.clip_id == clip_id and self.draft is not None:
            self.draft = style
            cursor = self.editor.textCursor()
            self.layout_document()
            self.editor.setTextCursor(cursor)
            self.update_geometry()
        else:
            updates = get_app().updates
            previous = updates.transaction_id
            updates.transaction_id = previous or get_app().project.generate_id()
            try:
                save_text_asset(style, clip.data.get("file_id"))
            finally:
                updates.transaction_id = previous
            self.window.refreshFrameSignal.emit()
        return True

    def create(self, point=None):
        self.armed = False
        self.preview.setCursor(Qt.ArrowCursor)
        project = get_app().project
        # Text belongs above media, never underneath a selected video clip.
        tracks = [t for t in Track.filter() if not t.data.get("lock", False)]
        if not tracks:
            return
        position = self.window._current_timeline_seconds()
        duration = get_app().get_settings().get("default-image-length") or 10.0
        # Next Marker cannot seek past the timeline end, so it stops on the
        # final frame of the last clip. Start after that clip, not over it.
        fps = project.get("fps")
        frame_seconds = float(fps["den"]) / fps["num"]
        ends = [c.data["position"] + c.data["end"] - c.data["start"] for c in Clip.filter()]
        position = max([end for end in ends if position < end <= position + frame_seconds + 1e-6], default=position)
        visible = [c for c in Clip.filter() if c.data["position"] < position + duration
                   and c.data["position"] + c.data["end"] - c.data["start"] > position]
        top_media = max((c.data["layer"] for c in visible), default=-1)
        available = [t for t in tracks if t.data["number"] > top_media]
        if available:
            layer = max(t.data["number"] for t in available)
        elif not visible:
            layer = max(t.data["number"] for t in tracks)
        else:
            layer = max(t.data["number"] for t in Track.filter()) + 1000000
        previous = Clip.get(id=getattr(self, "last_clip_id", None))
        style = copy.deepcopy(previous.data["direct_text"]) if previous and previous.data.get("direct_text") else default_text(project.get("width"), project.get("height"))
        style["text"] = "Text"
        data = new_text_clip(style, info.TITLE_PATH, position, layer, duration)
        data["id"] = project.generate_id()
        if previous:
            self.geometry(previous.data)
            for name in ("location_x", "location_y", "scale_x", "scale_y", "rotation"):
                data[name]["Points"][0]["co"]["Y"] = self.evaluated_transforms[name]
        elif point is not None:
            viewport = self.preview.centeredViewport(self.preview.width(), self.preview.height())
            for name, value in (("location_x", (point.x() - viewport.center().x()) / viewport.width()),
                                ("location_y", (point.y() - viewport.center().y()) / viewport.height())):
                data[name]["Points"][0]["co"]["Y"] = value
        updates = get_app().updates
        previous_transaction = updates.transaction_id
        transaction = updates.transaction_id = previous_transaction or project.generate_id()
        self.committing = True
        try:
            asset = save_text_asset(data["direct_text"])
            data["file_id"] = asset.id
            data["reader"] = copy.deepcopy(asset.data)
            if not Track.get(number=layer):
                track = Track()
                track.data = {"number": layer, "y": 0, "label": "", "lock": False}
                track.save()
            self.window.timeline.update_clip_data(data, only_basic_props=False, ignore_reader=False)
        finally:
            self.committing = False
            updates.transaction_id = previous_transaction
        self.last_clip_id = data["id"]
        self.window.refreshFrameSignal.emit()
        self.begin(data["id"])
        if self.clip_id != data["id"]:
            return
        self.created_clip_id, self.create_transaction = data["id"], transaction
        self.reveal_clip_id = data["id"]
        self.reveal_timer.start(0)

    def reveal_created_clip(self):
        if self._closed or not Clip.get(id=self.reveal_clip_id):
            return
        timeline = self.window.timeline
        begin_layout = getattr(timeline, "begin_properties_layout_change", None)
        if begin_layout:
            from qt_api import QPoint
            left = getattr(timeline, "track_name_width", 0)
            target_x = timeline.mapToGlobal(QPoint(round((left + timeline.width()) / 2), 0)).x()
            position = Clip.get(id=self.reveal_clip_id).data["position"]
            begin_layout((position, target_x))
        else:
            timeline.centerOnPlayhead()
        if hasattr(timeline, "v_scrollbar_position"):
            # Scroll only as far as needed; an already visible track stays put.
            timeline.geometry.mark_dirty()
            timeline.geometry.ensure()
            rect = timeline.geometry.calc_item_rect(Clip.get(id=self.reveal_clip_id), viewport=True)
            top = timeline.ruler_height + 4
            bottom = timeline.height() - timeline.scroll_bar_thickness - 4
            delta = rect.top() - top if rect.top() < top else max(0, rect.bottom() - bottom)
            total = timeline.v_scrollbar_position[2]
            if delta and total:
                span = timeline.v_scrollbar_position[1] - timeline.v_scrollbar_position[0]
                start = max(0.0, min(1.0 - span, timeline.v_scrollbar_position[0] + delta / total))
                timeline.v_scrollbar_position[:2] = [start, start + span]
                timeline.geometry.mark_dirty()
            timeline.update()

    def begin(self, clip_id, draft=None):
        self._ensure_gui()
        focus = get_app().focusWidget()
        # A clicked Tt button is not where the user was working.
        if focus is not None and focus is not self.editor:
            self.return_widget = None if isinstance(focus, QAbstractButton) else focus
        self.cancel()
        self.preview.clearTransformState()
        clip = Clip.get(id=clip_id) if clip_id else None
        self.edit_frame = self.window.preview_thread.current_frame or 1
        if clip:
            track = Track.get(number=clip.data["layer"])
            if track and track.data.get("lock", False):
                return
            # Timeline Edit Text reveals its clip at the playhead before editing.
            self.window.PauseSignal.emit()
            fps = get_app().project.get("fps")
            position = self.window._current_timeline_seconds()
            if not clip.data["position"] <= position < clip.data["position"] + clip.data["end"] - clip.data["start"]:
                self.edit_frame = round(clip.data["position"] * fps["num"] / fps["den"]) + 1
                self.window.SeekSignal.emit(self.edit_frame, True)
        data = copy.deepcopy(clip.data if clip else draft)
        if not data or not data.get("direct_text"):
            return
        self.clip_id = clip_id
        fps = get_app().project.get("fps")
        self.style_frame = self.preview._get_clip_frame_number(clip, float(fps["num"]) / fps["den"]) if clip else 1
        self.draft = evaluated_text_style(data, self.style_frame)
        self.original_style = copy.deepcopy(self.draft)
        self.original = data
        if clip_id:
            self.window.timeline.AddSelectionJS(clip_id, "clip", True)
            self.window.TransformSignal.emit([clip_id])
            table = self.window.propertyTableView
            table.select_item([{"id": clip_id, "type": "clip"}])
            table.clip_properties_model.update_timer.stop()
            table.clip_properties_model.update_item_timeout()
        self.toolbar.set_style(self.draft)
        self.layout_document()
        self.capture_background()
        self.view.show()
        self.view.raise_()
        self.toolbar.show()
        self.update_geometry()
        self.focus_editor()
        # Every way into typing selects the text, so typing replaces it.
        self.editor.selectAll()

    def focus_editor(self):
        """Keys reach a proxied editor only while its view has application focus."""
        self.editor.setFocus(Qt.OtherFocusReason)
        self.view.activateWindow()
        self.view.setFocus(Qt.OtherFocusReason)

    def layout_document(self):
        self.editor.blockSignals(True)
        text_document(self.draft, self.editor.document())
        palette = self.editor.palette()
        palette.setColor(QPalette.Text, QColor(self.draft["color"]))
        palette.setColor(QPalette.Base, QColor(self.draft["background"]))
        self.editor.setPalette(palette)
        self.editor.setStyleSheet("QTextEdit { background: %s; color: %s; padding: 0; border: none; }" % (self.draft["background"], self.draft["color"]))
        self.draft["height"] = max(self.draft["height"], int(self.editor.document().size().height() + 1))
        self.editor.setFixedSize(self.draft["width"], self.draft["height"])
        self.editor.blockSignals(False)

    def geometry(self, data):
        import openshot
        project = get_app().project
        native = openshot.Clip()
        native.SetJson(json.dumps(data))
        try:
            native.Open()
            return self._native_geometry(data, native)
        finally:
            native.Close()

    def _native_geometry(self, data, native):
        project = get_app().project
        fps = project.get("fps")
        frame = self.preview._get_clip_frame_number(type("ClipData", (), {"data": data})(), float(fps["num"]) / fps["den"])
        rate = float(fps["num"]) / fps["den"]
        frame = max(round(data["start"] * rate) + 1, min(frame, max(1, round(data["end"] * rate))))
        self.evaluated_transforms = {name: getattr(native, name).GetValue(frame) for name in ("location_x", "location_y", "scale_x", "scale_y", "rotation")}
        props = json.loads(native.PropertiesJSON(frame))
        self.geometry_props = props
        viewport = self.preview.centeredViewport(self.preview.width(), self.preview.height())
        clip = type("ClipData", (), {"data": data})()
        style = data["direct_text"]
        rect = self.preview._clip_display_rect(style["width"], style["height"], clip, props, viewport)
        self.handler_rect = rect
        self.handler_geometry = self.preview._build_clip_transform(rect.x(), rect.y(), rect.width(), rect.height(), props)
        transform = self.handler_geometry[0]
        from qt_api import QTransform
        transform = QTransform(transform)
        transform.scale(rect.width() / style["width"], rect.height() / style["height"])
        return transform

    def update_geometry(self):
        if self.draft is None:
            return
        self.view.setGeometry(self.preview.rect())
        self.scene.setSceneRect(QRectF(self.preview.rect()))
        data = copy.deepcopy(self.original)
        data["direct_text"] = self.draft
        self.proxy.setTransform(self.geometry(data))
        self.proxy.setOpacity(self.geometry_props.get("alpha", {}).get("value", 1.0))
        viewport = self.preview.centeredViewport(self.preview.width(), self.preview.height())
        image = self.background_image.scaled(viewport.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.backdrop.setPixmap(QPixmap.fromImage(image))
        self.backdrop.setPos(viewport.x(), viewport.y())
        self.view.viewport().update()
        self.toolbar.place(self.proxy.sceneBoundingRect().toAlignedRect())

    def hit(self, point):
        position = self.window._current_timeline_seconds()
        for clip in sorted(Clip.filter(intersect=position), key=lambda c: c.data["layer"], reverse=True):
            if clip.data.get("direct_text"):
                transform = self.geometry(clip.data)
                inverse, invertible = transform.inverted()
                style = clip.data["direct_text"]
                if invertible and QRectF(0, 0, style["width"], style["height"]).contains(inverse.map(QPointF(point))):
                    return clip.id
        return None

    def finish(self, *args, commit=False):
        if self.draft is None:
            return
        if not commit:
            return
        if self.editor.hasFocus():
            get_app().inputMethod().commit()
        style = copy.deepcopy(self.draft)
        style["text"] = self.editor.toPlainText()
        clip = Clip.get(id=self.clip_id) if self.clip_id else None
        if clip and clip.id == self.created_clip_id and not style["text"].strip():
            self.discard()
            return
        if (not self.clip_id and not style["text"].strip()) or (clip and style == self.original_style):
            self.cancel(return_focus=True)
            return
        if self.clip_id and not clip:
            self.cancel(return_focus=True)
            return
        updates = get_app().updates
        previous = updates.transaction_id
        updates.transaction_id = previous or self._creation_transaction() or get_app().project.generate_id()
        self.committing = True
        try:
            shared_style = copy.deepcopy(style)
            if clip:
                for key in TEXT_ANIMATED:
                    shared_style[key] = clip.data["direct_text"].get(key, default_text(1920, 1080)[key])
            asset = File.get(id=clip.data.get("file_id")) if clip else None
            if not asset or shared_style != asset.data["direct_text"]:
                asset = save_text_asset(shared_style, asset.id if asset else None)
            if clip is None:
                data = apply_text(self.original, style)
                data["file_id"] = asset.id
                data["reader"] = copy.deepcopy(asset.data)
                if not Track.get(number=data["layer"]):
                    track = Track()
                    track.data = {"number": data["layer"], "y": 0, "label": "", "lock": False}
                    track.save()
                self.window.timeline.update_clip_data(data, only_basic_props=False, ignore_reader=False)
                clip_id = data["id"]
            else:
                from classes.keyframe_editing import auto_keyframes_enabled
                data = Clip.get(id=clip.id).data
                changed_style = False
                for key in TEXT_ANIMATED:
                    if style.get(key) != self.original_style.get(key):
                        data = set_text_keyframe(data, key, style[key], self.style_frame,
                                                 auto_keyframes_enabled(self.window))
                        changed_style = True
                if changed_style:
                    self.window.timeline.update_clip_data(data, only_basic_props=False, ignore_reader=False)
                clip_id = clip.id
            self.last_clip_id = clip_id
        finally:
            self.committing = False
            updates.transaction_id = previous
        self.cancel(return_focus=True)
        self.window.timeline.AddSelectionJS(clip_id, "clip", True)
        self.window.TransformSignal.emit([clip_id])
        self.window.refreshFrameSignal.emit()
        self.reveal_clip_id = clip_id
        self.reveal_timer.start(0)

    def _creation_transaction(self):
        """The just-created clip's undo step, while it is still the newest one."""
        history = get_app().updates.actionHistory
        if (self.clip_id and self.clip_id == self.created_clip_id and history
                and history[-1].transaction == self.create_transaction):
            return self.create_transaction
        return None

    def discard(self):
        """Escape: abandon typing; a clip Tt just created is removed without history."""
        transaction = self._creation_transaction()
        target = self.return_widget
        self.cancel(return_focus=True)
        if not transaction:
            return
        updates = get_app().updates
        updates.undo()
        # Nothing was added from the user's point of view, so nothing to redo.
        updates.redoHistory = [a for a in updates.redoHistory if a.transaction != transaction]
        updates.update_watchers()
        self.window.refreshFrameSignal.emit()
        # Undo processes events and removes the selection, which drops focus.
        self.return_widget = target
        self.restore_focus()

    def style_changed(self, key, value):
        if self.draft is None:
            return
        self.draft["text"] = self.editor.toPlainText()
        self.draft[key] = value
        cursor = self.editor.textCursor()
        self.layout_document()
        self.editor.setTextCursor(cursor)
        self.update_geometry()

    def duplicate_file(self, file_id):
        """Open Edit Text on a copy; Apply adds it to Project Files, Cancel adds nothing."""
        return self.edit_file(file_id, duplicate=True)

    def edit_file(self, file_id, duplicate=False):
        """Edit one text file, or the shared style of several (file_id may be a list)."""
        from windows.text_style import TextStyleDialog
        file_ids = [file_id] if isinstance(file_id, str) else list(file_id)
        assets = [asset for asset in (File.get(id=fid) for fid in file_ids)
                  if asset and asset.data.get("type") == "QtTextReader"]
        if not assets:
            return
        asset = assets[0]
        if duplicate:
            assets = [asset]
        original = asset.data["direct_text"]
        dialog = TextStyleDialog(original, self.window, duplicate=duplicate, count=len(assets))
        if dialog.exec_():
            style = dialog.style()
            updates = get_app().updates
            previous = updates.transaction_id
            updates.transaction_id = previous or get_app().project.generate_id()
            try:
                if len(assets) > 1:
                    # Only what was changed applies; other differences between
                    # the texts (and their words) are kept.
                    changed = {key: value for key, value in style.items()
                               if key != "text" and value != original.get(key)}
                    for each in assets:
                        merged = copy.deepcopy(each.data["direct_text"])
                        merged.update(copy.deepcopy(changed))
                        result = save_text_asset(merged, each.id)
                    result = assets
                else:
                    result = save_text_asset(style, None if duplicate else asset.id)
                    if duplicate and style["text"] == original["text"]:
                        # Unchanged text would otherwise share the original's name.
                        result.data["name"] = asset.data["name"] + " " + get_app()._tr("(copy)")
                        result.save()
            finally:
                updates.transaction_id = previous
            self.window.refreshFrameSignal.emit()
            return result

    def more_style(self):
        if self.draft is None:
            return
        from windows.text_style import TextStyleDialog
        style = copy.deepcopy(self.draft)
        style["text"] = self.editor.toPlainText()
        dialog = TextStyleDialog(style, self.window)
        if dialog.exec_():
            self.draft = dialog.style()
            self.layout_document()
            self.toolbar.set_style(self.draft)
            self.update_geometry()
        self.focus_editor()

    def capture_background(self):
        """One isolated frame; never alter preview alpha, readers or persisted data."""
        import openshot
        # Use the native preview JSON to retain mapper/proxy configuration.
        # Every reader belongs exclusively to this temporary timeline.
        timeline = self.window.timeline_sync.timeline
        data = json.loads(timeline.Json())
        app_clips = {clip.id: clip.data for clip in Clip.filter()}
        for clip in data.get("clips", []):
            # Native JSON includes runtime FrameMappers, which Clip.SetJson
            # deliberately cannot load. The new timeline installs fresh mappers.
            reader = clip.get("reader", {})
            while reader.get("type") == "FrameMapper":
                reader = reader.get("reader", {})
            clip["reader"] = reader
            current = app_clips.get(clip.get("id"), {})
            if current.get("direct_text"):
                clip["reader"] = copy.deepcopy(current["reader"])
        data["clips"] = [c for c in data.get("clips", []) if c.get("id") != self.clip_id]
        import threading
        self.generation += 1
        self.background_ready = False
        self.snapshot_cancel = threading.Event()
        viewport = self.preview.centeredViewport(self.preview.width(), self.preview.height())
        self.background_image = self.preview.current_image.copy() if self.preview.current_image else QImage(1, 1, QImage.Format_RGBA8888)
        if not self.preview.current_image:
            self.background_image.fill(QColor("#000000"))
        task = SnapshotTask(data, self.edit_frame,
                            max(1, viewport.width()), max(1, viewport.height()), self.generation, self.snapshot_cancel)
        task.signals.ready.connect(self.snapshot_ready)
        # One owned worker bounds concurrent decoding. Canceled queued work exits
        # before creating readers; shutdown drains before the Qt app is destroyed.
        self.snapshot_pool.start(task)

    def snapshot_ready(self, image, generation, error):
        if generation != self.generation or self.draft is None:
            return
        if error:
            from classes.logger import log
            log.warning("Text preview background failed: %s", error)
            self.window.statusBar.showMessage(get_app()._tr("Unable to load text editing background"))
        elif image is not None:
            self.background_ready = True
            self.background_image = image
            self.update_geometry()

    def grow_document(self):
        if self.draft is None:
            return
        height = max(self.draft["height"], int(self.editor.document().size().height() + 1))
        if height != self.draft["height"]:
            before = self.geometry(self.original).map(QPointF(0, 0))
            self.draft["height"] = height
            after = self.geometry(self.original).map(QPointF(0, 0))
            viewport = self.preview.centeredViewport(self.preview.width(), self.preview.height())
            for key, delta, dimension in (("location_x", before.x() - after.x(), viewport.width()),
                                           ("location_y", before.y() - after.y(), viewport.height())):
                points = self.original[key]["Points"]
                if len(points) == 1:
                    offset = delta / max(dimension, 1)
                    points[0]["co"]["Y"] += offset
            self.editor.setFixedHeight(height)
            self.update_geometry()

    def eventFilter(self, watched, event):
        if watched is self.preview and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.update_geometry)
        return False

    def changed(self, action):
        if self.committing:
            return
        if action.type == "load":
            self.cancel()
            self.armed = False
        elif self.clip_id:
            clip = Clip.get(id=self.clip_id)
            if not clip:
                self.cancel()
            elif self.draft is not None:
                if clip.data["direct_text"] != self.original["direct_text"]:
                    cursor = self.editor.textCursor()
                    self.draft = copy.deepcopy(clip.data["direct_text"])
                    self.layout_document()
                    self.editor.setTextCursor(cursor)
                if clip.data.get("text_style_overrides") or self.original.get("text_style_overrides"):
                    evaluated = evaluated_text_style(clip.data, self.style_frame)
                    cursor = self.editor.textCursor()
                    self.draft["text"] = self.editor.toPlainText()
                    for key in TEXT_ANIMATED:
                        if clip.data.get("text_" + key) != self.original.get("text_" + key):
                            self.draft[key] = evaluated[key]
                            self.original_style[key] = evaluated[key]
                    self.layout_document()
                    self.editor.setTextCursor(cursor)
                self.original = copy.deepcopy(clip.data)
                self.update_geometry()

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self.reveal_timer.stop()
        self.cancel()
        app = get_app()
        app.updates.disconnect_listener(self)
        if not self._gui_ready:
            return
        self.window.PlaySignal.disconnect(self.cancel)
        self.window.SeekSignal.disconnect(self.cancel)
        self.preview.removeEventFilter(self)
        self.drain_snapshots()
        # Break the proxy/editor Python cycle before Qt destroys its children.
        self.editor.owner = None
        self.view.owner = None
        self.view.setScene(None)
        self.scene.clear()

    def drain_snapshots(self):
        if self.snapshot_cancel is not None:
            self.snapshot_cancel.set()
        self.snapshot_pool.clear()
        self.snapshot_pool.waitForDone()

    def cancel(self, *args, return_focus=False):
        self.reveal_timer.stop()
        if not self._gui_ready:
            return
        if self.draft is None and not self.view.isVisible() and not return_focus:
            # Seek/Play also land here; outside edit mode the preview's
            # normal transform selection must be left alone.
            return
        self.generation += 1
        if self.snapshot_cancel is not None:
            self.snapshot_cancel.set()
        previous_clip = self.clip_id
        self.draft = self.original = self.clip_id = None
        self.created_clip_id = self.create_transaction = None
        self.preview.clearTransformState()
        self.view.hide()
        self.toolbar.hide()
        if return_focus:
            if previous_clip and Clip.get(id=previous_clip):
                self.window.TransformSignal.emit([previous_clip])
            self.restore_focus()

    def restore_focus(self):
        target, self.return_widget = self.return_widget, None
        try:
            usable = target is not None and target.isVisible() and target.isEnabled()
        except RuntimeError:
            # The widget focused before editing has since been destroyed.
            usable = False
        (target if usable else self.window.timeline).setFocus(Qt.OtherFocusReason)
