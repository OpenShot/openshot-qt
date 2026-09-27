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
import shutil
from datetime import datetime
from requests import get
from threading import Thread
from classes import info
from classes.query import File
from classes.logger import log
from classes.app import get_app
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# Regex for parsing URLs: (examples)
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/path/no-cache/
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/path/
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/path
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1/
#  http://127.0.0.1:33723/thumbnails/9ATJTBQ71V/1
REGEX_THUMBNAIL_URL = re.compile(r"/thumbnails/(?P<file_id>.+?)/(?P<file_frame>\d+)/*(?P<only_path>path)?/*(?P<no_cache>no-cache)?")
THUMBNAIL_CACHE_VERSION = "20260327170000"
THUMBNAIL_CACHE_VERSION_TS = datetime.strptime(
    THUMBNAIL_CACHE_VERSION,
    "%Y%m%d%H%M%S",
).timestamp()
THUMBNAIL_PREWARM_FPS = 4
THUMBNAIL_DECODE_SCALE = 3.0


def GetThumbDeviceScale():
    """Return the current Qt device scale used for thumbnail assets."""
    try:
        app = get_app()
        scale = 1.0

        window = getattr(app, "window", None)
        if window and hasattr(window, "devicePixelRatioF"):
            scale = float(window.devicePixelRatioF())
        elif app and hasattr(app, "primaryScreen"):
            screen = app.primaryScreen()
            if screen:
                scale = float(screen.devicePixelRatio())
    except Exception:
        scale = 1.0
    return max(1.0, scale)


def ThumbnailFrameStepForFps(fps, target_fps=THUMBNAIL_PREWARM_FPS):
    """Return the coarse thumbnail frame step for a source FPS."""
    fps = float(fps or 0.0)
    target_fps = max(1.0, float(target_fps or 1.0))
    if fps <= 0.0:
        return 1
    return max(1, int(round(fps / target_fps)))


def RoundFrameToThumbnailGrid(frame_number, fps, target_fps=THUMBNAIL_PREWARM_FPS):
    """Round a requested frame to the nearest coarse thumbnail grid frame."""
    frame_number = max(1, int(frame_number or 1))
    step = ThumbnailFrameStepForFps(fps, target_fps=target_fps)
    return max(1, int(round((frame_number - 1) / float(step))) * step + 1)


def ThumbnailPathForFrame(file_id, thumbnail_frame):
    """Return the canonical thumbnail path for a file/frame pair."""
    return os.path.join(info.THUMBNAIL_PATH, str(file_id), "{}.png".format(int(thumbnail_frame or 1)))


def MigrateThumbnailLayout(thumbnail_root):
    """Move flat thumbnail files into per-file subfolders."""
    thumbnail_root = str(thumbnail_root or "")
    if not thumbnail_root or not os.path.isdir(thumbnail_root):
        return 0

    migrated = 0
    try:
        entries = os.listdir(thumbnail_root)
    except OSError as ex:
        # Cached thumbnails are optional; a denied cache must not prevent the
        # project itself from opening (e.g. macOS protected Downloads folders).
        log.warning("Unable to read thumbnail cache %s: %s", thumbnail_root, ex)
        return 0
    for entry in entries:
        source_path = os.path.join(thumbnail_root, entry)
        if not os.path.isfile(source_path):
            continue
        if not entry.lower().endswith(".png"):
            continue

        stem = entry[:-4]
        file_id = stem
        frame = "1"
        if "-" in stem:
            file_id, frame = stem.split("-", 1)
            if not frame.isdigit():
                continue

        target_dir = os.path.join(thumbnail_root, file_id)
        target_path = os.path.join(target_dir, "{}.png".format(frame))
        try:
            os.makedirs(target_dir, exist_ok=True)
            if os.path.abspath(source_path) == os.path.abspath(target_path):
                continue
            if not os.path.exists(target_path):
                shutil.move(source_path, target_path)
            else:
                os.remove(source_path)
        except OSError as ex:
            log.warning("Unable to migrate thumbnail %s: %s", source_path, ex)
            continue
        migrated += 1
    return migrated


def GenerateThumbnailFromFrame(frame, thumb_path, width, height, mask, overlay, rotate=0.0):
    """Create thumbnail image from an existing decoded frame."""
    try:
        scale = GetThumbDeviceScale()
    except Exception:
        scale = 1.0

    parent_path = os.path.dirname(thumb_path)
    os.makedirs(parent_path, exist_ok=True)

    thumb_width = round(width * scale)
    thumb_height = round(height * scale)
    frame.Thumbnail(
        thumb_path,
        thumb_width,
        thumb_height,
        mask,
        overlay,
        "#000",
        False,
        "png",
        85,
        float(rotate or 0.0),
        openshot.SCALE_CROP,
    )


def GetThumbPath(file_id, thumbnail_frame, clear_cache=False, attempts=1):
    """Get thumbnail path by invoking HTTP thumbnail request"""

    # Clear thumb cache (if requested)
    thumb_cache = ""
    if clear_cache:
        thumb_cache = "no-cache/"

    # Connect to thumbnail server and get image
    thumb_server_details = get_app().window.http_server_thread.server_address
    thumb_address = "http://%s:%s/thumbnails/%s/%s/path/%s" % (
        thumb_server_details[0],
        thumb_server_details[1],
        file_id,
        thumbnail_frame,
        thumb_cache)
    attempts = max(1, int(attempts or 1))
    for attempt in range(1, attempts + 1):
        try:
            r = get(thumb_address)
        except Exception:
            log.warning(
                "Thumbnail path request failed file_id=%s frame=%s attempt=%s/%s",
                file_id,
                thumbnail_frame,
                attempt,
                attempts,
                exc_info=1,
            )
            r = None

        if r is not None and r.ok and r.text:
            # Update thumbnail path to real one
            return r.text

        if r is not None:
            log.warning(
                "Thumbnail path request returned empty/miss file_id=%s frame=%s attempt=%s/%s status=%s",
                file_id,
                thumbnail_frame,
                attempt,
                attempts,
                getattr(r, "status_code", "n/a"),
            )

        if attempt < attempts:
            time.sleep(0.05)

    return ''


def GenerateThumbnail(file_path, thumb_path, thumbnail_frame, width, height, mask, overlay):
    """Create thumbnail image."""
    try:
        scale = GetThumbDeviceScale()
    except Exception:
        scale = 1.0

    # Create thumbnail folder (if needed)
    parent_path = os.path.dirname(thumb_path)
    if not os.path.exists(parent_path):
        os.mkdir(parent_path)

    thumb_width = round(width * scale)
    thumb_height = round(height * scale)
    decode_width = max(thumb_width, round(thumb_width * THUMBNAIL_DECODE_SCALE))
    decode_height = max(thumb_height, round(thumb_height * THUMBNAIL_DECODE_SCALE))

    def _render_with_reader(source_path, source_frame, inspect_reader):
        reader = None
        try:
            reader = openshot.Clip.CreateReader(source_path, inspect_reader)
            if not reader:
                raise RuntimeError("No reader available for thumbnail generation")

            if hasattr(reader, "SetMaxDecodeSize"):
                reader.SetMaxDecodeSize(decode_width, decode_height)
            reader.Open()

            reader.GetFrame(source_frame).Thumbnail(
                thumb_path,
                thumb_width,
                thumb_height,
                mask,
                overlay,
                "#000",
                False,
                "png",
                85,
                0.0,
                openshot.SCALE_CROP,
            )
            return True
        finally:
            if reader:
                try:
                    reader.Close()
                except Exception:
                    pass
        # Return False only when an exception is handled in caller.

    for inspect_reader in (False, True):
        try:
            if _render_with_reader(file_path, thumbnail_frame, inspect_reader):
                return
        except RuntimeError:
            # retry once with eager inspection if lightweight reader did not work
            continue

    # Any failure opening the reader (i.e. file missing or corrupt) use placeholder thumbnail
    not_found_path = os.path.join(info.IMAGES_PATH, "NotFound.svg")
    try:
        _render_with_reader(not_found_path, 1, False)
    except RuntimeError:
        log.warning(f"Failed to generate placeholder thumbnail from: {not_found_path}", exc_info=1)
    log.warning(f"Failed to generate thumbnail for missing file: {file_path}")


def ThumbnailCacheIsStale(thumb_path):
    """Return True when an on-disk thumbnail predates the current cache format."""
    try:
        return os.path.getmtime(thumb_path) < THUMBNAIL_CACHE_VERSION_TS
    except OSError:
        return True


class httpThumbnailServer(ThreadingMixIn, HTTPServer):
    """ This class allows to handle requests in separated threads.
        No further content needed, don't touch this. """


class httpThumbnailException(Exception):
    """ Custom exception if server cannot start. This can happen if a port does ot allow a connection
        due to another program or due to a firewall. """


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
        log.info("Starting thumbnail server listening on %s", self.server_address)
        self.running = True
        self.thumbServer.serve_forever(0.5)

    def __init__(self):
        """ Attempt to find an available port, and bind to that port for our thumbnail HTTP server.
            If not able to bind to localhost or a specific port, return an exception (and quit OpenShot). """
        Thread.__init__(self)
        self.daemon = True
        self.server_address = None
        self.running = False
        self.thumbServer = None

        exceptions = []
        initial_port = self.find_free_port()
        for attempt in range(3):
            try:
                # Configure server address and port for our HTTP thumbnail server
                self.server_address = ('127.0.0.1', initial_port + attempt)
                log.debug("Attempting to start thumbnail server listening on port %s", self.server_address)
                self.thumbServer = httpThumbnailServer(self.server_address, httpThumbnailHandler)
                self.thumbServer.daemon_threads = True
                exceptions.clear()
                break

            except Exception as ex:
                # Silently track each exception
                # Return full list of exceptions (from each attempt, if no attempt is successful)
                exceptions.append(f"{self.server_address} {ex}")

        if exceptions:
            # Return full list of attempts + exceptions if we failed to make a connection
            raise httpThumbnailException("\n".join(exceptions))


class httpThumbnailHandler(BaseHTTPRequestHandler):
    """ This class handles HTTP requests to the HTTP thumbnail server above."""

    def log_message(self, msg_format, *args):
        """ Log message from HTTPServer """
        log.info(msg_format % args)

    def log_error(self, msg_format, *args):
        """ Log error from HTTPServer """
        log.warning(msg_format % args)

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
        thumb_path = ThumbnailPathForFrame(file_id, file_frame)
        if not os.path.exists(thumb_path) and file_frame == 1:
            # Try ID with no frame # (for backwards compatibility)
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s.png" % file_id)
        if not os.path.exists(thumb_path) and file_frame != 1:
            # Try with ID and frame # in filename (for backwards compatibility)
            thumb_path = os.path.join(info.THUMBNAIL_PATH, "%s-%s.png" % (file_id, file_frame))

        if not os.path.exists(thumb_path) and not no_cache:
            fps_data = file.data.get("fps", {}) if isinstance(getattr(file, "data", None), dict) else {}
            fps_num = float(fps_data.get("num", 0.0) or 0.0)
            fps_den = float(fps_data.get("den", 1.0) or 1.0)
            fps = (fps_num / fps_den) if fps_num > 0.0 and fps_den > 0.0 else 0.0
            rounded_frame = RoundFrameToThumbnailGrid(file_frame, fps)
            if rounded_frame != file_frame:
                rounded_thumb_path = ThumbnailPathForFrame(file_id, rounded_frame)
                if os.path.exists(rounded_thumb_path) and not ThumbnailCacheIsStale(rounded_thumb_path):
                    thumb_path = rounded_thumb_path

        if not os.path.exists(thumb_path) or no_cache or ThumbnailCacheIsStale(thumb_path):
            # Generate thumbnail (since we can't find it)
            thumb_width = info.LIST_ICON_SIZE.width()
            thumb_height = info.LIST_ICON_SIZE.height()
            GenerateThumbnail(
                file_path,
                thumb_path,
                file_frame,
                thumb_width,
                thumb_height,
                mask_path,
                "")

        # Send message back to client
        if os.path.exists(thumb_path):
            if only_path:
                self.wfile.write(bytes(thumb_path, "utf-8"))
            else:
                with open(thumb_path, 'rb') as f:
                    self.wfile.write(f.read())

        # Pause processing of request (since we don't currently use thread pooling, this allows
        # the threads to be processed without choking the CPU as much
        # TODO: Make HTTPServer work with a limited thread pool and remove this sleep() hack.
        time.sleep(0.01)
