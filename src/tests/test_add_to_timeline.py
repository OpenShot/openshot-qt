"""
 @file
 @brief Regression tests for Add to Timeline dialog helpers
"""

import os
import sys
import types
import unittest


PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from qt_api import QCoreApplication, Qt
from qt_api import QApplication

from tests.qt_test_app import ensure_app_state as ensure_qt_app_state, get_or_create_app

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)


class DummySettings:
    def __init__(self):
        self.values = {
            "default-profile": "HD 720p 30 fps",
            "default-samplerate": 48000,
            "default-channels": 2,
        }

    def get(self, key):
        return self.values.get(key)


class DummyApp(QApplication):
    def __init__(self):
        super().__init__([])
        self.settings = DummySettings()

    def get_settings(self):
        return self.settings

    def _tr(self, text):
        return text


def ensure_app_state(app):
    return ensure_qt_app_state(app, DummySettings)


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class AddToTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app, cls._owns_app = get_or_create_app(DummyApp)
        cls.app = ensure_app_state(app)
        import windows.add_to_timeline as add_to_timeline_module
        cls.add_to_timeline_module = add_to_timeline_module

    def test_select_added_items_uses_timeline_selection_api_and_clears_file_selection(self):
        add_selection_js = Recorder()
        set_focus = Recorder()
        update = Recorder()
        mark_dirty = Recorder()
        file_clear = Recorder()
        list_clear = Recorder()

        win = types.SimpleNamespace(
            timeline=types.SimpleNamespace(
                AddSelectionJS=add_selection_js,
                setFocus=set_focus,
                update=update,
                geometry=types.SimpleNamespace(mark_dirty=mark_dirty),
            ),
            files_model=types.SimpleNamespace(
                selection_model=types.SimpleNamespace(clearSelection=file_clear),
                list_selection_model=types.SimpleNamespace(clearSelection=list_clear),
            ),
            addSelection=Recorder(),
        )

        self.add_to_timeline_module.AddToTimeline._select_added_items(
            object(),
            win,
            ["C1", "C2", "C3"],
        )

        self.assertEqual(
            add_selection_js.calls,
            [
                (("C1", "clip", True), {}),
                (("C2", "clip", False), {}),
                (("C3", "clip", False), {}),
            ],
        )
        self.assertEqual(file_clear.calls, [((), {})])
        self.assertEqual(list_clear.calls, [((), {})])
        self.assertEqual(set_focus.calls, [((), {})])
        self.assertEqual(mark_dirty.calls, [((), {})])
        self.assertEqual(update.calls, [((), {})])


if __name__ == "__main__":
    unittest.main()
