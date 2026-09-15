"""Exercise portal messages against a real, isolated D-Bus daemon."""

import asyncio
import importlib.util
import os
import select
import shutil
# Launch an isolated test D-Bus daemon with fixed argv, without a shell.
import subprocess  # nosec B404
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

import qt_api
from classes import portal_file_dialog as portal

HAS_DBUS_NEXT = importlib.util.find_spec("dbus_next") is not None
DBUS_DAEMON = shutil.which("dbus-daemon")


class PortalRoutingTests(unittest.TestCase):
    def test_other_platforms_and_themes_do_not_contact_portal(self):
        for platform, theme in (("win32", "xdgdesktopportal"), ("darwin", "xdgdesktopportal"),
                                ("linux", "gtk3"), ("linux", "")):
            with self.subTest(platform=platform, theme=theme), \
                    patch.object(sys, "platform", platform), \
                    patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": theme}), \
                    patch.object(portal, "show_dialog") as show:
                self.assertIsNone(qt_api._portal_file_dialog(None, "Open", "/tmp"))
                show.assert_not_called()

    def test_linux_portal_theme_uses_helper(self):
        with patch.object(sys, "platform", "linux"), \
                patch.dict(os.environ, {"QT_QPA_PLATFORMTHEME": "xdgdesktopportal"}), \
                patch.object(qt_api, "_is_android_runtime", return_value=False), \
                patch.object(portal, "show_dialog", return_value=[]) as show:
            self.assertEqual(qt_api._portal_file_dialog(None, "Open", "/tmp", multiple=True), [])
            show.assert_called_once_with(None, "Open", "/tmp", multiple=True)


class PortalReleaseTests(unittest.TestCase):
    def test_running_executable_is_probed_without_appimage_libraries(self):
        result = subprocess.CompletedProcess([], 0, b"xdg-desktop-portal 1.18.4\n")
        with patch.object(os, "readlink", return_value="/usr/libexec/xdg-desktop-portal"), \
                patch.dict(os.environ, {"LD_LIBRARY_PATH": "/app/lib", "LD_PRELOAD": "/app/wrap.so",
                                        "LD_AUDIT": "/app/audit.so"}), \
                patch.object(subprocess, "run", return_value=result) as run:
            self.assertEqual(portal._portal_release(123), (1, 18, 4))
            self.assertEqual(run.call_args.args[0], ["/proc/123/exe", "--version"])
            environment = run.call_args.kwargs["env"]
            for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT"):
                self.assertNotIn(name, environment)
            self.assertEqual(run.call_args.kwargs["timeout"], 1)

    def test_old_running_executable_after_package_upgrade(self):
        result = subprocess.CompletedProcess([], 0, b"xdg-desktop-portal 1.14.3\n")
        with patch.object(os, "readlink", return_value="/usr/libexec/xdg-desktop-portal (deleted)"), \
                patch.object(subprocess, "run", return_value=result):
            self.assertEqual(portal._portal_release(123), (1, 14, 3))

    def test_unrecognized_executable_is_not_run(self):
        with patch.object(os, "readlink", return_value="/usr/bin/something-else"), \
                patch.object(subprocess, "run") as run:
            self.assertIsNone(portal._portal_release(123))
            run.assert_not_called()

    def test_failed_or_unrecognized_version_is_unknown(self):
        with patch.object(os, "readlink", return_value="/usr/libexec/xdg-desktop-portal"):
            for failure in (OSError("denied"), subprocess.TimeoutExpired("portal", 1)):
                with self.subTest(failure=failure), patch.object(subprocess, "run", side_effect=failure):
                    self.assertIsNone(portal._portal_release(123))
            with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"unknown")):
                self.assertIsNone(portal._portal_release(123))


@unittest.skipUnless(HAS_DBUS_NEXT, "dbus-next is only required for Linux AppImage portals")
class PortalOptionsTests(unittest.TestCase):
    def test_paths_and_filters_have_portal_types(self):
        options = portal._options("/media/vidéo files", "Projects (*.osp);;Video (*.mp4 *.mov)",
                                  True, False, None)
        self.assertEqual(options["current_folder"].signature, "ay")
        self.assertEqual(options["current_folder"].value, os.fsencode("/media/vidéo files") + b"\0")
        self.assertEqual(options["filters"].signature, "a(sa(us))")
        self.assertEqual(options["filters"].value,
                         [["Projects", [[0, "*.osp"]]], ["Video", [[0, "*.mp4"], [0, "*.mov"]]]])
        self.assertTrue(options["multiple"].value)
        self.assertFalse(options["directory"].value)

    def test_save_name_and_existing_file_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            name = "vidéo one.osp"
            options = portal._options(directory, "", False, False, name)
            self.assertEqual(options["current_name"].value, name)
            self.assertNotIn("current_file", options)
            with open(os.path.join(directory, name), "w"):
                pass
            options = portal._options(directory, "", False, False, name)
            self.assertEqual(options["current_file"].value, os.fsencode(os.path.join(directory, name)) + b"\0")
            self.assertNotIn("multiple", options)

    def test_folder_is_single_selection(self):
        options = portal._options("/exports", "", True, True, None)
        self.assertTrue(options["directory"].value)
        self.assertFalse(options["multiple"].value)


@unittest.skipUnless(sys.platform.startswith("linux") and HAS_DBUS_NEXT and DBUS_DAEMON,
                     "requires Linux, dbus-next and dbus-daemon")
class PortalBusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Resolved test executable, fixed arguments, no shell.
        cls.daemon = subprocess.Popen(  # nosec B603
            [DBUS_DAEMON, "--session", "--nofork", "--print-address=1"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not select.select([cls.daemon.stdout], [], [], 5)[0]:
            cls.daemon.terminate()
            cls.daemon.communicate(timeout=5)
            raise RuntimeError("Private D-Bus daemon did not start")
        cls.address = cls.daemon.stdout.readline().strip()

    @classmethod
    def tearDownClass(cls):
        cls.daemon.terminate()
        cls.daemon.communicate(timeout=5)

    def request(self, version=4, status=0, uris=None, failure=None, save=False, folder=False,
                multiple=False, delayed=False, daemon_release=(1, 14, 3)):
        from dbus_next import Message, MessageType, Variant
        from dbus_next.aio import MessageBus

        captured = []
        self.closed_requests = 0
        self.opened_requests = 0

        async def scenario():
            service = await MessageBus().connect()
            await service.request_name(portal.SERVICE)

            def handle(message):
                if message.message_type != MessageType.METHOD_CALL:
                    return
                if message.member == "Get":
                    if failure == "version_timeout":
                        return True
                    return Message.new_method_return(message, "v", [Variant("u", version)])
                if message.member == "Close":
                    self.closed_requests += 1
                    return Message.new_method_return(message)
                if message.member not in ("OpenFile", "SaveFile"):
                    return
                captured.append(message)
                if failure == "method_error":
                    return Message.new_error(message, "org.freedesktop.portal.Error.Failed", "test failure")
                path = (portal.DESKTOP + "/request/" + message.sender[1:].replace(".", "_")
                        + "/" + message.body[2]["handle_token"].value)
                if failure == "owner_lost":
                    asyncio.ensure_future(service.release_name(portal.SERVICE))
                elif failure == "cancel":
                    asyncio.get_event_loop().call_soon(client.cancel)
                else:
                    result = {} if failure == "missing_uris" else {
                        "uris": Variant("as", uris if uris is not None else ["file:///media/vid%C3%A9o%20one.mp4"])}
                    # Intentionally send Response before the method reply. This
                    # catches the lost-signal race that can hang native dialogs.
                    signal = Message.new_signal(path, portal.REQUEST, "Response", "ua{sv}", [status, result])
                    if delayed:
                        asyncio.get_event_loop().call_later(0.05, service.send, signal)
                    else:
                        service.send(signal)
                return Message.new_method_return(message, "o", [path])

            service.add_message_handler(handle)
            try:
                options = portal._options("/media/vidéo files", "Project (*.osp)", multiple, folder,
                                          "new.osp" if save else None)
                def on_opened():
                    self.opened_requests += 1

                client = asyncio.ensure_future(portal._request("x11:123", "Choose", options, save, on_opened))
                return await asyncio.wait_for(client, 2)
            finally:
                await portal._close_bus(service)

        with patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": self.address}), \
                patch.object(portal, "CALL_TIMEOUT", 0.2), \
                patch.object(portal, "_portal_release", return_value=daemon_release):
            result = asyncio.run(scenario())
        return result, captured

    def test_modern_portal_receives_starting_folder_and_filter(self):
        result, calls = self.request()
        self.assertEqual([url.toLocalFile() for url in result], ["/media/vidéo one.mp4"])
        self.assertEqual(calls[0].signature, "ssa{sv}")
        self.assertEqual(calls[0].body[:2], ["x11:123", "Choose"])
        self.assertEqual(calls[0].body[2]["current_folder"].value, os.fsencode("/media/vidéo files") + b"\0")
        self.assertEqual(calls[0].body[2]["filters"].signature, "a(sa(us))")

    def test_older_portal_never_opens_a_dialog(self):
        for version in (0, 1, 2, 3):
            with self.subTest(version=version):
                result, calls = self.request(version=version)
                self.assertIsNone(result)
                self.assertEqual(calls, [])
                self.assertEqual(self.opened_requests, 0)

    def test_window_blocking_waits_for_accepted_pending_request(self):
        self.request(delayed=True)
        self.assertEqual(self.opened_requests, 1)
        self.request(status=1)
        self.assertEqual(self.opened_requests, 0)

    def test_ubuntu_2404_v3_portal_preserves_starting_folder(self):
        # xdg-desktop-portal 1.18.4 forwards current_folder for OpenFile,
        # although its public FileChooser interface still reports version 3.
        for save, folder in ((False, False), (True, False), (False, True)):
            with self.subTest(save=save, folder=folder):
                result, calls = self.request(version=3, daemon_release=(1, 18, 4), save=save, folder=folder)
                self.assertIsNotNone(result)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].body[2]["current_folder"].value,
                                 os.fsencode("/media/vidéo files") + b"\0")

    def test_v3_release_boundary_and_unknown_daemon(self):
        for release in (None, (1, 14, 3), (1, 16, 0)):
            with self.subTest(release=release):
                result, calls = self.request(version=3, daemon_release=release)
                self.assertIsNone(result)
                self.assertEqual(calls, [])
        result, calls = self.request(version=3, daemon_release=(1, 18, 0))
        self.assertIsNotNone(result)
        self.assertEqual(len(calls), 1)

    def test_newer_portal_and_save_folder_modes(self):
        for save, folder in ((True, False), (False, True)):
            with self.subTest(save=save, folder=folder):
                result, calls = self.request(version=5, save=save, folder=folder)
                self.assertIsNotNone(result)
                self.assertEqual(calls[0].member, "SaveFile" if save else "OpenFile")
                options = calls[0].body[2]
                if save:
                    self.assertEqual(options["current_name"].value, "new.osp")
                else:
                    self.assertTrue(options["directory"].value)

    def test_cancel_is_distinct_from_failure(self):
        self.assertEqual(self.request(status=1)[0], [])
        self.assertIsNone(self.request(status=2)[0])

    def test_multiple_imports_preserve_all_files(self):
        result, calls = self.request(multiple=True, uris=["file:///a.mp4", "file:///b.mp4"])
        self.assertEqual([url.toLocalFile() for url in result], ["/a.mp4", "/b.mp4"])
        self.assertTrue(calls[0].body[2]["multiple"].value)

    def test_shutdown_closes_pending_native_request(self):
        with self.assertRaises(asyncio.CancelledError):
            self.request(failure="cancel")
        self.assertEqual(self.closed_requests, 1)

    def test_invalid_results_fall_back(self):
        for uris in ([], ["https://example.com/file"], ["file:a.osp"],
                     ["file:///a.osp", "file:///b.osp"]):
            with self.subTest(uris=uris):
                self.assertIsNone(self.request(uris=uris)[0])
        self.assertIsNone(self.request(failure="missing_uris")[0])

    def test_service_disappearance_does_not_hang(self):
        self.assertIsNone(self.request(failure="owner_lost")[0])

    def test_method_errors_and_timeouts_are_bounded(self):
        with self.assertRaises(RuntimeError):
            self.request(failure="method_error")
        self.assertEqual(self.opened_requests, 0)
        with self.assertRaises(asyncio.TimeoutError):
            self.request(failure="version_timeout")
        self.assertEqual(self.opened_requests, 0)

    def test_repeated_dialogs_close_connections(self):
        before = len(os.listdir("/proc/self/fd"))
        for _ in range(3):
            self.request()
        self.assertEqual(len(os.listdir("/proc/self/fd")), before)


class PortalQtLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = qt_api.QtWidgets.QApplication.instance() or qt_api.QtWidgets.QApplication([])

    def test_qt_loop_preserves_cancel_success_and_failure(self):
        for result in ([], None, [qt_api.QtCore.QUrl.fromLocalFile("/tmp/test.osp")]):
            async def request(*args):
                self.assertTrue(parent.isEnabled())
                if result is not None:
                    args[-1]()  # The portal accepted a native dialog request.
                    self.assertFalse(parent.isEnabled())
                await asyncio.sleep(0.01)
                return result

            parent = qt_api.QtWidgets.QWidget()
            with self.subTest(result=result), patch.object(portal, "_options", return_value={}), \
                    patch.object(portal, "_request", side_effect=request):
                self.assertEqual(portal.show_dialog(parent, "Open", "/tmp"), result)
                self.assertTrue(parent.isEnabled())
            parent.deleteLater()

    def test_dependency_or_setup_failure_uses_fallback(self):
        parent = qt_api.QtWidgets.QWidget()
        with patch.object(portal, "_options", side_effect=ImportError("dbus_next")), \
                self.assertLogs(portal.logger, level="WARNING"):
            self.assertIsNone(portal.show_dialog(parent, "Open", "/tmp"))
        self.assertTrue(parent.isEnabled())
        parent.deleteLater()

    def test_fallback_never_disables_parent(self):
        async def unavailable(*args):
            await asyncio.sleep(0.01)
            return None

        parent = qt_api.QtWidgets.QWidget()
        with patch.object(portal, "_options", return_value={}), \
                patch.object(portal, "_request", side_effect=unavailable), \
                patch.object(parent, "setEnabled", wraps=parent.setEnabled) as set_enabled:
            self.assertIsNone(portal.show_dialog(parent, "Open", "/tmp"))
            set_enabled.assert_not_called()
        parent.deleteLater()

    def test_request_failure_restores_parent(self):
        async def fail(*args):
            raise RuntimeError("portal failed")

        parent = qt_api.QtWidgets.QWidget()
        with patch.object(portal, "_options", return_value={}), \
                patch.object(portal, "_request", side_effect=fail), \
                self.assertLogs(portal.logger, level="WARNING"):
            self.assertIsNone(portal.show_dialog(parent, "Open", "/tmp"))
        self.assertTrue(parent.isEnabled())
        parent.deleteLater()

    def test_parent_destruction_cancels_pending_dialog(self):
        cancelled = []

        async def pending(*args):
            try:
                await asyncio.sleep(100)
            finally:
                cancelled.append(True)

        parent = qt_api.QtWidgets.QWidget()
        qt_api.QtCore.QTimer.singleShot(30, parent.deleteLater)
        with patch.object(portal, "_options", return_value={}), \
                patch.object(portal, "_request", side_effect=pending):
            self.assertEqual(portal.show_dialog(parent, "Open", "/tmp"), [])
        self.assertEqual(cancelled, [True])

    def test_disabled_parent_stays_disabled(self):
        async def cancel(*args):
            return []

        parent = qt_api.QtWidgets.QWidget()
        parent.setEnabled(False)
        with patch.object(portal, "_options", return_value={}), \
                patch.object(portal, "_request", side_effect=cancel):
            self.assertEqual(portal.show_dialog(parent, "Open", "/tmp"), [])
        self.assertFalse(parent.isEnabled())
        parent.deleteLater()


if __name__ == "__main__":
    unittest.main()
