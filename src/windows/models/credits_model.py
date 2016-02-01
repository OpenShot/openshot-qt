""" 
 @file
 @brief This file contains the credits model, used by the about window
 @author Jonathan Thomas <jonathan@openshot.org>
 
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

from PyQt5.QtCore import Qt
from PyQt5.QtGui import *

from classes import info
from classes.logger import log
from classes.app import get_app

try:
    import json
except ImportError:
    import simplejson as json


class CreditsStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)


class CreditsModel():
    star_icon = QIcon(os.path.join(info.IMAGES_PATH, "star-icon.png"))
    paypal_icon = QIcon(os.path.join(info.IMAGES_PATH, "paypal-icon.png"))
    kickstarter_icon = QIcon(os.path.join(info.IMAGES_PATH, "kickstarter-icon.png"))

    def update_model(self, filter=None, clear=True):
        log.info("updating credits model.")
        app = get_app()
        _ = app._tr

        # Get window to check filters
        win = app.window

        # Clear all items
        if clear:
            log.info('cleared credits model')
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels(["", "", "", _("Name"), _("Email"), _("Website")])

        for person in self.credits_list:
            # Get details of person
            name = ""
            if "name" in person.keys():
                name = person["name"] or ""
            email = ""
            if "email" in person.keys():
                email = person["email"] or ""
            website = ""
            if "website" in person.keys():
                website = person["website"] or ""
            amount = 0.0
            if "amount" in person.keys():
                amount = person["amount"]
            icons = []
            if "icons" in person.keys():
                icons = person["icons"]

            if filter:
                if not (filter.lower() in name.lower() or filter.lower() in email.lower() or filter.lower() in website.lower()):
                    continue
            if len(name) < 2:
                # Skip blank names
                continue

            row = []

            # Append paypal icon (if needed)
            col = QStandardItem()
            if "p" in icons:
                col.setIcon(QIcon(self.paypal_icon))
                col.setToolTip(_("PayPal Supporter!"))
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            row.append(col)

            # Append kickstarter icon (if needed)
            col = QStandardItem()
            if "k" in icons:
                col.setIcon(QIcon(self.kickstarter_icon))
                col.setToolTip(_("Kickstarter Supporter!"))
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            row.append(col)

            # Append star icon (if needed)
            col = QStandardItem()
            if "s" in icons:
                col.setIcon(QIcon(self.star_icon))
                col.setToolTip(_("Multiple Contributions!"))
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            row.append(col)

            # Append name
            col = QStandardItem("Name")
            col.setText(name)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            row.append(col)

            # Append email
            col = QStandardItem("Email")
            col.setText(email)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            row.append(col)

            # Append website
            col = QStandardItem("Website")
            col.setText(website)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            row.append(col)

            # Append row to model
            self.model.appendRow(row)

    def __init__(self, credits, *args):

        # Create standard model
        self.app = get_app()
        self.model = CreditsStandardItemModel()
        self.model.setColumnCount(6)
        self.credits_list = credits
