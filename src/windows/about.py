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
from functools import partial

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog

from classes import info, ui_util
from classes.logger import log
from classes.app import get_app
from classes.metrics import track_metric_screen
from windows.views.credits_treeview import CreditsTreeView
from windows.views.changelog_treeview import ChangelogTreeView

import requests
import threading
import json
import datetime

import openshot


def parse_changelog(changelog_path):
    """Parse changelog data from specified gitlab-ci generated file."""
    if not os.path.exists(changelog_path):
        return None
    changelog_regex = re.compile(r'(\w{6,10})\s+(\d{4}-\d{2}-\d{2})\s+(.*)\s{2,99}?(.*)')
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

        # Load logo banner (using display DPI)
        icon = QIcon(":/about/AboutLogo.png")
        self.lblAboutLogo.setPixmap(icon.pixmap(icon.availableSizes()[0]))

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

        create_text = _('Create &amp; Edit Amazing Videos and Movies')
        description_text = _("OpenShot Video Editor is an Award-Winning, Free, and<br> Open-Source Video Editor for Linux, Mac, Chrome OS, and Windows.")
        learnmore_text = _('Learn more')
        copyright_text = _('Copyright &copy; %(begin_year)s-%(current_year)s') % {
            'begin_year': '2008',
            'current_year': str(datetime.datetime.today().year)
            }
        about_html = '''
            <html><head/><body style="padding:24px 0;"><hr/>
            <div align="center" style="margin:12px 0;">
              <p style="font-size:10pt;font-weight:600;margin-bottom:18px;">
                %s
              </p>
              <p style="font-size:10pt;margin-bottom:12px;">%s
                <a href="https://www.openshot.org/%s?r=about-us"
                   style="text-decoration:none;">%s</a>
              </p>
            </div>
            </body></html>
            ''' % (
                create_text,
                description_text,
                info.website_language(),
                learnmore_text)
        company_html = '''
            <html><head/>
            <body style="font-size:10pt;font-weight:400;font-style:normal;padding:24px 0;">
            <hr />
            <div style="margin:12px 0;font-weight:600;" align="center">
              %s
              <a href="http://www.openshotstudios.com?r=about-us"
                 style="text-decoration:none;">OpenShot Studios, LLC</a><br/>
            </div>
            </body></html>
            ''' % (copyright_text)

        # Set description and company labels
        self.lblAboutDescription.setText(about_html)
        self.lblAboutCompany.setText(company_html)

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

    def display_release(self, version_text):

        self.txtversion.setText(version_text)
        self.txtversion.setAlignment(Qt.AlignCenter)

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
                        if frozen_git_SHA == release_git_SHA:
                            # Remove -release-candidate... from build name
                            log.warning("Official release detected with SHA (%s) for v%s" %
                                        (release_git_SHA, info.VERSION))
                            build_name = build_name.replace("-candidate", "")
                            frozen_version_label = f'<br/><br/><b>{build_name} ({string_official})</b><br/>{string_release_date}: {version_date}<br><a href="https://www.openshot.org{release_notes}" style="text-decoration:none;">{string_release_notes}</a>'
                        else:
                            # Display current build name - unedited
                            log.warning("Build SHA (%s) does not match an official release SHA (%s) for v%s" %
                                        (frozen_git_SHA, release_git_SHA, info.VERSION))
                            frozen_version_label = f"<br/><br/><b>{build_name}</b><br/>{string_release_date}: {version_date}"

            # Init some variables
            openshot_qt_version = _("Version: %s") % info.VERSION
            libopenshot_version = "libopenshot: %s" % openshot.OPENSHOT_VERSION_FULL

            # emit release found
            self.releaseFound.emit("<b>%s</b><br/>%s%s" % (openshot_qt_version,
                                                           libopenshot_version,
                                                           frozen_version_label))

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

    def Filter_Triggered(self, textbox, treeview):
        """Callback for filter being changed"""
        # Update model for treeview
        treeview.refresh_view(filter=textbox.text())

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
            <html><head/><body>
            <p align="center">
              <a href="https://www.openshot.org/%sdonate/?app-about-us">%s</a>
            </p>
            </body></html>
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
        self.txtDeveloperFilter.textChanged.connect(partial(
            self.Filter_Triggered,
            self.txtDeveloperFilter,
            self.developersListView))

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
            self.txtTranslatorFilter.textChanged.connect(partial(
                self.Filter_Triggered,
                self.txtTranslatorFilter,
                self.translatorsListView))
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
        self.txtSupporterFilter.textChanged.connect(partial(
            self.Filter_Triggered,
            self.txtSupporterFilter,
            self.supportersListView))


class Changelog(QDialog):
    """ Changelog Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'changelog.ui')

    def Filter_Triggered(self, textbox, treeview):
        """Callback for filter being changed"""
        # Update model for treeview
        treeview.refresh_view(filter=textbox.text())

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
        filter = {
            "openshot-qt": self.txtChangeLogFilter_openshot_qt,
            "libopenshot": self.txtChangeLogFilter_libopenshot,
            "libopenshot-audio": self.txtChangeLogFilter_libopenshot_audio,
        }

        # Update github link button
        github_text = _("OpenShot on GitHub")
        github_html = '''
            <html><head/><body>
            <p align="center">
                <a href="https://github.com/OpenShot/">%s</a>
            </p>
            </body></html>
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
            filter[project].textChanged.connect(
                partial(self.Filter_Triggered, filter[project], cl_treeview))
