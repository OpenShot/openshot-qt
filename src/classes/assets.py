"""
 @file
 @brief This file generates the path for a project's assets
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
from classes import info, settings
from classes.logger import log


def get_assets_path(file_path=None, create_paths=True):
    """Get and/or create the current assets path. This path is used for thumbnail and blender files,
    and is unique to each project. For example: `Project1.osp` would use `Project1_assets` folder."""
    if not file_path:
        return info.USER_PATH

    try:
        # Generate asset folder name, max 30 chars of filename + "_assets"
        file_path = file_path
        asset_filename = os.path.splitext(os.path.basename(file_path))[0]
        asset_folder_name = asset_filename[:30] + "_assets"
        asset_path = os.path.join(os.path.dirname(file_path), asset_folder_name)

        # Create asset folder, if necessary
        if create_paths:
            if not os.path.exists(asset_path):
                os.mkdir(asset_path)
                log.info("Asset dir created as {}".format(asset_path))
            else:
                log.info("Using existing asset folder {}".format(asset_path))

            # Create asset thumbnails folder
            asset_thumbnails_folder = os.path.join(asset_path, "thumbnail")
            if not os.path.exists(asset_thumbnails_folder):
                os.mkdir(asset_thumbnails_folder)
                log.info("New thumbnails folder: {}".format(asset_thumbnails_folder))

            # Create asset title folder
            asset_titles_folder = os.path.join(asset_path, "title")
            if not os.path.exists(asset_titles_folder):
                os.mkdir(asset_titles_folder)
                log.info("New titles folder: {}".format(asset_titles_folder))

            # Create asset blender folder
            asset_blender_folder = os.path.join(asset_path, "blender")
            if not os.path.exists(asset_blender_folder):
                os.mkdir(asset_blender_folder)
                log.info("New blender folder: {}".format(asset_blender_folder))

        return asset_path

    except Exception as ex:
        log.error("Error while getting/creating asset folder {}: {}".format(asset_path, ex))
