"""
 @file
 @brief This file is used to determine if an extension is an image format
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

def is_image(file_object):
    """Check a File object if the file extension is a known image format"""
    path = file_object["path"].lower()
    img_file_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".svg",
        ".thm",
        ".gif",
        ".bmp",
        ".pgm",
        ".tif",
        ".tiff",
    )
    return path.endswith(img_file_extensions)

def get_media_type(file_object):
    """Check a File object and determine the media type (video, image, audio)"""
    if file_object["has_video"] and not is_image(file_object):
        return "video"
    elif file_object["has_video"] and is_image(file_object):
        return "image"
    elif file_object["has_audio"] and not file_object["has_video"]:
        return "audio"
    else:
        # If none set, just assume video
        return "video"
