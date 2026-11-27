"""Exercise portable paths, startup scaling, and settings persistence."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
HOST_RUNTIME = (sys.platform, sys.executable, getattr(sys, 'frozen', None))
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from classes import user_paths
from classes.agent.protocol import session_dir


class PortablePathsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'host-home'
        self.app = self.root / 'OpenShot 4.2 - fix for xyz'
        self.app.mkdir()
        for patcher in (
                patch.object(user_paths, 'sys', SimpleNamespace(
                    platform='win32', frozen=True,
                    executable=str(self.app / 'openshot-qt.exe'))),
                patch.object(user_paths.os.path, 'expanduser', return_value=str(self.home))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_windows_marker_selects_local_data_without_changing_home(self):
        self.assertFalse(user_paths.is_portable())
        self.assertEqual(user_paths.user_path(), str(self.home / '.openshot_qt'))
        (self.app / 'portable').touch()
        self.assertTrue(user_paths.is_portable())
        self.assertEqual(user_paths.user_path(), str(self.app / '.openshot_qt'))
        self.assertEqual(os.path.expanduser('~'), str(self.home))
        self.assertFalse((self.app / '.openshot_qt').exists())

    def test_directory_named_portable_does_not_enable_mode(self):
        (self.app / 'portable').mkdir()
        self.assertFalse(user_paths.is_portable())

    def test_windows_simulation_does_not_change_host_runtime(self):
        self.assertIsNot(user_paths.sys, sys)
        self.assertEqual(
            (sys.platform, sys.executable, getattr(sys, 'frozen', None)), HOST_RUNTIME)

    def test_marker_is_ignored_on_other_platforms(self):
        (self.app / 'portable').touch()
        for platform in ('linux', 'darwin'):
            with self.subTest(platform=platform), patch.object(user_paths.sys, 'platform', platform):
                self.assertFalse(user_paths.is_portable())
                self.assertEqual(user_paths.user_path(), str(self.home / '.openshot_qt'))

    def test_independent_copies_and_relocation_ignore_working_directory(self):
        (self.app / 'portable').touch()
        original = Path(user_paths.user_path())
        moved = self.root / 'another-drive' / 'OpenShot'
        moved.parent.mkdir()
        self.app.rename(moved)
        with patch.object(user_paths.sys, 'executable', str(moved / 'openshot-qt.exe')):
            self.assertEqual(user_paths.user_path(), str(moved / '.openshot_qt'))
            self.assertNotEqual(user_paths.user_path(), str(original))
        self.app.mkdir()
        # A normal installation stays independent of the portable copy.
        self.assertEqual(user_paths.user_path(), str(self.home / '.openshot_qt'))

    def test_cli_session_default_and_explicit_override(self):
        (self.app / 'portable').touch()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(session_dir(), self.app / '.openshot_qt' / 'sessions')
            os.environ['OPENSHOT_SESSION_DIR'] = str(self.root / 'explicit-sessions')
            self.assertEqual(session_dir(), self.root / 'explicit-sessions')


class PortableStartupTests(unittest.TestCase):
    def test_portable_scale_and_info_use_same_data_root_before_qt_creation(self):
        # Exercise real Qt/settings I/O, with only the resolver seeing Windows.
        # Video-engine ABI checks belong to check_hardware_package.py, not this
        # unit test of data paths and startup scale. Engine thread defaults are
        # unrelated to that behavior and can use a small deterministic double.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'OpenShot'
            settings = app / '.openshot_qt' / 'openshot.settings'
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps([{'setting': 'ui-scale', 'value': 1.5}]))
            (app / 'portable').touch()
            home = root / 'host-home'
            host_settings = home / '.openshot_qt' / 'openshot.settings'
            host_settings.parent.mkdir(parents=True)
            host_content = json.dumps([{'setting': 'ui-scale', 'value': 2.5}])
            host_settings.write_text(host_content)
            script = '''
import os, sys
from types import SimpleNamespace
from unittest.mock import patch
host_platform = sys.platform
host_executable = sys.executable
host_frozen = getattr(sys, 'frozen', None)
# Fail any accidental import of the engine's extension. Keep real Qt, the
# settings store, JSON I/O, and filesystem operations under test.
sys.modules['_openshot'] = None
native_defaults = SimpleNamespace(DefaultOMPThreads=lambda: 4, DefaultFFThreads=lambda: 4)
sys.modules['openshot'] = SimpleNamespace(
    Settings=SimpleNamespace(Instance=lambda: native_defaults))
import qt_api
from classes import user_paths
sys.modules['OpenGL'] = None
portable_runtime = SimpleNamespace(platform='win32', frozen=True, executable=sys.argv[1])
with patch.object(user_paths, 'sys', portable_runtime):
    from classes import info
    from classes.qt_bootstrap import configure_qt
    from classes.agent.protocol import session_dir
    assert info.PORTABLE
    assert info.USER_PATH == user_paths.user_path()
    # A Windows simulation must not affect platform-sensitive stdlib imports
    # (Python 3.7's subprocess would otherwise try importing msvcrt on macOS).
    import subprocess
    assert sys.platform == host_platform
    assert sys.executable == host_executable
    assert getattr(sys, 'frozen', None) == host_frozen
    assert str(session_dir()) == os.path.join(info.USER_PATH, 'sessions')
    configure_qt()
    assert os.environ['QT_SCALE_FACTOR'] == sys.argv[4]
    assert qt_api.QApplication.instance() is None
    from classes.settings import SettingStore
    store = SettingStore()
    defaults = store._apply_runtime_defaults([
        {'setting': 'unsaved-assets-path', 'value': 'unused'}])
    assert defaults[0]['value'] == ''  # Portable default must survive a drive move.
    info.setup_userdirs()
    assert os.path.isdir(info.RECOVERY_PATH)
    assert os.path.isdir(info.CACHE_PATH)
    assert info.HOME_PATH == sys.argv[3]
    store.defaults_path = os.path.join(sys.argv[2], 'settings', '_default.settings')
    store.load()
    assert info.configure_asset_defaults(store.get('unsaved-assets-path')) == info.USER_PATH
    store.set('ui-scale', 2.0)
    store.save()
    configure_qt()
    assert os.environ['QT_SCALE_FACTOR'] == '2.0'
    # A read-only portable folder must not cause a fallback into the host home.
    with patch.object(info.os.path, 'exists', return_value=False), \\
         patch.object(info.os, 'makedirs', side_effect=PermissionError('read-only')):
        try:
            info.setup_userdirs()
        except PermissionError:
            pass
        else:
            raise AssertionError('Expected read-only portable folder to fail')
    assert info.USER_PATH == user_paths.user_path()
'''
            from tests.agent_test_support import subprocess_environment
            environment = subprocess_environment(
                QT_QPA_PLATFORM='offscreen', HOME=str(home), USERPROFILE=str(home))
            environment.pop('OPENSHOT_SESSION_DIR', None)
            for expected in ('1.5', '2.0'):
                result = subprocess.run(
                    [sys.executable, '-c', script, str(app / 'openshot-qt.exe'),
                     str(SOURCE), str(home), expected],
                    cwd=directory, env=environment, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(host_settings.read_text(), host_content)
                if expected == '1.5':
                    previous = app
                    app = root / 'Moved OpenShot'
                    previous.rename(app)
            self.assertFalse(previous.exists(), 'Portable startup recreated the old installation folder')
