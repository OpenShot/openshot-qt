"""
 @file
 @brief This file connects to libopenshot and logs debug messages (if debug preference enabled)
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

from threading import Thread
from classes import info
from classes.logger import log
from classes.app import get_app
import openshot
import os
import zmq


class LoggerLibOpenShot(Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = False
        self.context = None
        self.socket = None


    def kill(self):
        self.running = False
        log.info('Shutting down libopenshot logger')

    def run(self):
        # Running
        self.running = True

        # Get settings
        s = get_app().get_settings()

        # Get port from settings
        port = s.get("debug-port")
        debug_enabled = s.get("debug-mode")

        # Set port on ZmqLogger singleton
        openshot.ZmqLogger.Instance().Connection("tcp://*:%s" % port)

        # Set filepath for ZmqLogger also
        openshot.ZmqLogger.Instance().Path(os.path.join(info.USER_PATH, 'libopenshot.log'))

        # Enable / Disable logger
        openshot.ZmqLogger.Instance().Enable(debug_enabled)

        # Socket to talk to server
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, '')

        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)

        log.info("Connecting to libopenshot with debug port: %s" % port)
        self.socket.connect("tcp://localhost:%s" % port)

        while self.running:
            msg = None

            # Receive all debug message sent from libopenshot (if any)
            try:
                socks = dict(poller.poll(1000))
                if socks and socks.get(self.socket) == zmq.POLLIN:
                    msg = self.socket.recv(zmq.NOBLOCK)
                if msg:
                    log.info(msg.strip().decode('UTF-8'))
            except Exception as ex:
                log.warning(ex)

        # Close zmq connection
        if self.context:
            self.context.destroy()
        if self.socket:
            self.socket.close()
        if openshot.ZmqLogger.Instance():
            # Close libopenshot logger
            openshot.ZmqLogger.Instance().Close()
