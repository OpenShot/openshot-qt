"""Shared styling controls for preview drafts and generated Project Files assets."""
import copy
import json
import os
import openshot

from qt_api import (Qt, QEvent, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QFontComboBox,
                    QSpinBox, QToolButton, QIcon, QSize, QComboBox, QPushButton, QColor,
                    QDialog, QDialogButtonBox, QTextEdit, QPalette, QLabel, QTimer, QImage, QPixmap, QSizePolicy)
from classes.app import get_app
from classes import info
from windows.color_picker import ColorPicker
from classes.direct_text import text_document, reader_data


class TextStyleToolbar(QWidget):
    def __init__(self, owner):
        super().__init__(owner.window)
        self.owner = owner
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setToolTip(get_app()._tr("Enter to apply text, Shift+Enter for a new line, Escape to cancel"))
        self.loading = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.font = QFontComboBox()
        self.font.setMaximumWidth(140)
        self.font.setToolTip(get_app()._tr("Font"))
        self.size = QSpinBox()
        self.size.setRange(8, 1000)
        self.size.setToolTip(get_app()._tr("Font size"))
        self.bold = QToolButton()
        self.bold.setCheckable(True)
        self.bold.setIcon(QIcon(os.path.join(info.IMAGES_PATH, "text-bold.svg")))
        self.bold.setToolTip(get_app()._tr("Bold"))
        self.italic = QToolButton()
        self.italic.setCheckable(True)
        self.italic.setIcon(QIcon(os.path.join(info.IMAGES_PATH, "text-italic.svg")))
        self.italic.setToolTip(get_app()._tr("Italic"))
        self.color = QToolButton()
        self.color.setToolTip(get_app()._tr("Text color"))
        self.color.setIconSize(QSize(32, 20))
        self.alignment = QComboBox()
        self.alignment.addItems([get_app()._tr(s) for s in ("Left", "Center", "Right")])
        self.more = QPushButton(get_app()._tr("More…"))
        for control in (self.font, self.size, self.bold, self.italic, self.color, self.alignment, self.more):
            layout.addWidget(control)
            control.installEventFilter(self)
            if hasattr(control, "lineEdit") and control.lineEdit() is not None:
                control.lineEdit().installEventFilter(self)
        self.font.currentFontChanged.connect(lambda f: self.change("font_family", f.family()))
        self.size.valueChanged.connect(lambda v: self.change("font_size", v))
        self.bold.toggled.connect(lambda v: self.change("font_bold", v))
        self.italic.toggled.connect(lambda v: self.change("font_italic", v))
        self.alignment.currentIndexChanged.connect(lambda i: self.change("alignment", ("left", "center", "right")[i]))
        self.color.clicked.connect(self.pick_color)
        self.more.clicked.connect(owner.more_style)

    def eventFilter(self, watched, event):
        if (hasattr(self.owner, "finish") and event.type() in (QEvent.ShortcutOverride, QEvent.KeyPress)
                and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape)
                and not self.font.view().isVisible() and not self.alignment.view().isVisible()):
            if event.type() == QEvent.ShortcutOverride:
                event.accept()
            elif event.key() == Qt.Key_Escape:
                self.owner.discard()
            else:
                self.size.interpretText()
                self.owner.finish(commit=True)
            return True
        return super().eventFilter(watched, event)

    def change(self, key, value):
        if not self.loading:
            self.owner.style_changed(key, value)

    def update_swatch(self, value):
        swatch = QPixmap(32, 20)
        swatch.fill(QColor(value))
        self.color.setIcon(QIcon(swatch))

    def pick_color(self):
        if self.owner.draft is None:
            return
        def selected(color):
            self.change("color", color.name(QColor.HexArgb))
            self.update_swatch(color)
        self.color_picker = ColorPicker(QColor(self.owner.draft["color"]), parent=self.owner.window,
                                        title=get_app()._tr("Text color"), callback=selected)

    def set_style(self, style):
        from qt_api import QFont
        self.loading = True
        try:
            self.update_swatch(style["color"])
            self.font.setCurrentFont(QFont(style["font_family"]))
            self.size.setValue(style["font_size"])
            self.bold.setChecked(style.get("font_bold", False))
            self.italic.setChecked(style.get("font_italic", False))
            self.alignment.setCurrentIndex(("left", "center", "right").index(style["alignment"]))
        finally:
            self.loading = False


class TextStyleDialog(QDialog):
    """Changes stay local until Apply; closing the dialog discards them."""
    def __init__(self, style, parent):
        super().__init__(parent)
        self.window = self
        self.draft = copy.deepcopy(style)
        self.setWindowTitle(get_app()._tr("Edit Text"))
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        self.toolbar = TextStyleToolbar(self)
        self.toolbar.more.hide()
        self.toolbar.set_style(self.draft)
        layout.addWidget(self.toolbar)
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setStyleSheet("QTextEdit { background: #202020; }")
        layout.addWidget(self.editor)
        self.preview = QLabel()
        self.preview.setFixedHeight(130)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: #000000;")
        layout.addWidget(self.preview)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)
        self.editor.textChanged.connect(lambda: self.preview_timer.start(100))
        form = QFormLayout()
        layout.addLayout(form)
        for key, label in (("background", "Background fill"), ("stroke_color", "Text outline color"),
                           ("border_color", "Border color")):
            button = QPushButton(get_app()._tr("Choose…"))
            button.clicked.connect(lambda checked=False, k=key: self.pick_color(k))
            form.addRow(get_app()._tr(label), button)
        for key, label, maximum in (("padding", "Padding", 200), ("stroke_width", "Text outline width", 30),
                                    ("border_width", "Border width", 30), ("width", "Text box width", 8192)):
            spin = QSpinBox()
            spin.setRange(64 if key == "width" else 0, maximum)
            spin.setValue(int(self.draft.get(key, 0)))
            spin.valueChanged.connect(lambda value, k=key: self.style_changed(k, value))
            form.addRow(get_app()._tr(label), spin)
        layout.addWidget(QLabel(get_app()._tr("Text changes apply to every clip using this Project Files item.")))
        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def style(self):
        result = copy.deepcopy(self.draft)
        result["text"] = self.editor.toPlainText()
        return result

    def refresh(self):
        text_document(self.draft, self.editor.document())
        palette = self.editor.palette()
        palette.setColor(QPalette.Text, QColor(self.draft["color"]))
        self.editor.setPalette(palette)

    def style_changed(self, key, value):
        self.draft["text"] = self.editor.toPlainText()
        self.draft[key] = value
        cursor = self.editor.textCursor()
        self.refresh()
        self.editor.setTextCursor(cursor)

    def pick_color(self, key):
        self.color_picker = ColorPicker(QColor(self.draft.get(key, "#ffffff")), parent=self,
                                        title=get_app()._tr("Select a Color"),
                                        callback=lambda color: self.style_changed(key, color.name(QColor.HexArgb)))

    def render_preview(self):
        style = self.style()
        style["height"] = max(style["height"], int(text_document(style).size().height() + 1))
        reader = openshot.QtTextReader()
        reader.SetJson(json.dumps(reader_data(style)))
        reader.Open()
        try:
            frame = reader.GetFrame(1)
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(),
                           frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
        finally:
            reader.Close()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def more_style(self):
        pass
