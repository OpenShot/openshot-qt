"""
 @file
 @brief This file loads the About dialog (i.e about Openshot Project)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

import os
import codecs
import re
import platform
import ctypes
import math
import random
import subprocess

from qt_api import Qt, pyqtSignal
from qt_api import QTimer
from qt_api import QDialog, QLabel, QFont, QFontDatabase, QLineEdit
from qt_api import QColor, QLinearGradient, QPainter, QPointF, QRadialGradient, QRectF, QSvgRenderer
from qt_api import QElapsedTimer, QEvent, QPixmap, QRegion

from classes import info, release_details, ui_util
from classes.logger import log
from classes.app import get_app
from classes.metrics import track_metric_screen
from windows.views.credits_treeview import CreditsTreeView
from windows.views.changelog_treeview import ChangelogTreeView
from windows.views.menu import StyledContextMenu

import threading
import json
import datetime

import openshot

try:
    import distro
except ImportError:
    distro = None


def parse_changelog(changelog_path):
    """Parse changelog data from specified gitlab-ci generated file."""
    if not os.path.exists(changelog_path):
        return None
    changelog_regex = re.compile(r'(\w{6,10})\s+(\d{4}-\d{2}-\d{2})\s+(.*?)\s{2,}(.*)')
    changelog_list = []
    try:
        with codecs.open(changelog_path, 'r', encoding='utf_8') as changelog_file:
            # Split changelog safely (since multiline regex fails to parse the windows line endings correctly)
            # All our log files use unit line endings (even on Windows)
            change_log_lines = changelog_file.read().split("\n")
            for change in change_log_lines:
                # Generate match object with fields from all matching lines
                match = changelog_regex.findall(change)
                if match:
                    changelog_list.append({
                        "hash": match[0][0].strip(),
                        "date": match[0][1].strip(),
                        "author": match[0][2].strip(),
                        "subject": match[0][3].strip(),
                        })
    except Exception:
        log.warning("Parse error reading {}".format(changelog_path), exc_info=1)
        return None
    log.debug("Parsed {} changelog lines from {}".format(len(changelog_list), changelog_path))
    return changelog_list


class About(QDialog):
    """ About Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'about.ui')
    releaseFound = pyqtSignal(str)

    def __init__(self):
        # Create dialog class
        super().__init__()

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        self.setObjectName("aboutDialog")
        ui_util.init_ui(self)
        self.about_logo = QSvgRenderer(":/about/about-wordmark.svg", self)
        self.background_cache_key = None
        self.particle_time = 0.0
        self.particle_clock = QElapsedTimer()
        self.particle_timer = QTimer(self)
        self.particle_timer.setInterval(50)
        self.particle_timer.timeout.connect(self.advance_particles)
        # Fixed seeds keep resizing/reopening from reshuffling the star field.
        rng = random.Random(2008)
        self.particles = [
            (rng.random(), rng.random(), rng.uniform(9.0, 22.0),
             rng.uniform(-6.0, 6.0), rng.uniform(0, math.tau), i % 6)
            for i in range(28)
        ]
        self.particle_frame = []

        # get translations
        self.app = get_app()
        _ = self.app._tr

        self.setStyleSheet("""
            QDialog#aboutDialog { background: transparent; border: none; }
            QLabel { background: transparent; color: #F4F7FF; }
            QWidget#aboutToolbar {
                background: rgba(12,18,33,95);
                border-top: 1px solid rgba(215,230,255,25);
            }
            QPushButton {
                color: #F4F7FF; background: transparent; border: 1px solid transparent;
                border-radius: 6px; padding: 0px 8px; font-size: 13px;
                min-height: 34px;
            }
            QPushButton:hover { background: rgba(220,232,255,24); }
            QPushButton:focus { border-color: #91C3FF; }
            QPushButton#btnCopyVersionInfo { border-color: rgba(211,226,255,65); padding: 0px 14px; }
            QPushButton#pushButton_3 { background: #DDEBFF; color: #172B4A; font-weight:600; min-width:80px; }
            QPushButton#pushButton_3:hover { background: #FFFFFF; }
        """)
        self.setFont(QFont("Noto Sans", 10))
        self.setMinimumSize(760, 450)
        self.lblAboutLogo.setMinimumHeight(102)
        self.lblAboutLogo.setMinimumWidth(340)
        self.pushButton_3.setDefault(True)
        self.lblAboutCompany.setOpenExternalLinks(True)
        # Hide chnagelog button by default
        self.btnchangelog.setVisible(False)

        projects = ['openshot-qt', 'libopenshot', 'libopenshot-audio']
        # Old paths
        paths = [os.path.join(info.PATH, 'settings', '{}.log'.format(p)) for p in projects]
        # New paths
        paths.extend([os.path.join(info.PATH, 'resources', '{}.log'.format(p)) for p in projects])
        if any([os.path.exists(path) for path in paths]):
            self.btnchangelog.setVisible(True)
        else:
            log.warn("No changelog files found, disabling button")

        self.lblTagline.setText(_("Create. Edit. Inspire."))
        self.lblAboutDescription.setText(_(
            "Award-winning, free, and open-source video editing for Linux, Mac, Chrome OS, and Windows."))
        self.lblAboutCompany.setText(
            '© 2008–%s <a href="https://www.openshotstudios.com?r=about-us" '
            'style="color:#B1BCD1; text-decoration:none;">OpenShot Studios, LLC</a>'
            % datetime.datetime.today().year)
        self.lblVersionHeading.setText(_("VERSION"))
        for key, caption in (("Library", "Libraries"), ("Released", "Date"),
                             ("Build", "Build"), ("Commit", "Package")):
            getattr(self, "lbl%sKey" % key).setText(_(caption))
        for key in ("Library", "Released", "Build", "Commit"):
            getattr(self, "lbl%sValue" % key).setWordWrap(False)
        self.source_details = {}
        self.layout_about_content()
        self.display_release("")
        self.copy_version_tooltip = _("Copy Version Info")
        self.copy_success_message = _("Version info copied to clipboard")
        self.btnCopyVersionInfo.setToolTip(self.copy_version_tooltip)
        self.btnCopyVersionInfo.setText(_("Copy Version Info"))
        self.copy_feedback_timer = QTimer(self)
        self.copy_feedback_timer.setSingleShot(True)
        self.copy_feedback_timer.timeout.connect(self.hide_copy_confirmation)
        self.copy_feedback_label = QLabel(self.copy_success_message, self)
        self.copy_feedback_label.setObjectName("copyFeedbackLabel")
        self.copy_feedback_label.setAlignment(Qt.AlignCenter)
        self.copy_feedback_label.setStyleSheet("""
            QLabel#copyFeedbackLabel {
                background: rgba(20, 25, 35, 240);
                border-radius: 15px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 600;
                padding: 7px 18px;
            }
        """)
        self.copy_feedback_label.hide()

        # set events handlers
        self.btncredit.clicked.connect(self.load_credit)
        self.btnlicense.clicked.connect(self.load_license)
        self.btnchangelog.clicked.connect(self.load_changelog)
        self.btnCopyVersionInfo.clicked.connect(self.copy_version_info)

        # Track metrics
        track_metric_screen("about-screen")

        # Connect signals
        self.releaseFound.connect(self.display_release)

        # Load release details from HTTP
        self.get_current_release()

    def paintEvent(self, event):
        """Composite cached artwork with a small, softly drifting particle field."""
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio, self.lblAboutLogo.geometry().getRect())
        if key != self.background_cache_key:
            self.background_cache_key = key
            self.background_cache = self.make_about_pixmap(ratio)
            background_painter = QPainter(self.background_cache)
            self.paint_background(background_painter)
            background_painter.end()
            self.logo_rect = self.about_logo_rect()
            self.logo_cache = self.make_about_pixmap(ratio, self.logo_rect.size(), transparent=True)
            logo_painter = QPainter(self.logo_cache)
            self.about_logo.render(logo_painter, QRectF(QPointF(0, 0), self.logo_rect.size()))
            logo_painter.end()
            self.particle_sprites = []
            for color, radius in (("#FFFFFF", 3), ("#91C3FF", 4), ("#E35CFF", 5),
                                  ("#FFFFFF", 2), ("#91C3FF", 3), ("#E35CFF", 4)):
                sprite = QPixmap(math.ceil(12 * ratio), math.ceil(12 * ratio))
                sprite.setDevicePixelRatio(ratio)
                sprite.fill(Qt.transparent)
                glow = QRadialGradient(QPointF(6, 6), radius)
                glow.setColorAt(0, QColor(color))
                tint = QColor(color)
                tint.setAlpha(110)
                glow.setColorAt(0.3, tint)
                tint.setAlpha(0)
                glow.setColorAt(1, tint)
                sprite_painter = QPainter(sprite)
                sprite_painter.fillRect(QRectF(0, 0, 12, 12), glow)
                sprite_painter.end()
                self.particle_sprites.append(sprite)
            self.particle_frame = self.current_particle_frame()

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.background_cache)
        exposed = event.region()
        for x, y, opacity, sprite in self.particle_frame:
            if not exposed.intersects(QRectF(x - 6, y - 6, 12, 12).toAlignedRect()):
                continue
            painter.setOpacity(opacity)
            painter.drawPixmap(QPointF(x - 6, y - 6), self.particle_sprites[sprite])
        painter.setOpacity(1)
        if exposed.intersects(self.logo_rect.toAlignedRect()):
            painter.drawPixmap(self.logo_rect.topLeft(), self.logo_cache)
        painter.end()

    def make_about_pixmap(self, ratio, size=None, transparent=False):
        """Keep the background opaque and alpha compositing limited to the logo."""
        size = size or self.size()
        pixmap = QPixmap(math.ceil(size.width() * ratio), math.ceil(size.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.transparent if transparent else QColor("#101827"))
        return pixmap

    def current_particle_frame(self):
        """Return buoyant independent drifts, with fades to hide edge wrapping."""
        frame = []
        width, height = self.width(), self.height()
        t = self.particle_time
        for u, v, speed, drift, phase, sprite in self.particles:
            x = (u * width + drift * t + 12 * math.sin(t * 0.55 + phase)) % width
            y = (v * height - speed * t) % height
            edge = min(1.0, x / 16, (width - x) / 16, y / 16, (height - y) / 16)
            opacity = (0.44 + 0.16 * math.sin(t * 0.22 + phase)) * edge
            # Fade toward the footer, where the small version text needs contrast.
            opacity *= 1.0 - 0.50 * (y / height) ** 2
            frame.append((x, y, opacity, sprite))
        return frame

    def advance_particles(self):
        """Update only the old/new sprite bounds, leaving most pixels untouched."""
        self.particle_time += min(self.particle_clock.restart() / 1000.0, 0.1)
        frame = self.current_particle_frame()
        dirty = QRegion()
        for old, new in zip(self.particle_frame, frame):
            old_rect = QRectF(old[0] - 7, old[1] - 7, 14, 14).toAlignedRect()
            new_rect = QRectF(new[0] - 7, new[1] - 7, 14, 14).toAlignedRect()
            # One small rectangle per particle keeps the clip region simple.
            # At a wrap, keep the two edges separate instead of dirtying a strip.
            if old_rect.intersects(new_rect):
                dirty |= QRegion(old_rect.united(new_rect))
            else:
                dirty |= QRegion(old_rect)
                dirty |= QRegion(new_rect)
        self.particle_frame = frame
        self.update(dirty)

    def update_particle_timer(self):
        """Do no animation work while hidden or minimized."""
        if self.isVisible() and not self.isMinimized():
            if not self.particle_timer.isActive():
                self.particle_clock.start()
                self.particle_timer.start()
        else:
            self.particle_timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        # Set after stylesheet polishing, which resets this attribute. Every
        # exposed pixel is covered by our cache, so Qt need not clear beneath it.
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.update_particle_timer()

    def hideEvent(self, event):
        self.particle_timer.stop()
        super().hideEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange and hasattr(self, "particle_timer"):
            self.update_particle_timer()

    def paint_background(self, painter):
        """Generate the gradient once per size or display-density change."""
        width, height = self.width(), self.height()

        # Overlapping blue, violet and pink light pools echo the website hero.
        # Normalized coordinates keep the composition at any size/aspect ratio.
        painter.save()
        painter.scale(width, height)
        canvas = QRectF(0, 0, 1, 1)
        base = QLinearGradient(0, 0, 1, 1)
        base.setColorAt(0, QColor("#0C1730"))
        base.setColorAt(0.40, QColor("#21123D"))
        base.setColorAt(0.72, QColor("#341442"))
        base.setColorAt(1, QColor("#101827"))
        painter.fillRect(canvas, base)
        for x, y, radius, color, alpha in (
                (-0.04, 0.18, 0.72, "#0065ED", 215),
                (0.58, -0.16, 0.74, "#741BEB", 235),
                (1.06, 0.43, 0.66, "#EA189B", 235),
                (0.28, 0.85, 0.55, "#3625CB", 125)):
            glow = QRadialGradient(QPointF(x, y), radius)
            tint = QColor(color)
            tint.setAlpha(alpha)
            glow.setColorAt(0, tint)
            tint.setAlpha(int(alpha * 0.55))
            glow.setColorAt(0.45, tint)
            tint.setAlpha(0)
            glow.setColorAt(1, tint)
            painter.fillRect(canvas, glow)

        # Gently shade the footer to keep version information and controls legible.
        shade = QLinearGradient(0, 0, 0, 1)
        shade.setColorAt(0, QColor(20, 25, 35, 0))
        shade.setColorAt(0.55, QColor(20, 25, 35, 0))
        shade.setColorAt(1, QColor(20, 25, 35, 190))
        painter.fillRect(canvas, shade)
        painter.restore()

    def about_logo_rect(self):
        """Fit the wordmark to its layout space without stretching it."""
        # Reserve real layout space for the logo so translated text cannot overlap it.
        area = QRectF(self.lblAboutLogo.geometry()).adjusted(0, 0, 0, 0)
        size = self.about_logo.viewBoxF().size()
        size.scale(area.size(), Qt.KeepAspectRatio)
        logo_rect = QRectF(QPointF(0, 0), size)
        logo_rect.moveCenter(area.center())
        return logo_rect

    def contextMenuEvent(self, event):
        """Handle right-click context menu."""
        menu = StyledContextMenu(parent=self)

        # get translations
        self.app = get_app()
        _ = self.app._tr

        # Add "Copy Version Info" action
        copy_action = menu.addAction(_("Copy Version Info"))
        action = menu.exec_(event.globalPos())

        if action == copy_action:
            self.copy_version_info()

    def copy_version_info(self):
        """Copy a compact markdown version info block to the clipboard."""
        clipboard = get_app().clipboard()
        clipboard.setText(self.build_version_info_markdown())
        self.show_copy_confirmation()

    def show_copy_confirmation(self):
        """Briefly confirm the copy action through the glyph tooltip."""
        self.btnCopyVersionInfo.setToolTip(self.copy_success_message)
        self.copy_feedback_label.setText(self.copy_success_message)
        self.copy_feedback_label.adjustSize()
        self.position_copy_confirmation()
        self.copy_feedback_label.raise_()
        self.copy_feedback_label.show()
        self.copy_feedback_timer.start(1500)

    def hide_copy_confirmation(self):
        """Hide copy confirmation and restore the glyph tooltip."""
        self.copy_feedback_label.hide()
        self.btnCopyVersionInfo.setToolTip(self.copy_version_tooltip)

    def position_copy_confirmation(self):
        """Center the copy confirmation above the bottom buttons."""
        label_size = self.copy_feedback_label.sizeHint()
        x = int((self.width() - label_size.width()) / 2)
        y = max(0, self.height() - label_size.height() - 52)
        self.copy_feedback_label.move(x, y)

    def layout_about_content(self):
        """Align both columns to the same header and body bands as the artwork."""
        width, height = self.width(), self.height()
        sx, sy = width / 760.0, (height - 72) / 378.0
        def place(widget, x, y, w, h):
            widget.setGeometry(round(x * sx), round(y * sy), round(w * sx), round(h * sy))
        place(self.lblAboutLogo, 40, 36, 352, 102)
        place(self.lblVersionHeading, 446, 47, 272, 22)
        place(self.txtversion, 446, 79, 272, 38)
        place(self.lblTagline, 40, 174, 352, 42)
        place(self.lblAboutDescription, 40, 226, 348, 62)
        place(self.lblAboutCompany, 40, 334, 352, 22)
        place(self.columnSeparator, 416, 43, 1, 303)
        for i, key in enumerate(("Build", "Released", "Library", "Commit")):
            y, h = 177 + i * 32, 24
            place(getattr(self, "lbl%sKey" % key), 446, y, 54, h)
            place(getattr(self, "lbl%sValue" % key), 506, y, 234, h)
        self.aboutToolbar.setGeometry(0, height - 72, width, 72)
        self.btnCopyVersionInfo.setFixedSize(168, 36)
        self.pushButton_3.setFixedSize(98, 36)
        for button, size in ((self.btncredit, 66), (self.btnlicense, 66), (self.btnchangelog, 93)):
            button.setFixedSize(size, 36)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout_about_content()
        for key in ("Library", "Released", "Build", "Commit"):
            label = getattr(self, "lbl%sValue" % key)
            label.setText(label.fontMetrics().elidedText(label.toolTip(), Qt.ElideRight, label.width()))
        if hasattr(self, "copy_feedback_label") and self.copy_feedback_label.isVisible():
            self.position_copy_confirmation()

    def build_version_info_markdown(self):
        """Return a compact markdown block with version, system, and performance info."""
        lines = ["**OpenShot Version Info**", ""]

        def add(label, value):
            lines.append(f"- **{label}:** {value}")

        build, date, package = self.about_build_summary()
        add("Version", info.VERSION)
        add("Build", build)
        add("Build Date", date)
        add("Libraries", f"Video {openshot.OPENSHOT_VERSION_FULL} | Audio {self.audio_version()}")
        add("Package", package)
        add("OS", self.get_os_details())
        cpu = self.get_cpu_details()
        if cpu:
            add("CPU", cpu)
        memory = self.get_ram_details()
        if memory:
            add("Memory", memory)

        from classes.distribution import distribution_label
        add("Distribution", distribution_label())
        if self.source_details:
            add("Source", " | ".join(f"{key}: {value}" for key, value in self.source_details.items()))
        metadata = release_details.get_build_details()
        for project in ('openshot-qt', 'libopenshot', 'libopenshot-audio'):
            component = metadata.get(project) or {}
            commit = component.get('CI_COMMIT_SHA') if isinstance(component, dict) else None
            if commit:
                add(f"{project} commit", commit)
        build_name, _ = self.get_build_details()
        if build_name:
            add("Build identifier", build_name)

        diagnostics = getattr(self.app, "gpu_diagnostics", None)
        details = self.get_performance_details()
        details.extend(diagnostics.copy_lines() if diagnostics else ["GPU diagnostics: not collected"])
        for detail in details:
            label, separator, value = detail.partition(":")
            if separator:
                add(label, value.lstrip())
            else:
                lines.append("- " + detail)
        return "\n".join(lines)

    def get_build_details(self):
        """Return the recorded build identifier and date when available."""
        metadata = release_details.get_build_details()
        date = ''
        if metadata.get('date'):
            try:
                date = datetime.datetime.strptime(metadata['date'], '%Y-%m-%d %H:%M').strftime('%Y-%m-%d')
            except (TypeError, ValueError):
                pass
        return metadata.get('build_name') or '', date

    def get_os_details(self):
        """Return a compact OS name/version string."""
        system_name = platform.system()
        if system_name == "Linux" and distro:
            distro_name = " ".join(part for part in distro.linux_distribution()[0:2] if part)
            return distro_name or "Linux"
        if system_name == "Windows":
            version_parts = [part for part in platform.win32_ver()[0:2] if part]
            return " ".join(version_parts) or "Windows"
        if system_name == "Darwin":
            mac_version = platform.mac_ver()[0]
            return f"macOS {mac_version}" if mac_version else "macOS"
        return platform.platform()

    def get_cpu_details(self):
        """Return a compact CPU description when available."""
        system_name = platform.system()
        cpu_name = ""

        try:
            if system_name == "Linux" and os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as cpuinfo_file:
                    for line in cpuinfo_file:
                        if ":" in line and line.lower().startswith("model name"):
                            cpu_name = line.split(":", 1)[1].strip()
                            break
            elif system_name == "Darwin":
                cpu_name = platform.processor().strip()
            elif system_name == "Windows":
                cpu_name = platform.processor().strip()
        except Exception:
            log.warning("Failed to gather CPU details", exc_info=1)

        cpu_name = cpu_name or platform.processor().strip() or platform.machine().strip()
        cpu_count = os.cpu_count()
        if cpu_name and cpu_count:
            return f"{cpu_name} ({cpu_count} threads)"
        return cpu_name

    def get_ram_details(self):
        """Return total system RAM in GB when available."""
        total_bytes = 0
        try:
            if platform.system() == "Windows":
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                memory_status = MEMORYSTATUSEX()
                memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):
                    total_bytes = int(memory_status.ullTotalPhys)
            else:
                page_size = os.sysconf("SC_PAGE_SIZE")
                phys_pages = os.sysconf("SC_PHYS_PAGES")
                total_bytes = int(page_size * phys_pages)
        except Exception:
            log.warning("Failed to gather RAM details", exc_info=1)

        if total_bytes <= 0:
            return ""
        return f"{round(total_bytes / float(1024 ** 3))} GB"

    def get_performance_details(self):
        """Return compact cache and thread settings."""
        settings = get_app().get_settings()
        cache_mode = settings.get("cache-mode") or "CacheMemory"
        cache_mode_map = {
            "CacheMemory": "Memory",
            "CacheDisk": "Disk",
        }
        cache_limit = settings.get("cache-limit-mb")
        cache_frames = settings.get("cache-max-frames")
        cache_ahead = settings.get("cache-ahead-percent")
        cache_preroll_min = settings.get("cache-preroll-min-frames")
        cache_preroll_max = settings.get("cache-preroll-max-frames")
        omp_threads = settings.get("omp_threads_number")
        ff_threads = settings.get("ff_threads_number")
        hw_decoder = self.get_hardware_decoder_name(settings.get("hw-decoder"))
        hw_decode_card = settings.get("graca_number_de")
        hw_encode_card = settings.get("graca_number_en")

        cache_ahead_pct = int(round(float(cache_ahead) * 100))

        return [
            (
                f"Cache: {cache_mode_map.get(cache_mode, cache_mode)}, "
                f"{cache_limit} MB, {cache_frames} frames, "
                f"ahead {cache_ahead_pct}%, pre-roll {cache_preroll_min}/{cache_preroll_max}"
            ),
            (
                f"Performance: Threads: OMP {omp_threads} | FFmpeg {ff_threads}, "
                f"Legacy HW preferences: Decode: {hw_decoder} ({hw_decode_card}) | Encode: {hw_encode_card}"
            ),
        ]

    def get_hardware_decoder_name(self, decoder_value):
        """Return a short hardware decoder label for the current setting value."""
        decoder_map = {
            "0": "None",
            "1": "VA-API",
            "2": "NVDEC",
            "3": "D3D9",
            "4": "D3D11",
            "5": "MacOS",
            "6": "VDPAU",
            "7": "QSV",
        }
        return decoder_map.get(str(decoder_value), str(decoder_value))

    def audio_version(self):
        """Ask the loaded audio library, independently of package metadata."""
        getter = getattr(openshot, "GetAudioVersion", None)
        return getter() if callable(getter) else self.app._tr("Not available")

    def about_build_summary(self):
        """Describe only build provenance that this copy actually records."""
        from classes.distribution import get_distribution_info
        _ = self.app._tr
        metadata = release_details.get_build_details()
        qt = metadata.get('openshot-qt') or {}
        if not isinstance(qt, dict):
            qt = {}
        name = metadata.get('build_name') or ''
        number = str(qt.get('CI_PIPELINE_ID') or '')
        if not number.isdecimal():
            number = ''
        match = re.search(r'-(?:daily|release-candidate)-(\d+)', name)
        if not number and match:
            number = match.group(1)
        if release_details.is_release_build(metadata, getattr(self, 'release_metadata', None)):
            kind = _('Release')
        elif '-release-candidate' in name:
            kind = _('RC')
        elif '-daily' in name:
            kind = _('Daily')
        elif name == 'OpenShot-v' + info.VERSION and release_details.RELEASE_VERSION_RE.fullmatch(info.VERSION):
            # A recorded release artifact describes its build type, independently
            # of the online commit check used to confirm official provenance.
            kind = _('Release')
        else:
            local = self.source_details or metadata.get('build_type') == 'local'
            kind = _('Local') if local else _('External')
        build = kind + (' | ' + str(number) if number else '')
        date = _('Not recorded')
        if metadata.get('date'):
            try:
                parsed = datetime.datetime.strptime(metadata['date'], '%Y-%m-%d %H:%M')
                date = parsed.strftime('%B %d, %Y').replace(' 0', ' ')
            except (TypeError, ValueError):
                pass
        distribution = get_distribution_info()
        formats = {'appimage': 'AppImage', 'flatpak': 'Flatpak', 'snap': 'Snap',
                   'msix': 'MSIX', 'exe': 'Windows installer', 'appbundle': 'macOS app'}
        package = formats.get(distribution['package_type'])
        if not package:
            package = _('Source checkout') if self.source_details else _('Unknown')
        package += ' | ' + platform.system() + ' ' + platform.machine()
        return build, date, package

    def display_release(self, version_text):
        """Keep four version rows balanced for packaged and source builds."""
        self.txtversion.setText(info.VERSION)
        build, date, package = self.about_build_summary()
        values = {'Library': self.app._tr('Video %s') % openshot.OPENSHOT_VERSION_FULL
                  + ' | ' + self.app._tr('Audio %s') % self.audio_version(),
                  'Released': date, 'Build': build, 'Commit': package}
        for key, value in values.items():
            label = getattr(self, "lbl%sValue" % key)
            label.setTextFormat(Qt.PlainText)
            label.setToolTip(value)
            available = label.width() - label.margin() * 2
            label.setText(label.fontMetrics().elidedText(value, Qt.ElideRight, available))
        self.txtversion.setToolTip(version_text)

    def read_source_details(self):
        """Read real checkout metadata on the release worker, never the UI thread."""
        root = os.path.dirname(info.PATH)
        if not os.path.exists(os.path.join(root, ".git")):
            return {}
        try:
            def git(*args):
                return subprocess.check_output(
                    ["git", "-C", root, *args], text=True, timeout=2,
                    stderr=subprocess.DEVNULL).strip()
            commit, date = git("show", "-s", "--format=%h%n%cs", "HEAD").splitlines()
            return dict(commit=commit, date=date, branch=git("branch", "--show-current"))
        except (OSError, subprocess.SubprocessError, ValueError):
            return {}

    def get_current_release(self):
        """Get the current version """
        t = threading.Thread(target=self.get_release_from_http, daemon=True)
        t.start()

    def get_release_from_http(self):
        """Get the current version # from openshot.org"""
        try:
            self.source_details = self.read_source_details()
            release_metadata = release_details.get_release_details(info.VERSION)
            self.release_metadata = release_metadata

            # get translations
            self.app = get_app()
            _ = self.app._tr

            # Look for frozen version info
            frozen_version_label = ""
            version_info = release_details.get_build_details()
            if version_info:
                qt_metadata = version_info.get("openshot-qt")
                frozen_git_SHA = qt_metadata.get("CI_COMMIT_SHA", "") if isinstance(qt_metadata, dict) else ""
                build_name = version_info.get('build_name') or ""
                string_release_date = _("Release Date")
                string_release_notes = _("Release Notes")
                string_official = _("Official")
                version_date = version_info.get("date")

                formatted_date = ""
                if version_date:
                    try:
                        date_obj = datetime.datetime.strptime(version_date, "%Y-%m-%d %H:%M")
                        formatted_date = date_obj.strftime("%Y-%m-%d")
                    except Exception:
                        log.warning("Failed to parse release date: %s", version_date, exc_info=1)

                if release_details.is_release_build(version_info, release_metadata):
                    # Remove -release-candidate... from build name
                    log.warning(
                        "Official release detected with SHA (%s) for v%s" %
                        (release_metadata.get("sha", ""), info.VERSION))
                    build_name = build_name.replace("-candidate", "")
                    frozen_version_label = f'{build_name} | {string_official}'
                    if formatted_date:
                        frozen_version_label += f'<br/>{string_release_date}: {formatted_date}'
                    release_notes = release_metadata.get("notes")
                    if string_release_notes and release_notes:
                        frozen_version_label += (
                            f' | <a href="{release_notes}" '
                            f'style="text-decoration:none;color: #91C3FF;">{string_release_notes}</a>')
                else:
                    # Display current build name - unedited
                    if release_metadata:
                        log.warning("Build SHA (%s) does not match an official release SHA (%s) for v%s" %
                                    (frozen_git_SHA, release_metadata.get("sha", ""), info.VERSION))
                    frozen_version_label = build_name or ""
                    if formatted_date:
                        frozen_version_label += f"<br/>{string_release_date}: {formatted_date}"

            # Init some variables
            openshot_qt_version = _("Version: %s") % info.VERSION
            libopenshot_version = "%s" % openshot.OPENSHOT_VERSION_FULL
            version_text = f"{openshot_qt_version} | {libopenshot_version}"
            if frozen_version_label:
                version_text += f"<br/>{frozen_version_label}"

            # emit release found
            self.releaseFound.emit(version_text)

        except Exception:
            log.warning("Failed to get OpenShot release details", exc_info=True)


    def load_credit(self):
        """ Load Credits for everybody who has contributed in several domain for Openshot """
        log.debug('Credit screen has been opened')
        windo = Credits()
        windo.exec_()

    def load_license(self):
        """ Load License of the project """
        log.debug('License screen has been opened')
        windo = License()
        windo.exec_()

    def load_changelog(self):
        """ Load the changelog window """
        log.debug('Changelog screen has been opened')
        windo = Changelog()
        windo.exec_()


def style_information_dialog(dialog, width, height):
    """Shared readable typography and footer sizing, using each theme's colors."""
    dialog.resize(width, height)
    dialog.setMinimumSize(560, 420)
    dialog.setStyleSheet("""
        QLabel, QLineEdit, QTreeView, QHeaderView, QTabBar { font-size: 13px; }
        QLineEdit { min-height: 30px; padding: 0px 8px; }
        QTreeView::item { padding: 4px 0px; }
        QPushButton { font-size: 13px; min-height: 32px; padding: 0px 16px; }
        QPushButton#btnclose { border: 1px solid palette(mid); border-radius: 4px; }
    """)
    dialog.btnclose.setMinimumWidth(88)
    dialog.btnclose.setDefault(True)
    for field in dialog.findChildren(QLineEdit):
        field.setClearButtonEnabled(True)


class License(QDialog):
    """ License Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'license.ui')

    def __init__(self):
        # Create dialog class
        super().__init__()

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init Ui
        ui_util.init_ui(self)
        style_information_dialog(self, 680, 640)

        # get translations
        self.app = get_app()
        _ = self.app._tr

        # Init license
        with open(os.path.join(info.RESOURCES_PATH, 'license.txt'), 'r') as my_license:
            text = my_license.read()
            font = QFontDatabase.systemFont(getattr(QFontDatabase, "SystemFont", QFontDatabase).FixedFont)
            font.setPixelSize(13)
            self.textBrowser.setStyleSheet('font-family: "%s"; font-size: 13px;' % font.family())
            self.textBrowser.document().setDefaultFont(font)
            self.textBrowser.document().setDocumentMargin(16)
            self.textBrowser.setPlainText(text)

        # Scroll to top
        cursor = self.textBrowser.textCursor()
        cursor.setPosition(0)
        self.textBrowser.setTextCursor(cursor)


class Credits(QDialog):
    """ Credits Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'credits.ui')


    def __init__(self):

        # Create dialog class
        super().__init__()

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init Ui
        ui_util.init_ui(self)
        style_information_dialog(self, 860, 580)


        # get translations
        self.app = get_app()
        _ = self.app._tr

        # Update supporter button
        supporter_text = _("Become a Supporter")
        supporter_html = '''
            <p align="left">
              <a href="https://www.openshot.org/%sdonate/?app-about-us">%s</a>
            </p>
            ''' % (info.website_language(), supporter_text)
        self.lblBecomeSupporter.setText(supporter_html)

        # Get list of developers
        developer_list = []
        with codecs.open(
                os.path.join(info.RESOURCES_PATH, 'contributors.json'), 'r', 'utf_8'
                ) as contributors_file:
            developer_string = contributors_file.read()
            developer_list = json.loads(developer_string)

        self.developersListView = CreditsTreeView(
            credits=developer_list, columns=["email", "website"])
        self.vboxDevelopers.addWidget(self.developersListView)
        self.txtDeveloperFilter.textChanged.connect(
            self.developersListView.filter_changed)

        # Get string of translators for the current language
        translator_credits = []
        unique_translators = []
        translator_credits_string = _("translator-credits").replace(
            "Launchpad Contributions:\n", ""
            ).replace("translator-credits", "")
        if translator_credits_string:
            # Parse string into a list of dictionaries
            translator_rows = translator_credits_string.split("\n")
            stripped_rows = [s.strip().capitalize() for s in translator_rows if "Template-Name:" not in s]
            for row in sorted(stripped_rows):
                # Split each row into 2 parts (name and username)
                translator_parts = row.split("https://launchpad.net/")
                if len(translator_parts) >= 2:
                    name = translator_parts[0].strip().title()
                    username = translator_parts[1].strip()
                    if username not in unique_translators:
                        unique_translators.append(username)
                        translator_credits.append({
                            "name": name,
                            "website": "https://launchpad.net/%s" % username
                            })

            # Add translators listview
            self.translatorsListView = CreditsTreeView(
                translator_credits, columns=["website"])
            self.vboxTranslators.addWidget(self.translatorsListView)
            self.txtTranslatorFilter.textChanged.connect(
                self.translatorsListView.filter_changed)
        else:
            # No translations for this language, hide credits
            self.tabCredits.removeTab(1)

        # Get list of supporters
        supporter_list = []
        with codecs.open(
                os.path.join(info.RESOURCES_PATH, 'supporters.json'), 'r', 'utf_8'
                ) as supporter_file:
            supporter_string = supporter_file.read()
            supporter_list = json.loads(supporter_string)

        # Add supporters listview
        self.supportersListView = CreditsTreeView(
            supporter_list, columns=["website"])
        self.vboxSupporters.addWidget(self.supportersListView)
        self.txtSupporterFilter.textChanged.connect(
            self.supportersListView.filter_changed)


class Changelog(QDialog):
    """ Changelog Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'changelog.ui')

    def __init__(self):

        # Create dialog class
        super().__init__()

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init Ui
        ui_util.init_ui(self)
        style_information_dialog(self, 980, 600)


        # get translations
        _ = get_app()._tr

        # Connections to objects imported from .ui file
        tab = {
            "openshot-qt": self.tab_openshot_qt,
            "libopenshot": self.tab_libopenshot,
            "libopenshot-audio": self.tab_libopenshot_audio,
        }
        vbox = {
            "openshot-qt": self.vbox_openshot_qt,
            "libopenshot": self.vbox_libopenshot,
            "libopenshot-audio": self.vbox_libopenshot_audio,
        }

        # Update github link button
        github_text = _("OpenShot on GitHub")
        github_html = '''
            <p align="left">
                <a href="https://github.com/OpenShot/">%s</a>
            </p>
            ''' % (github_text)
        self.lblGitHubLink.setText(github_html)

        # Read changelog file for each project
        for project in ['openshot-qt', 'libopenshot', 'libopenshot-audio']:
            changelog_list = None
            for directory in ('settings', 'resources'):
                changelog_path = os.path.join(info.PATH, directory, '{}.log'.format(project))
                if os.path.exists(changelog_path):
                    changelog_list = parse_changelog(changelog_path)
                    if changelog_list:
                        break
            if not changelog_list:
                log.warn("Could not load changelog for {}".format(project))
                # Hide the tab for this changelog
                tabindex = self.tabChangelog.indexOf(tab[project])
                if tabindex >= 0:
                    self.tabChangelog.removeTab(tabindex)
                continue
            # Populate listview widget with changelog data
            cl_treeview = ChangelogTreeView(
                commits=changelog_list,
                commit_url="https://github.com/OpenShot/{}/commit/%s/".format(project))
            vbox[project].addWidget(cl_treeview)
            if project == 'openshot-qt':
                self.txtChangeLogFilter_openshot_qt.textChanged.connect(cl_treeview.filter_changed)
            elif project == 'libopenshot':
                self.txtChangeLogFilter_libopenshot.textChanged.connect(cl_treeview.filter_changed)
            else:
                self.txtChangeLogFilter_libopenshot_audio.textChanged.connect(cl_treeview.filter_changed)

        if self.tabChangelog.count() == 0:
            self.tabChangelog.hide()
            empty = QLabel(_("Changelog details are not included with this build.\nView the project history on GitHub."), self)
            empty.setObjectName("lblEmptyChangelog")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            self.verticalLayout.insertWidget(0, empty, 1)
