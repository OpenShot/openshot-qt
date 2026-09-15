"""Exercise real Python handlers without importing the application or Qt."""
import importlib.util
import io
import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import classes


class LoggerSinkTests(unittest.TestCase):
    def test_console_debug_is_not_filtered_by_file_level(self):
        with tempfile.TemporaryDirectory() as directory:
            info = types.ModuleType('classes.info')
            info.USER_PATH = directory
            info.LOG_LEVEL_FILE = 'INFO'
            info.LOG_LEVEL_CONSOLE = 'DEBUG'
            spec = importlib.util.spec_from_file_location('test_logging_module',
                Path(__file__).parents[1] / 'classes' / 'logger.py')
            module = importlib.util.module_from_spec(spec)
            root = logging.RootLogger(logging.ERROR)
            root.manager = logging.Manager(root)
            console = io.StringIO()
            # Other tests may already have imported classes.info and installed
            # application handlers. Isolate both the package attribute and logger tree.
            with patch.dict(sys.modules, {'classes.info': info}), \
                    patch.object(classes, 'info', info, create=True), \
                    patch('logging.getLogger', return_value=root), \
                    patch('sys.stderr', console):
                spec.loader.exec_module(module)
            try:
                module.log.debug('debug-to-console')
                module.log.warning('warning-to-both')
                module.set_level_file(logging.DEBUG)
                module.set_level_console(logging.ERROR)
                module.log.debug('debug-to-file')
                module.fh.flush()
                content = (Path(directory) / 'openshot-qt.log').read_text()
                self.assertIn('debug-to-console', console.getvalue())
                self.assertNotIn('debug-to-console', content)
                self.assertIn('warning-to-both', content)
                self.assertIn('debug-to-file', content)
                self.assertNotIn('debug-to-file', console.getvalue())
                module.set_level_file(100)
                module.set_level_console(100)
                self.assertFalse(module.log.isEnabledFor(logging.CRITICAL))
            finally:
                for handler in (module.fh, module.sh):
                    module.log.removeHandler(handler)
                    handler.close()


if __name__ == '__main__':
    unittest.main()
