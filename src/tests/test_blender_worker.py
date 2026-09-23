"""Exercise Blender worker failures and cancellation with real child processes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

from qt_api import QThread, QTimer, Qt
from windows.views.blender_listview import Worker, BlenderListView
from tests.qt_test_app import get_or_create_app
from tests.test_project_data import DummyApp, ensure_app_state


@unittest.skipIf(os.name == 'nt', 'Executable subprocess fixture uses a POSIX shebang')
class BlenderWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(DummyApp)

    def setUp(self):
        ensure_app_state(self.app)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script = self.root / 'blender'
        self.script.write_text('''#!%s
import os, signal, subprocess, sys, time
from pathlib import Path
root = Path(__file__).parent
mode = (root / 'mode').read_text()
version = '-v' in sys.argv
if mode == 'bad-version' and version:
    print('unexpected version output')
    sys.exit(0)
if (mode == 'version-hang' and version) or (mode == 'render-hang' and not version):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (root / 'ready').write_text(str(os.getpid()))
    time.sleep(60)
if mode == 'pipe-holder' and not version:
    code = "import signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path(%%r).write_text('ready'); time.sleep(60)" %% str(root / 'ready')
    subprocess.Popen([sys.executable, '-c', code])
    sys.exit(0)
if version:
    print('Blender 5.3.0')
else:
    os.write(1, b'bad byte: \\xff\\nFra:1,234\\n')
    print("Saved: '/tmp/frame1234.png'", flush=True)
    if mode == 'render-error':
        sys.exit(1)
''' % sys.executable)
        self.script.chmod(0o700)
        self.app.settings.values['blender_command'] = str(self.script)
        self.worker = Worker('template.blend', 'script.py', 1234)
        self.finished = Mock()
        self.errors = Mock()
        self.complete = Mock()
        self.worker.finished.connect(self.finished, Qt.DirectConnection)
        self.worker.blender_error_with_data.connect(self.errors, Qt.DirectConnection)
        self.worker.render_complete.connect(self.complete, Qt.DirectConnection)

    def mode(self, mode):
        (self.root / 'mode').write_text(mode)

    def test_fast_exit_output_is_drained_and_invalid_utf8_does_not_abort(self):
        self.mode('success')
        self.worker.Render()
        self.finished.assert_called_once()
        self.complete.assert_called_once()
        self.errors.assert_not_called()
        self.assertEqual(self.worker.frame_count, 1)
        self.assertEqual(self.worker.current_frame, 1234)
        self.assertIsNotNone(self.worker.process.poll())

    def test_version_parse_failure_always_finishes(self):
        self.mode('bad-version')
        self.worker.Render()
        self.finished.assert_called_once()
        self.errors.assert_called_once()
        self.complete.assert_not_called()

    def test_spawn_failure_always_finishes(self):
        self.worker.blender_exec_path = str(self.root / 'missing')
        self.worker.Render()
        self.finished.assert_called_once()
        self.complete.assert_not_called()

    def test_render_failure_does_not_import_partial_frames(self):
        self.mode('render-error')
        self.worker.Render()
        self.finished.assert_called_once()
        self.complete.assert_not_called()
        self.errors.assert_called_once()

    def test_version_timeout_reaps_process_and_finishes(self):
        self.mode('version-hang')
        with patch.object(self.worker, '_communicate', side_effect=subprocess.TimeoutExpired('blender', 10)):
            self.worker.Render()
        self.finished.assert_called_once()
        self.assertIsNotNone(self.worker.process.poll())

    def test_cancel_before_start_does_not_spawn(self):
        self.worker.Cancel()
        with patch('windows.views.blender_listview.subprocess.Popen') as spawn:
            self.worker.Render()
        spawn.assert_not_called()
        self.finished.assert_called_once()

    def test_dialog_cancel_joins_silent_render_and_version_threads(self):
        for mode in ('render-hang', 'version-hang', 'pipe-holder'):
            with self.subTest(mode=mode):
                self.mode(mode)
                ready = self.root / 'ready'
                ready.unlink(missing_ok=True)
                worker = Worker('template.blend', 'script.py', 40)
                errors = Mock()
                worker.blender_error_with_data.connect(errors, Qt.DirectConnection)
                worker.blender_error_nodata.connect(errors, Qt.DirectConnection)
                thread = QThread()
                worker.moveToThread(thread)
                thread.started.connect(worker.Render)
                worker.finished.connect(thread.quit, Qt.DirectConnection)
                thread.finished.connect(worker.deleteLater)
                view = types.SimpleNamespace(preview_timer=QTimer(), worker=worker, background=thread)
                view.preview_timer.start(60000)
                thread.start()
                try:
                    deadline = time.monotonic() + 5
                    while not ready.exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(ready.exists())
                    started = time.monotonic()
                    BlenderListView.Cancel(view)
                    self.assertLess(time.monotonic() - started, 5)
                    self.assertFalse(thread.isRunning())
                    self.assertFalse(view.preview_timer.isActive())
                    self.assertIsNotNone(worker.process.poll())
                    errors.assert_not_called()
                    # Repeated dialog close/reject is harmless.
                    BlenderListView.Cancel(view)
                finally:
                    if thread.isRunning():
                        worker.Cancel()
                        thread.quit()
                        thread.wait(5000)


class BlenderWindowsBranchTests(unittest.TestCase):
    """Exercise Windows launch/capture paths; native OS calls require Windows CI."""

    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(DummyApp)

    def setUp(self):
        from contextlib import ExitStack
        ensure_app_state(self.app)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='blender windows ')))
        self.helper = self.root / 'fake blender.py'
        self.helper.write_text('''
import os, sys, time
from pathlib import Path
root = Path(__file__).parent
mode = (root / 'mode').read_text()
version = '-v' in sys.argv
if mode == 'version-hang' and version:
    (root / 'ready').write_text('ready')
    time.sleep(60)
if version:
    print('unexpected version' if mode == 'bad-version' else 'Blender 5.3.0')
else:
    if mode == 'live-progress':
        os.write(1, b"Fra:40\\nSaved: '/tmp/frame")
        time.sleep(.15)
        os.write(1, b"0040.png'\\n")
        (root / 'ready').write_text('ready')
        time.sleep(60)
    else:
        print("Saved: '/tmp/frame0040.png'", end='', flush=True)
        if mode == 'render-error':
            sys.exit(1)
''')
        self.app.settings.values['blender_command'] = 'C:\\Program Files\\Blender\\blender.exe'
        self.stack.enter_context(patch('windows.views.blender_listview.sys.platform', 'win32'))
        if os.name != 'nt':
            self.stack.enter_context(patch.object(subprocess, 'STARTUPINFO',
                lambda: types.SimpleNamespace(dwFlags=0), create=True))
            self.stack.enter_context(patch.object(subprocess, 'STARTF_USESHOWWINDOW', 1, create=True))
            self.stack.enter_context(patch.object(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200, create=True))
        native_popen = subprocess.Popen
        self.launches = []
        self.capture_paths = []

        def launch(command, **kwargs):
            self.launches.append(dict(kwargs))
            self.capture_paths.append(kwargs['stdout'].name)
            if os.name != 'nt':
                # These are Win32-only OS arguments. Assert them below, but let
                # Linux run the helper to exercise the actual capture logic.
                kwargs.pop('startupinfo')
                kwargs.pop('creationflags')
            return native_popen([sys.executable, str(self.helper), *command[1:]], **kwargs)
        self.stack.enter_context(patch('windows.views.blender_listview.subprocess.Popen', side_effect=launch))
        self.worker = Worker('template.blend', 'script.py', 40)

    def mode(self, value):
        (self.root / 'mode').write_text(value)

    def assert_capture_closed(self):
        self.assertIsNone(self.worker._output_reader)
        self.assertIsNone(self.worker._output_writer)
        self.assertTrue(all(not Path(path).exists() for path in self.capture_paths))

    def test_launch_flags_and_successful_output_with_unterminated_final_line(self):
        self.mode('success')
        done = Mock()
        self.worker.render_complete.connect(done, Qt.DirectConnection)
        self.worker.Render()
        done.assert_called_once()
        self.assertEqual(self.worker.frame_count, 1)
        self.assertEqual(len(self.launches), 2)
        for args in self.launches:
            self.assertFalse(args['start_new_session'])
            self.assertEqual(args['creationflags'], subprocess.CREATE_NEW_PROCESS_GROUP)
            self.assertTrue(args['startupinfo'].dwFlags & subprocess.STARTF_USESHOWWINDOW)
            self.assertNotEqual(args['stdout'], subprocess.PIPE)
        self.assert_capture_closed()

    def test_windows_cancel_preserves_live_progress_and_joins_threads(self):
        for mode in ('live-progress', 'version-hang'):
            with self.subTest(mode=mode):
                self.mode(mode)
                ready = self.root / 'ready'
                ready.unlink(missing_ok=True)
                self.worker = Worker('template.blend', 'script.py', 40)
                frames = []
                self.worker.frame_saved.connect(
                    lambda frame: frames.append((frame, self.worker.process.poll())), Qt.DirectConnection)
                thread = QThread()
                self.worker.moveToThread(thread)
                thread.started.connect(self.worker.Render)
                self.worker.finished.connect(thread.quit, Qt.DirectConnection)
                thread.finished.connect(self.worker.deleteLater)
                thread.start()
                try:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        if ready.exists() and (mode == 'version-hang' or frames):
                            break
                        time.sleep(.01)
                    self.assertTrue(ready.exists())
                    if mode == 'live-progress':
                        self.assertEqual(frames, [(40, None)])  # Arrived before exit.
                    view = types.SimpleNamespace(preview_timer=QTimer(), worker=self.worker, background=thread)
                    with patch('windows.views.blender_listview.os.killpg', create=True) as kill_group:
                        started = time.monotonic()
                        BlenderListView.Cancel(view)
                        self.assertLess(time.monotonic() - started, 5)
                        kill_group.assert_not_called()
                    self.assertFalse(thread.isRunning())
                    self.assertIsNotNone(self.worker.process.poll())
                    self.assert_capture_closed()
                finally:
                    if thread.isRunning():
                        self.worker.Cancel()
                        thread.quit()
                        thread.wait(5000)

    def test_windows_failure_releases_capture_files(self):
        for mode in ('bad-version', 'render-error'):
            with self.subTest(mode=mode):
                self.mode(mode)
                self.worker = Worker('template.blend', 'script.py')
                finished, errors, complete = Mock(), Mock(), Mock()
                self.worker.finished.connect(finished, Qt.DirectConnection)
                self.worker.blender_error_with_data.connect(errors, Qt.DirectConnection)
                self.worker.render_complete.connect(complete, Qt.DirectConnection)
                self.worker.Render()
                finished.assert_called_once()
                errors.assert_called_once()
                complete.assert_not_called()
                self.assert_capture_closed()

    def test_windows_spawn_failure_releases_capture_files(self):
        with patch('windows.views.blender_listview.subprocess.Popen', side_effect=OSError('cannot launch')):
            self.worker.Render()
        self.assert_capture_closed()

    def test_windows_kill_fallback_never_uses_posix_signals(self):
        process = Mock()
        process.poll.return_value = None
        self.worker.process = process
        with patch('windows.views.blender_listview.sleep'), \
                patch('windows.views.blender_listview.os.killpg', create=True) as kill_group:
            self.worker.Cancel()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        kill_group.assert_not_called()
