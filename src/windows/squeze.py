""" 
 @file
 @brief This file contains the squeze dialog (i.e see the effect applied on the video file)
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

from PyQt5.QtWidgets import *

from classes import info, ui_util
from classes.logger import log
from classes.app import get_app


class Squeze(QDialog):
    """ Squeze Dialog """

    # Path to ui file
    ui_path = os.path.join(info.PATH, 'windows', 'ui', 'squeze.ui')

    def __init__(self):
        # Create dialog class
        QDialog.__init__(self)

        # Load UI from designer
        ui_util.load_ui(self, self.ui_path)

        # Init UI
        ui_util.init_ui(self)

        # Get translations
        app = get_app()
        _ = app._tr


        # set events handlers
        self.btncrop.clicked.connect(self.load_crop)
        self.btnsqueze.clicked.connect(self.load_squeze)
        self.btnletterbox.clicked.connect(self.load_letter_box)
        self.btnnone.clicked.connect(self.close_dialog)
        self.btnnone.pressed.connect(self.reject)

    def load_crop(self):
        log.info('crop function is called')
        pass

    def load_squeze(self):
        log.info('squeze function is called')
        pass

    def load_letter_box(self):
        log.info('letter box function is called')
        pass

    def close_dialog(self):
        # QDialog.close()
        QDialog.rejected()
        log.info('None screen is closed')
