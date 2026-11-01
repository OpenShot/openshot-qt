"""
 @file
 @brief Executable dispatch, AppImage launch contracts, and Windows console streams.

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
import json
import os
from pathlib import Path
import shutil
import subprocess  # nosec B404 - Launch controlled local processes without a shell.
import sys
import tempfile
import unittest
from unittest.mock import patch

from classes.agent.protocol import CommandError, cli_command


class CommonEntryTests(unittest.TestCase):
    def test_source_and_installed_cli_help_without_native_or_qt(self):
        source = Path(__file__).resolve().parents[1]
        for installed in (False, True):
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                package = root / 'openshot_qt'
                (package / 'classes' / 'agent').mkdir(parents=True)
                (package / 'windows' / 'views' / 'timeline_backend').mkdir(parents=True)
                for name in ('__init__.py', 'launch.py', 'cli.py', 'classes/__init__.py',
                             'classes/cli_console.py', 'classes/windows_dlls.py', 'classes/easing.py', 'classes/agent/__init__.py', 'classes/agent/protocol.py',
                             'classes/look_presets.py', 'classes/color_presets.py', 'classes/film_grain_presets.py',
                             'windows/__init__.py', 'windows/views/__init__.py', 'windows/views/timeline_backend/__init__.py',
                             'windows/views/timeline_backend/enums.py'):
                    shutil.copy2(source / name, package / name)
                # Missing native/Qt dependencies must not matter to --cli help.
                for name in ('openshot.py', 'qt_api.py'):
                    (package / name).write_text('raise AssertionError("GUI/native initialization during CLI help")\n')
                env = dict(os.environ, PYTHONPATH=str(root))
                if installed:
                    command = [sys.executable, '-c', 'from openshot_qt.launch import main; main()']
                else:
                    command = [sys.executable, str(package / 'launch.py')]
                result = subprocess.run(command + ['--cli', 'clip', 'keyframe', 'help'], cwd=directory,  # nosec B603 - Fixed test executable and argument array; no shell.
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('keyframe', result.stdout)
                self.assertIn('transform', result.stdout)
                result = subprocess.run(command + ['--cli', 'intro'], cwd=directory,  # nosec B603 - Fixed test executable and argument array; no shell.
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Keep the two clocks straight', result.stdout)
                self.assertNotIn('commands:', result.stdout)
                self.assertLessEqual(max(map(len, result.stdout.splitlines())), 68)
                result = subprocess.run(command + ['--cli', 'effects', 'keyframe', 'presets'],  # nosec B603 - Fixed test executable and argument array; no shell.
                                        cwd=directory, env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('ease-in-out', {row['id'] for row in json.loads(result.stdout)['result']})
                result = subprocess.run(command + ['--cli', 'not-a-command'], cwd=directory,  # nosec B603 - Fixed test executable and argument array; no shell.
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('invalid choice', result.stderr)

    def test_dedicated_alias_accepts_common_prefix(self):
        cli = Path(__file__).resolve().parents[1] / 'cli.py'
        outputs = []
        for args in ([], ['help'], ['--help'], ['--cli'], ['--cli', 'help'], ['--cli', '--help']):
            result = subprocess.run([sys.executable, str(cli), *args], capture_output=True,  # nosec B603 - Fixed test executable and argument array; no shell.
                                    text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        for output in outputs:
            self.assertEqual(outputs[0], output)
        self.assertIn('Workflow:', outputs[0])

    def test_frozen_resource_paths_follow_executable_not_bytecode(self):
        info = Path(__file__).resolve().parents[1] / 'classes/info.py'
        script = """
import os,sys
source = open(sys.argv[1], encoding='utf-8').read()
sys.frozen = True
sys.executable = sys.argv[2]
root = os.path.dirname(sys.executable)
namespace = {'__file__': os.path.join(root, 'lib', 'classes', 'info.pyc')}
exec(compile(source, namespace['__file__'], 'exec'), namespace)
assert namespace['PATH'] == root
for name, folder in (('EXPORT_PRESETS_PATH', 'presets'), ('PROFILES_PATH', 'profiles'),
                     ('RESOURCES_PATH', 'resources'), ('IMAGES_PATH', 'images')):
    assert namespace[name] == os.path.join(root, folder), name
"""
        for relative in ('openshot-qt.exe', 'OpenShot.app/Contents/MacOS/openshot-qt'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                env = dict(os.environ, PYTHONPATH=str(info.parent.parent))
                result = subprocess.run([sys.executable, '-c', script, str(info), str(Path(directory) / relative)],
                                        capture_output=True, text=True, timeout=20, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_frozen_console_help_does_not_require_file_global(self):
        cli = Path(__file__).resolve().parents[1] / 'cli.py'
        script = """
import sys
source = open(sys.argv[1], encoding='utf-8').read()
sys.frozen = True
sys.argv = ['openshot-cli.exe', '--help']
exec(compile(source, 'frozen-cli', 'exec'), {'__name__': '__main__'})
"""
        env = dict(os.environ, PYTHONPATH=str(cli.parent))
        result = subprocess.run([sys.executable, '-c', script, str(cli)],
                                capture_output=True, text=True, timeout=20, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Workflow:', result.stdout)

    @unittest.skipUnless(os.name == 'nt', 'Requires Windows native standard handles')
    def test_windows_gui_style_missing_streams_preserve_redirected_io(self):
        script = '''
import sys
from classes.cli_console import ensure_standard_streams
original = (sys.stdin, sys.stdout, sys.stderr)
sys.stdin = sys.stdout = sys.stderr = None
ensure_standard_streams()
print('stdout:' + sys.stdin.readline().strip())
print('stderr:ready', file=sys.stderr)
'''
        interpreter = Path(sys.executable).with_name('pythonw.exe')
        if not interpreter.is_file():
            interpreter = Path(sys.executable)
        result = subprocess.run([str(interpreter), '-c', script], input='input text\n',  # nosec B603 - Fixed test executable and argument array; no shell.
                                capture_output=True, text=True, timeout=20,
                                env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'stdout:input text')
        self.assertEqual(result.stderr.strip(), 'stderr:ready')


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux AppImage launcher')
class AppImageEntryTests(unittest.TestCase):
    def setUp(self):
        from tests.source_tree import source_path
        self.temp = tempfile.TemporaryDirectory(prefix='openshot appimage test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle with spaces.AppDir'
        self.bin = self.bundle / 'usr' / 'bin'
        self.bin.mkdir(parents=True)
        self.work = self.root / 'user project'
        self.work.mkdir()
        shutil.copy2(source_path('installer/AppRun'), self.bundle / 'AppRun')
        shutil.copy2(source_path('installer/launch-linux.sh'), self.bin / 'openshot-qt-launch')
        for path in (self.bundle / 'AppRun', self.bin / 'openshot-qt-launch'):
            path.chmod(0o755)
        probe = self.bin / 'openshot-qt'
        probe.write_text('#!' + sys.executable + '\n' + '''
import json, os, sys
print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(),
                  'appdir': os.environ['APPDIR'], 'appimage': os.environ.get('APPIMAGE'), 'libraries': os.environ['LD_LIBRARY_PATH'],
                  'plugins': os.environ['QT_PLUGIN_PATH'], 'data': os.environ['XDG_DATA_DIRS'],
                  'theme': os.environ.get('QT_QPA_PLATFORMTHEME')}))
if '--stdin' in sys.argv:
    print(sys.stdin.read(), end='')
if '--error' in sys.argv:
    print('cli failure', file=sys.stderr)
    sys.exit(7)
''')
        probe.chmod(0o755)
        self.env = dict(os.environ, APPDIR='/old/parent/mount', APPIMAGE='/old/parent.AppImage')
        self.env.pop('QT_QPA_PLATFORMTHEME', None)
        self.env.pop('XDG_DATA_DIRS', None)

    def run_bundle(self, *args, **kwargs):
        return subprocess.run([str(self.bundle / 'AppRun'), *args], cwd=self.work,  # nosec B603 - Fixed test executable and argument array; no shell.
                              env=self.env, capture_output=True, text=True, timeout=20, **kwargs)

    def test_gui_and_cli_keep_arguments_paths_and_environment(self):
        for args in ([], ['my project.osp'], ['--cli', 'file', 'import', 'a clip; $(literal).mp4'],
                     ['--cli', 'edit', 'apply', '--json', '@my edits.json']):
            with self.subTest(args=args):
                result = self.run_bundle(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data['args'], args)
                self.assertEqual(data['cwd'], str(self.work))
                self.assertEqual(data['appdir'], str(self.bundle))
                self.assertIsNone(data['appimage'])
                self.assertEqual(data['libraries'], str(self.bin))
                self.assertEqual(data['plugins'], str(self.bin))
                self.assertEqual(data['data'], str(self.bundle / 'usr' / 'share') + ':/usr/local/share:/usr/share')

    def test_stdin_stderr_exit_status_and_portal_override(self):
        result = self.run_bundle('--cli', '--stdin', input='{"commands":[]}\n')
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.endswith('{"commands":[]}\n'))
        result = self.run_bundle('--cli', '--error')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stderr, 'cli failure\n')
        (self.bin / 'platformthemes').mkdir()
        (self.bin / 'platformthemes' / 'libqxdgdesktopportal.so').touch()
        self.assertEqual(json.loads(self.run_bundle('--cli').stdout)['theme'], 'xdgdesktopportal')
        self.env['QT_QPA_PLATFORMTHEME'] = 'custom'
        self.assertEqual(json.loads(self.run_bundle('--cli').stdout)['theme'], 'custom')

    def test_frozen_workers_reopen_image_instead_of_using_client_mount(self):
        image = self.root / 'OpenShot with spaces.AppImage'
        image.write_text('#!/bin/sh\nexit 0\n')
        image.chmod(0o755)
        with patch('sys.frozen', True, create=True), patch('sys.executable', str(self.bin / 'openshot-qt')), patch.dict(os.environ, {'APPIMAGE': str(image), 'APPDIR': str(self.bundle)}):
            for args in [('session', 'serve'), ('--_export-worker', str(self.root / 'job with spaces'))]:
                self.assertEqual(cli_command(*args), [str(image), '--cli', *args])
            image.unlink()
            with self.assertRaises(CommandError) as error:
                cli_command('session', 'serve')
            self.assertEqual(error.exception.code, 'missing_appimage')

    def test_extracted_and_unrelated_frozen_builds_use_local_cli(self):
        alias = self.bin / 'openshot-cli'
        alias.touch()
        with patch('sys.frozen', True, create=True), patch('sys.executable', str(self.bin / 'openshot-qt')):
            with patch.dict(os.environ, {'APPIMAGE': '', 'APPDIR': str(self.bundle)}):
                self.assertEqual(cli_command('session', 'serve'), [str(alias), 'session', 'serve'])
            with patch.dict(os.environ, {'APPIMAGE': '/other.AppImage', 'APPDIR': '/unrelated'}):
                self.assertEqual(cli_command('--help'), [str(alias), '--help'])

    def test_source_checkout_ignores_inherited_appimage_environment(self):
        with patch.dict(os.environ, {'APPIMAGE': '/other.AppImage', 'APPDIR': '/unrelated'}):
            self.assertEqual(cli_command('--help')[0], sys.executable)

    def test_windows_console_companion_command(self):
        from pathlib import PosixPath
        companion = self.bin / 'openshot-qt-cmd.exe'
        companion.touch()
        with patch('sys.frozen', True, create=True), patch('sys.platform', 'win32'), patch('sys.executable', str(self.bin / 'openshot-qt.exe')), patch('classes.agent.protocol.Path', PosixPath), patch('os.name', 'nt'):
            self.assertEqual(cli_command('session', 'serve'), [str(companion), '--cli', 'session', 'serve'])
