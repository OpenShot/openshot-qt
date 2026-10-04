"""In-preview text editing. Graphics proxy mapping preserves caret/IME at rotation."""
import copy
import json

from qt_api import (
    Qt, QEvent, QGraphicsScene, QGraphicsView, QTextEdit, QFrame, QPalette,
    QColor,
    QTextCursor, QRectF, QPointF, QObject, QTimer, QImage, QPixmap, QRunnable, QThreadPool, pyqtSignal,
)
from classes.app import get_app
from classes import info
from classes.query import Clip, Track
from classes.direct_text import default_text, apply_text, new_text_clip, text_document


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
                           frame.GetWidth() * 4, QImage.Format_RGBA8888).copy()
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

    def drawForeground(self, painter, rect):
        owner = self.owner
        if owner is None or owner.draft is None:
            return
        preview = owner.preview
        if not preview.transforming_clip or preview.transforming_clip.id != owner.clip_id:
            return
        transform, unpacked, origin = owner.handler_geometry
        sx, sy, _, _, _, ox, oy = unpacked
        preview.transform = transform
        preview.originHandle = origin
        painter.save()
        painter.setTransform(transform)
        preview.drawTransformHandler(painter, sx, sy, owner.handler_rect.width(),
                                     owner.handler_rect.height(), ox, oy, skip_origin=True)
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
            # File actions can leave editing and commit before serialization.
            file_keys = (Qt.Key_S, Qt.Key_O, Qt.Key_N, Qt.Key_Q, Qt.Key_E)
            if not (event.key() in file_keys and event.modifiers() & Qt.ControlModifier):
                event.accept()
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or (
                event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier):
            self.owner.finish()
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
        self.forwarded_drag = False
        get_app().updates.add_listener(self)

    def _ensure_gui(self):
        if self._gui_ready:
            return
        self._gui_ready = True
        window, preview = self.window, self.preview
        self.snapshot_pool = QThreadPool(self)
        self.snapshot_pool.setMaxThreadCount(1)
        get_app().focusChanged.connect(self.focus_changed)
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
        window.installEventFilter(self)
        self.view_port = self.view.viewport()
        self.view_port.installEventFilter(self)
        self.editor.textChanged.connect(self.grow_document)
        window.PlaySignal.connect(self.finish)
        window.SeekSignal.connect(self.finish)

    def arm(self):
        """Tt creates a real selected clip immediately, ready for replacement."""
        self.finish()
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
        data = apply_text(clip.data, style, info.TITLE_PATH)
        self.window.timeline.update_clip_data(data, only_basic_props=False)
        painter = getattr(self.window.timeline, "clip_painter", None)
        if painter:
            painter.invalidate_clip_thumbnails(clip_id)
        self.window.refreshFrameSignal.emit()
        if self.clip_id == clip_id and self.draft:
            cursor = self.editor.textCursor()
            self.draft = data["direct_text"]
            self.original = copy.deepcopy(data)
            self.layout_document()
            self.editor.setTextCursor(cursor)
            self.update_geometry()
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
        visible = [c for c in Clip.filter() if c.data["position"] < position + duration
                   and c.data["position"] + c.data["end"] - c.data["start"] > position]
        top_media = max((c.data["layer"] for c in visible), default=-1)
        available = [t for t in tracks if t.data["number"] > top_media]
        if available:
            layer = max(t.data["number"] for t in available)
        elif not visible:
            layer = max(t.data["number"] for t in tracks)
        else:
            track = Track()
            layer = max(t.data["number"] for t in Track.filter()) + 1000000
            track.data = {"number": layer, "y": 0, "label": "", "lock": False}
            track.save()
        previous = Clip.get(id=getattr(self, "last_clip_id", None))
        style = copy.deepcopy(previous.data["direct_text"]) if previous and previous.data.get("direct_text") else default_text(project.get("width"), project.get("height"))
        style["text"] = "Text"
        data = new_text_clip(style, info.TITLE_PATH, self.window._current_timeline_seconds(), layer,
                             get_app().get_settings().get("default-image-length") or 10.0)
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
        self.window.timeline.update_clip_data(data, only_basic_props=False)
        self.window.timeline.AddSelectionJS(data["id"], "clip", True)
        self.window.refreshFrameSignal.emit()
        self.window.dockProperties.show()
        self.begin(data["id"])
        self.editor.selectAll()
        self.reveal_clip_id = data["id"]
        self.reveal_timer.start(0)

    def reveal_created_clip(self):
        if self._closed or self.clip_id != self.reveal_clip_id or not Clip.get(id=self.clip_id):
            return
        timeline = self.window.timeline
        begin_layout = getattr(timeline, "begin_properties_layout_change", None)
        if begin_layout:
            from qt_api import QPoint
            left = getattr(timeline, "track_name_width", 0)
            target_x = timeline.mapToGlobal(QPoint(round((left + timeline.width()) / 2), 0)).x()
            position = Clip.get(id=self.clip_id).data["position"]
            begin_layout((position, target_x))
        else:
            timeline.centerOnPlayhead()
        if hasattr(timeline, "v_scrollbar_position"):
            timeline.geometry.ensure()
            ratio = timeline.v_scrollbar_position[1] - timeline.v_scrollbar_position[0]
            content_height = timeline.v_scrollbar_position[2] or timeline.height()
            clip_rect = timeline.geometry.calc_item_rect(Clip.get(id=self.clip_id))
            top = max(0.0, min((clip_rect.top() - timeline.ruler_height) / max(1, content_height), 1.0 - ratio))
            timeline.v_scrollbar_position[:2] = [top, top + ratio]
            timeline.geometry.mark_dirty()
            timeline.update()

    def begin(self, clip_id, draft=None):
        self._ensure_gui()
        self.finish()
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
        self.draft = data["direct_text"]
        self.original = data
        self.anchor_offsets = {"location_x": 0.0, "location_y": 0.0}
        self.window.timeline.AddSelectionJS(clip_id, "clip", True)
        self.window.TransformSignal.emit([clip_id])
        table = self.window.propertyTableView
        table.select_item([{"id": clip_id, "type": "clip"}])
        table.clip_properties_model.update_timer.stop()
        table.clip_properties_model.update_item_timeout()
        self.layout_document()
        self.capture_background()
        self.view.show()
        self.view.raise_()
        self.update_geometry()
        self.editor.setFocus(Qt.OtherFocusReason)
        self.editor.moveCursor(QTextCursor.End)

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

    def finish(self, *args):
        if self.draft is None:
            return
        if self.editor.hasFocus():
            get_app().inputMethod().commit()
        self.draft["text"] = self.editor.toPlainText()
        data = self.original
        if self.clip_id:
            clip = Clip.get(id=self.clip_id)
            # A deleted clip/project replacement must never be resurrected.
            if not clip:
                self.cancel()
                return
            data = clip.data
        if not self.clip_id or self.draft != data["direct_text"]:
            data = copy.deepcopy(data)
            for key, offset in self.anchor_offsets.items():
                if self.clip_id and offset and len(data[key]["Points"]) == 1:
                    data[key]["Points"][0]["co"]["Y"] += offset
            data = apply_text(data, self.draft, info.TITLE_PATH)
            self.window.timeline.update_clip_data(data, only_basic_props=False)
            self.window.refreshFrameSignal.emit()
        clip_id = data.get("id")
        self.last_clip_id = clip_id
        self.cancel()
        if clip_id:
            # Keep timeline selection and its delayed transform notification in
            # agreement with the text just edited, including preview double-click.
            self.window.timeline.AddSelectionJS(clip_id, "clip", True)
            self.window.TransformSignal.emit([clip_id])

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
                    self.anchor_offsets[key] += offset
            self.editor.setFixedHeight(height)
            self.update_geometry()

    def focus_changed(self, old, new):
        if self.draft is None or new is None:
            return
        if (new is self.editor or self.editor.isAncestorOf(new)
                or new is self.view or self.view.isAncestorOf(new)
                or new is self.window.dockProperties or self.window.dockProperties.isAncestorOf(new)):
            return
        # A color dialog temporarily owns focus while retaining this edit.
        if get_app().activeModalWidget() is not None:
            return
        self.finish()

    def eventFilter(self, watched, event):
        if watched is self.preview and event.type() == QEvent.MouseButtonRelease and self.forwarded_drag:
            self.forwarded_drag = False
            self.preview.releaseMouse()
        if watched is self.window and event.type() == QEvent.WindowDeactivate:
            self.end_forwarded_drag()
        if watched is self.preview and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.update_geometry)
        if watched is self.view_port and event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            point = self.view.mapToScene(event.pos())
            local = self.proxy.mapFromScene(point)
            # Corners and the rectangle edge switch straight into native drag.
            # Interior clicks retain normal QTextEdit caret/selection behavior.
            from math import hypot
            transform = self.proxy.sceneTransform()
            origin = transform.map(QPointF(0, 0))
            unit_x, unit_y = transform.map(QPointF(1, 0)), transform.map(QPointF(0, 1))
            mx = 8 / max(0.001, hypot(unit_x.x() - origin.x(), unit_x.y() - origin.y()))
            my = 8 / max(0.001, hypot(unit_y.x() - origin.x(), unit_y.y() - origin.y()))
            inner = QRectF(0, 0, self.draft["width"], self.draft["height"]).adjusted(mx, my, -mx, -my) if self.draft else QRectF()
            if self.draft is not None and not inner.contains(local):
                self.finish()
                # TransformSignal clears native hit geometry. Repaint now before
                # forwarding this physical press, rather than waiting a frame.
                self.preview.repaint()
                from qt_api import QCoreApplication, QMouseEvent
                QCoreApplication.sendEvent(self.preview, QMouseEvent(QEvent.MouseMove, point, Qt.NoButton, Qt.NoButton, event.modifiers()))
                if self.preview.hover_transform_mode and self.preview.hover_transform_mode.startswith("shear_"):
                    self.preview.hover_transform_mode = "location"
                QCoreApplication.sendEvent(self.preview, QMouseEvent(QEvent.MouseButtonPress, point, event.button(), event.buttons(), event.modifiers()))
                self.forwarded_drag = True
                self.preview.grabMouse()
                return True
        return False

    def end_forwarded_drag(self):
        if not self.forwarded_drag:
            return
        from qt_api import QCoreApplication, QMouseEvent
        QCoreApplication.sendEvent(self.preview, QMouseEvent(QEvent.MouseButtonRelease,
                                  QPointF(self.preview.mouse_position), Qt.LeftButton,
                                  Qt.NoButton, Qt.NoModifier))
        self.forwarded_drag = False
        self.preview.releaseMouse()

    def changed(self, action):
        if action.type == "load":
            self.end_forwarded_drag()
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
                self.original = copy.deepcopy(clip.data)
                self.update_geometry()

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self.reveal_timer.stop()
        self.finish()
        self.cancel()
        app = get_app()
        app.updates.disconnect_listener(self)
        if not self._gui_ready:
            return
        app.focusChanged.disconnect(self.focus_changed)
        self.window.PlaySignal.disconnect(self.finish)
        self.window.SeekSignal.disconnect(self.finish)
        self.end_forwarded_drag()
        self.preview.removeEventFilter(self)
        self.window.removeEventFilter(self)
        self.view_port.removeEventFilter(self)
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

    def cancel(self):
        self.reveal_timer.stop()
        if not self._gui_ready:
            return
        self.generation += 1
        if self.snapshot_cancel is not None:
            self.snapshot_cancel.set()
        self.draft = self.original = self.clip_id = None
        self.view.hide()
