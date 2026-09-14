"""Location-aware Linux file dialogs, bypassing old Qt portal plugins.

FileChooser v4 advertises OpenFile.current_folder. xdg-desktop-portal 1.18
already supports it while reporting v3. None means fallback; [] means cancelled.
The optional dbus-next dependency is bundled in Linux AppImages.
"""

import asyncio
import logging
import os
import re
import subprocess
import uuid

from qt_api import QtCore, QtWidgets

logger = logging.getLogger(__name__)
SERVICE = "org.freedesktop.portal.Desktop"
DESKTOP = "/org/freedesktop/portal/desktop"
CHOOSER = "org.freedesktop.portal.FileChooser"
REQUEST = "org.freedesktop.portal.Request"
CALL_TIMEOUT = 3.0


def _portal_release(pid):
    """Check the running daemon, including v3 releases with current_folder.

    Query its actual executable rather than the installed package, which might
    have been upgraded without restarting the service. Do not load AppImage
    libraries into this host executable.
    """
    executable = "/proc/%d/exe" % pid
    try:
        name = os.path.basename(os.readlink(executable)).replace(" (deleted)", "")
        if name != "xdg-desktop-portal":
            return None
        environment = dict(os.environ)
        for variable in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT"):
            environment.pop(variable, None)
        environment["LC_ALL"] = "C"
        result = subprocess.run(
            [executable, "--version"], env=environment, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=1, check=True)
        match = re.fullmatch(rb"xdg-desktop-portal (\d+)\.(\d+)\.(\d+)\s*", result.stdout)
        return tuple(int(part) for part in match.groups()) if match else None
    except (OSError, subprocess.SubprocessError) as exc:
        logger.info("Cannot determine running file portal release: %s", exc)
        return None


async def _close_bus(bus):
    bus.disconnect()
    try:
        if bus.unique_name:
            await asyncio.wait_for(bus.wait_for_disconnect(), CALL_TIMEOUT)
    except Exception:
        pass
    finally:
        # dbus-next 0.2.3 shuts down, but does not close, these descriptors.
        # Release them before closing our per-dialog asyncio loop.
        bus._stream.close()
        bus._sock.close()


def _options(directory, file_filter, multiple, folder, save_name):
    """Build typed portal options; paths are byte arrays, not file URLs."""
    from dbus_next import Variant

    options = {"modal": Variant("b", True)}
    if directory:
        options["current_folder"] = Variant("ay", os.fsencode(os.path.abspath(directory)) + b"\0")
    if save_name is not None:
        options["current_name"] = Variant("s", save_name)
        path = os.path.join(directory, save_name)
        if os.path.isfile(path):
            options["current_file"] = Variant("ay", os.fsencode(os.path.abspath(path)) + b"\0")
    else:
        options["multiple"] = Variant("b", multiple and not folder)
        options["directory"] = Variant("b", folder)
    if file_filter:
        filters = []
        for entry in file_filter.split(";;"):
            match = re.fullmatch(r"(.*)\(([^()]*)\)\s*", entry)
            label, patterns = match.groups() if match else (entry, entry)
            conditions = [[0, pattern] for pattern in patterns.split()]
            if not conditions:
                raise ValueError("Empty file filter")
            filters.append([label.strip(), conditions])
        options["filters"] = Variant("a(sa(us))", filters)
    return options


async def _request(parent_id, caption, options, save=False, on_opened=None):
    """Run one request on a private connection, subscribing before opening it."""
    from dbus_next import Message, MessageType, Variant
    from dbus_next.aio import MessageBus

    bus = MessageBus()
    handle = None
    owner = SERVICE
    finished = False
    disconnected = None

    async def call(destination, path, interface, member, signature="", body=None):
        reply = await asyncio.wait_for(bus.call(Message(
            destination=destination, path=path, interface=interface,
            member=member, signature=signature, body=body or [],
        )), CALL_TIMEOUT)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError("%s: %s" % (reply.error_name, reply.body))
        return reply

    try:
        await asyncio.wait_for(bus.connect(), CALL_TIMEOUT)
        reply = await call(SERVICE, DESKTOP, "org.freedesktop.DBus.Properties",
                           "Get", "ss", [CHOOSER, "version"])
        version = reply.body[0]
        owner = reply.sender
        supported = version.signature == "u" and version.value >= 4
        if version.signature == "u" and version.value == 3:
            pid = await call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                             "org.freedesktop.DBus", "GetConnectionUnixProcessID", "s", [owner])
            release = _portal_release(pid.body[0])
            supported = release is not None and release >= (1, 18, 0)
            logger.info("File portal interface 3, running daemon release: %s", release)
        logger.info("File portal interface %s: starting-folder support %s", version.value, supported)
        if not supported:
            return None
        token = "openshot_" + uuid.uuid4().hex
        handle = DESKTOP + "/request/" + bus.unique_name[1:].replace(".", "_") + "/" + token
        options = dict(options, handle_token=Variant("s", token))
        response = asyncio.get_event_loop().create_future()

        def receive(message):
            if message.message_type != MessageType.SIGNAL:
                return
            if (message.sender == owner and message.path == handle
                    and message.interface == REQUEST and message.member == "Response"):
                if not response.done():
                    response.set_result(message.body)
            elif (message.sender == "org.freedesktop.DBus"
                  and message.interface == "org.freedesktop.DBus"
                  and message.member == "NameOwnerChanged"
                  and message.body[0] == SERVICE and message.body[1] == owner):
                if not response.done():
                    response.set_result(None)

        bus.add_message_handler(receive)
        for rule in [
            "type='signal',sender='%s',interface='%s',path='%s'" % (owner, REQUEST, handle),
            "type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',"
            "member='NameOwnerChanged',arg0='%s'" % SERVICE,
        ]:
            await call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                       "org.freedesktop.DBus", "AddMatch", "s", [rule])

        reply = await call(owner, DESKTOP, CHOOSER, "SaveFile" if save else "OpenFile",
                           "ssa{sv}", [parent_id, caption, options])
        if reply.body != [handle]:
            # Modern portals must use handle_token. Close an unexpected handle
            # rather than waiting forever on a path we did not subscribe to.
            if reply.signature == "o":
                handle = reply.body[0]
            raise RuntimeError("Unexpected portal request handle")
        if not response.done() and on_opened is not None:
            on_opened()
        disconnected = asyncio.ensure_future(bus.wait_for_disconnect())
        await asyncio.wait([response, disconnected], return_when=asyncio.FIRST_COMPLETED)
        result = response.result() if response.done() else None
        if result is None:
            return None
        status, results = result
        finished = True
        if status == 1:
            return []
        if status != 0:
            return None
        uris = results.get("uris")
        if uris is None or uris.signature != "as" or not uris.value:
            return None
        if (save or not options.get("multiple", Variant("b", False)).value) and len(uris.value) != 1:
            return None
        urls = [QtCore.QUrl(uri) for uri in uris.value]
        if not all(url.isValid() and url.isLocalFile() and os.path.isabs(url.toLocalFile())
                   for url in urls):
            return None
        return urls
    finally:
        if handle and not finished and bus.connected:
            # Also closes the dialog when the application quits or setup fails.
            try:
                await call(owner, handle, REQUEST, "Close")
            except Exception:
                pass
        await _close_bus(bus)
        if disconnected is not None:
            await asyncio.gather(disconnected, return_exceptions=True)


def show_dialog(parent, caption, directory, file_filter="", multiple=False,
                folder=False, save_name=None):
    """Keep the desktop wrappers synchronous while servicing Qt and D-Bus."""
    loop = asyncio.new_event_loop()
    timer = QtCore.QTimer()
    qt_loop = QtCore.QEventLoop()
    task = None
    parent_connected = False
    window = parent.window() if parent is not None else None
    window_disabled = False
    try:
        parent_id = ""
        if window is not None and QtWidgets.QApplication.platformName() == "xcb":
            parent_id = "x11:%x" % int(window.winId())
        options = _options(directory, file_filter, multiple, folder, save_name)

        def on_opened():
            nonlocal window_disabled
            # Probing an older or unavailable portal must not gray out the
            # application before its ordinary Qt dialog opens.
            if window is not None and window.isEnabled():
                window.setEnabled(False)
                window_disabled = True

        task = loop.create_task(_request(parent_id, caption, options, save_name is not None, on_opened))

        def advance():
            loop.call_soon(loop.stop)
            loop.run_forever()
            if task.done():
                qt_loop.quit()

        timer.timeout.connect(advance)
        timer.start(10)
        if window is not None:
            window.destroyed.connect(qt_loop.quit)
            parent_connected = True
        execute = getattr(qt_loop, "exec", None) or qt_loop.exec_
        execute()
        # Exiting the event loop before a response (e.g. application shutdown)
        # is cancellation, never a reason to open another dialog.
        return task.result() if task.done() else []
    except Exception as exc:
        logger.warning("Native file portal unavailable; using Qt dialog: %s", exc)
        return None
    finally:
        timer.stop()
        if task is not None and not task.done():
            task.cancel()
            loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
        loop.close()
        if window is not None:
            try:
                if parent_connected:
                    window.destroyed.disconnect(qt_loop.quit)
                if window_disabled:
                    window.setEnabled(True)
            except RuntimeError:
                # The parent can be destroyed during application shutdown.
                pass
