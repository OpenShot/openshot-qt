"""Logging precedence and backwards-compatible command-line behavior."""
import argparse
import contextlib
import io
import os
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from classes import log_config as config


class LoggingConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        config._environment = None
        config._cli = {}

    def tearDown(self):
        self.env.stop()
        config._environment = None
        config._cli = {}

    def parse(self, *args):
        parser = argparse.ArgumentParser()
        config.add_arguments(parser)
        parsed = parser.parse_args(args)
        config.configure_arguments(parser, parsed)
        return parser

    def test_each_preference_only_affects_its_file(self):
        for component in ('python', 'native'):
            self.assertEqual(config.resolve(component, 'file')[0], 'INFO')
            self.assertEqual(config.resolve(component, 'file', True)[0], 'DEBUG')
            self.assertEqual(config.resolve(component, 'console', True)[0], 'INFO')

    def test_native_group_beats_shared_destination(self):
        os.environ.update(OPENSHOT_LOG_FILE_LEVEL='error', LIBOPENSHOT_LOG_LEVEL='warning')
        self.assertEqual(config.resolve('native', 'file', True), ('WARNING', 'LIBOPENSHOT_LOG_LEVEL'))
        self.assertEqual(config.resolve('python', 'file', True)[0], 'ERROR')

    def test_destination_cli_beats_general_and_environment(self):
        os.environ['LIBOPENSHOT_LOG_LEVEL'] = 'OFF'
        self.parse('--log-level', 'debug', '--log-console-level', 'warning')
        self.assertEqual(config.resolve('native', 'file')[0], 'DEBUG')
        self.assertEqual(config.resolve('native', 'console')[0], 'WARNING')

    def test_legacy_aliases(self):
        for alias, destination in (('--debug-file', 'file'), ('--debug-console', 'console')):
            self.parse(alias)
            self.assertEqual(config.resolve('python', destination)[0], 'DEBUG')
            self.assertEqual(config.resolve('native', destination)[0], 'INFO')
            other = 'console' if destination == 'file' else 'file'
            self.assertEqual(config.resolve('python', other)[0], 'INFO')
        os.environ['LIBOPENSHOT_DEBUG'] = '0'
        config._cli = {}
        config._environment = None
        self.assertEqual(config.resolve('native', 'console')[0], 'DEBUG')
        self.assertEqual(config.resolve('python', 'console')[0], 'INFO')

    def test_debug_flag_only_changes_python(self):
        for flag in ('--debug', '-d', '--debug-ui'):
            self.parse(flag)
            for destination in ('file', 'console'):
                self.assertEqual(config.resolve('python', destination)[0], 'DEBUG')
                self.assertEqual(config.resolve('native', destination)[0], 'INFO')
            self.assertEqual(config.resolve('native', 'file', True)[0], 'DEBUG')
            self.assertEqual(config.preference_description(), '')

    def test_debug_flag_preserves_native_environment_and_preference(self):
        os.environ.update(LIBOPENSHOT_LOG_FILE_LEVEL='error', OPENSHOT_LOG_CONSOLE_LEVEL='warning')
        self.parse('--debug')
        self.assertEqual(config.resolve('native', 'file', True)[0], 'ERROR')
        self.assertEqual(config.resolve('native', 'console')[0], 'WARNING')
        self.assertEqual(config.resolve('python', 'console')[0], 'DEBUG')
        self.assertIn('LIBOPENSHOT_LOG_FILE_LEVEL', config.preference_description(True))

    def test_destination_level_with_debug_flag_still_controls_both(self):
        self.parse('--debug', '--log-console-level', 'warning')
        self.assertEqual(config.resolve('python', 'file')[0], 'DEBUG')
        self.assertEqual(config.resolve('native', 'file')[0], 'INFO')
        for component in ('python', 'native'):
            self.assertEqual(config.resolve(component, 'console')[0], 'WARNING')

    def test_engine_flag_only_changes_engine(self):
        self.parse('--debug-engine')
        for destination in ('file', 'console'):
            self.assertEqual(config.resolve('native', destination)[0], 'DEBUG')
            self.assertEqual(config.resolve('python', destination)[0], 'INFO')
        self.assertEqual(config.resolve('python', 'file', True)[0], 'DEBUG')
        self.assertIn('command line', config.preference_description())
        self.assertEqual(config.preference_description(component='python'), '')

    def test_both_component_flags_override_environment(self):
        os.environ['OPENSHOT_LOG_LEVEL'] = 'off'
        self.parse('--debug-ui', '--debug-engine')
        for component in ('python', 'native'):
            for destination in ('file', 'console'):
                self.assertEqual(config.resolve(component, destination)[0], 'DEBUG')

    def test_engine_flag_respects_explicit_destination_level(self):
        self.parse('--debug-engine', '--log-console-level', 'warning')
        self.assertEqual(config.resolve('native', 'file')[0], 'DEBUG')
        self.assertEqual(config.resolve('python', 'file')[0], 'INFO')
        for component in ('python', 'native'):
            self.assertEqual(config.resolve(component, 'console')[0], 'WARNING')

    def test_engine_general_conflict_in_either_order(self):
        for args in (('--debug-engine', '--log-level', 'off'),
                     ('--log-level', 'off', '--debug-engine')):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.parse(*args)

    def test_both_saved_preferences_default_off_and_keep_engine_key(self):
        import json
        settings = json.loads((Path(__file__).parents[1] / 'settings' / '_default.settings').read_text())
        settings = {item['setting']: item for item in settings}
        for key, title in (('debug-ui', 'User Interface Debug Logging'),
                           ('debug-mode', 'Video & Audio Engine Debug Logging')):
            self.assertFalse(settings[key]['value'])
            self.assertFalse(settings[key]['restart'])
            self.assertEqual(settings[key]['title'], title)

    def test_modern_environment_overrides_legacy(self):
        os.environ.update(LIBOPENSHOT_DEBUG='', OPENSHOT_LOG_LEVEL='error')
        self.assertEqual(config.resolve('native', 'console')[0], 'ERROR')

    def test_invalid_environment_falls_back_and_warns_once(self):
        os.environ.update(OPENSHOT_LOG_LEVEL='warning', LIBOPENSHOT_LOG_FILE_LEVEL='nope')
        with contextlib.redirect_stderr(io.StringIO()) as output:
            for _ in range(2):
                self.assertEqual(config.resolve('native', 'file')[0], 'WARNING')
        self.assertEqual(output.getvalue().count('ignoring invalid'), 1)

    def test_conflicts_rejected_in_either_order(self):
        pairs = [('--debug', '--log-level', 'off'),
                 ('--debug-file', '--log-file-level', 'off'),
                 ('--debug-console', '--log-console-level', 'off'),
                 ('--log-level', 'debug', '--log-level', 'off')]
        for args in pairs:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.parse(*args)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse('--log-level', 'off', '--debug')

    def test_every_level_argument_and_supported_level(self):
        # Tuple order: UI file, UI console, engine file, engine console.
        targets = {'--log-level': (0, 1, 2, 3),
                   '--log-file-level': (0, 2), '--log-console-level': (1, 3)}
        outputs = (('python', 'file'), ('python', 'console'),
                   ('native', 'file'), ('native', 'console'))
        for option, affected in targets.items():
            for value in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'OFF'):
                with self.subTest(option=option, value=value):
                    self.parse(option, value.lower())
                    expected = [value if i in affected else 'INFO' for i in range(4)]
                    self.assertEqual([config.resolve(*output)[0] for output in outputs], expected)

    def test_every_environment_level_variable(self):
        targets = {'OPENSHOT_LOG_LEVEL': (0, 1, 2, 3),
                   'OPENSHOT_LOG_FILE_LEVEL': (0, 2),
                   'OPENSHOT_LOG_CONSOLE_LEVEL': (1, 3),
                   'LIBOPENSHOT_LOG_LEVEL': (2, 3),
                   'LIBOPENSHOT_LOG_FILE_LEVEL': (2,),
                   'LIBOPENSHOT_LOG_CONSOLE_LEVEL': (3,)}
        outputs = (('python', 'file'), ('python', 'console'),
                   ('native', 'file'), ('native', 'console'))
        for variable, affected in targets.items():
            for value in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'OFF'):
                with self.subTest(variable=variable, value=value), \
                        patch.dict(os.environ, {variable: value.lower()}, clear=True):
                    config._environment = None
                    expected = [value if i in affected else 'INFO' for i in range(4)]
                    self.assertEqual([config.resolve(*output)[0] for output in outputs], expected)

    def test_invalid_level_arguments_are_rejected(self):
        for option in ('--log-level', '--log-file-level', '--log-console-level'):
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                self.parse(option, 'verbose')

    def test_each_destination_overrides_general_environment_level(self):
        os.environ.update(OPENSHOT_LOG_LEVEL='off', OPENSHOT_LOG_FILE_LEVEL='warning',
                          OPENSHOT_LOG_CONSOLE_LEVEL='error', LIBOPENSHOT_LOG_LEVEL='info',
                          LIBOPENSHOT_LOG_FILE_LEVEL='debug', LIBOPENSHOT_LOG_CONSOLE_LEVEL='critical')
        self.assertEqual(config.resolve('python', 'file')[0], 'WARNING')
        self.assertEqual(config.resolve('python', 'console')[0], 'ERROR')
        self.assertEqual(config.resolve('native', 'file')[0], 'DEBUG')
        self.assertEqual(config.resolve('native', 'console')[0], 'CRITICAL')

    def test_aliases_hidden_from_help(self):
        help_text = self.parse().format_help()
        self.assertNotIn('--debug-file', help_text)
        self.assertNotIn('--debug-console', help_text)
        self.assertIn('--debug-ui', help_text)
        self.assertIn('--debug-engine', help_text)


if __name__ == '__main__':
    unittest.main()
