"""
 @file
 @brief Keyboard-search support for tree views with a thumbnail first column
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


class NameColumnKeyboardSearchMixin:
    """Run Qt's incremental keyboard search against the visible name column."""

    keyboard_search_column = 1

    def keyboardSearch(self, search):
        model = self.model()
        current = self.currentIndex()
        if model and model.rowCount() > 0:
            if current.isValid():
                name_index = current.sibling(current.row(), self.keyboard_search_column)
            else:
                name_index = model.index(0, self.keyboard_search_column)
            if name_index.isValid():
                self.setCurrentIndex(name_index)
        super().keyboardSearch(search)
