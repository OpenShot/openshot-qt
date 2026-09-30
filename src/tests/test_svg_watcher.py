"""Portable Qt/file-system tests: no libopenshot or application installation needed."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock

from qt_api import QApplication, QEventLoop, QTimer
from classes.svg_watcher import SvgWatcher
from tests.qt_test_app import get_or_create_app


class SvgWatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, _ = get_or_create_app(lambda: QApplication([]))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='SVG title ü ')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'title with spaces.svg'
        self.path.write_text('<svg><text>original</text></svg>')
        self.watcher = SvgWatcher()
        self.watcher.watch(str(self.path))
        self.addCleanup(self.watcher.stop)
        self.changed = Mock()
        self.watcher.changed.connect(self.changed)

    def settle(self):
        self.watcher.check()
        self.watcher.check()

    def test_repeated_in_place_and_atomic_saves(self):
        for number in range(4):
            contents = '<svg><text>save %s</text></svg>' % number
            if number % 2:
                replacement = self.path.with_suffix('.new')
                replacement.write_text(contents)
                os.replace(replacement, self.path)
            else:
                self.path.write_text(contents)
            self.watcher.check()
            self.assertEqual(self.changed.call_count, number)
            self.watcher.check()
            self.assertEqual(self.changed.call_count, number + 1)
            self.assertEqual(self.changed.call_args.args[0].toxml(), '<?xml version="1.0" ?>' + contents)
        self.settle()
        self.assertEqual(self.changed.call_count, 4)

    def test_partial_missing_and_non_svg_files_preserve_last_good_document(self):
        for contents in (b'', b'<svg>', b'<html/>', b'not xml',
                         b'<?xml version="1.0" encoding="unknown"?><svg/>',
                         b'<?xml version="1.0" encoding="UTF-32"?><svg/>'):
            self.path.write_bytes(contents)
            self.settle()
            self.changed.assert_not_called()
        self.path.unlink()
        self.settle()
        self.path.write_text('<svg><text>recovered</text></svg>')
        self.settle()
        self.changed.assert_called_once()

    def test_file_missing_when_watch_starts_recovers(self):
        self.path.unlink()
        self.watcher.watch(str(self.path))
        self.settle()
        self.changed.assert_not_called()
        self.path.write_text('<svg><text>restored</text></svg>')
        self.settle()
        self.changed.assert_called_once()

    def test_watcher_switch_and_stop(self):
        other = self.path.with_name('other.svg')
        other.write_text('<svg/>')
        self.watcher.watch(str(other))
        self.path.write_text('<svg><text>old file</text></svg>')
        self.settle()
        self.changed.assert_not_called()
        self.watcher.stop()
        other.write_text('<svg><text>closed</text></svg>')
        self.settle()
        self.changed.assert_not_called()
        self.assertFalse(self.watcher.timer.isActive())

    def test_timer_delivers_a_save_with_unchanged_size_and_timestamp(self):
        original = self.path.stat()
        self.path.write_text('<svg><text>modified</text></svg>')
        os.utime(self.path, ns=(original.st_atime_ns, original.st_mtime_ns))
        deadline = time.monotonic() + 4
        while not self.changed.called and time.monotonic() < deadline:
            loop = QEventLoop()
            QTimer.singleShot(20, loop.quit)
            loop.exec()
        self.changed.assert_called_once()
        self.assertIn('modified', self.changed.call_args.args[0].toxml())

    def test_own_content_and_unchanged_files_do_not_emit(self):
        self.settle()
        self.changed.assert_not_called()
        contents = b'<svg><text>internal</text></svg>'
        self.path.write_bytes(contents)
        self.watcher.remember(contents)
        self.settle()
        self.changed.assert_not_called()

    def test_explicit_final_read_flushes_valid_svg_immediately(self):
        self.path.write_text('<svg><text>just saved</text></svg>')
        self.watcher.check(force=True)
        self.changed.assert_called_once()


if __name__ == '__main__':
    unittest.main()
