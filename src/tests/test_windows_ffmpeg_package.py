"""Selected FFmpeg runtime DLLs must replace SDK copies in Windows packages."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from tests.source_tree import source_path

spec = importlib.util.spec_from_file_location('windows_ffmpeg', source_path('installer/windows_ffmpeg.py'))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class WindowsFFmpegPackageTests(unittest.TestCase):
    def test_selected_runtime_replaces_sdk_dlls_and_includes_dispatcher_notices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prefix, package = root / 'ffmpeg', root / 'package'
            (prefix / 'bin').mkdir(parents=True)
            (package / 'lib').mkdir(parents=True)
            for name in ('avcodec-61.dll', 'avutil-59.dll', 'libvpl.dll'):
                (prefix / 'bin' / name).write_bytes(b'hardware build')
                (package / 'lib' / name).write_bytes(b'old SDK build')
            licensing = prefix / 'share/vpl/licensing'
            licensing.mkdir(parents=True)
            (licensing / 'LICENSE').write_text('dispatcher license')
            report = runtime.stage_ffmpeg_runtime(prefix, package)
            self.assertEqual({row['name'] for row in report['files']},
                             {'avcodec-61.dll', 'avutil-59.dll', 'libvpl.dll'})
            for row in report['files']:
                self.assertEqual((package / 'lib' / row['name']).read_bytes(), b'hardware build')
            self.assertEqual((package / 'licenses/oneVPL/LICENSE').read_text(), 'dispatcher license')

    def test_missing_ffmpeg_prefix_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'No Windows FFmpeg DLLs'):
                runtime.stage_ffmpeg_runtime(Path(directory) / 'missing', Path(directory) / 'package')


spec = importlib.util.spec_from_file_location('check_hardware_package', source_path('installer/check_hardware_package.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class HardwarePackageCheckTests(unittest.TestCase):
    def test_mac_and_windows_check_bundled_presets_without_runner_paths(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import patch
        for platform in ('win32', 'darwin'):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as directory:
                package = Path(directory)
                names = ('openshot-qt',) if platform == 'darwin' else ('openshot-qt-cmd.exe', 'openshot-cli.exe')
                for name in names:
                    (package / name).touch()
                codecs = ('h264_videotoolbox',) if platform == 'darwin' else checker.REQUIRED_ENCODERS
                rows = [{'video_codec': codec, 'codecs_available': True} for codec in codecs]
                response = SimpleNamespace(returncode=0, stdout=json.dumps({'ok': True, 'result': rows}), stderr='')
                dirty = {key: '/runner/sdk' for key in ('PYTHONPATH', 'DYLD_LIBRARY_PATH', 'LD_LIBRARY_PATH')}
                with patch.dict(checker.os.environ, dirty), \
                        patch.object(checker.subprocess, 'run', return_value=response) as run, \
                        patch('builtins.print'):
                    checker.check_package(package, platform=platform)
                    self.assertEqual(run.call_count, len(names))
                    for call in run.call_args_list:
                        for key in dirty:
                            self.assertNotIn(key, call.kwargs['env'])
                    rows[0]['codecs_available'] = False
                    response.stdout = json.dumps({'ok': True, 'result': rows})
                    with self.assertRaisesRegex(RuntimeError, 'missing hardware export'):
                        checker.check_package(package, platform=platform)
                    response.stdout = json.dumps({'ok': True, 'result': []})
                    with self.assertRaisesRegex(RuntimeError, 'empty preset catalogue'):
                        checker.check_package(package, platform=platform)
