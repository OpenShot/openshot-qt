"""
 @file
 @brief This file loads the About dialog (i.e about Openshot Project)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
from functools import partial

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from classes import info, ui_util
from classes.logger import log
from classes.app import get_app
from classes.metrics import *
from windows.views.credits_treeview import CreditsTreeView

try:
    import json
except ImportError:
    import simplejson as json


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

        # set events handlers
        self.btncredit.clicked.connect(self.load_credit)
        self.btnlicense.clicked.connect(self.load_license)

        # Init some variables
        self.txtversion.setText(_("Version: %s") % info.VERSION)
        self.txtversion.setAlignment(Qt.AlignCenter)

        # Track metrics
        track_metric_screen("about-screen")

    def load_credit(self):
        """ Load Credits for everybody who has contribuated in several domain for Openshot """
        log.info('Credit screen has been opened')
        windo = Credits()
        windo.exec_()

    def load_license(self):
        """ Load License of the project """
        log.info('License screen has been opened')
        windo = License()
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
        with open(os.path.join(info.PATH, 'settings', 'license.txt'), 'r') as my_license:
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

        # Add credits listview
        self.developersListView = CreditsTreeView(credits=info.CREDITS['code'], columns=["email", "website"])
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
            # No translations for this langauge, hide credits
            self.tabCredits.removeTab(1)

        # Get list of supporters
        supporter_list = []
        import codecs
        with codecs.open(os.path.join(info.PATH, 'settings', 'supporters.json'), 'r', 'utf-8') as supporter_file:
            supporter_string = supporter_file.read()
            supporter_list = json.loads(supporter_string)

        # Add supporters listview
        self.supportersListView = CreditsTreeView(supporter_list, columns=["website"])
        self.vboxSupporters.addWidget(self.supportersListView)
        self.txtSupporterFilter.textChanged.connect(partial(self.Filter_Triggered, self.txtSupporterFilter, self.supportersListView))

