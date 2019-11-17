"""
 @file
 @brief This file has code to generate thumbnail images and HTTP thumbnail server
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
import re
import openshot
import socket
from threading import Thread
from classes import info
from classes.query import File
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

REGEX_THUMBNAIL_URL = re.compile(r"/thumbnails/(.+?)/(\d+)(/path/)?")


def GenerateThumbnail(file_path, thumb_path, thumbnail_frame, width, height, mask, overlay):
    """Create thumbnail image, and check for rotate metadata (if any)"""

    # Create a clip object and get the reader
    clip = openshot.Clip(file_path)
    reader = clip.Reader()

    # Open reader
    reader.Open()

    # Get the 'rotate' metadata (if any)
    rotate = 0.0
    try:
        if reader.info.metadata.count("rotate"):
            rotate = float(reader.info.metadata.find("rotate").value()[1])
    except:
        pass

    # Create thumbnail folder (if needed)
    parent_path, file_name = os.path.split(thumb_path)
    if not os.path.exists(parent_path):
        os.mkdir(parent_path)

    # Save thumbnail image and close readers
    reader.GetFrame(thumbnail_frame).Thumbnail(thumb_path, width, height, mask, overlay, "#000", False, "png", 100, rotate)
    reader.Close()
    clip.Close()


class httpThumbnailServer(ThreadingMixIn, HTTPServer):
    """ This class allows to handle requests in separated threads.
        No further content needed, don't touch this. """


class httpThumbnailServerThread(Thread):
    """ This class runs a HTTP thumbnail server inside a thread
        so we don't block the main thread with handle_request()."""

    def find_free_port(self):
        """Find the first available socket port"""
        s = socket.socket()
        s.bind(('', 0))
        return s.getsockname()[1]

    def kill(self):
        self.running = False
        self.thumbServer.shutdown()

    def run(self):
        self.running = True

        # Start listening for HTTP requests (and check for shutdown every 0.5 seconds)
        self.server_address = ('127.0.0.1', self.find_free_port())
        self.thumbServer = httpThumbnailServer(self.server_address, httpThumbnailHandler)
        self.thumbServer.serve_forever(0.5)


class httpThumbnailHandler(BaseHTTPRequestHandler):
    """ This class handles HTTP requests to the HTTP thumbnail server above."""

    def do_GET(self):
        """ Process each GET request and return a value (image or file path)"""
        # Parse URL
        url_output = REGEX_THUMBNAIL_URL.findall(self.path)
        if url_output and len(url_output[0]) == 3:
            # Path is expected to have 3 matched components (third is optional though)
            #   /thumbnails/FILE-ID/FRAME-NUMBER/   or
            #   /thumbnails/FILE-ID/FRAME-NUMBER/path/
            self.send_response(200)
        else:
            self.send_error(404)
            return

        # Get URL parts
        file_id = url_output[0][0]
        file_frame = int(url_output[0][1])
        only_path = url_output[0][2]

        # Catch undefined calls
        if file_id == "undefined":
            self.send_error(404)
            return

        # Send headers
        if not only_path:
            self.send_header('Content-type', 'image/png')
        else:
            self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Locate thumbnail
        thumb_path = os.path.join(info.THUMBNAIL_PATH, file_id, "%s.png" % file_frame)
        if not os.path.exists(thumb_path) and file_frame == 1:
            # Try with no frame # (for backwards compatibility)
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file_id)
        if not os.path.exists(thumb_path) and file_frame != 1:
            # Try with no frame # (for backwards compatibility)
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s-%s.png" % (file_id, file_frame))

        if not os.path.exists(thumb_path):
            # Generate thumbnail (since we can't find it)
            file = File.get(id=file_id)

            # Convert path to the correct relative path (based on this folder)
            file_path = file.absolute_path()

            # Determine if video overlay should be applied to thumbnail
            overlay_path = ""
            if file.data["media_type"] == "video":
                overlay_path = os.path.join(info.IMAGES_PATH, "overlay.png")

            # Create thumbnail image
            GenerateThumbnail(file_path, thumb_path, file_frame, 98, 64, os.path.join(info.IMAGES_PATH, "mask.png"), overlay_path)

        # Send message back to client
        if os.path.exists(thumb_path):
            if not only_path:
                self.wfile.write(open(thumb_path, 'rb').read())
            else:
                self.wfile.write(bytes(thumb_path, "utf-8"))
        return
