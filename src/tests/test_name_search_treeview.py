"""
 @file
 @brief Unit tests for tree-view keyboard search
 @author OpenShot Studios, LLC

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
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

import unittest

from qt_api import QApplication, QAbstractItemView, QStandardItem, QStandardItemModel
from qt_api import QTreeView

from windows.views.name_search_treeview import NameColumnKeyboardSearchMixin


class SearchTreeView(NameColumnKeyboardSearchMixin, QTreeView):
    pass


class NameColumnKeyboardSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_keyboard_search_uses_name_instead_of_blank_thumbnail_column(self):
        model = QStandardItemModel()
        for name in ("Alpha", "Bravo", "Charlie"):
            model.appendRow([QStandardItem(""), QStandardItem(name)])

        view = SearchTreeView()
        view.setModel(model)
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        view.setCurrentIndex(model.index(0, 0))

        view.keyboardSearch("c")

        current = view.currentIndex()
        self.assertEqual(current.row(), 2)
        self.assertEqual(current.column(), 1)
        self.assertEqual(current.data(), "Charlie")


if __name__ == "__main__":
    unittest.main()
