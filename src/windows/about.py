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
from functools import partial

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from classes import info, ui_util
from classes.logger import log
from classes.app import get_app
from classes.metrics import *
from windows.views.credits_treeview import CreditsTreeView
from windows.views.changelog_treeview import ChangelogTreeView

import json
import datetime

class About(QDialog):
    """ About Dialog """

    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'about.ui')

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

        # Hide chnagelog button by default
        self.btnchangelog.setVisible(False)
        for project in ['openshot-qt', 'libopenshot', 'libopenshot-audio']:
            changelog_path = os.path.join(info.PATH, 'settings', '%s.log' % project)
            if os.path.exists(changelog_path):
                # Attempt to open changelog with utf-8, and then utf-16-le (for unix / windows support)
                for encoding_name in ('utf_8', 'utf_16'):
                    try:
                        with codecs.open(changelog_path, 'r', encoding=encoding_name) as changelog_file:
                            if changelog_file.read():
                                self.btnchangelog.setVisible(True)
                                break
                    except:
                        log.warning('Failed to parse log file %s with encoding %s' % (changelog_path, encoding_name))

        create_text = _('Create &amp; Edit Amazing Videos and Movies')
        description_text = _('OpenShot Video Editor 2.x is the next generation of the award-winning <br/>OpenShot video editing platform.')
        learnmore_text = _('Learn more')
        copyright_text = _('Copyright &copy; %(begin_year)s-%(current_year)s') % {'begin_year': '2008', 'current_year': str(datetime.datetime.today().year) }
        about_html = '<html><head/><body><hr/><p align="center"><span style=" font-size:10pt; font-weight:600;">%s</span></p><p align="center"><span style=" font-size:10pt;">%s </span><a href="https://www.openshot.org/%s?r=about-us"><span style=" font-size:10pt; text-decoration: none; color:#55aaff;">%s</span></a><span style=" font-size:10pt;">.</span></p></body></html>' % (create_text, description_text, info.website_language(), learnmore_text)
        company_html = '<html><head/><body style="font-size:11pt; font-weight:400; font-style:normal;">\n<hr />\n<p align="center" style=" margin-top:12px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><span style=" font-size:10pt; font-weight:600;">%s </span><a href="http://www.openshotstudios.com?r=about-us"><span style=" font-size:10pt; font-weight:600; text-decoration: none; color:#55aaff;">OpenShot Studios, LLC<br /></span></a></p></body></html>' % (copyright_text)

        # Set description and company labels
        self.lblAboutDescription.setText(about_html)
        self.lblAboutCompany.setText(company_html)

        # set events handlers
        self.btncredit.clicked.connect(self.load_credit)
        self.btnlicense.clicked.connect(self.load_license)
        self.btnchangelog.clicked.connect(self.load_changelog)

        # Init some variables
        openshot_qt_version = _("Version: %s") % info.VERSION
        libopenshot_version = "libopenshot: %s" % openshot.OPENSHOT_VERSION_FULL
        self.txtversion.setText("<b>%s</b><br/>%s" % (openshot_qt_version, libopenshot_version))
        self.txtversion.setAlignment(Qt.AlignCenter)

        # Track metrics
        track_metric_screen("about-screen")

    def load_credit(self):
        """ Load Credits for everybody who has contributed in several domain for Openshot """
        log.info('Credit screen has been opened')
        windo = Credits()
        windo.exec_()

    def load_license(self):
        """ Load License of the project """
        log.info('License screen has been opened')
        windo = License()
        windo.exec_()

    def load_changelog(self):
        """ Load the changelog window """
        log.info('Changelog screen has been opened')
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
        supporter_html = '<html><head/><body><p align="center"><a href="https://www.openshot.org/%sdonate/?app-about-us"><span style=" text-decoration: underline; color:#55aaff;">%s</span></a></p></body></html>' % (info.website_language(), supporter_text)
        self.lblBecomeSupporter.setText(supporter_html)

        # Get list of developers
        developer_list = []
        with codecs.open(os.path.join(info.RESOURCES_PATH, 'contributors.json'), 'r', 'utf_8') as contributors_file:
            developer_string = contributors_file.read()
            developer_list = json.loads(developer_string)

        self.developersListView = CreditsTreeView(credits=developer_list, columns=["email", "website"])
        self.vboxDevelopers.addWidget(self.developersListView)
        self.txtDeveloperFilter.textChanged.connect(partial(self.Filter_Triggered, self.txtDeveloperFilter, self.developersListView))

        # Get string of translators for the current language
        translator_credits = []
        translator_credits_string = _("translator-credits").replace("Launchpad Contributions:\n", "").replace("translator-credits","")
        if translator_credits_string:
            # Parse string into a list of dictionaries
            translator_rows = translator_credits_string.split("\n")
            for row in translator_rows:
                # Split each row into 2 parts (name and username)
                translator_parts = row.split("https://launchpad.net/")
                name = translator_parts[0].strip()
                username = translator_parts[1].strip()
                translator_credits.append({"name":name, "website":"https://launchpad.net/%s" % username})

            # Add translators listview
            self.translatorsListView = CreditsTreeView(translator_credits, columns=["website"])
            self.vboxTranslators.addWidget(self.translatorsListView)
            self.txtTranslatorFilter.textChanged.connect(partial(self.Filter_Triggered, self.txtTranslatorFilter, self.translatorsListView))
        else:
            # No translations for this language, hide credits
            self.tabCredits.removeTab(1)

        # Get list of supporters
        supporter_list = []
        with codecs.open(os.path.join(info.RESOURCES_PATH, 'supporters.json'), 'r', 'utf_8') as supporter_file:
            supporter_string = supporter_file.read()
            supporter_list = json.loads(supporter_string)

        # Add supporters listview
        self.supportersListView = CreditsTreeView(supporter_list, columns=["website"])
        self.vboxSupporters.addWidget(self.supportersListView)
        self.txtSupporterFilter.textChanged.connect(partial(self.Filter_Triggered, self.txtSupporterFilter, self.supportersListView))


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
        self.app = get_app()
        _ = self.app._tr

        # Update github link button
        github_text = _("OpenShot on GitHub")
        github_html = '<html><head/><body><p align="center"><a href="https://github.com/OpenShot/"><span style=" text-decoration: underline; color:#55aaff;">%s</span></a></p></body></html>' % (github_text)
        self.lblGitHubLink.setText(github_html)

        # Get changelog for openshot-qt (if any)
        changelog_list = []
        changelog_path = os.path.join(info.PATH, 'settings', 'openshot-qt.log')
        if os.path.exists(changelog_path):
            # Attempt to open changelog with utf-8, and then utf-16-le (for unix / windows support)
            for encoding_name in ('utf_8', 'utf_16'):
                try:
                    with codecs.open(changelog_path, 'r', encoding=encoding_name) as changelog_file:
                        for line in changelog_file:
                            changelog_list.append({'hash': line[:9].strip(),
                                                   'date': line[9:20].strip(),
                                                   'author': line[20:45].strip(),
                                                   'subject': line[45:].strip() })
                        break
                except:
                    log.warning('Failed to parse log file %s with encoding %s' % (changelog_path, encoding_name))
        self.openshot_qt_ListView = ChangelogTreeView(commits=changelog_list, commit_url="https://github.com/OpenShot/openshot-qt/commit/%s/")
        self.vbox_openshot_qt.addWidget(self.openshot_qt_ListView)
        self.txtChangeLogFilter_openshot_qt.textChanged.connect(partial(self.Filter_Triggered, self.txtChangeLogFilter_openshot_qt, self.openshot_qt_ListView))

        # Get changelog for libopenshot (if any)
        changelog_list = []
        changelog_path = os.path.join(info.PATH, 'settings', 'libopenshot.log')
        if os.path.exists(changelog_path):
            # Attempt to open changelog with utf-8, and then utf-16-le (for unix / windows support)
            for encoding_name in ('utf_8', 'utf_16'):
                try:
                    with codecs.open(changelog_path, 'r', encoding=encoding_name) as changelog_file:
                        for line in changelog_file:
                            changelog_list.append({'hash': line[:9].strip(),
                                                   'date': line[9:20].strip(),
                                                   'author': line[20:45].strip(),
                                                   'subject': line[45:].strip() })
                        break
                except:
                    log.warning('Failed to parse log file %s with encoding %s' % (changelog_path, encoding_name))
        self.libopenshot_ListView = ChangelogTreeView(commits=changelog_list, commit_url="https://github.com/OpenShot/libopenshot/commit/%s/")
        self.vbox_libopenshot.addWidget(self.libopenshot_ListView)
        self.txtChangeLogFilter_libopenshot.textChanged.connect(partial(self.Filter_Triggered, self.txtChangeLogFilter_libopenshot, self.libopenshot_ListView))

        # Get changelog for libopenshot-audio (if any)
        changelog_list = []
        changelog_path = os.path.join(info.PATH, 'settings', 'libopenshot-audio.log')
        if os.path.exists(changelog_path):
            # Attempt to support Linux- and Windows-encoded files by opening
            # changelog with utf-8, then utf-16 (endianness via the BOM, which
            # gets filtered out automatically by the decoder)
            for encoding_name in ('utf_8', 'utf_16'):
                try:
                    with codecs.open(changelog_path, 'r', encoding=encoding_name) as changelog_file:
                        for line in changelog_file:
                            changelog_list.append({'hash': line[:9].strip(),
                                                   'date': line[9:20].strip(),
                                                   'author': line[20:45].strip(),
                                                   'subject': line[45:].strip() })
                        break
                except:
                    log.warning('Failed to parse log file %s with encoding %s' % (changelog_path, encoding_name))
        self.libopenshot_audio_ListView = ChangelogTreeView(commits=changelog_list, commit_url="https://github.com/OpenShot/libopenshot-audio/commit/%s/")
        self.vbox_libopenshot_audio.addWidget(self.libopenshot_audio_ListView)
        self.txtChangeLogFilter_libopenshot_audio.textChanged.connect(partial(self.Filter_Triggered, self.txtChangeLogFilter_libopenshot_audio, self.libopenshot_audio_ListView))
