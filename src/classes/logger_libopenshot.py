"""
 @file
 @brief This file connects to libopenshot and logs debug messages (if debug preference enabled)
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2016 OpenShot Studios, LLC
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
from classes import settings, info
from classes.logger import log
import openshot
import os
import zmq


class LoggerLibOpenShot(Thread):

    def kill(self):
        self.running = False

    def run(self):
        # Running
        self.running = True

        # Get settings
        s = settings.get_settings()

        # Get port from settings
        port = s.get("debug-port")

        # Set port on ZmqLogger singleton
        openshot.ZmqLogger.Instance().Connection("tcp://*:%s" % port)

        # Set filepath for ZmqLogger also
        openshot.ZmqLogger.Instance().Path(os.path.join(info.USER_PATH, 'libopenshot.log'))

        # Socket to talk to server
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt_string(zmq.SUBSCRIBE, '')

        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)

        log.info("Connecting to libopenshot with debug port: %s" % port)
        socket.connect ("tcp://localhost:%s" % port)

        while self.running:
            msg = None

            # Receive all debug message sent from libopenshot (if any)
            socks = dict(poller.poll(1000))
            if socks:
                if socks.get(socket) == zmq.POLLIN:
                    msg = socket.recv(zmq.NOBLOCK)

            # Log the message (if any)
            if msg:
                log.info(msg.strip().decode('UTF-8'))