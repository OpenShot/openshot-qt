"""Preference migration and live application of logging settings."""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import classes
from classes import log_config


def load_method(path, name, namespace):
    tree = ast.parse((SOURCE / path).read_text())
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.Module(body=[method], type_ignores=[])
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace[name]


class LoggingPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.old_cli, self.old_environment = log_config._cli, log_config._environment
        log_config._cli, log_config._environment = {}, None
        self.native = Mock()
        self.python_logger = types.ModuleType('classes.logger')
        self.python_logger.log = Mock()
        self.python_logger.set_level_file = Mock()
        self.python_logger.set_level_console = Mock()
        info = types.SimpleNamespace(USER_PATH='/test-user')
        openshot = types.SimpleNamespace(Logger=types.SimpleNamespace(Instance=lambda: self.native))
        spec = importlib.util.spec_from_file_location('logging_coordinator_test',
                                                     SOURCE / 'classes/logger_libopenshot.py')
        self.coordinator = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'openshot': openshot, 'classes.logger': self.python_logger}), \
                patch.object(classes, 'info', info, create=True):
            spec.loader.exec_module(self.coordinator)

    def tearDown(self):
        log_config._cli, log_config._environment = self.old_cli, self.old_environment
        self.environment.stop()

    def test_live_preference_combinations_configure_independent_files(self):
        for ui, engine in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(ui=ui, engine=engine):
                self.coordinator.configure(engine, ui_debug=ui)
                self.python_logger.set_level_file.assert_called_with(10 if ui else 20)
                self.python_logger.set_level_console.assert_called_with(20)
                self.native.SetFileLevel.assert_called_with('DEBUG' if engine else 'INFO')
                self.native.SetConsoleLevel.assert_called_with('INFO')
        self.native.Path.assert_not_called()  # Changing levels must not reopen the file.

    def test_checkbox_updates_preserve_other_setting_and_respect_cli(self):
        parser = argparse.ArgumentParser()
        log_config.add_arguments(parser)
        log_config.configure_arguments(parser, parser.parse_args(['--debug-engine']))
        values = {'debug-ui': False, 'debug-mode': False}
        settings = types.SimpleNamespace(get=values.get, set=values.__setitem__)
        dialog = types.SimpleNamespace(s=settings, logging_tooltip=Mock(return_value='tooltip'),
                                       check_for_restart=Mock(), apply_dependencies_for_controller=Mock())
        callback = load_method('windows/preferences.py', 'bool_value_changed',
                               {'Qt': types.SimpleNamespace(Checked=2), 'log': Mock()})
        with patch.object(classes, 'logger_libopenshot', self.coordinator, create=True):
            for key, state, expected in (
                    ('debug-ui', 2, {'debug-ui': True, 'debug-mode': False}),
                    ('debug-mode', 2, {'debug-ui': True, 'debug-mode': True}),
                    ('debug-ui', 0, {'debug-ui': False, 'debug-mode': True}),
                    ('debug-mode', 0, {'debug-ui': False, 'debug-mode': False})):
                with self.subTest(key=key, state=state):
                    callback(dialog, Mock(), {'setting': key}, state)
                    self.assertEqual(values, expected)
                    self.native.SetFileLevel.assert_called_with('DEBUG')
                    self.native.SetConsoleLevel.assert_called_with('DEBUG')
                    self.python_logger.set_level_file.assert_called_with(10 if expected['debug-ui'] else 20)
                    self.python_logger.set_level_console.assert_called_with(20)

    def test_saved_engine_preference_migrates_and_ui_preference_round_trips(self):
        merge = load_method('classes/json_data.py', 'merge_settings', {})
        defaults = (SOURCE / 'settings/_default.settings').read_text()
        old = [{'setting': 'debug-mode', 'value': True, 'title': 'Debug Mode (Verbose)'},
               {'setting': 'debug-port', 'value': 5556}]
        merged = merge(None, json.loads(defaults), old)
        by_key = {item['setting']: item for item in merged}
        self.assertTrue(by_key['debug-mode']['value'])
        self.assertEqual(by_key['debug-mode']['title'], 'Video & Audio Engine Debug Logging')
        self.assertFalse(by_key['debug-ui']['value'])
        self.assertNotIn('debug-port', by_key)
        by_key['debug-ui']['value'] = True
        reloaded = merge(None, json.loads(defaults), json.loads(json.dumps(merged)))
        reloaded = {item['setting']: item for item in reloaded}
        self.assertTrue(reloaded['debug-ui']['value'])
        self.assertTrue(reloaded['debug-mode']['value'])


if __name__ == '__main__':
    unittest.main()
