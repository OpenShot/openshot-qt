"""Shared styling controls for preview drafts and generated Project Files assets."""
import copy
import json
import os
import openshot

from qt_api import (Qt, QEvent, QFontMetrics, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QGridLayout, QFontComboBox,
                    QSpinBox, QAbstractSpinBox, QToolButton, QButtonGroup, QIcon, QSize, QRectF, QColor,
                    QDialog, QPushButton, QPlainTextEdit, QLabel, QTimer, QImage, QPixmap, QPainter,
                    QPainterPath, QByteArray, QSvgRenderer, QSizePolicy, pyqtProperty)
from classes.app import get_app
from classes import info
from windows.color_picker import ColorPicker
from classes.direct_text import fit_height, reader_data, reset_style

ALIGNMENTS = ("left", "center", "right")
# Icon artwork is drawn in this color and recolored to match the theme.
ICON_PLACEHOLDER = "#9dccff"


def themed_icon(name, color, size=18):
    with open(os.path.join(info.IMAGES_PATH, name + ".svg"), encoding="utf-8") as svg:
        markup = svg.read().replace(ICON_PLACEHOLDER, QColor(color).name())
    ratio = get_app().devicePixelRatio()
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(markup.encode("utf-8"))).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return QIcon(pixmap)


def swatch_icon(color, outline, size=QSize(18, 18)):
    """A rounded color chip; transparency shows over a checkerboard."""
    ratio = get_app().devicePixelRatio()
    pixmap = QPixmap(int(size.width() * ratio), int(size.height() * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.5, 0.5, size.width() - 1, size.height() - 1), 4, 4)
    painter.setClipPath(path)
    color = QColor(color)
    if color.alpha() < 255:
        cell = 5
        for row in range(0, size.height(), cell):
            for col in range(0, size.width(), cell):
                shade = "#ffffff" if (row // cell + col // cell) % 2 else "#b4b4b4"
                painter.fillRect(col, row, cell, cell, QColor(shade))
    painter.fillPath(path, color)
    painter.setClipping(False)
    painter.setPen(QColor(outline))
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


class TextStyleToolbar(QFrame):
    """Compact text formatting bar, floated over the video preview or embedded in a dialog."""

    def __init__(self, owner, parent=None, roomy=False):
        super().__init__(parent or owner.window)
        self.owner = owner
        self.setObjectName("textStyleBar")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setToolTip(get_app()._tr("Enter to apply text, Shift+Enter for a new line, Escape to cancel"))
        self.loading = False
        self._icon_color = QColor()
        self._color_value = "#ffffff"
        # The dialog's bar has room for larger controls and size arrows.
        self.setProperty("roomy", roomy)
        self.button_size = QSize(33, 31) if roomy else None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*((5, 5, 6, 5) if roomy else (6, 4, 6, 4)))
        layout.setSpacing(9 if roomy else 2)
        self.font = QFontComboBox()
        self.font.setFixedWidth(166 if roomy else 150)
        self.font.setToolTip(get_app()._tr("Font"))
        # Long names show their start rather than scrolling to the end.
        self.font.currentFontChanged.connect(lambda font: self.font.lineEdit().setCursorPosition(0))
        self.size = QSpinBox()
        self.size.setRange(8, 1000)
        if roomy:
            self.size.setFixedWidth(69)
        else:
            self.size.setButtonSymbols(QAbstractSpinBox.NoButtons)
            self.size.setAlignment(Qt.AlignCenter)
            self.size.setFixedWidth(52)
        self.size.setToolTip(get_app()._tr("Font size"))
        if roomy:
            for control in (self.font, self.size):
                control.setFixedHeight(27)
        self.bold = self._button(get_app()._tr("Bold"), checkable=True)
        self.italic = self._button(get_app()._tr("Italic"), checkable=True)
        self.color = self._button(get_app()._tr("Text color"))
        if roomy:
            self.color.setFixedWidth(25)
        self.alignment = QButtonGroup(self)
        self.alignment.setExclusive(True)
        align_buttons = []
        for index, label in enumerate(("Align left", "Align center", "Align right")):
            button = self._button(get_app()._tr(label), checkable=True)
            self.alignment.addButton(button, index)
            align_buttons.append(button)
        self.more = self._button(get_app()._tr("More text options…"))
        groups = [(self.font, self.size), (self.bold, self.italic), (self.color,), align_buttons]
        if not roomy:
            groups[1:3] = [(self.bold, self.italic, self.color)]
            groups.append((self.more,))
        for number, group in enumerate(groups):
            if number:
                self.divider = self._divider()
                layout.addWidget(self.divider)
            for control in group:
                if roomy and control is self.italic:
                    layout.addSpacing(4)
                layout.addWidget(control)
        if roomy:
            self.more.hide()
            layout.addStretch()
        for control in (self.font, self.size, self.font.lineEdit(), self.size.lineEdit()):
            if control is not None:
                control.installEventFilter(self)
        self.font.currentFontChanged.connect(lambda f: self.change("font_family", f.family()))
        self.size.valueChanged.connect(lambda v: self.change("font_size", v))
        self.bold.toggled.connect(lambda v: self.change("font_bold", v))
        self.italic.toggled.connect(lambda v: self.change("font_italic", v))
        self.alignment.buttonToggled.connect(self._alignment_toggled)
        self.color.clicked.connect(self.pick_color)
        self.more.clicked.connect(owner.more_style)
        self.refresh_icons()

    def _button(self, tooltip, checkable=False):
        button = QToolButton()
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        button.setAutoRaise(True)
        button.setIconSize(QSize(18, 18))
        if self.button_size:
            button.setFixedSize(self.button_size)
            button.setIconSize(QSize(22, 22))
        # Formatting clicks keep the caret in the text being edited.
        button.setFocusPolicy(Qt.NoFocus)
        return button

    def _divider(self):
        line = QFrame()
        line.setObjectName("textStyleDivider")
        line.setFrameShape(QFrame.VLine)
        line.setFixedSize(1, 18)
        holder = QWidget()
        spacing = QHBoxLayout(holder)
        spacing.setContentsMargins(*((3, 0, 3, 0) if self.button_size else (4, 0, 4, 0)))
        spacing.addWidget(line)
        return holder

    def getIconColor(self):
        return self._icon_color

    def setIconColor(self, color):
        # Themes set this from their stylesheet with qproperty-iconColor.
        self._icon_color = QColor(color)
        self.refresh_icons()

    iconColor = pyqtProperty(QColor, getIconColor, setIconColor)

    def refresh_icons(self):
        color = self._icon_color if self._icon_color.isValid() else self.palette().windowText().color()
        size = 22 if self.button_size else 18
        self.bold.setIcon(themed_icon("text-bold", color, size))
        self.italic.setIcon(themed_icon("text-italic", color, size))
        for button, name in zip(self.alignment.buttons(), ALIGNMENTS):
            button.setIcon(themed_icon("text-align-" + name, color, size))
        self.more.setIcon(themed_icon("text-more", color, size))
        self.update_swatch(self._color_value)

    def changeEvent(self, event):
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange):
            self.refresh_icons()
        super().changeEvent(event)

    def eventFilter(self, watched, event):
        if (hasattr(self.owner, "finish") and event.type() in (QEvent.ShortcutOverride, QEvent.KeyPress)
                and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape)
                and not self.font.view().isVisible()):
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

    def _alignment_toggled(self, button, checked):
        if checked:
            self.change("alignment", ALIGNMENTS[self.alignment.id(button)])

    def update_swatch(self, value):
        self._color_value = value
        size = QSize(22, 22) if self.button_size else QSize(18, 18)
        self.color.setIconSize(size)
        self.color.setIcon(swatch_icon(value, self.palette().mid().color(), size))

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
            self.alignment.button(ALIGNMENTS.index(style["alignment"])).setChecked(True)
        finally:
            self.loading = False

    def place(self, avoid=None, margin=8):
        """Float over the top of the parent, or the bottom when that would cover the text."""
        parent = self.parentWidget()
        self.adjustSize()
        x = max(margin, (parent.width() - self.width()) // 2)
        rect = self.rect().translated(x, margin)
        if avoid is not None and rect.intersects(avoid):
            rect.moveBottom(parent.height() - margin - 1)
        self.move(rect.topLeft())
        self.raise_()


class TextStyleDialog(QDialog):
    """Changes stay local until Apply; closing the dialog discards them."""
    PREVIEW_HEIGHTS = (156, 360)

    def __init__(self, style, parent, duplicate=False, count=1, title=None):
        super().__init__(parent)
        self.setObjectName("textStyleDialog")
        self.window = self
        self.draft = copy.deepcopy(style)
        self.setWindowTitle(title or (get_app()._tr("Edit Text") if count < 2 else get_app()._tr("Edit Style")))
        self.setMinimumWidth(560)
        # Slightly larger text than other dialogs; the words being edited larger still.
        self.body_font = self._scaled_font(self.font(), 1.08)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 13, 11, 16)
        layout.setSpacing(8)

        self.preview = QLabel()
        self.preview.setObjectName("textStylePreview")
        self.preview.setFixedHeight(self.PREVIEW_HEIGHTS[0])
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        layout.addWidget(self.preview)
        layout.addSpacing(2)

        # Text: the words and the same style bar shown over the video preview.
        text_section = self._section(layout, 8, (12, 10, 12, 9))
        if count > 1:
            heading = get_app()._tr("Text (first of %d selected)") % count
        else:
            heading = get_app()._tr("Text")
        words = QVBoxLayout()
        words.setSpacing(5)
        words.addWidget(self._heading(heading))
        text_section.addLayout(words)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("textStyleEditor")
        self.editor.setPlaceholderText(get_app()._tr("Type your text"))
        self.editor.setFont(self._scaled_font(self.body_font, 1.11))
        self.editor.setFixedHeight(61)
        self.editor.setPlainText(self.draft.get("text", ""))
        # Several texts share one style edit; each keeps its own words.
        self.editor.setEnabled(count < 2)
        words.addWidget(self.editor)
        self.toolbar = TextStyleToolbar(self, self, roomy=True)
        self.toolbar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.toolbar.set_style(self.draft)
        text_section.addWidget(self.toolbar)

        # Box: colors on the left, sizes on the right.
        box_section = self._section(layout, 7, (12, 8, 12, 12))
        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        title_row.addWidget(self._heading(get_app()._tr("Box")))
        title_row.addWidget(self._line(QFrame.HLine), 1)
        box_section.addLayout(title_row)
        grid = QGridLayout()
        grid.setContentsMargins(2, 0, 10, 0)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(9)
        # Label columns fit the longest label in this language and font.
        metrics = QFontMetrics(self.body_font)
        left = max(metrics.horizontalAdvance(get_app()._tr(label))
                   for label in ("Background", "Text outline", "Border", "Box width"))
        right = max(metrics.horizontalAdvance(get_app()._tr(label))
                    for label in ("Padding", "Width", "Letter spacing"))
        for column, width in ((0, max(83, left + 8)), (2, 20), (4, 22), (5, max(96, right + 6))):
            grid.setColumnMinimumWidth(column, width)
        grid.setColumnStretch(7, 1)
        self.swatches = {}
        self.spins = {}
        rows = (("background", "Background", "padding", "Padding", 0, 200),
                ("stroke_color", "Text outline", "stroke_width", "Width", 0, 30),
                ("border_color", "Border", "border_width", "Width", 0, 30))
        for row, (color_key, color_label, number_key, number_label, minimum, maximum) in enumerate(rows):
            grid.addWidget(QLabel(get_app()._tr(color_label)), row, 0)
            swatch = QToolButton()
            swatch.setObjectName("textStyleSwatch")
            swatch.setToolTip(get_app()._tr("Choose color"))
            swatch.setFixedSize(34, 24)
            swatch.setIconSize(QSize(28, 18))
            swatch.clicked.connect(lambda checked=False, k=color_key: self.pick_color(k))
            self.swatches[color_key] = swatch
            grid.addWidget(swatch, row, 1)
            grid.addWidget(QLabel(get_app()._tr(number_label)), row, 5)
            grid.addWidget(self._spin(number_key, minimum, maximum), row, 6)
        grid.addWidget(QLabel(get_app()._tr("Box width")), len(rows), 0)
        grid.addWidget(self._spin("width", 64, 8192), len(rows), 1)
        grid.addWidget(QLabel(get_app()._tr("Letter spacing")), len(rows), 5)
        grid.addWidget(self._spin("letter_spacing", -50, 200), len(rows), 6)
        grid.addWidget(self._line(QFrame.VLine), 0, 3, len(rows) + 1, 1, Qt.AlignHCenter)
        box_section.addLayout(grid)
        self.update_swatches()

        layout.addSpacing(4)
        footer = QHBoxLayout()
        footer.setContentsMargins(6, 0, 0, 0)
        footer.setSpacing(12)
        if count > 1:
            note = get_app()._tr("Style changes apply to all %d selected texts.") % count
        elif duplicate:
            note = get_app()._tr("Apply adds this copy to Project Files.")
        else:
            note = get_app()._tr("Changes apply to every clip that uses this text.")
        footer.addWidget(self._muted(note), 1)
        defaults = QPushButton(get_app()._tr("Restore Defaults"))
        defaults.setObjectName("textStyleLink")
        defaults.setToolTip(get_app()._tr("Restore the default font, size and colors, keeping the text"))
        defaults.clicked.connect(self.restore_defaults)
        footer.addWidget(defaults)
        cancel = QPushButton(get_app()._tr("Cancel"))
        cancel.setObjectName("textStyleLink")
        cancel.setProperty("dialogRole", "cancel")
        cancel.clicked.connect(self.reject)
        apply = QPushButton(get_app()._tr("Apply"))
        apply.setObjectName("acceptButton")
        apply.setProperty("dialogRole", "primary")
        apply.setDefault(True)
        apply.setMinimumSize(71, 33)
        apply.clicked.connect(self.accept)
        apply.setToolTip(get_app()._tr("Apply (Ctrl+Enter)"))
        footer.addWidget(cancel)
        footer.addWidget(apply)
        layout.addLayout(footer)

        # The theme's stylesheet sets fonts per widget, so a dialog font would not reach them.
        from qt_api import QAbstractButton, QAbstractSpinBox as SpinBox, QComboBox
        for widget in self.findChildren((QLabel, QAbstractButton, SpinBox, QComboBox)):
            if widget.objectName() != "textStyleHeading":
                widget.setFont(self.body_font)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)
        self.editor.textChanged.connect(lambda: self.preview_timer.start(100))
        self.preview_timer.start(0)
        self.editor.installEventFilter(self)
        if count < 2:
            self.editor.setFocus()
            self.editor.selectAll()
        else:
            apply.setFocus()

    def eventFilter(self, watched, event):
        # Enter types a new line in the editor; Ctrl+Enter applies (ahead of
        # any main window shortcut bound to the same keys).
        if (watched is self.editor and event.type() in (QEvent.ShortcutOverride, QEvent.KeyPress)
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and event.modifiers() & Qt.ControlModifier):
            if event.type() == QEvent.ShortcutOverride:
                event.accept()
            else:
                self.accept()
            return True
        return super().eventFilter(watched, event)

    def _section(self, layout, spacing, margins):
        """A rounded card holding one group of settings."""
        frame = QFrame()
        frame.setObjectName("textStyleSection")
        layout.addWidget(frame)
        section = QVBoxLayout(frame)
        section.setContentsMargins(*margins)
        section.setSpacing(spacing)
        return section

    def _line(self, shape):
        line = QFrame()
        line.setObjectName("textStyleRule")
        line.setFrameShape(shape)
        if shape == QFrame.HLine:
            line.setFixedHeight(1)
        else:
            line.setFixedWidth(1)
        return line

    def _heading(self, text):
        label = QLabel(text)
        label.setObjectName("textStyleHeading")
        label.setFont(self._scaled_font(self.body_font, 1.1))
        label.setFixedHeight(19)
        return label

    @staticmethod
    def _scaled_font(font, factor):
        font = type(font)(font)
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() * factor)
        else:
            font.setPixelSize(round(font.pixelSize() * factor))
        return font

    def _muted(self, text):
        label = QLabel(text)
        label.setWordWrap(True)
        palette = label.palette()
        text_color, window = palette.windowText().color(), palette.window().color()
        muted = QColor(*(round(a * 0.7 + b * 0.3) for a, b in zip(text_color.getRgb()[:3], window.getRgb()[:3])))
        label.setStyleSheet("color: %s;" % muted.name())
        return label

    def _spin(self, key, minimum, maximum):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(" px")
        spin.setFixedSize(164, 26)
        spin.setValue(int(self.draft.get(key, 0)))
        spin.valueChanged.connect(lambda value, k=key: self.style_changed(k, value))
        self.spins[key] = spin
        return spin

    def restore_defaults(self):
        project = get_app().project
        self.draft = reset_style(self.style(), project.get("width"), project.get("height"))
        self.toolbar.set_style(self.draft)
        for key, spin in self.spins.items():
            spin.blockSignals(True)
            spin.setValue(int(self.draft.get(key, 0)))
            spin.blockSignals(False)
        self.update_swatches()
        self.preview_timer.start(0)

    def update_swatches(self):
        for key, swatch in self.swatches.items():
            swatch.setIcon(swatch_icon(self.draft.get(key, "#00000000"), self.palette().mid().color(), QSize(28, 18)))

    def style(self):
        result = copy.deepcopy(self.draft)
        result["text"] = self.editor.toPlainText()
        return result

    def style_changed(self, key, value):
        self.draft[key] = value
        self.update_swatches()
        self.preview_timer.start(100)

    def pick_color(self, key):
        self.color_picker = ColorPicker(QColor(self.draft.get(key, "#ffffff")), parent=self,
                                        title=get_app()._tr("Select a Color"),
                                        callback=lambda color: self.style_changed(key, color.name(QColor.HexArgb)))

    def render_preview(self):
        style = fit_height(self.style())
        # The scale follows only the box width, so a bigger font looks bigger.
        # The preview grows with the text, and only very tall text is fit.
        margin = 24
        shortest, tallest = self.PREVIEW_HEIGHTS
        fit = min(1.0, (self.preview.width() - margin) / style["width"],
                  (tallest - margin) / style["height"])
        self.preview.setFixedHeight(max(shortest, min(tallest, round(style["height"] * fit) + margin)))
        # Draw at the exact device pixels shown, using the native reader's
        # preview raster scale so layout matches the video, then display sharp.
        ratio = self.preview.devicePixelRatioF()
        scale = max(fit * ratio, 0.01)
        reader = openshot.QtTextReader()
        reader.SetJson(json.dumps(reader_data(style, {"num": 30, "den": 1})))
        timeline = openshot.Timeline(style["width"], style["height"], openshot.Fraction(30, 1),
                                     44100, 2, openshot.LAYOUT_STEREO)
        clip = openshot.Clip(reader)
        clip.scale = openshot.SCALE_NONE
        clip.ParentTimeline(timeline)
        timeline.preview_width = max(1, round(style["width"] * scale))
        timeline.preview_height = max(1, round(style["height"] * scale))
        reader.Open()
        try:
            frame = reader.GetFrame(1)
            image = QImage(frame.GetPixelsBytes(), frame.GetWidth(), frame.GetHeight(),
                           frame.GetWidth() * 4, QImage.Format_RGBA8888_Premultiplied).copy()
        finally:
            reader.Close()
            # The clip points at the reader and timeline; release it first.
            del clip
        image.setDevicePixelRatio(ratio)
        self.preview.setPixmap(QPixmap.fromImage(image))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.preview_timer.start(50)

    def more_style(self):
        pass
