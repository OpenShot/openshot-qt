"""
 @file
 @brief This file is responsible for serializing copy/paste clipboard data for OpenShot
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2024 OpenShot Studios, LLC
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

import pickle
import json
from PyQt5.QtCore import QMimeData
from classes.query import QueryObject


class ClipboardManager:
    """ Manages clipboard operations for QueryObjects or lists of QueryObjects """
    MIME_TYPE = "application/x-flowcut-generic"

    @staticmethod
    def to_mime(data):
        """
        Converts QueryObject or list of QueryObjects to QMimeData.
        Handles both JSON (for text) and pickled formats.
        """
        mime_data = QMimeData()

        # Unpack if only a single item in a list
        if isinstance(data, list) and len(data) == 1:
            data = data[0]

        try:
            # If data is a single QueryObject, serialize its .data attribute
            json_data = {}
            if isinstance(data, QueryObject):
                json_data = json.dumps(data.data, indent=4)
            # If data is a list of QueryObjects, serialize the list of .data attributes
            elif isinstance(data, list) and all(isinstance(obj, QueryObject) for obj in data):
                json_data = json.dumps([obj.data for obj in data], indent=4)

            # Pickle the entire object (single or list) for the custom MIME format
            pickled_data = pickle.dumps(data)

            # Set the JSON representation of .data as the text
            mime_data.setText(json_data)

            # Set the pickled data in the custom MIME format
            mime_data.setData(ClipboardManager.MIME_TYPE, pickled_data)

        except (TypeError, AttributeError) as e:
            print(f"Error serializing data: {e}")

        return mime_data

    @staticmethod
    def from_mime(mime_data):
        """
        Converts QMimeData back into the original object (QueryObject or list of QueryObjects).
        Assumes the data is pickled.
        """
        if mime_data.hasFormat(ClipboardManager.MIME_TYPE):
            try:
                pickled_data = mime_data.data(ClipboardManager.MIME_TYPE).data()
                return pickle.loads(pickled_data)
            except (pickle.UnpicklingError, AttributeError) as e:
                print(f"Error unpickling data: {e}")

        print("No valid Flowcut MIME type found.")
        return None
