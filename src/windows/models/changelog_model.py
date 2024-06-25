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

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem

from classes.logger import log
from classes.app import get_app


class ChangelogStandardItemModel(QStandardItemModel):
    def __init__(self, parent=None):
        QStandardItemModel.__init__(self)


class ChangelogModel():

    def update_model(self, filter=None, clear=True):
        log.info("updating changelog model.")
        app = get_app()
        _ = app._tr

        # Clear all items
        if clear:
            log.info('cleared changelog model')
            self.model.clear()

        # Add Headers
        self.model.setHorizontalHeaderLabels(
            [_("Hash"), _("Date"), _("Author"), _("Subject")])

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
            flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

            col = QStandardItem(hash_str)
            col.setToolTip(hash_str)
            col.setFlags(flags)
            row.append(col)

            col = QStandardItem(date_str)
            col.setToolTip(date_str)
            col.setFlags(flags)
            row.append(col)

            # Append website
            col = QStandardItem(author_str)
            col.setToolTip(author_str)
            col.setFlags(flags)
            row.append(col)

            # Append website
            col = QStandardItem(subject_str)
            col.setToolTip(subject_str)
            col.setFlags(flags)
            row.append(col)

            # Append row to model
            self.model.appendRow(row)

    def __init__(self, commits, *args):

        # Create standard model
        self.app = get_app()
        self.model = ChangelogStandardItemModel()
        self.model.setColumnCount(4)
        self.commit_list = commits
