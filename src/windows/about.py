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

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QDialog

from classes import info, ui_util
from classes.logger import log
from classes.app import get_app
from classes.metrics import track_metric_screen
from windows.views.credits_treeview import CreditsTreeView
from windows.views.changelog_treeview import ChangelogTreeView
from windows.views.menu import StyledContextMenu

import requests
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
        QDialog.__init__(self)

        # Load UI from designer & init
        ui_util.load_ui(self, self.ui_path)
        ui_util.init_ui(self)

        # get translations
        self.app = get_app()
        _ = self.app._tr

        self.setStyleSheet("""
            QDialog {
                background-image: url(:/about/AboutLogo.png);
                background-repeat: no-repeat;
                background-position: center;
                background-size: stretch;
                margin: 0px;
                padding: 0px;
                border: none;
            }
            QLabel#txtversion, QLabel#lblAboutCompany {
                background: transparent;
                margin-bottom: 10px;
            }
        """)

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

        description_text = _("OpenShot Video Editor is an Award-Winning, Free, and<br> Open-Source Video Editor for Linux, Mac, Chrome OS, and Windows.")
        copyright_text = _('Copyright &copy; %(begin_year)s-%(current_year)s') % {
            'begin_year': '2008',
            'current_year': str(datetime.datetime.today().year)
            }
        about_html = '''
            <div align="center" style="">
              <p style="font-size:11pt; font-weight: 300;">%s</p>
            </div>
            ''' % (description_text,)
        company_html = '''
            <div style="font-weight:400;" align="right">
              %s<br>
              <a href="http://www.openshotstudios.com?r=about-us"
                 style="text-decoration:none; color: #91C3FF;">OpenShot Studios, LLC</a>
            </div>
            ''' % (copyright_text)

        # Set description and company labels
        self.lblAboutDescription.setWordWrap(True)
        self.lblAboutDescription.setText(about_html)
        self.lblAboutCompany.setText(company_html)
        self.lblAboutCompany.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.txtversion.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        # set events handlers
        self.btncredit.clicked.connect(self.load_credit)
        self.btnlicense.clicked.connect(self.load_license)
        self.btnchangelog.clicked.connect(self.load_changelog)

        # Track metrics
        track_metric_screen("about-screen")

        # Connect signals
        self.releaseFound.connect(self.display_release)

        # Load release details from HTTP
        self.get_current_release()

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

    def build_version_info_markdown(self):
        """Return a compact markdown block with version, system, and performance info."""
        lines = ["**OpenShot Version Info**"]

        version_line = f"Version: {info.VERSION} | libopenshot: {openshot.OPENSHOT_VERSION_FULL}"
        lines.append(version_line)

        build_name, release_date = self.get_build_details()
        build_parts = []
        if build_name:
            build_parts.append(f"Build: {build_name}")
        if release_date:
            build_parts.append(f"Released: {release_date}")
        if build_parts:
            lines.append(" | ".join(build_parts))

        lines.append(f"OS: {self.get_os_details()}")

        hardware_parts = []
        cpu_name = self.get_cpu_details()
        if cpu_name:
            hardware_parts.append(f"CPU: {cpu_name}")
        ram_total = self.get_ram_details()
        if ram_total:
            hardware_parts.append(f"RAM: {ram_total}")
        if hardware_parts:
            lines.append(" | ".join(hardware_parts))

        lines.extend(self.get_performance_details())
        return "\n".join(lines)

    def get_build_details(self):
        """Return build name and release date from version.json when available."""
        version_path = os.path.join(info.PATH, "settings", "version.json")
        if not os.path.exists(version_path):
            return "", ""

        try:
            with open(version_path, "r", encoding="UTF-8") as f:
                version_info = json.loads(f.read())
        except Exception:
            log.warning("Failed to parse build details from %s", version_path, exc_info=1)
            return "", ""

        build_name = version_info.get("build_name", "")
        release_date = ""
        version_date = version_info.get("date")
        if version_date:
            try:
                date_obj = datetime.datetime.strptime(version_date, "%Y-%m-%d %H:%M")
                release_date = date_obj.strftime("%Y-%m-%d")
            except Exception:
                log.warning("Failed to parse release date: %s", version_date, exc_info=1)
        return build_name, release_date

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
                f"Cards: Decode: {hw_decoder} ({hw_decode_card}) | Encode: {hw_encode_card}"
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
            "5": "VideoToolbox",
            "6": "VDPAU",
            "7": "QSV",
        }
        return decoder_map.get(str(decoder_value), str(decoder_value))

    def display_release(self, version_text):

        version_html = '''
            <div style="font-weight:400;" align="left">
              %s
            </div>
            ''' % (version_text)

        self.txtversion.setText(version_html)

    def get_current_release(self):
        """Get the current version """
        t = threading.Thread(target=self.get_release_from_http, daemon=True)
        t.start()

    def get_release_from_http(self):
        """Get the current version # from openshot.org"""
        RELEASE_URL = 'http://www.openshot.org/releases/%s/'

        # Send metric HTTP data
        try:
            release_details = {}
            r = requests.get(RELEASE_URL % info.VERSION,
                             headers={"user-agent": "openshot-qt-%s" % info.VERSION}, verify=False)
            if r.ok:
                log.warning("Found current release: %s" % r.json())
                release_details = r.json()
            else:
                log.warning("Failed to find current release: %s" % r.status_code)
            release_git_SHA = release_details.get("sha", "")
            release_notes = release_details.get("notes", "")

            # get translations
            self.app = get_app()
            _ = self.app._tr

            # Look for frozen version info
            frozen_version_label = ""
            version_path = os.path.join(info.PATH, "settings", "version.json")
            if os.path.exists(version_path):
                with open(version_path, "r", encoding="UTF-8") as f:
                    version_info = json.loads(f.read())
                    if version_info:
                        frozen_git_SHA = version_info.get("openshot-qt", {}).get("CI_COMMIT_SHA", "")
                        build_name = version_info.get('build_name')
                        string_release_date = _("Release Date")
                        string_release_notes = _("Release Notes")
                        string_official = _("Official")
                        version_date = version_info.get("date")

                        # Parse the date string into a datetime object
                        date_obj = datetime.datetime.strptime(version_date, "%Y-%m-%d %H:%M")
                        formatted_date = date_obj.strftime("%Y-%m-%d")

                        if frozen_git_SHA == release_git_SHA:
                            # Remove -release-candidate... from build name
                            log.warning("Official release detected with SHA (%s) for v%s" % (release_git_SHA, info.VERSION))
                            build_name = build_name.replace("-candidate", "")
                            frozen_version_label = f'{build_name} | {string_official}<br/>{string_release_date}: {formatted_date}'
                            if string_release_notes:
                                frozen_version_label += f' | <a href="{release_notes}" style="text-decoration:none;color: #91C3FF;">{string_release_notes}</a>'
                        else:
                            # Display current build name - unedited
                            log.warning("Build SHA (%s) does not match an official release SHA (%s) for v%s" %
                                        (frozen_git_SHA, release_git_SHA, info.VERSION))
                            frozen_version_label = f"{build_name}<br/>{string_release_date}: {formatted_date}"

            # Init some variables
            openshot_qt_version = _("Version: %s") % info.VERSION
            libopenshot_version = "%s" % openshot.OPENSHOT_VERSION_FULL
            version_text = f"{openshot_qt_version} | {libopenshot_version}"
            if frozen_version_label:
                version_text += f"<br/>{frozen_version_label}"

            # emit release found
            self.releaseFound.emit(version_text)

        except Exception as Ex:
            log.error("Failed to get version from: %s" % RELEASE_URL % info.VERSION)


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


class License(QDialog):
    """ License Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'license.ui')

    def __init__(self):
        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init Ui
        ui_util.init_ui(self)

        # get translations
        self.app = get_app()
        _ = self.app._tr

        # Init license
        with open(os.path.join(info.RESOURCES_PATH, 'license.txt'), 'r') as my_license:
            text = my_license.read()
            self.textBrowser.append(text)

        # Scroll to top
        cursor = self.textBrowser.textCursor()
        cursor.setPosition(0)
        self.textBrowser.setTextCursor(cursor)


class Credits(QDialog):
    """ Credits Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'credits.ui')


    def __init__(self):

        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init Ui
        ui_util.init_ui(self)


        # get translations
        self.app = get_app()
        _ = self.app._tr

        # Update supporter button
        supporter_text = _("Become a Supporter")
        supporter_html = '''
            <p align="center">
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
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init Ui
        ui_util.init_ui(self)


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
            <p align="center">
                <a href="https://github.com/OpenShot/">%s</a>
            </p>
            ''' % (github_text)
        self.lblGitHubLink.setText(github_html)

        # Read changelog file for each project
        for project in ['openshot-qt', 'libopenshot', 'libopenshot-audio']:
            changelog_path = os.path.join(info.PATH, 'settings', '{}.log'.format(project))
            if os.path.exists(changelog_path):
                log.debug("Reading changelog file: {}".format(changelog_path))
                changelog_list = parse_changelog(changelog_path)
            else:
                changelog_list = None
            if changelog_list is None:
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
