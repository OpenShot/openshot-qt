"""
 @file
 @brief This file contains the titles treeview, used by the title editor window
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

from classes import info
from PyQt5.QtCore import QTimer, Qt, QModelIndex
from PyQt5.QtWidgets import QListView

from windows.models.titles_model import TitlesModel, TitleRoles


class TitlesListView(QListView):
    """ A QListView QWidget used on the title editor window """

    def currentChanged(self, current: QModelIndex, previous: QModelIndex):
        # Get current selection (if any)
        current = self.selectionModel().currentIndex()
        if not current.isValid():
            return

        # Display title in graphicsView
        self.win.filename = current.sibling(current.row(), 0).data(TitleRoles.PathRole)
        self.win.create_temp_title(self.win.filename)
        self.win.load_svg_template()
        # Display temp image (slight delay to allow screen to be shown first)
        QTimer.singleShot(50, self.win.display_svg)

    def refresh_view(self):
        self.title_model.update_model()

        # Sort by column 0
        self.title_model.proxy_model.sort(0)

    def __init__(self, *args, window=None, **kwargs):
        # Invoke parent init
        super().__init__(*args, **kwargs)
        # Get Model data
        self.win = window or self.parent()
        self.title_model = TitlesModel(self.win)
        # Setup header columns
        self.setModel(self.title_model.proxy_model)
        self.setIconSize(info.LIST_ICON_SIZE)
        self.setGridSize(info.LIST_GRID_SIZE)
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.ElideRight)

        self.refresh_view()
