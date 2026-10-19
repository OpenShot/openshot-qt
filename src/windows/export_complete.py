"""Export summary shown in place of the export settings after a successful export."""

import os

from qt_api import (
    QApplication, QByteArray, QColor, QEvent, QFrame, QGridLayout, QHBoxLayout, QIcon, QLabel,
    QLineEdit, QPainter, QPalette, QPixmap, QPushButton, QSize, QSizePolicy, QSvgRenderer, Qt,
    QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from classes.desktop_open import open_file, reveal_file

# Feather-style 24px outline icons, tinted at render time.
ICONS = {
    "check": '<path d="M6 12.5l4 4 8-9" stroke-width="2.6"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "film": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 12h18M3 7.5h4M3 16.5h4'
            'M17 7.5h4M17 16.5h4"/>',
    "quality": '<path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.3 6L12 16.4 6.6 19.4l1.3-6L3.4 9.3l6-.7z"/>',
    "size": '<ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13'
            'M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15'
              'A1.5 1.5 0 0 1 3 18.5z"/>',
    "play": '<path d="M7 4.5v15l12.5-7.5z" fill="{color}"/>',
    "frames": '<rect x="3" y="5" width="13" height="10" rx="1.5"/><path d="M8 19h11.5a1.5 1.5 0 0 0 1.5-1.5V9"/>',
}
SUCCESS = "#2fbf71"
# Mid-tone accents read on both light and dark backgrounds.
ACCENTS = {"file": "#4a9eff", "film": "#a06cf0", "quality": "#f0a020", "size": "#2fbfa0",
           "clock": "#4a9eff", "frames": "#a06cf0"}
VIDEO_CODECS = (("libx264", "H.264"), ("h264", "H.264"), ("libx265", "H.265"), ("hevc", "H.265"),
                ("libvpx-vp9", "VP9"), ("vp9", "VP9"), ("libvpx", "VP8"), ("av1", "AV1"),
                ("libaom", "AV1"), ("libsvtav1", "AV1"), ("prores", "ProRes"), ("dnxhd", "DNxHD"),
                ("mpeg4", "MPEG-4"), ("mpeg2", "MPEG-2"), ("libtheora", "Theora"), ("mjpeg", "MJPEG"))
AUDIO_CODECS = (("aac", "AAC"), ("libmp3lame", "MP3"), ("mp3", "MP3"), ("libvorbis", "Vorbis"),
                ("libopus", "Opus"), ("opus", "Opus"), ("flac", "FLAC"), ("pcm", "PCM"), ("ac3", "AC-3"))


def svg_pixmap(name, color, size, ratio=1.0):
    color = QColor(color).name()
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
           'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + ICONS[name] + '</svg>')
    renderer = QSvgRenderer(QByteArray(svg.replace("{color}", color).encode("utf-8")))
    pixmap = QPixmap(QSize(int(size * ratio), int(size * ratio)))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def success_badge(size, ratio=1.0):
    """A filled success circle with a white check."""
    pixmap = QPixmap(QSize(int(size * ratio), int(size * ratio)))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(SUCCESS))
    painter.drawEllipse(0, 0, pixmap.width(), pixmap.height())
    inset = pixmap.width() * 0.22
    check = svg_pixmap("check", "#ffffff", 24, (pixmap.width() - 2 * inset) / 24.0)
    painter.drawPixmap(int(inset), int(inset), check)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def luma(color):
    """Perceived brightness 0-255 (HSL lightness rates pure blue as mid-gray)."""
    return 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()


def codec_name(codec, table):
    codec = (codec or "").lower()
    for prefix, name in table:
        if codec.startswith(prefix) or prefix in codec:
            return name
    return codec.upper()


def format_label(container, video_codec, audio_codec, kind):
    container = (container or "").upper()
    if kind == "audio":
        codec = codec_name(audio_codec, AUDIO_CODECS)
    else:
        codec = codec_name(video_codec, VIDEO_CODECS)
    if not codec or codec == container:
        return container
    return "%s (%s)" % (container, codec)


def format_size(size):
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return ("%d %s" if unit == "B" else "%.1f %s") % (size, unit)
        size /= 1024.0


def format_duration(seconds):
    seconds = max(0, int(round(seconds)))
    return "%d:%02d:%02d" % (seconds // 3600, (seconds // 60) % 60, seconds % 60)


class InfoCard(QFrame):
    def __init__(self, icon, title, value, parent=None):
        super().__init__(parent)
        self.setObjectName("exportInfoCard")
        self.icon_name = icon
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        self.icon = QLabel(self)
        self.icon.setFixedSize(24, 24)
        layout.addWidget(self.icon, 0, Qt.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.title = QLabel(title, self)
        self.title.setObjectName("exportInfoTitle")
        self.value = QLabel(value, self)
        self.value.setObjectName("exportInfoValue")
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.addWidget(self.title)
        text.addWidget(self.value)
        layout.addLayout(text, 1)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setAccessibleName("%s: %s" % (title, value))

    def refresh_icon(self, light):
        color = QColor(ACCENTS.get(self.icon_name, "#4a9eff"))
        if light:
            color = color.darker(125)
        self.icon.setPixmap(svg_pixmap(self.icon_name, color, 24, self.devicePixelRatioF()))


class ExportCompletePanel(QWidget):
    """Summary of the exported file with quick ways to find or watch it."""

    MAX_COLUMNS = 3

    def __init__(self, translate, parent=None):
        super().__init__(parent)
        _ = self.translate = translate
        self.setObjectName("exportComplete")
        self.path = ""
        self.cards = []
        self.columns = 0
        self.styling = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.banner = QFrame(self)
        self.banner.setObjectName("exportSuccess")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(16, 12, 16, 12)
        banner_layout.setSpacing(14)
        self.badge = QLabel(self.banner)
        self.badge.setFixedSize(40, 40)
        banner_layout.addWidget(self.badge, 0, Qt.AlignVCenter)
        headline = QVBoxLayout()
        headline.setSpacing(2)
        self.headline = QLabel(_("Export Complete"), self.banner)
        self.headline.setObjectName("exportSuccessTitle")
        self.subtitle = QLabel(self.banner)
        self.subtitle.setObjectName("exportSuccessSubtitle")
        self.subtitle.setWordWrap(True)
        headline.addWidget(self.headline)
        headline.addWidget(self.subtitle)
        banner_layout.addLayout(headline, 1)
        layout.addWidget(self.banner)

        self.location_label = QLabel(_("File Location:"), self)
        layout.addWidget(self.location_label)
        location = QHBoxLayout()
        location.setSpacing(6)
        self.location = QLineEdit(self)
        self.location.setObjectName("exportLocation")
        self.location.setReadOnly(True)
        self.location.setAccessibleName(_("File Location"))
        self.location_label.setBuddy(self.location)
        location.addWidget(self.location, 1)
        self.copy_button = QToolButton(self)
        self.copy_button.setObjectName("exportCopyPath")
        self.copy_button.setToolTip(_("Copy Path"))
        self.copy_button.setAccessibleName(_("Copy Path"))
        self.copy_button.setIconSize(QSize(16, 16))
        self.copy_button.clicked.connect(self.copy_path)
        location.addWidget(self.copy_button)
        layout.addLayout(location)

        self.cards_layout = QGridLayout()
        self.cards_layout.setHorizontalSpacing(8)
        self.cards_layout.setVerticalSpacing(8)
        layout.addLayout(self.cards_layout)
        layout.addStretch(1)

        self.divider = QFrame(self)
        self.divider.setObjectName("exportDivider")
        self.divider.setFixedHeight(1)
        layout.addWidget(self.divider)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.reveal_button = QPushButton(_("Open Containing Folder"), self)
        self.reveal_button.setObjectName("exportRevealButton")
        self.reveal_button.setCursor(Qt.PointingHandCursor)
        self.reveal_button.setIconSize(QSize(18, 18))
        self.reveal_button.clicked.connect(self.reveal)
        actions.addWidget(self.reveal_button)
        actions.addStretch(1)
        self.open_button = QPushButton(self)
        self.open_button.setObjectName("exportOpenButton")
        # Themes give dialog primary buttons their accent color.
        self.open_button.setProperty("dialogRole", "primary")
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.setIconSize(QSize(16, 16))
        self.open_button.clicked.connect(self.open)
        actions.addWidget(self.open_button)
        layout.addLayout(actions)

        self.apply_style()

    def show_result(self, path, kind, details):
        """kind: video, audio or image_sequence. details: (icon, title, value) tuples."""
        _ = self.translate
        self.path = path
        self.subtitle.setText({
            "audio": _("Your audio has been exported successfully."),
            "image_sequence": _("Your image sequence has been exported successfully."),
        }.get(kind, _("Your video has been exported successfully.")))
        self.location.setText(path)
        self.location.setCursorPosition(0)
        self.location.setToolTip(path)
        self.open_button.setText(_("Play Audio") if kind == "audio" else _("Watch Video"))
        self.open_button.setVisible(kind != "image_sequence")
        for card in self.cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self.cards = [InfoCard(icon, title, value, self) for icon, title, value in details]
        self.columns = 0
        self.apply_style()
        self.reflow()

    def reflow(self):
        """Use as many equal columns as keep every value on one line."""
        if not self.cards:
            return
        margins = self.layout().contentsMargins()
        available = self.width() - margins.left() - margins.right()
        spacing = self.cards_layout.horizontalSpacing()
        widest = max(card.sizeHint().width() for card in self.cards)
        columns = self.MAX_COLUMNS
        while columns > 1 and columns * widest + (columns - 1) * spacing > available:
            columns -= 1
        if columns == self.columns:
            return
        self.columns = columns
        for card in self.cards:
            self.cards_layout.removeWidget(card)
        for index, card in enumerate(self.cards):
            self.cards_layout.addWidget(card, index // columns, index % columns)
        for column in range(self.MAX_COLUMNS):
            self.cards_layout.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def focus_primary(self):
        (self.open_button if self.open_button.isVisible() else self.reveal_button).setFocus(Qt.OtherFocusReason)

    def copy_path(self):
        QApplication.clipboard().setText(self.path)
        QToolTip.showText(self.copy_button.mapToGlobal(self.copy_button.rect().bottomLeft()),
                          self.translate("Copied"), self.copy_button)

    def reveal(self):
        return reveal_file(self.window(), self.path)

    def open(self):
        return open_file(self.window(), self.path)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.StyleChange) and not self.styling:
            self.apply_style()

    def apply_style(self):
        """Derive every color from the active theme, so all themes (and system palettes) fit."""
        self.styling = True
        try:
            palette = self.palette()
            text = palette.color(QPalette.WindowText)
            light = luma(text) < 128
            link = palette.color(QPalette.Link)
            # Keep the theme's link color unless it would be unreadable here.
            if light != (luma(link) < 128) or link.saturation() < 40:
                link = QColor("#1f6fc5" if light else "#7ab8ff")

            def rgba(color, alpha):
                color = QColor(color)
                return "rgba(%d, %d, %d, %d)" % (color.red(), color.green(), color.blue(), alpha)

            success = QColor(SUCCESS)
            self.setStyleSheet("""
                QFrame#exportSuccess {{
                    background-color: {success_fill};
                    border: 1px solid {success_border};
                    border-radius: 8px;
                }}
                QLabel#exportSuccessTitle {{ font-size: 15pt; font-weight: bold; background: transparent; }}
                QLabel#exportSuccessSubtitle {{ color: {muted}; background: transparent; }}
                QFrame#exportInfoCard {{
                    background-color: {card_fill};
                    border: 1px solid {card_border};
                    border-radius: 6px;
                }}
                QFrame#exportInfoCard QLabel {{ background: transparent; border: none; }}
                QLabel#exportInfoTitle {{ color: {muted}; }}
                QLabel#exportInfoValue {{ font-weight: bold; }}
                QFrame#exportDivider {{ background-color: {card_border}; border: none; }}
                QPushButton#exportRevealButton {{
                    background: transparent; border: none; padding: 4px 2px;
                    color: {link}; text-decoration: underline;
                }}
                QPushButton#exportRevealButton:hover, QPushButton#exportRevealButton:focus {{
                    color: {link_hover};
                }}
                QPushButton#exportOpenButton {{ padding: 8px 18px 8px 14px; }}
            """.format(
                success_fill=rgba(success, 46 if light else 38),
                success_border=rgba(success, 150 if light else 120),
                muted=rgba(text, 175),
                card_fill=rgba(text, 10 if light else 12),
                card_border=rgba(text, 40 if light else 30),
                link=link.name(),
                link_hover=(link.darker(125) if light else link.lighter(120)).name(),
            ))
            ratio = self.devicePixelRatioF()
            side = self.location.sizeHint().height()
            self.copy_button.setFixedSize(side, side)
            self.badge.setPixmap(success_badge(40, ratio))
            self.copy_button.setIcon(QIcon(svg_pixmap("copy", text, 16, ratio)))
            self.reveal_button.setIcon(QIcon(svg_pixmap("folder", link, 18, ratio)))
            self.open_button.setIcon(QIcon(svg_pixmap("play", "#ffffff", 16, ratio)))
            for card in self.cards:
                card.refresh_icon(light)
        finally:
            self.styling = False


def export_details(dialog, path, kind, translate):
    """Summarize the finished export from the dialog's final settings."""
    _ = translate
    details = []
    if kind == "image_sequence":
        details.append(("file", _("Format"), dialog.txtImageFormat.text().strip().lstrip("-%0123456789d.").upper()
                        or dialog.txtVideoFormat.text().upper()))
    else:
        details.append(("file", _("Format"), format_label(
            dialog.txtVideoFormat.text().strip(), dialog.txtVideoCodec.text().strip(),
            dialog.txtAudioCodec.text().strip(), kind)))
    fps_num, fps_den = dialog.txtFrameRateNum.value(), dialog.txtFrameRateDen.value() or 1
    fps = fps_num / float(fps_den) if fps_num else 0.0
    if kind != "audio":
        details.append(("film", _("Resolution"), resolution_label(dialog, fps)))
    quality = getattr(dialog, "cboSimpleQuality", None)
    quality_value = quality.currentData() if quality is not None else None
    quality_text = {"Low": _("Low Quality"), "Med": _("Medium Quality"),
                    "High": _("High Quality")}.get(quality_value)
    if quality_text:
        details.append(("quality", _("Quality"), quality_text))
    if kind == "image_sequence":
        frames = max(0, dialog.txtEndFrame.value() - dialog.txtStartFrame.value() + 1)
        details.append(("frames", _("Frames"), str(frames)))
    else:
        try:
            details.append(("size", _("File Size"), format_size(os.path.getsize(path))))
        except OSError:
            pass
    if fps:
        frames = max(0, dialog.txtEndFrame.value() - dialog.txtStartFrame.value() + 1)
        details.append(("clock", _("Duration"), format_duration(frames / fps)))
    return details


def resolution_label(dialog, fps):
    width, height = dialog.txtWidth.value(), dialog.txtHeight.value()
    profile_box = getattr(dialog, "cboSimpleVideoProfile", None)
    if profile_box is not None and profile_box.currentData():
        try:
            import openshot
            profile = openshot.Profile(profile_box.currentData())
            # The profile's own name (e.g. "HD 720p 30 fps"), unless Advanced overrode its size.
            if profile.info.width == width and profile.info.height == height and profile.info.description:
                return profile.info.description
        except Exception:
            pass
    fps_text = ("%.2f" % fps).rstrip("0").rstrip(".")
    return "%d × %d, %s fps" % (width, height, fps_text)
