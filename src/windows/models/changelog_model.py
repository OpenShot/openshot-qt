""" 
 @file
 @brief This file contains the git changelog model, used by the about window
 @author Jonathan Thomas <jonathan@openshot.org>

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

from PyQt5.QtCore import Qt
from PyQt5.QtGui import *

from classes import info
from classes.logger import log
from classes.app import get_app

import json

class ChangelogStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)


class ChangelogModel():

    def update_model(self, filter=None, clear=True):
        log.info("updating changelog model.")
        app = get_app()
        _ = app._tr

        # Get window to check filters
        win = app.window

        # Clear all items
        if clear:
            log.info('cleared changelog model')
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels([_("Hash"), _("Date"), _("Author"), _("Subject")])

        for commit in self.commit_list:
            # Get details of person
            hash_str = commit.get("hash", "")
            date_str = commit.get("date", "")
            author_str = commit.get("author", "")
            subject_str = commit.get("subject", "")

            if filter and not (
                filter.lower() in hash_str.lower()
                or filter.lower() in date_str.lower()
                or filter.lower() in author_str.lower()
                or filter.lower() in subject_str.lower()
            ):
                continue


            row = []

            # Append name
            col = QStandardItem("Hash")
            col.setText(hash_str)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            col.setToolTip(hash_str)
            row.append(col)

            # Append email
            col = QStandardItem("Date")
            col.setText(date_str)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            col.setToolTip(date_str)
            row.append(col)

            # Append website
            col = QStandardItem("Author")
            col.setText(author_str)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            col.setToolTip(author_str)
            row.append(col)

            # Append website
            col = QStandardItem("Subject")
            col.setText(subject_str)
            col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            col.setToolTip(subject_str)
            row.append(col)

            # Append row to model
            self.model.appendRow(row)

    def __init__(self, commits, *args):

        # Create standard model
        self.app = get_app()
        self.model = ChangelogStandardItemModel()
        self.model.setColumnCount(4)
        self.commit_list = commits
