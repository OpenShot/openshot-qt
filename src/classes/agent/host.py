"""
 @file
 @brief Qt local command server, shared by the GUI and offscreen session host.

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
import hmac
import json
import os
from pathlib import Path
import secrets
import uuid

from qt_api import QObject
from .protocol import CommandError, MAX_MESSAGE, VERSION, decode, encode, network, session_dir
from .service import EditingService


class SessionServer(QObject):
    def __init__(self, app, mode='gui', session_id=None):
        super().__init__(app)
        self.app = app
        self.session_id = session_id or uuid.uuid4().hex
        self.service = EditingService(app, self.session_id, mode)
        self.token = secrets.token_hex(32)
        self.server = network().QLocalServer(self)
        self.buffers = {}
        self.busy = False
        directory = session_dir()
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        # macOS temporary directories leave little room for a Unix socket name.
        # Discovery records carry the full endpoint; it need not contain the session ID.
        self.endpoint = 'osa-' + uuid.uuid4().hex[:16]
        if not self.server.listen(self.endpoint):
            raise RuntimeError(self.server.errorString())
        self.server.newConnection.connect(self.accept)
        self.record_path = directory / (self.session_id + '.json')
        record = {'protocol': VERSION, 'session_id': self.session_id, 'endpoint': self.server.fullServerName(),
                  'pid': os.getpid(), 'mode': mode, 'token': self.token}
        fd = os.open(str(self.record_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream)
        app.aboutToQuit.connect(self.close)

    def accept(self):
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            sock.setReadBufferSize(MAX_MESSAGE + 4)
            self.buffers[sock] = bytearray()
            sock.readyRead.connect(lambda s=sock: self.receive(s))
            sock.disconnected.connect(lambda s=sock: self.disconnected(s))

    def disconnected(self, sock):
        self.buffers.pop(sock, None)
        sock.deleteLater()

    def receive(self, sock):
        buffer = self.buffers.get(sock)
        if buffer is None:
            return
        buffer.extend(bytes(sock.readAll()))
        while buffer:
            request_id = None
            try:
                message = decode(buffer)
                if message is None:
                    return
                if not isinstance(message, dict):
                    raise CommandError('invalid_request', 'Expected JSON-RPC object.')
                request_id = message.get('id')
                token = message.get('token')
                if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
                    raise CommandError('unauthorized', 'Invalid session token.')
                if message.get('jsonrpc') != '2.0':
                    raise CommandError('invalid_request', 'Expected jsonrpc 2.0.')
                if self.busy:
                    raise CommandError('busy', 'A command is already executing; retry after inspecting session state.')
                self.busy = True
                try:
                    result = self.service.execute(message.get('method'), message.get('params', {}), operation_id=str(request_id))
                finally:
                    self.busy = False
                response = {'jsonrpc': '2.0', 'id': request_id, 'result': result}
                packet = encode(response)
            except Exception as exc:
                code = getattr(exc, 'code', 'invalid_request')
                rpc_code = {'invalid_json': -32700, 'invalid_request': -32600,
                            'unknown_method': -32601, 'validation_error': -32602}.get(code, -32000)
                response = {'jsonrpc': '2.0', 'id': request_id, 'error': {
                    'code': rpc_code, 'message': str(exc),
                    'data': {'code': code, 'details': getattr(exc, 'details', None)}}}
                packet = encode(response)
                buffer.clear()
            sock.write(packet)
            sock.flush()

    def close(self):
        self.server.close()
        for sock in list(self.buffers):
            sock.abort()
        try:
            self.record_path.unlink()
        except FileNotFoundError:
            pass


def show_session(app):
    """Attach an editor to the existing project without reloading or resetting history."""
    if app.platformName().lower() in ('offscreen', 'minimal'):
        raise CommandError('display_unavailable',
                           'This session uses a headless Qt display backend. Start a new session from a desktop terminal '
                           'with QT_QPA_PLATFORM unset, using session start --show. Save this project first to transfer it.')
    if not app.window:
        from classes.updates import UpdateAction
        listeners = list(app.updates.updateListeners)
        if not app.gui(preserve_session=True):
            raise CommandError('startup_failed', 'Unable to initialize the editor window.')
        action = UpdateAction(type='load', values=app.project._data)
        for listener in list(app.updates.updateListeners):
            if listener not in listeners:
                listener.changed(action)
        app.updates.update_watchers()
        app.window.refreshFrameSignal.emit()
    app.setQuitOnLastWindowClosed(True)
    if app.window.isMinimized():
        app.window.showNormal()
    app.window.show()
    app.window.raise_()
    app.window.activateWindow()
    app.agent_server.service.mode = 'gui'
    record = json.loads(app.agent_server.record_path.read_text())
    record['mode'] = 'gui'
    app.agent_server.record_path.write_text(json.dumps(record))
    return app.agent_server.service.status()


def serve(project=None, session_id=None, show=False):
    # Desktop sessions remain windowless until requested; displayless hosts use Qt offscreen.
    import sys
    if sys.platform.startswith('linux') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from classes import info
    info.setup_userdirs()
    from classes.app import OpenShotApp
    app = OpenShotApp(['openshot-cli'], mode='agent')
    app.setQuitOnLastWindowClosed(False)
    session_id = session_id or uuid.uuid4().hex
    info.configure_asset_defaults(str(session_dir() / 'assets' / session_id))
    if project:
        app.project.load(str(Path(project).resolve()), clear_thumbnails=False, interactive=False)
        app.updates.load_history(app.project)
    app.agent_server = SessionServer(app, mode='headless', session_id=session_id)
    if show:
        show_session(app)
    return app.exec() if hasattr(app, 'exec') else app.exec_()
