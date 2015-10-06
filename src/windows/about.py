"""
 @file
 @brief This file loads the About dialog (i.e about Openshot Project)
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2014 OpenShot Studios, LLC
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

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from classes import info, ui_util
from classes.logger import log
from classes.app import get_app


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
        self.txtversion.setText(info.VERSION)
        self.txtversion.setAlignment(Qt.AlignCenter)

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
        # license_path = os.path.join(path_xdg, 'COPYING')
        # license_path = os.path.join(info.PATH, 'COPYING')
        # my_license = open('license_path', "r")
        # content = my_license.read()
        # for text in license_path:
        # self.textBrowser.append(text)
        # self.textBrowser.append(content)
        with open("(os.path.join(info.PATH, 'COPYING'))", 'r') as my_license:
            text = my_license.read()
            self.textBrowser.append(text)


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

        # Init authors
        authors = []
        for person in info.CREDITS['code']:
            name = person['name']
            email = person['email']
            authors.append("%s <%s>" % (name, email))
        self.textBrowserwritten.append(str(authors))

        # Init documentaters
        authors = []
        for person in info.CREDITS['documentation']:
            name = person['name']
            email = person['email']
            authors.append("%s <%s>" % (name, email))
        self.textBrowserdocumented.append(str(authors))

        # Init artwork
        artists = []
        for person in info.CREDITS['artwork']:
            name = person['name']
            email = person['email']
            artists.append("%s <%s>" % (name, email))
        self.textBrowserartwork.append(str(artists))

        # Init translation authors
        authors = []
        for person in info.CREDITS['translation']:
            name = person['name']
            email = person['email']
            authors.append("%s <%s>" % (name, email))
        self.textBrowsertranslated.append(str(authors))

        # Init Kicstarter Backers
        # backers = []
        # for person in info.CREDITS['backers']
        # name = person['name']
        # email = person['email']
        # backers.append("%s <%s>" % (name, email))
        # self.textBrowserkickstarter.append(str(backers))
