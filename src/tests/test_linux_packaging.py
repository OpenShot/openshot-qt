# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reject the incomplete Qt/Wayland runtime that disables AppImage GPU presentation."""
import importlib.util
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from tests.source_tree import source_path

spec = importlib.util.spec_from_file_location('linux_qt', source_path('installer/linux_qt.py'))
linux_qt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linux_qt)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux AppImage runtime')
class LinuxQtPackagingTests(unittest.TestCase):
    def make_runtime(self, root):
        for name in ('libQt5WaylandClient.so.5',) + linux_qt.DISPLAY_PLUGINS:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def test_plugins_and_their_scan_inputs_come_from_the_selected_qt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_runtime(root)
            files = linux_qt.display_plugins(root)
            self.assertIn((str(root / linux_qt.WAYLAND_PLUGINS[0]), linux_qt.WAYLAND_PLUGINS[0]), files)
            self.assertIn((str(root / 'wayland-decoration-client/libbradient.so'),
                           'wayland-decoration-client/libbradient.so'), files)
            (root / linux_qt.WAYLAND_PLUGINS[2]).unlink()
            with self.assertRaisesRegex(RuntimeError, 'install qtwayland5'):
                linux_qt.display_plugins(root)

    def test_missing_selected_x11_or_portal_plugin_does_not_use_system_qt(self):
        for name in ('platforms/libqxcb.so', 'platformthemes/libqxdgdesktopportal.so'):
            with self.subTest(plugin=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_runtime(root)
                (root / name).unlink()
                with self.assertRaisesRegex(RuntimeError, 'Matching Qt display plugins'):
                    linux_qt.display_plugins(root)

    def test_missing_qt_runtime_and_bundled_host_wayland_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_runtime(root)
            library = root / 'libQt5WaylandClient.so.5'
            library.unlink()
            with self.assertRaisesRegex(RuntimeError, 'missing.*libQt5WaylandClient'):
                linux_qt.check_display_runtime(root)
            library.touch()
            (root / 'libwayland-client.so.0').touch()
            with self.assertRaisesRegex(RuntimeError, 'host display libraries.*libwayland-client'):
                linux_qt.check_display_runtime(root)

    def test_host_qt_fallback_and_unresolved_plugin_dependencies_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_runtime(root)
            with patch.object(linux_qt.subprocess, 'run') as run:
                run.return_value.returncode = 0
                run.return_value.stderr = ''
                run.return_value.stdout = 'libQt5WaylandClient.so.5 => /usr/lib/libQt5WaylandClient.so.5 (0x123)'
                with self.assertRaisesRegex(RuntimeError, 'outside AppImage'):
                    linux_qt.check_display_runtime(root)
                run.return_value.stdout = 'libQt5WaylandClient.so.5 => not found'
                with self.assertRaisesRegex(RuntimeError, 'Unresolved Qt display dependency'):
                    linux_qt.check_display_runtime(root)
                run.return_value.stdout = 'libQt5WaylandClient.so.5 => %s (0x123)' % (root / 'libQt5WaylandClient.so.5')
                linux_qt.check_display_runtime(root)
