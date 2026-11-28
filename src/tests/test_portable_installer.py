"""Compile and execute the Windows installer with a tiny, isolated payload.

Windows builders require ISCC on PATH (or OPENSHOT_TEST_ISCC).
Release signing and translations are excluded; production installer code, tasks,
and deletion rules are used unchanged. Registry writes use a test-only HKCU key.
"""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import uuid


@unittest.skipUnless(os.name == 'nt', 'Inno Setup execution requires native Windows')
class PortableInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = os.environ.get('OPENSHOT_TEST_ISCC') or shutil.which('iscc.exe')
        if not cls.compiler:
            for folder in ('Inno Setup 7', 'Inno Setup 6'):
                for base in (os.environ.get('ProgramFiles', ''), os.environ.get('ProgramFiles(x86)', '')):
                    candidate = Path(base) / folder / 'ISCC.exe'
                    if candidate.is_file():
                        cls.compiler = str(candidate)
                        break
        if not cls.compiler:
            if os.environ.get('OPENSHOT_REQUIRE_INNO_TESTS') == '1':
                raise RuntimeError('ISCC.exe is required for portable installer tests on this builder')
            raise unittest.SkipTest('ISCC.exe is not installed')

        temporary = tempfile.TemporaryDirectory(prefix='openshot-inno-')
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        repo = Path(__file__).resolve().parents[2]
        stage = cls.root / 'fixture'
        (stage / 'installer').mkdir(parents=True)
        (stage / 'build' / 'payload' / 'lib').mkdir(parents=True)
        (stage / 'xdg').mkdir()
        shutil.copy2(repo / 'COPYING', stage / 'COPYING')
        for name in ('installer-logo.bmp', 'isportable.iss'):
            shutil.copy2(repo / 'installer' / name, stage / 'installer' / name)
        shutil.copy2(repo / 'xdg' / 'openshot-qt.ico', stage / 'xdg' / 'openshot-qt.ico')
        (stage / 'build' / 'payload' / 'openshot-qt.exe').write_bytes(b'portable test payload v2')
        (stage / 'build' / 'payload' / 'lib' / 'current.dll').write_bytes(b'current library v2')

        script = (repo / 'installer' / 'windows-installer.iss').read_text(encoding='utf-8')
        cls.identity = str(uuid.uuid4()).upper()
        cls.registry = 'Software\\OpenShotPortableTests\\' + cls.identity
        # Keep the actual installer sections and Pascal code. Isolate resources
        # and registry destinations so testing never changes installed OpenShot.
        script = script.replace('4BB0DCDC-BC24-49EC-8937-72956C33A470', cls.identity)
        script = re.sub(r'\[Languages\].*?(?=\[CustomMessages\])',
                        '[Languages]\nName: "english"; MessagesFile: "compiler:Default.isl"\n\n',
                        script, flags=re.S)
        script = re.sub(r'^italian\.FirewallException=.*\n', '', script, flags=re.M)
        script = script.replace('SignedUninstaller=yes', 'SignedUninstaller=no')
        script = script.replace('Root: HKLM;', 'Root: HKCU;')
        script = script.replace('Subkey: "Software\\', 'Subkey: "' + cls.registry + '\\')
        # The normal installer has legacy DLL cleanup hooks. Exercise their
        # conditions without ever renaming files in the builder's Windows folder.
        for location in ('{sys}', '{win}\\system32', '{syswow64}'):
            script = script.replace(location + '\\zlib1.', '{app}\\test-system\\zlib1.')
        script_path = stage / 'installer' / 'windows-installer.iss'
        script_path.write_text(script, encoding='utf-8')
        cls.legacy_key = cls.registry + '\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + cls.identity + '_is1'
        cls.addClassCleanup(cls.remove_test_registry)
        cls.command([cls.compiler, '/Q', '/DVERSION=4.2.0.0', '/DPY_EXE_DIR=payload',
                     '/DONLY_64_BIT=', '/O' + cls.windows_path(cls.root / 'output'),
                     cls.windows_path(script_path)])
        cls.installer = cls.root / 'output' / 'OpenShot.exe'
        if not cls.installer.is_file():
            raise AssertionError('Inno Setup did not produce the test installer')

    @classmethod
    def windows_path(cls, path):
        return str(path)

    @classmethod
    def command(cls, args, success=True):
        result = subprocess.run(list(args),
                                cwd=cls.root, capture_output=True, text=True,
                                errors='replace', timeout=90)
        if success and result.returncode != 0:
            raise AssertionError('Windows command failed ({}): {}\n{}\n{}'.format(
                result.returncode, args, result.stdout, result.stderr))
        return result

    @classmethod
    def remove_test_registry(cls):
        cls.command(['reg.exe', 'delete', 'HKCU\\' + cls.registry, '/f'], success=False)

    def setUp(self):
        self.destination = self.root / self._testMethodName / 'OpenShot 4.2.0 - fix for xyz'
        self.destination.mkdir(parents=True)
        self.log = self.destination.parent / 'setup.log'

    def install(self, portable=True, success=True):
        args = [self.windows_path(self.installer), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                '/NORESTART', '/CURRENTUSER', '/NOICONS', '/TASKS=', '/SP-',
                '/DIR=' + self.windows_path(self.destination),
                '/LOG=' + self.windows_path(self.log)]
        if portable:
            args.append('/portable=1')
        result = self.command(args, success=False)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr + self.read_log())
        else:
            self.assertNotEqual(result.returncode, 0, self.read_log())
        return result

    def read_log(self):
        return self.log.read_text(encoding='utf-8-sig', errors='replace') if self.log.exists() else ''

    def seed_data(self):
        data = self.destination / '.openshot_qt'
        for relative in ('openshot.settings', 'recovery/unsaved.osp', 'cache/frame.png',
                         'profiles/custom', 'yolo/model.onnx', 'default.osp'):
            path = data / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('preserve ' + relative).encode())
        return self.snapshot(data)

    @staticmethod
    def snapshot(folder):
        return {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in folder.rglob('*') if path.is_file()}

    def assert_payload(self):
        self.assertEqual((self.destination / 'openshot-qt.exe').read_bytes(), b'portable test payload v2')
        self.assertEqual((self.destination / 'lib' / 'current.dll').read_bytes(), b'current library v2')

    def test_fresh_portable_install_with_custom_folder_name(self):
        self.install()
        self.assert_payload()
        self.assertEqual((self.destination / 'portable').read_bytes(), b'')
        self.assertFalse((self.destination / 'unins000.exe').exists())
        self.assertFalse((self.destination / '.openshot_qt').exists())  # Created by the app, not setup.

    def test_unicode_destination(self):
        self.destination = self.destination.parent / 'OpenShot - réglage 日本語'
        self.install()
        self.assert_payload()
        self.assertEqual((self.destination / 'portable').read_bytes(), b'')

    def seed_user_files(self):
        files = ('project.osp', 'media/footage.mp4', 'project_assets/title.svg',
                 'lib/user-media/clip.wav', 'notes.txt', 'old-lib/nested/obsolete.dll',
                 'obsolete.dll')
        for relative in files:
            path = self.destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('user file ' + relative).encode())
        return {relative: (self.destination / relative).read_bytes() for relative in files}

    def assert_user_files(self, expected):
        for relative, contents in expected.items():
            with self.subTest(path=relative):
                self.assertEqual((self.destination / relative).read_bytes(), contents)

    def test_upgrade_preserves_projects_media_and_unowned_files_in_both_modes(self):
        original_destination = self.destination
        for portable in (True, False):
            with self.subTest(portable=portable):
                self.destination = original_destination / ('portable' if portable else 'standard')
                self.destination.mkdir(parents=True)
                try:
                    self.install(portable=portable)
                    before = self.seed_data()
                    user_files = self.seed_user_files()
                    (self.destination / 'openshot-qt.exe').write_bytes(b'old executable')
                    (self.destination / 'lib' / 'current.dll').write_bytes(b'old library')
                    self.install(portable=portable)
                    self.assert_payload()
                    self.assert_user_files(user_files)
                    self.assertEqual(self.snapshot(self.destination / '.openshot_qt'), before)
                finally:
                    if not portable:
                        self.uninstall_if_present()

    def test_first_standard_install_preserves_existing_projects_and_media(self):
        user_files = self.seed_user_files()
        try:
            self.install(portable=False)
            self.assert_payload()
            self.assert_user_files(user_files)
        finally:
            self.uninstall_if_present()

    def test_first_portable_install_preserves_existing_local_data(self):
        before = self.seed_data()
        user_files = self.seed_user_files()
        self.install()
        self.assert_user_files(user_files)
        self.assertEqual(self.snapshot(self.destination / '.openshot_qt'), before)

    def test_upgrade_without_portable_argument_still_preserves_data(self):
        self.install()
        before = self.seed_data()
        user_files = self.seed_user_files()
        try:
            self.install(portable=False)
            self.assert_user_files(user_files)
            self.assertEqual(self.snapshot(self.destination / '.openshot_qt'), before)
            self.assertTrue((self.destination / 'portable').is_file())
        finally:
            self.uninstall_if_present()

    def test_normal_install_does_not_enable_portable_mode(self):
        try:
            self.install(portable=False)
            self.assert_payload()
            self.assertFalse((self.destination / 'portable').exists())
            self.assertTrue((self.destination / 'unins000.exe').is_file())
        finally:
            self.uninstall_if_present()

    def uninstall_if_present(self):
        uninstaller = self.destination / 'unins000.exe'
        if uninstaller.is_file():
            self.command([self.windows_path(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'])

    def test_portable_install_does_not_delete_legacy_registry_key(self):
        key = 'HKCU\\' + self.legacy_key
        self.command(['reg.exe', 'add', key, '/v', 'sentinel', '/d', 'keep', '/f'])
        self.install()
        result = self.command(['reg.exe', 'query', key, '/v', 'sentinel'])
        self.assertIn('keep', result.stdout)

    def test_two_portable_installations_remain_independent(self):
        first = self.destination
        self.install()
        before = self.seed_data()
        self.destination = first.parent / 'OpenShot another version'
        self.install()
        self.assertFalse((self.destination / '.openshot_qt').exists())
        self.assertEqual(self.snapshot(first / '.openshot_qt'), before)

    def test_locked_binary_blocks_upgrade_without_deleting_data(self):
        self.install()
        before = self.seed_data()
        with (self.destination / 'openshot-qt.exe').open('rb'):
            self.install(success=False)
        self.assertEqual(self.snapshot(self.destination / '.openshot_qt'), before)

    def test_unwritable_marker_name_fails_installation(self):
        (self.destination / 'portable').mkdir()
        executable = self.destination / 'openshot-qt.exe'
        executable.write_bytes(b'keep the old executable')
        before = self.seed_data()
        self.install(success=False)
        self.assertEqual(executable.read_bytes(), b'keep the old executable')
        self.assertEqual(self.snapshot(self.destination / '.openshot_qt'), before)


if __name__ == '__main__':
    unittest.main()
