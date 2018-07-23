""" 
 @file
 @brief This file contains helper functions for Qt types (string to base64)
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>
 
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

from PyQt5.QtCore import QByteArray


# Utility functions for handling qt types

# QByteArray helpers
def str_to_bytes(string):
    """ This is required to save Qt byte arrays into a base64 string (to save screen preferences) """
    return QByteArray.fromBase64(string.encode("utf-8"))


def bytes_to_str(bytes):
    """ This is required to load base64 Qt byte array strings into a Qt byte array (to load screen preferences) """
    return bytes.toBase64().data().decode("utf-8")
