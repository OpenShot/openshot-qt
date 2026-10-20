"""Export result tab: a summary after success, or the error after a failure."""

import os

from qt_api import (
    QApplication, QByteArray, QColor, QEvent, QFrame, QGridLayout, QHBoxLayout, QIcon, QLabel,
    QLineEdit, QPainter, QPalette, QPen, QPixmap, QPointF, QPolygonF, QPushButton, QScrollArea, QSize, QSizePolicy,
    QSvgRenderer, Qt, QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from classes.desktop_open import open_file, reveal_file

# Feather-style 24px outline icons, tinted at render time.
ICONS = {
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "film": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 12h18M3 7.5h4M3 16.5h4'
            'M17 7.5h4M17 16.5h4"/>',
    "size": '<ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13'
            'M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "folder": '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h8.5A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15'
              'A1.5 1.5 0 0 1 3 18.5z"/>',
    "play": '<path d="M7 4.5v15l12.5-7.5z" fill="{color}"/>',
    "frames": '<rect x="3" y="5" width="13" height="10" rx="1.5"/><path d="M8 19h11.5a1.5 1.5 0 0 0 1.5-1.5V9"/>',
    "timer": '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 13.5V10M10 2.5h4M18.5 6.5l1.5-1.5"/>',
    "audio": '<path d="M3 12h2M7 8v8M11 4.5v15M15 8v8M19 10.5v3M21 12h0"/>',
}
# Signal bars, filled up to the quality level.
QUALITY_LEVELS = {"Low": 1, "Med": 2, "High": 3}
for _level in (1, 2, 3):
    ICONS["quality-%d" % _level] = "".join(
        '<rect x="%g" y="%g" width="4" height="%g" rx="1"%s/>'
        % (3.5 + 6.5 * bar, 19 - 5 * (bar + 1), 5 * (bar + 1),
           ' fill="{color}"' if bar < _level else ' stroke-opacity="0.45"')
        for bar in range(3))
SUCCESS = "#2fbf71"
ERROR = "#e5484d"
# Mid-tone accents read on both light and dark backgrounds.
ACCENTS = {"file": "#4a9eff", "film": "#a06cf0", "quality-1": "#f0a020", "quality-2": "#f0a020",
           "quality-3": "#f0a020", "size": "#2fbfa0", "clock": "#4a9eff", "frames": "#a06cf0",
           "timer": "#e8618c", "audio": "#a06cf0"}
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


def status_badge(success, size, ratio=1.0):
    """A filled circle: green with a check, or red with an exclamation mark."""
    pixmap = QPixmap(QSize(int(size * ratio), int(size * ratio)))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(SUCCESS if success else ERROR))
    side = pixmap.width()
    painter.drawEllipse(0, 0, side, side)
    # Drawn in pixmap units, so the mark stays centered at any size and DPI.
    painter.setPen(QPen(QColor("#ffffff"), side * 0.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    if success:
        painter.drawPolyline(QPolygonF([QPointF(side * 0.29, side * 0.52), QPointF(side * 0.44, side * 0.66),
                                        QPointF(side * 0.71, side * 0.37)]))
    else:
        painter.drawLine(QPointF(side * 0.5, side * 0.27), QPointF(side * 0.5, side * 0.56))
        painter.drawPoint(QPointF(side * 0.5, side * 0.73))
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


def format_elapsed(seconds):
    """Compact wall time, e.g. 0.8s, 42s, 3m 07s, 1h 05m."""
    if seconds < 10:
        return "%.1fs" % max(0.0, seconds)
    seconds = int(round(seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % (seconds // 60, seconds % 60)
    return "%dh %02dm" % (seconds // 3600, (seconds // 60) % 60)


class InfoCard(QFrame):
    def __init__(self, icon, title, value, parent=None):
        super().__init__(parent)
        self.setObjectName("exportInfoCard")
        self.icon_name = icon
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        self.icon = QLabel(self)
        self.icon.setFixedSize(22, 22)
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
        self.icon.setPixmap(svg_pixmap(self.icon_name, color, 22, self.devicePixelRatioF()))


class ExportResultTab(QWidget):
    """Success summary with ways to find or watch the file, or the error with a retry.

    Details scroll above a pinned action row, so the tab never grows the dialog
    and its buttons stay visible with large theme fonts.
    """

    MAX_COLUMNS = 3

    def __init__(self, translate, parent=None):
        super().__init__(parent)
        _ = self.translate = translate
        self.setObjectName("exportResult")
        # Let themes paint this page like the Simple/Advanced tabs.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.success = True
        self.path = ""
        self.error = ""
        self.cards = []
        self.columns = 0
        self.styling = False
        self.on_retry = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("exportResultScroll")
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("exportResultContent")
        self.content.installEventFilter(self)
        self.scroll.setWidget(self.content)
        # setWidget() turns this on; the theme's own background must show through.
        self.content.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(self.scroll, 1)

        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(10, 10, 10, 6)
        layout.setSpacing(8)

        self.banner = QFrame(self)
        self.banner.setObjectName("exportBanner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        banner_layout.setSpacing(12)
        self.badge = QLabel(self.banner)
        self.badge.setFixedSize(36, 36)
        banner_layout.addWidget(self.badge, 0, Qt.AlignVCenter)
        headline = QVBoxLayout()
        headline.setSpacing(1)
        self.headline = QLabel(self.banner)
        self.headline.setObjectName("exportBannerTitle")
        self.subtitle = QLabel(self.banner)
        self.subtitle.setObjectName("exportBannerSubtitle")
        self.subtitle.setWordWrap(True)
        headline.addWidget(self.headline)
        headline.addWidget(self.subtitle)
        banner_layout.addLayout(headline, 1)
        layout.addWidget(self.banner)

        # Success: where the file is. Failure: what went wrong.
        self.detail_label = QLabel(self)
        layout.addWidget(self.detail_label)
        # One quiet card: the path plus a flat copy button inside it.
        self.location_box = QFrame(self)
        self.location_box.setObjectName("exportLocationBox")
        location = QHBoxLayout(self.location_box)
        location.setContentsMargins(8, 2, 2, 2)
        location.setSpacing(2)
        self.location = QLineEdit(self.location_box)
        self.location.setFrame(False)
        self.location.setObjectName("exportLocation")
        self.location.setReadOnly(True)
        self.detail_label.setBuddy(self.location)
        location.addWidget(self.location, 1)
        self.copy_button = QToolButton(self.location_box)
        self.copy_button.setObjectName("exportCopyPath")
        self.copy_button.setToolTip(_("Copy Path"))
        self.copy_button.setAccessibleName(_("Copy Path"))
        self.copy_button.setIconSize(QSize(14, 14))
        self.copy_button.setAutoRaise(True)
        self.copy_button.setCursor(Qt.PointingHandCursor)
        self.copy_button.clicked.connect(self.copy_path)
        location.addWidget(self.copy_button)
        layout.addWidget(self.location_box)
        self.error_text = QLabel(self)
        self.error_text.setObjectName("exportErrorText")
        self.error_text.setWordWrap(True)
        self.error_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.error_text)

        self.cards_layout = QGridLayout()
        self.cards_layout.setHorizontalSpacing(8)
        self.cards_layout.setVerticalSpacing(8)
        layout.addLayout(self.cards_layout)
        layout.addStretch(1)

        footer = QVBoxLayout()
        footer.setContentsMargins(10, 0, 10, 8)
        footer.setSpacing(6)
        self.divider = QFrame(self)
        self.divider.setObjectName("exportDivider")
        self.divider.setFixedHeight(1)
        footer.addWidget(self.divider)
        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.link_button = QPushButton(self)
        self.link_button.setObjectName("exportLinkButton")
        self.link_button.setCursor(Qt.PointingHandCursor)
        self.link_button.setIconSize(QSize(16, 16))
        self.link_button.clicked.connect(self.secondary_action)
        actions.addWidget(self.link_button)
        actions.addStretch(1)
        self.primary_button = QPushButton(self)
        self.primary_button.setObjectName("exportPrimaryButton")
        # Themes give dialog primary buttons their accent color.
        self.primary_button.setProperty("dialogRole", "primary")
        self.primary_button.setCursor(Qt.PointingHandCursor)
        self.primary_button.setIconSize(QSize(14, 14))
        self.primary_button.clicked.connect(self.primary_action)
        actions.addWidget(self.primary_button)
        footer.addLayout(actions)
        outer.addLayout(footer)

    def show_success(self, path, kind, details):
        """kind: video, audio or image_sequence. details: (icon, title, value) tuples."""
        _ = self.translate
        self.success, self.path, self.error = True, path, ""
        self.headline.setText(_("Export Complete"))
        self.subtitle.setText({
            "audio": _("Your audio has been exported successfully."),
            "image_sequence": _("Your image sequence has been exported successfully."),
        }.get(kind, _("Your video has been exported successfully.")))
        self.detail_label.setText(_("File Location:"))
        self.location.setText(path)
        self.location.setCursorPosition(0)
        self.location.setToolTip(path)
        self.location.setAccessibleName(_("File Location"))
        self.link_button.setText(_("Open Containing Folder"))
        self.primary_button.setText(_("Play Audio") if kind == "audio" else _("Watch Video"))
        self.primary_button.setVisible(kind != "image_sequence")
        self.set_details(details)

    def show_failure(self, message, details, on_retry=None):
        _ = self.translate
        self.success, self.path, self.error = False, "", message
        self.on_retry = on_retry
        self.headline.setText(_("Export Failed"))
        self.subtitle.setText(_("Sorry, there was an error exporting your video."))
        self.detail_label.setText(_("Error Details:"))
        self.error_text.setText(message)
        self.link_button.setText(_("Copy Error Details"))
        self.primary_button.setText(_("Try Again"))
        self.primary_button.setVisible(on_retry is not None)
        self.set_details(details)

    def set_details(self, details):
        self.location_box.setVisible(self.success)
        self.error_text.setVisible(not self.success)
        for card in self.cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self.cards = [InfoCard(icon, title, value, self.content) for icon, title, value in details]
        self.columns = 0
        self.apply_style()
        self.reflow()

    def reflow(self):
        """Use as many equal columns as keep every value on one line."""
        if not self.cards:
            return
        margins = self.content.layout().contentsMargins()
        available = self.scroll.viewport().width() - margins.left() - margins.right()
        spacing = self.cards_layout.horizontalSpacing()
        widest = max(card.sizeHint().width() for card in self.cards)
        columns = self.MAX_COLUMNS
        while columns > 1 and columns * widest + (columns - 1) * spacing > available:
            columns -= 1
        # Prefer full rows: 4 cards as 2x2 rather than 3 + 1.
        even = [count for count in range(columns, 1, -1) if len(self.cards) % count == 0]
        if even:
            columns = even[0]
        if columns == self.columns:
            return
        self.columns = columns
        for card in self.cards:
            self.cards_layout.removeWidget(card)
        for index, card in enumerate(self.cards):
            self.cards_layout.addWidget(card, index // columns, index % columns)
        for column in range(self.MAX_COLUMNS):
            self.cards_layout.setColumnStretch(column, 1 if column < columns else 0)

    def eventFilter(self, watched, event):
        if watched is self.content and event.type() == QEvent.Resize:
            self.reflow()
        return False

    def minimumSizeHint(self):
        # Never force the export dialog to grow; the details scroll instead.
        return QSize(0, 0)

    def focus_primary(self):
        button = self.primary_button if self.primary_button.isVisibleTo(self) else self.link_button
        button.setFocus(Qt.OtherFocusReason)

    def copy_path(self):
        self.copy_text(self.path, self.copy_button)

    def copy_text(self, text, anchor):
        QApplication.clipboard().setText(text)
        QToolTip.showText(anchor.mapToGlobal(anchor.rect().bottomLeft()), self.translate("Copied"), anchor)

    def error_report(self):
        lines = [self.headline.text(), self.error]
        lines += ["%s: %s" % (card.title.text(), card.value.text()) for card in self.cards]
        return "\n".join(lines)

    def secondary_action(self):
        if self.success:
            return reveal_file(self.window(), self.path)
        self.copy_text(self.error_report(), self.link_button)
        return True

    def primary_action(self):
        if self.success:
            return open_file(self.window(), self.path)
        if self.on_retry:
            self.on_retry()
        return True

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange and not self.styling:
            self.apply_style()

    def apply_style(self):
        """Derive every color from the active theme, so all themes (and system palettes) fit."""
        self.styling = True
        try:
            palette = self.palette()
            # Active colors: the tab is built while the exporting dialog is still disabled.
            text = palette.color(QPalette.Active, QPalette.WindowText)
            light = luma(text) < 128
            link = palette.color(QPalette.Active, QPalette.Link)
            # Keep the theme's link color unless it would be unreadable here.
            if light != (luma(link) < 128) or link.saturation() < 40:
                link = QColor("#1f6fc5" if light else "#7ab8ff")

            def rgba(color, alpha):
                color = QColor(color)
                return "rgba(%d, %d, %d, %d)" % (color.red(), color.green(), color.blue(), alpha)

            status = QColor(SUCCESS if self.success else ERROR)
            self.setStyleSheet("""
                QWidget#exportResultContent, QScrollArea#exportResultScroll {{
                    background: transparent; border: none;
                }}
                QFrame#exportBanner {{
                    background-color: {status_fill};
                    border: 1px solid {status_border};
                    border-radius: 8px;
                }}
                QLabel#exportBannerTitle {{ font-size: 13pt; font-weight: bold; background: transparent; }}
                QLabel#exportBannerSubtitle {{ color: {muted}; background: transparent; }}
                QFrame#exportInfoCard, QLabel#exportErrorText {{
                    background-color: {card_fill};
                    border: 1px solid {card_border};
                    border-radius: 6px;
                }}
                QLabel#exportErrorText {{ padding: 8px 10px; }}
                QFrame#exportLocationBox {{
                    background-color: {card_fill};
                    border: 1px solid {card_border};
                    border-radius: 6px;
                }}
                QFrame#exportLocationBox QLineEdit {{
                    background: transparent; border: none; padding: 3px 0;
                    color: {muted}; selection-background-color: {card_border};
                }}
                QFrame#exportLocationBox QToolButton {{
                    background: transparent; border: none; border-radius: 4px; padding: 3px;
                }}
                QFrame#exportLocationBox QToolButton:hover, QFrame#exportLocationBox QToolButton:focus {{
                    background-color: {card_border};
                }}
                QFrame#exportInfoCard QLabel {{ background: transparent; border: none; }}
                QLabel#exportInfoTitle {{ color: {muted}; }}
                QLabel#exportInfoValue {{ font-weight: bold; }}
                QFrame#exportDivider {{ background-color: {card_border}; border: none; }}
                QPushButton#exportLinkButton {{
                    background: transparent; border: none; padding: 4px 2px;
                    color: {link}; text-decoration: underline;
                }}
                QPushButton#exportLinkButton:hover, QPushButton#exportLinkButton:focus {{
                    color: {link_hover};
                }}
                QPushButton#exportPrimaryButton {{ padding: 6px 16px 6px 12px; }}
            """.format(
                status_fill=rgba(status, 46 if light else 38),
                status_border=rgba(status, 150 if light else 120),
                muted=rgba(text, 175),
                card_fill=rgba(text, 10 if light else 12),
                card_border=rgba(text, 40 if light else 30),
                link=link.name(),
                link_hover=(link.darker(125) if light else link.lighter(120)).name(),
            ))
            ratio = self.devicePixelRatioF()
            self.badge.setPixmap(status_badge(self.success, 36, ratio))
            background = palette.color(QPalette.Active, QPalette.Window)
            muted_icon = QColor(*(int(a * 0.7 + b * 0.3) for a, b in zip(text.getRgb()[:3], background.getRgb()[:3])))
            self.copy_button.setIcon(QIcon(svg_pixmap("copy", muted_icon, 14, ratio)))
            self.link_button.setIcon(QIcon(svg_pixmap("folder" if self.success else "copy", link, 16, ratio)))
            self.primary_button.setIcon(QIcon(svg_pixmap("play", "#ffffff", 14, ratio)) if self.success else QIcon())
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
        details.append(("quality-%d" % QUALITY_LEVELS[quality_value], _("Quality"), quality_text))
    if kind == "audio":
        details.append(("audio", _("Audio"), audio_label(dialog, translate)))
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
    elapsed = getattr(dialog, "export_elapsed", None)
    if path and elapsed is not None:
        details.append(("timer", _("Export Time"), format_elapsed(elapsed)))
    return details


def audio_label(dialog, translate):
    _ = translate
    rate = dialog.txtSampleRate.value()
    rate_text = ("%.1f" % (rate / 1000.0)).rstrip("0").rstrip(".") + " kHz"
    channels = dialog.txtChannels.value()
    names = {1: _("Mono"), 2: _("Stereo")}
    return "%s, %s" % (rate_text, names.get(channels, _("%d Channels") % channels))


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
