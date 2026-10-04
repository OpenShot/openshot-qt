"""In-preview text editing. Graphics proxy mapping preserves caret/IME at rotation."""
import copy
import json

from qt_api import (
    Qt, QEvent, QGraphicsScene, QGraphicsView, QTextEdit, QFrame, QPalette,
    QColor, QFontComboBox, QSpinBox, QComboBox, QPushButton, QLabel, QToolBar,
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
        get_app().updates.add_listener(self)

    def _ensure_gui(self):
        if self._gui_ready:
            return
        self._gui_ready = True
        window, preview = self.window, self.preview
        self.snapshot_pool = QThreadPool(self)
        self.snapshot_pool.setMaxThreadCount(1)
        get_app().focusChanged.connect(self.focus_changed)
        self.view = QGraphicsView(preview)
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
        self.toolbar = QToolBar(get_app()._tr("Text"), window.dockVideoContents)
        window.tabVideo.insertWidget(0, self.toolbar)
        self.toolbar.hide()
        self._controls()
        preview.installEventFilter(self)
        self.view_port = self.view.viewport()
        self.view_port.installEventFilter(self)
        self.editor.textChanged.connect(self.grow_document)
        window.PlaySignal.connect(self.finish)
        window.SeekSignal.connect(self.finish)

    def _controls(self):
        _ = get_app()._tr
        done = QPushButton(_("Done"))
        done.clicked.connect(self.finish)
        self.toolbar.addWidget(done)
        self.family = QFontComboBox()
        self.family.setAccessibleName(_("Font"))
        self.family.setMaximumWidth(150)
        self.family.setToolTip(_("Font"))
        self.toolbar.addWidget(self.family)
        self.size = QSpinBox()
        self.size.setRange(8, 1000)
        self.size.setSuffix(_(" px"))
        self.size.setAccessibleName(_("Font Size"))
        self.size.setToolTip(_("Font Size"))
        self.toolbar.addWidget(self.size)
        self.alignment = QComboBox()
        for label, value in ((_("Left"), "left"), (_("Center"), "center"), (_("Right"), "right")):
            self.alignment.addItem(label, value)
        self.alignment.setAccessibleName(_("Alignment"))
        self.alignment.setToolTip(_("Alignment"))
        self.toolbar.addWidget(self.alignment)
        self.color = QPushButton(_("Text Color"))
        self.color.clicked.connect(self.choose_color)
        self.toolbar.addWidget(self.color)
        self.background = QComboBox()
        self.background.addItem(_("Transparent"), "#00000000")
        self.background.addItem(_("Dark Background"), "#202020")
        self.background.setAccessibleName(_("Background"))
        self.toolbar.addWidget(self.background)
        self.background.currentIndexChanged.connect(self.change_style)
        self.toolbar.addWidget(QLabel(_("Wrap Width")))
        self.wrap = QSpinBox()
        self.wrap.setRange(64, 8192)
        self.wrap.setAccessibleName(_("Wrap Width"))
        self.toolbar.addWidget(self.wrap)
        self.family.currentFontChanged.connect(self.change_style)
        self.size.valueChanged.connect(self.change_style)
        self.alignment.currentIndexChanged.connect(self.change_style)
        self.wrap.valueChanged.connect(self.change_style)

    def choose_color(self):
        from qt_api import QColorDialog
        color = QColorDialog.getColor(QColor(self.draft["color"]), self.window, get_app()._tr("Text Color"))
        if color.isValid():
            self.draft["color"] = color.name()
            self.change_style()

    def arm(self):
        self._ensure_gui()
        self.finish()
        self.armed = True
        self.window.PauseSignal.emit()
        self.preview.setCursor(Qt.IBeamCursor)
        self.window.statusBar.showMessage(get_app()._tr("Click the preview to add text"))

    def create(self, point):
        self.armed = False
        self.preview.setCursor(Qt.ArrowCursor)
        project = get_app().project
        # Prefer the selected unlocked track, otherwise the highest unlocked track.
        selected = Clip.get(id=self.window.selected_clips[0]) if self.window.selected_clips else None
        tracks = [t for t in Track.filter() if not t.data.get("lock", False)]
        if not tracks:
            return
        layer = selected.data["layer"] if selected and any(t.data["number"] == selected.data["layer"] for t in tracks) else max(t.data["number"] for t in tracks)
        style = default_text(project.get("width"), project.get("height"))
        data = new_text_clip(style, info.TITLE_PATH, self.window._current_timeline_seconds(), layer,
                             get_app().get_settings().get("default-image-length") or 10.0)
        viewport = self.preview.centeredViewport(self.preview.width(), self.preview.height())
        for name, value in (("location_x", (point.x() - viewport.center().x()) / viewport.width()),
                            ("location_y", (point.y() - viewport.center().y()) / viewport.height())):
            data[name]["Points"][0]["co"]["Y"] = value
        # Creating and entering text is one transaction, saved only on Done.
        self.begin(None, data)

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
        for widget in (self.family, self.size, self.alignment, self.wrap, self.background):
            widget.blockSignals(True)
        from qt_api import QFont
        self.family.setCurrentFont(QFont(self.draft["font_family"]))
        self.size.setValue(self.draft["font_size"])
        self.wrap.setValue(self.draft["width"])
        self.background.setCurrentIndex(self.background.findData(self.draft["background"]))
        self.alignment.setCurrentIndex(self.alignment.findData(self.draft["alignment"]))
        for widget in (self.family, self.size, self.alignment, self.wrap, self.background):
            widget.blockSignals(False)
        self.layout_document()
        self.capture_background()
        self.toolbar.show()
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
        self.editor.setStyleSheet("QTextEdit { background: %s; color: %s; padding: 0; }" % (self.draft["background"], self.draft["color"]))
        self.draft["height"] = max(self.draft["height"], int(self.editor.document().size().height() + 1))
        self.editor.setFixedSize(self.draft["width"], self.draft["height"])
        self.editor.blockSignals(False)

    def change_style(self, *args):
        if not self.draft:
            return
        self.draft.update(text=self.editor.toPlainText(), font_family=self.family.currentFont().family(),
                          font_size=self.size.value(), alignment=self.alignment.currentData(), width=self.wrap.value(), background=self.background.currentData())
        cursor_position = self.editor.textCursor().position()
        self.layout_document()
        cursor = self.editor.textCursor()
        cursor.setPosition(min(cursor_position, len(self.draft["text"])))
        self.editor.setTextCursor(cursor)
        self.update_geometry()
        self.editor.setFocus(Qt.OtherFocusReason)

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
        props = json.loads(native.PropertiesJSON(frame))
        self.geometry_props = props
        viewport = self.preview.centeredViewport(self.preview.width(), self.preview.height())
        clip = type("ClipData", (), {"data": data})()
        style = data["direct_text"]
        rect = self.preview._clip_display_rect(style["width"], style["height"], clip, props, viewport)
        transform = self.preview._build_clip_transform(rect.x(), rect.y(), rect.width(), rect.height(), props)[0]
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
                or new is self.toolbar or self.toolbar.isAncestorOf(new)):
            return
        # A color dialog temporarily owns focus while retaining this edit.
        if get_app().activeModalWidget() is not None:
            return
        self.finish()

    def eventFilter(self, watched, event):
        if watched is self.preview and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self.update_geometry)
        if watched is self.view_port and event.type() == QEvent.MouseButtonPress:
            point = self.view.mapToScene(event.pos())
            if self.draft is not None and not self.proxy.contains(self.proxy.mapFromScene(point)):
                self.finish()
                return True
        return False

    def changed(self, action):
        if action.type == "load":
            self.cancel()
            self.armed = False
        elif self.clip_id and not Clip.get(id=self.clip_id):
            self.cancel()

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self.finish()
        self.cancel()
        app = get_app()
        app.updates.disconnect_listener(self)
        if not self._gui_ready:
            return
        app.focusChanged.disconnect(self.focus_changed)
        self.window.PlaySignal.disconnect(self.finish)
        self.window.SeekSignal.disconnect(self.finish)
        self.preview.removeEventFilter(self)
        self.view_port.removeEventFilter(self)
        self.drain_snapshots()
        # Break the proxy/editor Python cycle before Qt destroys its children.
        self.editor.owner = None
        self.view.setScene(None)
        self.scene.clear()

    def drain_snapshots(self):
        if self.snapshot_cancel is not None:
            self.snapshot_cancel.set()
        self.snapshot_pool.clear()
        self.snapshot_pool.waitForDone()

    def cancel(self):
        if not self._gui_ready:
            return
        self.generation += 1
        if self.snapshot_cancel is not None:
            self.snapshot_cancel.set()
        self.draft = self.original = self.clip_id = None
        self.view.hide()
        self.toolbar.hide()
