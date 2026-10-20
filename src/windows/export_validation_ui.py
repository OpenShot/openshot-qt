"""
 @file
 @brief Live validation for the export dialog: outlines, section icons, choices, and the Export gate.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """

from functools import lru_cache, partial
import html
import json
import os
import tempfile
import threading

import openshot
from qt_api import (
    QColor, QComboBox, QHBoxLayout, QIcon, QLabel, QLineEdit, QMenu, QObject, QPen, QPoint, QPointF, QPolygonF,
    QRectF, QSize, QSpinBox, QTimer, QToolButton, QVBoxLayout, QWidget, QWidgetAction, Qt, pyqtSignal, QEvent,
)
from classes.ui_util import painted_icon
from classes.app import get_app
from classes.logger import log
from classes import export_validation
from classes.export_settings import test_writer
from classes.export_validation import Capabilities, ExportValidator, ERROR, WARNING

# One engine check at a time: the writer keeps some state (i.e. hardware devices) process-wide
ENGINE_LOCK = threading.Lock()

# Settings that belong to one stream, so the other stream can still be checked when they're wrong
VIDEO_FIELDS = {"vcodec", "width", "height", "video_bitrate"}
AUDIO_FIELDS = {"acodec", "sample_rate", "channel_layout", "audio_bitrate"}

ERROR_COLOR = "#e5484d"
WARNING_COLOR = "#f5a524"

ISSUE_STYLES = """
QLineEdit[exportIssue="error"], QSpinBox[exportIssue="error"], QComboBox[exportIssue="error"] {
    border: 1.2px solid %(error)s;
    border-radius: 4px;
}
QLineEdit[exportIssue="warning"], QSpinBox[exportIssue="warning"], QComboBox[exportIssue="warning"] {
    border: 1.2px solid %(warning)s;
    border-radius: 4px;
}
QToolButton#exportIssuesButton[exportIssue="error"] { color: %(error)s; }
QToolButton#exportIssuesButton[exportIssue="warning"] { color: %(warning)s; }
""" % {"error": ERROR_COLOR, "warning": WARNING_COLOR}

# Encoders listed first in the codec menus (when the format can hold them)
PREFERRED_ENCODERS = {
    "video": ["libx264", "libx265", "libvpx-vp9", "libvpx", "libsvtav1", "libaom-av1", "librav1e",
              "prores_ks", "mpeg4", "libxvid", "mpeg2video", "libtheora", "gif", "h264_nvenc", "hevc_nvenc",
              "h264_vaapi", "hevc_vaapi", "h264_qsv", "h264_videotoolbox"],
    "audio": ["aac", "libmp3lame", "libopus", "libvorbis", "flac", "ac3", "mp2", "pcm_s16le"],
}

# Export To combo order (matching export.py)
EXPORT_MODES = [export_validation.VIDEO_AUDIO, export_validation.VIDEO_ONLY,
                export_validation.AUDIO_ONLY, export_validation.IMAGE_SEQUENCE]

SEVERITY_RANK = {None: 0, WARNING: 1, ERROR: 2}

# Settings a preset may adjust quietly. A missing encoder stays red instead of being swapped,
# so choosing a hardware target never silently exports with a different encoder.
AUTO_FIX_FIELDS = {"sample_rate", "channel_layout"}


def _enum(owner, name, scope):
    """Read a Qt enum value under Qt5 or Qt6 naming."""
    value = getattr(owner, name, None)
    return value if value is not None else getattr(getattr(owner, scope), name)


# Problem messages wrap at this width (in the status menu and tooltips)
MESSAGE_WIDTH = 360


def rich_text(lines):
    """Tooltip text Qt wraps at a comfortable width, instead of one long line."""
    return "<qt>%s</qt>" % "<br>".join(html.escape(line) for line in lines)


@lru_cache(maxsize=None)
def issue_icon(severity, size=14):
    """A small round badge (red for errors, amber for warnings)."""
    def paint(painter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(ERROR_COLOR if severity == ERROR else WARNING_COLOR))
        painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))
        pen = QPen(QColor("#ffffff"), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        middle = size / 2.0
        painter.drawLine(QPointF(middle, size * 0.27), QPointF(middle, size * 0.56))
        painter.drawPoint(QPointF(middle, size * 0.74))
    return painted_icon(size, size, paint)


def chevron_icon(color, size=16):
    """A small down chevron, for the choice menus."""
    def paint(painter):
        pen = QPen(color, 1.3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(QPolygonF([QPointF(size * 0.3, size * 0.4), QPointF(size * 0.5, size * 0.6),
                                        QPointF(size * 0.7, size * 0.4)]))
    return painted_icon(size, size, paint)


class IssueMenuItem(QWidget):
    """One problem in the status menu: badge, wrapped message, and its fix, clickable as a row."""
    clicked = pyqtSignal()

    def __init__(self, icon, message, fix_text="", parent=None):
        super().__init__(parent)
        self.setObjectName("exportIssueItem")
        self.setAttribute(Qt.WA_Hover, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        # Use the menu's own (theme) text color: palette roles like highlighted-text don't match
        # every theme (i.e. black on Cosmic Dusk's dark menus). Hover only tints the background.
        text_color = QColor("#ffffff")
        if parent is not None:
            parent.ensurePolished()
            text_color = parent.palette().color(parent.foregroundRole())
        self.setStyleSheet("""
            QWidget#exportIssueItem { border-radius: 4px; background: transparent; }
            QWidget#exportIssueItem:hover, QWidget#exportIssueItem:focus {
                background: rgba(128, 128, 128, 56); }
            QWidget#exportIssueItem QLabel { color: %s; background: transparent; }
        """ % text_color.name())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(8)
        badge = QLabel(self)
        badge.setPixmap(icon.pixmap(QSize(14, 14)))
        badge.setFixedSize(14, 14)
        layout.addWidget(badge, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.message = QLabel(message, self)
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.PlainText)
        text.addWidget(self.message)
        self.fix = None
        if fix_text:
            self.fix = QLabel(fix_text, self)
            self.fix.setTextFormat(Qt.PlainText)
            font = self.fix.font()
            font.setBold(True)
            self.fix.setFont(font)
            text.addWidget(self.fix)
        layout.addLayout(text)
        layout.addStretch(1)
        self.fit_message()

    def fit_message(self):
        """Size the message for its wrapped lines (menus don't size wrapped labels themselves)."""
        # Measure with the theme's font, which is only applied once polished
        self.ensurePolished()
        self.message.ensurePolished()
        natural = self.message.fontMetrics().boundingRect(self.message.text()).width() + 8
        width = min(natural, MESSAGE_WIDTH)
        self.message.setFixedSize(width, self.message.heightForWidth(width))
        self.adjustSize()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange) and hasattr(self, "message"):
            self.fit_message()

    def mouseReleaseEvent(self, event):
        if self.rect().contains(event.pos()):
            self.clicked.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class ExportValidationUI(QObject):
    # A background engine check finished: (settings key, result)
    engineChecked = pyqtSignal(str, object)

    """Watch the export dialog's settings, mark invalid ones, and gate the Export button."""

    def __init__(self, dialog, validator=None):
        super().__init__(dialog)
        self.dialog = dialog
        self._ = get_app()._tr
        self.validator = validator or ExportValidator(Capabilities(), self._)
        self.issues = []
        self.auto_fix = False
        # Engine check (export_settings.test_writer) for the current settings: key -> result
        self.engine_key = None
        self.engine_result = None
        self.engine_running = None
        self.engine_available = hasattr(openshot.FFmpegWriter, "Test") and hasattr(dialog, "writer_settings")
        self.engineChecked.connect(self._engine_checked)
        self.fields = {
            "vformat": dialog.txtVideoFormat,
            "vcodec": dialog.txtVideoCodec,
            "video_bitrate": dialog.txtVideoBitRate,
            "width": dialog.txtWidth,
            "height": dialog.txtHeight,
            "image_format": dialog.txtImageFormat,
            "acodec": dialog.txtAudioCodec,
            "sample_rate": dialog.txtSampleRate,
            "channel_layout": dialog.cboChannelLayout,
            "audio_bitrate": dialog.txtAudioBitrate,
            "end_frame": dialog.txtEndFrame,
            "folder": dialog.txtExportFolder,
        }
        self.tooltips = {widget: widget.toolTip() for widget in self.fields.values()}
        # Style only these widgets; restyling the whole dialog re-shows hidden dialog buttons
        for widget in self.fields.values():
            widget.setStyleSheet(widget.styleSheet() + ISSUE_STYLES)
        toolbox = dialog.toolBox
        self.page_icons = [toolbox.itemIcon(index) for index in range(toolbox.count())]
        self.toolbox_tab = self._tab_index(toolbox)
        self.tab_icon = dialog.exportTabs.tabIcon(self.toolbox_tab) if self.toolbox_tab >= 0 else QIcon()

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.validate)

        self._connect_signals()
        self._add_choice_menus()
        self._add_status_button()
        self.validate()

    # ----- Setup -----

    def _connect_signals(self):
        d = self.dialog
        for widget in (d.txtVideoFormat, d.txtVideoCodec, d.txtVideoBitRate, d.txtImageFormat,
                       d.txtAudioCodec, d.txtAudioBitrate, d.txtExportFolder):
            widget.textChanged.connect(self.schedule)
        for widget in (d.txtWidth, d.txtHeight, d.txtSampleRate, d.txtStartFrame, d.txtEndFrame):
            widget.valueChanged.connect(self.schedule)
        for widget in (d.cboExportTo, d.cboChannelLayout):
            widget.currentIndexChanged.connect(self.schedule)

    def _add_choice_menus(self):
        _ = self._
        color = self.dialog.palette().color(self.dialog.foregroundRole())
        icon = chevron_icon(color)
        position = _enum(QLineEdit, "TrailingPosition", "ActionPosition")
        for field in ("vformat", "vcodec", "video_bitrate", "acodec", "audio_bitrate"):
            widget = self.fields[field]
            action = widget.addAction(icon, position)
            action.setToolTip(_("Choose a compatible option"))
            action.triggered.connect(partial(self.show_choices, field))

        # Spin boxes have no room inside, so the sample rate gets a button beside it
        layout = getattr(self.dialog, "horizontalLayout_21", None)
        if layout is not None:
            button = QToolButton(self.dialog)
            button.setObjectName("btnSampleRateChoices")
            button.setIcon(icon)
            button.setAutoRaise(True)
            button.setToolTip(_("Choose a compatible option"))
            button.clicked.connect(partial(self.show_choices, "sample_rate"))
            layout.addWidget(button)

    def _add_status_button(self):
        self.status_button = QToolButton(self.dialog)
        self.status_button.setObjectName("exportIssuesButton")
        self.status_button.setStyleSheet(ISSUE_STYLES)
        self.status_button.setAutoRaise(True)
        self.status_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.status_button.clicked.connect(self.show_issue_menu)
        self.status_button.setVisible(False)
        layout = getattr(self.dialog, "horizontalLayout", None)
        index = layout.indexOf(self.dialog.buttonBox) if layout is not None else -1
        if index >= 0:
            layout.insertWidget(index, self.status_button)

    def _tab_index(self, widget):
        tabs = self.dialog.exportTabs
        for index in range(tabs.count()):
            if tabs.widget(index).isAncestorOf(widget):
                return index
        return -1

    # ----- Reading settings -----

    def current_settings(self):
        d = self.dialog
        mode_index = d.cboExportTo.currentIndex()
        return {
            "mode": EXPORT_MODES[mode_index] if 0 <= mode_index < len(EXPORT_MODES) else EXPORT_MODES[0],
            "vformat": d.txtVideoFormat.text(),
            "vcodec": d.txtVideoCodec.text(),
            "video_bitrate": d.txtVideoBitRate.text(),
            "width": d.txtWidth.value(),
            "height": d.txtHeight.value(),
            "image_format": d.txtImageFormat.text(),
            "acodec": d.txtAudioCodec.text(),
            "sample_rate": d.txtSampleRate.value(),
            "channel_layout": d.cboChannelLayout.currentData(),
            "audio_bitrate": d.txtAudioBitrate.text(),
            "start_frame": d.txtStartFrame.value(),
            "end_frame": d.txtEndFrame.value(),
            "folder": d.txtExportFolder.text(),
        }

    # ----- Validation -----

    def schedule(self, *_args):
        self.timer.start()

    def request_auto_fix(self):
        """Fix what we can on the next pass (used when a preset fills in the settings)."""
        self.auto_fix = True
        self.schedule()

    def validate(self):
        self.timer.stop()
        issues = self.validator.validate(self.current_settings())
        if self.auto_fix:
            self.auto_fix = False
            for _attempt in range(3):
                fixable = [issue for issue in issues if issue.is_error and issue.fix is not None
                           and issue.field in AUTO_FIX_FIELDS]
                if not fixable:
                    break
                for issue in fixable:
                    log.info("Adjusting export setting for this FFmpeg build: %s", issue)
                    self.apply_fix(issue, revalidate=False)
                issues = self.validator.validate(self.current_settings())
            self.timer.stop()
        engine = self._engine_issue(issues)
        if engine:
            issues.append(engine)
        self.issues = issues
        self._show_issues()
        self._update_audio_controls()
        self.update_export_button()

    # ----- Engine check -----

    def _engine_request(self, only=None):
        """(key, test_writer arguments) for the current settings, or None when there's nothing to check.

        only: "audio" or "video" checks just that stream.
        """
        video, audio, mode, quality_mode = self.dialog.writer_settings()
        mode = only or mode
        ext = (video.get("vformat") or "").strip().lstrip(".")
        if not ext:
            return None
        # Only the extension matters; nothing is written
        path = os.path.join(tempfile.gettempdir(), "openshot-export-check." + ext)
        args = (path, video, audio, mode, quality_mode)
        relevant = {key: value for key, value in video.items() if key not in ("start_frame", "end_frame")}
        key = json.dumps([relevant, audio, mode, quality_mode, ext], sort_keys=True)
        return key, args

    def _engine_issue(self, quick_issues):
        """The engine check's verdict for these settings, starting a background check when needed."""
        if not self.engine_available or not self.dialog.exportTabs.isEnabled():
            return None
        # Quick checks explain what's wrong more precisely. Still check the other stream, so
        # (i.e.) a wrong audio codec shows up together with a wrong video codec.
        wrong = {issue.field for issue in quick_issues if issue.is_error} - {"end_frame", "folder"}
        only = None
        if wrong:
            mode = self.current_settings()["mode"]
            if mode != export_validation.VIDEO_AUDIO:
                return None
            if wrong <= VIDEO_FIELDS:
                only = "audio"
            elif wrong <= AUDIO_FIELDS:
                only = "video"
            else:
                return None
        try:
            request = self._engine_request(only)
        except (ValueError, TypeError):
            return None
        if request is None:
            return None
        key, args = request
        if key == self.engine_key:
            return self.validator.engine_issue(self.current_settings(), self.engine_result)
        if self.engine_running != key:
            self.engine_running = key
            threading.Thread(target=self._run_engine_check, args=(key, args), daemon=True).start()
        return None

    def _run_engine_check(self, key, args):
        with ENGINE_LOCK:
            result = test_writer(*args)
        try:
            self.engineChecked.emit(key, result)
        except RuntimeError:
            pass  # The dialog closed while checking

    def _engine_checked(self, key, result):
        if self.engine_running == key:
            self.engine_running = None
        self.engine_key, self.engine_result = key, result
        self.validate()

    def confirm_with_engine(self):
        """Check the current settings with the engine before exporting. Returns False if they fail.

        A passing result for unchanged settings is reused; anything else is checked again, so a
        one-off failure doesn't block the next attempt.
        """
        if not self.engine_available:
            return True
        request = self._engine_request()
        if request is None:
            return True
        key, args = request
        if key != self.engine_key or not self.engine_result.get("ok"):
            with ENGINE_LOCK:
                result = test_writer(*args)
            self.engine_key, self.engine_result = key, result
        self.validate()
        return not self.has_errors()

    @property
    def errors(self):
        return [issue for issue in self.issues if issue.is_error]

    def has_errors(self):
        return bool(self.errors)

    def update_export_button(self):
        # Disabled tabs mean an export is running, and the button must stay off
        d = self.dialog
        d.export_button.setEnabled(not self.has_errors() and d.exportTabs.isEnabled())

    # ----- Showing issues -----

    def _worst(self, issues):
        worst = None
        for issue in issues:
            if SEVERITY_RANK[issue.severity] > SEVERITY_RANK[worst]:
                worst = issue.severity
        return worst

    def _show_issues(self):
        _ = self._
        by_field = {}
        for issue in self.issues:
            by_field.setdefault(issue.field, []).append(issue)

        for field, widget in self.fields.items():
            field_issues = by_field.get(field, [])
            severity = self._worst(field_issues) or ""
            if widget.property("exportIssue") != severity:
                widget.setProperty("exportIssue", severity)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            lines = [self.tooltips[widget]] if self.tooltips[widget] else []
            for issue in field_issues:
                lines.append(issue.message)
                if issue.fix_label:
                    lines.append(_("Suggested: %s") % issue.fix_label)
            widget.setToolTip(rich_text(lines) if field_issues else "\n".join(lines))

        # Badge each toolbox section, and the tab holding them
        toolbox = self.dialog.toolBox
        tab_severity = None
        for index in range(toolbox.count()):
            page = toolbox.widget(index)
            page_issues = [issue for field, widget in self.fields.items() if page.isAncestorOf(widget)
                           for issue in by_field.get(field, [])]
            severity = self._worst(page_issues)
            toolbox.setItemIcon(index, issue_icon(severity) if severity else self.page_icons[index])
            if SEVERITY_RANK[severity] > SEVERITY_RANK[tab_severity]:
                tab_severity = severity
        if self.toolbox_tab >= 0:
            self.dialog.exportTabs.setTabIcon(
                self.toolbox_tab, issue_icon(tab_severity) if tab_severity else self.tab_icon)

        # Summarize next to the Export button
        errors = len(self.errors)
        warnings = len(self.issues) - errors
        if errors:
            text = _("1 problem") if errors == 1 else _("%d problems") % errors
            severity = ERROR
        elif warnings:
            text = _("1 warning") if warnings == 1 else _("%d warnings") % warnings
            severity = WARNING
        else:
            text, severity = "", ""
        self.status_button.setText(text)
        self.status_button.setIcon(issue_icon(severity) if severity else QIcon())
        self.status_button.setToolTip(rich_text(issue.message for issue in self.issues))
        self.status_button.setProperty("exportIssue", severity)
        self.status_button.style().unpolish(self.status_button)
        self.status_button.style().polish(self.status_button)
        self.status_button.setVisible(bool(self.issues))

    def _update_audio_controls(self):
        """Grey out channel layouts the audio codec can't use, and the bit rate of lossless codecs."""
        _ = self._
        settings = self.current_settings()
        codec, _is_default = self.validator.effective_codec(settings, "acodec", "default_audio_codec")
        info = self.validator.caps.encoder(codec) if codec else {}

        combo = self.dialog.cboChannelLayout
        layouts = info.get("channel_layouts")
        model = combo.model()
        for index in range(combo.count()):
            item = model.item(index) if hasattr(model, "item") else None
            if item is not None:
                item.setEnabled(not layouts or combo.itemData(index) in layouts)

        bitrate = self.dialog.txtAudioBitrate
        lossless = bool(info.get("lossless") and not info.get("lossy"))
        bitrate.setEnabled(not lossless)
        if lossless:
            bitrate.setToolTip(_("%s is lossless, so the bit rate isn't used.") % info.get("name", codec))

    # ----- Fixing and revealing -----

    def apply_fix(self, issue, revalidate=True):
        widget = self.fields.get(issue.field)
        if widget is None or issue.fix is None:
            return
        if isinstance(widget, QLineEdit):
            widget.setText(str(issue.fix))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(issue.fix))
        elif isinstance(widget, QComboBox):
            index = widget.findData(issue.fix)
            if index >= 0:
                widget.setCurrentIndex(index)
        if revalidate:
            self.validate()

    def fix_all(self):
        for _attempt in range(3):
            fixable = [issue for issue in self.issues if issue.is_error and issue.fix is not None]
            if not fixable:
                break
            for issue in fixable:
                self.apply_fix(issue, revalidate=False)
            self.validate()

    def reveal(self, field):
        """Show the tab and section holding a setting, and focus it."""
        widget = self.fields.get(field)
        if widget is None:
            return
        tab = self._tab_index(widget)
        if tab >= 0:
            self.dialog.exportTabs.setCurrentIndex(tab)
        toolbox = self.dialog.toolBox
        for index in range(toolbox.count()):
            if toolbox.widget(index).isAncestorOf(widget):
                toolbox.setCurrentIndex(index)
                break
        widget.setFocus()

    def reveal_first_error(self):
        if self.errors:
            self.reveal(self.errors[0].field)

    def show_issue_menu(self):
        menu = self.issue_menu()
        # Open above the button, which sits at the bottom of the dialog
        position = self.status_button.mapToGlobal(QPoint(0, 0))
        position.setY(position.y() - menu.sizeHint().height())
        menu.exec_(position)

    def issue_menu(self):
        """The status button's menu: each problem, wrapped, with its fix (and Fix All)."""
        _ = self._
        menu = QMenu(self.dialog)
        fixable = [issue for issue in self.errors if issue.fix is not None]
        if len(fixable) > 1:
            menu.addAction(_("Fix All")).triggered.connect(self.fix_all)
            menu.addSeparator()
        for issue in self.issues:
            fix_text = _("Use %s") % issue.fix_label if issue.fix is not None else ""
            item = IssueMenuItem(issue_icon(issue.severity), issue.message, fix_text, menu)
            action = QWidgetAction(menu)
            action.setDefaultWidget(item)
            menu.addAction(action)
            # triggered(bool) passes "checked", which isn't for these slots
            if issue.fix is not None:
                action.triggered.connect(lambda _checked=False, issue=issue: self.apply_fix(issue))
            else:
                action.triggered.connect(lambda _checked=False, field=issue.field: self.reveal(field))
            # Rows are widgets, so trigger and close the menu ourselves
            item.clicked.connect(action.trigger)
            item.clicked.connect(menu.close)
        return menu

    # ----- Choices -----

    def _encoder_label(self, encoder):
        name = encoder.get("name", "")
        long_name = (encoder.get("long_name") or "").strip()
        # FFmpeg repeats library names (i.e. "libx264 H.264 / AVC"), so drop the repeat
        if long_name == name or long_name.startswith(name + " "):
            long_name = long_name[len(name):].strip(" -")
        return "%s (%s)" % (long_name, name) if long_name else name

    def _encoder_choices(self, media_type, vformat):
        """(top choices, More menu nodes) for an encoder field."""
        caps = self.validator.caps
        if caps.available:
            encoders = caps.encoders(media_type, vformat)
        else:
            encoders = [{"name": name} for name in PREFERRED_ENCODERS[media_type] if caps.encoder(name).get("found")]
        if media_type == "video" and self.validator.is_cover_image_format(vformat):
            # Only a cover image fits (i.e. mp3)
            encoders = [encoder for encoder in encoders if encoder["name"] in export_validation.COVER_IMAGE_CODECS]
        names = [encoder["name"] for encoder in encoders]
        top = [encoders[names.index(name)] for name in PREFERRED_ENCODERS[media_type] if name in names]
        rest = [dict(caps.encoder(encoder["name"]), **encoder) for encoder in encoders if encoder not in top]
        more = export_validation.encoder_menu(rest, media_type, self._)
        choice = lambda encoder: (self._encoder_label(encoder), encoder["name"])
        return [choice(e) for e in top], self._menu_choices(more, choice)

    def _format_choices(self):
        """(common formats, More menu with every other format) for the format field."""
        caps = self.validator.caps
        common = caps.formats() if caps.available else export_validation.COMMON_FORMATS
        rest = [row for row in caps.all_formats() if row.get("extension") not in common]
        more = export_validation.format_menu(rest, self._, caps.encoder)
        choice = lambda row: ("%s — %s" % (row["extension"], row["long_name"]) if row.get("long_name")
                              else row["extension"], row["extension"])
        return [(name, name) for name in common], self._menu_choices(more, choice)

    def _menu_choices(self, nodes, choice):
        """Turn grouped_menu() nodes into (label, value) choices and (title, [choices]) groups."""
        choices = []
        for node in nodes:
            if isinstance(node, tuple):
                choices.append((node[0], self._menu_choices(node[1], choice)))
            else:
                choices.append(choice(node))
        return choices

    def choices(self, field):
        """Return (choices, more_choices) as lists of (label, value)."""
        caps = self.validator.caps
        settings = self.current_settings()
        vformat = (settings["vformat"] or "").strip()
        if field == "vformat":
            return self._format_choices()
        if field == "vcodec":
            return self._encoder_choices("video", vformat)
        if field == "acodec":
            return self._encoder_choices("audio", vformat)
        if field == "audio_bitrate":
            return [(rate, rate) for rate in export_validation.COMMON_AUDIO_BITRATES], []
        if field == "video_bitrate":
            values = list(export_validation.COMMON_VIDEO_BITRATES)
            codec, _is_default = self.validator.effective_codec(settings, "vcodec", "default_video_codec")
            options = (caps.encoder(codec).get("quality_options") or []) if codec else []
            for unit in ("crf", "qp"):
                if unit in options:
                    values += export_validation.COMMON_QUALITY_VALUES[unit]
            return [(value, value) for value in values], []
        if field == "sample_rate":
            codec, _is_default = self.validator.effective_codec(settings, "acodec", "default_audio_codec")
            rates = (caps.encoder(codec).get("sample_rates") if codec else None) \
                or export_validation.COMMON_SAMPLE_RATES
            return [("%d Hz" % rate, rate) for rate in sorted(set(rates), reverse=True)], []
        return [], []

    def show_choices(self, field, *_args):
        widget = self.fields[field]
        self.choices_menu(field).exec_(widget.mapToGlobal(widget.rect().bottomLeft()))

    def choices_menu(self, field):
        """The choice menu for a field: compatible options first, the rest grouped under More."""
        _ = self._
        widget = self.fields[field]
        choices, more = self.choices(field)
        menu = QMenu(self.dialog)
        current = widget.value() if isinstance(widget, QSpinBox) else widget.text().strip()
        for label, value in choices:
            self._add_choice(menu, field, label, value, current)
        if more:
            submenu = menu.addMenu(_("More")) if choices else menu
            self._add_choices(submenu, field, more, current)
        if menu.isEmpty():
            menu.addAction(_("No compatible options found")).setEnabled(False)
        return menu

    def _add_choices(self, menu, field, choices, current):
        """Add (label, value) choices, and (title, [choices]) groups as submenus."""
        for label, value in choices:
            if isinstance(value, list):
                # "&" marks a shortcut in menu text, so double it (i.e. Lossless & PCM Audio)
                self._add_choices(menu.addMenu(label.replace("&", "&&")), field, value, current)
            else:
                self._add_choice(menu, field, label, value, current)

    def _add_choice(self, menu, field, label, value, current):
        action = menu.addAction(str(label).replace("&", "&&"))
        action.setCheckable(True)
        action.setChecked(value == current)
        action.triggered.connect(partial(self._choose, field, value))

    def _choose(self, field, value, *_args):
        widget = self.fields[field]
        if isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        else:
            widget.setText(str(value))
        self.validate()
