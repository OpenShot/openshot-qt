"""
 @file
 @brief Synchronous CLI client; the editor's server is asynchronous.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
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
import time
import uuid

from .protocol import CommandError, decode, encode, network, records


def request(record, method, params=None, timeout=30):
    from qt_api import QCoreApplication
    _app = QCoreApplication.instance() or QCoreApplication([])  # Keep Qt alive through the request.
    sock = network().QLocalSocket()
    deadline = time.monotonic() + timeout
    remaining = lambda: max(1, int((deadline - time.monotonic()) * 1000))
    try:
        sock.connectToServer(record['endpoint'])
        if not sock.waitForConnected(min(remaining(), 1000)):
            raise CommandError('connection_failed', 'Session is not reachable: ' + sock.errorString())
        request_id = uuid.uuid4().hex
        sock.write(encode({'jsonrpc': '2.0', 'id': request_id, 'token': record['token'],
                           'method': method, 'params': params or {}}))
        sock.flush()
        buffer = bytearray()
        while time.monotonic() < deadline:
            if sock.bytesAvailable() or sock.waitForReadyRead(remaining()):
                buffer.extend(bytes(sock.readAll()))
                response = decode(buffer)
                if response is not None:
                    if response.get('id') != request_id:
                        raise CommandError('protocol_error', 'Response request ID does not match.')
                    if 'error' in response:
                        error = response['error']
                        details = error.get('data') or {}
                        raise CommandError(details.get('code', error['code']), error['message'], details.get('details', details))
                    return response['result']
            elif not sock.isOpen():
                break
        raise CommandError('timeout', 'No response before timeout. Inspect operation get '+request_id+' and current state before retrying a mutation.', {'operation_id': request_id})
    finally:
        sock.abort()


def discover():
    live = []
    for record in records():
        try:
            status = request(record, 'session.status', timeout=1)
            live.append((record, status['data']))
        except CommandError:
            continue
    return live


def select(session):
    if session:
        matches = [r for r in records() if r['session_id'] == session]
    else:
        matches = [r for r, status in discover()]
    if len(matches) != 1:
        raise CommandError('session_required', 'Select one running session with --session ID. Run: openshot-cli session list')
    return matches[0]
