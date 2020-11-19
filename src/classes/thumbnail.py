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
import time
from threading import Thread
from classes import info
from classes.query import File
from classes.logger import log
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# Regex for parsing URLs: (examples)
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/path/no-cache/
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/path/
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/path
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1
REGEX_THUMBNAIL_URL = re.compile(r"/thumbnails/(?P<file_id>.+?)/(?P<file_frame>\d+)/*(?P<only_path>path)?/*(?P<no_cache>no-cache)?")


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
            rotate_data = reader.info.metadata.find("rotate").value()[1]
            rotate = float(rotate_data)
    except ValueError as ex:
        log.warning("Could not parse rotation value {}: {}".format(rotate_data, ex))
    except Exception:
        log.warning("Error reading rotation metadata from {}".format(file_path), exc_info=1)

    # Create thumbnail folder (if needed)
    parent_path = os.path.dirname(thumb_path)
    if not os.path.exists(parent_path):
        os.mkdir(parent_path)

    # Save thumbnail image and close readers
    reader.GetFrame(thumbnail_frame).Thumbnail(thumb_path, width, height, mask, overlay, "#000", False, "png", 85, rotate)
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
        socket_port = s.getsockname()[1]
        s.close()
        return socket_port

    def kill(self):
        self.running = False
        log.info('Shutting down thumbnail server: %s' % str(self.server_address))
        self.thumbServer.shutdown()

    def run(self):
        self.running = True

        # Start listening for HTTP requests (and check for shutdown every 0.5 seconds)
        self.server_address = ('127.0.0.1', self.find_free_port())
        self.thumbServer = httpThumbnailServer(self.server_address, httpThumbnailHandler)
        self.thumbServer.daemon_threads = True
        log.info(
            "Starting thumbnail server listening on port %d",
            self.server_address[1])
        self.thumbServer.serve_forever(0.5)

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.server_address = None


class httpThumbnailHandler(BaseHTTPRequestHandler):
    """ This class handles HTTP requests to the HTTP thumbnail server above."""

    def log_message(self, msg_format, *args):
        """ Log message from HTTPServer """
        log.info(msg_format % args)

    def log_error(self, msg_format, *args):
        """ Log error from HTTPServer """
        log.error(msg_format % args)

    def do_GET(self):
        """ Process each GET request and return a value (image or file path)"""
        mask_path = os.path.join(info.IMAGES_PATH, "mask.png")

        # Parse URL
        url_output = REGEX_THUMBNAIL_URL.match(self.path)
        if url_output and len(url_output.groups()) == 4:
            # Path is expected to have 3 matched components (third is optional though)
            #   /thumbnails/FILE-ID/FRAME-NUMBER/   or
            #   /thumbnails/FILE-ID/FRAME-NUMBER/path/  or
            #   /thumbnails/FILE-ID/FRAME-NUMBER/no-cache/  or
            #   /thumbnails/FILE-ID/FRAME-NUMBER/path/no-cache/
            self.send_response_only(200)
        else:
            self.send_error(404)
            return

        # Get URL parts
        file_id = url_output.group('file_id')
        file_frame = int(url_output.group('file_frame'))
        only_path = url_output.group('only_path')
        no_cache = url_output.group('no_cache')

        log.debug(
            "Processing thumbnail request for %s frame %d",
            file_id, file_frame)

        try:
            # Look up file data
            file = File.get(id=file_id)

            # Ensure file location is an absolute path
            file_path = file.absolute_path()
        except AttributeError:
            # Couldn't match file ID
            log.debug("No ID match, returning 404")
            self.send_error(404)
            return

        # Send headers
        if not only_path:
            self.send_header('Content-type', 'image/png')
        else:
            self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        # Locate thumbnail
        thumb_path = os.path.join(info.THUMBNAIL_PATH, file_id, "%s.png" % file_frame)
        if not os.path.exists(thumb_path) and file_frame == 1:
            # Try ID with no frame # (for backwards compatibility)
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file_id)
        if not os.path.exists(thumb_path) and file_frame != 1:
            # Try with ID and frame # in filename (for backwards compatibility)
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s-%s.png" % (file_id, file_frame))

        if not os.path.exists(thumb_path) or no_cache:
            # Generate thumbnail (since we can't find it)

            # Determine if video overlay should be applied to thumbnail
            overlay_path = ""
            if file.data["media_type"] == "video":
                overlay_path = os.path.join(info.IMAGES_PATH, "overlay.png")

            # Create thumbnail image
            GenerateThumbnail(
                file_path,
                thumb_path,
                file_frame,
                98, 64,
                mask_path,
                overlay_path)

        # Send message back to client
        if os.path.exists(thumb_path):
            if not only_path:
                self.wfile.write(open(thumb_path, 'rb').read())
            else:
                self.wfile.write(bytes(thumb_path, "utf-8"))

        # Pause processing of request (since we don't currently use thread pooling, this allows
        # the threads to be processed without choking the CPU as much
        # TODO: Make HTTPServer work with a limited thread pool and remove this sleep() hack.
        time.sleep(0.01)

