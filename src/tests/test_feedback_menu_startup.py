"""Exercise generated Qt menus, undo/redo, and shutdown in a real OpenShot app."""

import os
from pathlib import Path
import shutil
import subprocess  # nosec B404 - Isolate the real Qt app in a test process.
import sys
import tempfile
import unittest


class FeedbackMenuStartupTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is needed to generate a tiny audio/video fixture")
    def test_clip_menus_and_undo_redo_preserve_edits_and_count_once(self):
        # A subprocess isolates real Qt, project data, and player threads from unit-test stubs.
        script = r'''

import importlib
import os
import tempfile
import traceback
from unittest.mock import patch
from classes import info, version

profile_dir = tempfile.TemporaryDirectory(prefix="openshot-notification-test-")
original = info.USER_PATH
profile = os.path.join(profile_dir.name, ".openshot_qt")
for key, value in list(vars(info).items()):
    if isinstance(value, str) and value.startswith(original):
        setattr(info, key, profile + value[len(original):])
info._path_defaults = {key: profile + value[len(original):]
                       for key, value in info._path_defaults.items()}
info.setup_userdirs()
info.FEEDBACK_PREVIEW = False
info.CMDLINE_LANGUAGE = "en_US"
info.UPDATE_PREVIEW = False
version.get_current_Version = lambda: None
from classes.app import OpenShotApp
from qt_api import QTimer, Qt, QT_API
binding = {"pyqt5": "PyQt5", "pyqt6": "PyQt6", "pyside6": "PySide6"}[QT_API]
QTest = importlib.import_module(binding + ".QtTest").QTest
app = OpenShotApp([], mode="unittest")
app.settings.set("tutorial_enabled", False)
app.settings.set("unique_install_id", "preview-only")
app.settings.set("send_metrics", False)
passed = False


import copy
import json
import sys
import openshot
from classes.query import Clip

def verify():
    global passed
    try:
        window = app.window
        controller = window.feedback_controller
        controller.timer.stop()
        media = openshot.Clip(os.environ['FEEDBACK_TEST_MEDIA'])
        media.Open()
        clip = Clip()
        clip.data = json.loads(media.Json())
        clip.data.update(start=0.0, end=2.0, duration=2.0, position=0.0,
                         layer=app.project.get('layers')[-1]['number'])
        clip.save()
        original = copy.deepcopy(clip.data)
        window.selected_items = [{'id': clip.id, 'type': 'clip'}]
        window.preview_thread.current_frame = 24
        app.clipboard().setText("feedback audit")
        app.processEvents()
        window.preview_thread.current_frame = 24
        with patch('windows.views.timeline.StyledContextMenu.show_at', lambda menu, pos: menu):
            menu = window.timeline.ShowClipMenu(clip.id)
        targets=[]
        def collect(menu, path=()):
            for action in menu.actions():
                current=path+(action.text().replace('&',''),)
                if action.menu(): collect(action.menu(), current)
                elif path and (path[0] in ('Fade','Motion','Look','Slice') or path[:2] == ('Audio','Volume')) and not action.isSeparator() and current[-1] not in ('Adjust Colors','Analyze Colors'):
                    targets.append((current,action))
        collect(menu)
        assert len(targets) >= 20, 'Expected the full clip menu'
        assert any(path[-1] == 'Super 8' for path, _ in targets)
        for path,action in targets:
            for other in Clip.filter():
                if other.id != clip.id: other.delete()
            current=Clip.get(id=clip.id);current.data=copy.deepcopy(original);current.save()
            app.settings.set('feedback-action-count',0)
            app.settings.set('feedback-action-categories',[])
            with patch.object(sys,'excepthook') as errors:
                action.trigger()
            assert not errors.called,(path, errors.call_args)
            assert app.settings.get('feedback-action-count') <= 1, (path,'double counted')
            count = app.settings.get('feedback-action-count')
            if count:
                result = copy.deepcopy(Clip.get(id=clip.id).data)
                app.updates.undo()
                assert app.settings.get('feedback-action-count') == count, (path,'undo counted')
                app.updates.redo()
                assert app.settings.get('feedback-action-count') == count, (path,'redo counted')
                assert Clip.get(id=clip.id).data == result, (path,'redo changed edit')
        print('Verified menu actions:', len(targets), flush=True)
        passed=True
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()
assert app.gui()
QTimer.singleShot(4000,verify)
app.exec_()
assert passed
'''
        with tempfile.TemporaryDirectory(prefix="openshot-feedback-menu-") as folder:
            media = str(Path(folder) / "clip.mp4")
            # Fixed fixture arguments, a temporary output path, and no shell.
            subprocess.run([  # nosec B603
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=24",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-t", "2", "-c:v", "mpeg4", "-c:a", "aac", "-y", media,
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]),
                       QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                       FEEDBACK_TEST_MEDIA=media)
            # Execute only the literal test script above, using this Python interpreter.
            result = subprocess.run([sys.executable, "-c", script], env=env,  # nosec B603
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout[-16000:])
        # Qt callbacks can report exceptions without a nonzero process exit.
        self.assertNotIn("Traceback (most recent call last)", result.stdout, result.stdout[-16000:])
