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
import shutil
from classes import info
from classes.logger import log


def get_assets_path(file_path=None, create_paths=True):
    """Get and/or create the current assets path. This path is used for thumbnail and blender files,
    and is unique to each project. For example: `Project1.osp` would use `Project1_assets` folder."""
    if not file_path:
        return info.ASSETS_PATH

    # Android content:// handles are not local filesystem paths.
    # Keep all project assets in the app's user storage directory instead.
    if str(file_path).startswith("content://"):
        return info.USER_PATH

    file_abs = os.path.abspath(str(file_path))
    backup_abs = os.path.abspath(info.BACKUP_FILE)
    recovery_abs = os.path.abspath(info.RECOVERY_PATH) + os.sep
    if file_abs == backup_abs or file_abs.startswith(recovery_abs):
        return info.USER_PATH

    try:
        # Generate asset folder name filename + "_assets"
        file_path = file_path
        asset_filename = os.path.splitext(os.path.basename(file_path))[0]
        asset_folder_name = asset_filename[:248] + "_assets" #Windows max name size is 255. 248 = 255 - len("_assets")
        asset_path = os.path.join(os.path.dirname(file_path), asset_folder_name)

        # Previous Assets File Name Convention.
        # We can remove the 30_char variables after 05/27/2022
        asset_folder_name_30_char = asset_filename[:30] + "_assets"
        asset_path_30_char = os.path.join(os.path.dirname(file_path), asset_folder_name_30_char)

        # Create asset folder, if necessary
        if create_paths:
            if not os.path.exists(asset_path):
                if os.path.exists(asset_path_30_char):
                    # Copy assets folder, if it follows the previous naming convention
                    # must leave a copy for possible projects that shared the folder.
                    try:
                        shutil.copytree(asset_path_30_char, asset_path)
                        log.info("Copying shortened asset folder. {}".format(asset_path))
                    except:
                        log.error("Could not make a copy of assets folder")
                else:
                    os.mkdir(asset_path)
                    log.info("Asset dir created as {}".format(asset_path))
            else:
                log.debug("Using existing asset folder {}".format(asset_path))

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

            # Create asset clipboard folder
            asset_clipboard_folder = os.path.join(asset_path, "clipboard")
            if not os.path.exists(asset_clipboard_folder):
                os.mkdir(asset_clipboard_folder)
                log.info("New clipboard folder: {}".format(asset_clipboard_folder))

            # Create asset ComfyUI output folder
            asset_comfy_output_folder = os.path.join(asset_path, "comfyui-output")
            if not os.path.exists(asset_comfy_output_folder):
                os.mkdir(asset_comfy_output_folder)
                log.info("New ComfyUI output folder: {}".format(asset_comfy_output_folder))

            # Create asset protobuf data folder
            asset_protobuf_folder = os.path.join(asset_path, "protobuf_data")
            if not os.path.exists(asset_protobuf_folder):
                os.mkdir(asset_protobuf_folder)
                log.info("New protobuf data folder: {}".format(asset_protobuf_folder))

            # Create asset optimized-preview folder
            asset_proxy_folder = os.path.join(asset_path, "optimized")
            if not os.path.exists(asset_proxy_folder):
                os.mkdir(asset_proxy_folder)
                log.info("New optimized folder: {}".format(asset_proxy_folder))

        return asset_path

    except Exception as ex:
        log.error("Error while getting/creating asset folder {}: {}".format(asset_path, ex))
