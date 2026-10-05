# @file
# @brief Test timeline editing latency and undo behavior
# @author OpenShot Studios, LLC
#
# @section LICENSE
#
# Copyright (c) 2008-2026 OpenShot Studios, LLC
# (http://www.openshotstudios.com). This file is part of
# OpenShot Video Editor (http://www.openshot.org), an open-source project
# dedicated to delivering high quality video editing and animation solutions
# to the world.
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
#

"""Editing hot-path regressions with real project/history mutations."""
import copy
import json
import tempfile
import types
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from classes.project_data import ProjectDataStore
from classes.query import Clip, QueryObject
from classes.updates import UpdateAction, UpdateManager


class EditingFixture:
    """Headless dispatch fixture: no decoding, rendering or cache policy emulation."""
    def __init__(self, count=8, samples=100):
        global MenuSlice, TimelineView
        from qt_api import QApplication
        from tests.qt_test_app import get_or_create_app, ensure_app_state
        self.qt_app, _ = get_or_create_app(lambda: QApplication([]))
        from tests.test_project_data import DummySettings
        ensure_app_state(self.qt_app, DummySettings)
        from windows.views.timeline import MenuSlice, TimelineView
        self.project = ProjectDataStore.__new__(ProjectDataStore)
        from classes.json_data import JsonDataStore
        JsonDataStore.__init__(self.project)
        self.project._data = {
            "clips": [{"id": "C%d" % i, "layer": 1, "position": 0.,
                       "start": 0., "end": 10., "duration": 10.,
                       "reader": {"duration": 100., "has_single_image": False},
                       "effects": [{"id": "E%d" % i, "name": "test"}],
                       "ui": {"audio_data": [0.125] * samples}}
                      for i in range(count)],
            "fps": {"num": 30000, "den": 1001}, "layers": [],
            "effects": [], "history": {},
        }
        self.project.has_unsaved_changes = False
        self.updates = UpdateManager()
        self.updates.add_listener(self.project)
        self.window = MagicMock()
        self.refreshes = 0
        self.ignored = False
        self.signals = []
        def ignore(value, spinner):
            self.signals.append(value)
            self.ignored = value
            if not value:
                self.refreshes += 1
        self.window.IgnoreUpdates.emit.side_effect = ignore
        self.app = types.SimpleNamespace(project=self.project, updates=self.updates,
                                         window=self.window, processEvents=lambda: None)
        self.helper = types.SimpleNamespace(
            window=self.window, show_wait_spinner=True,
            get_uuid=lambda: "split", _apply_effect_colors=lambda data: None,
            _assign_new_effect_ids=lambda data: None, redraw_audio_timer=MagicMock(),
        )
        self.helper.delete_invalid_timeline_item = lambda clip: TimelineView.delete_invalid_timeline_item(self.helper, clip)
        self.helper.update_clip_data = lambda *a, **kw: TimelineView.update_clip_data(self.helper, *a, **kw)
        self.helper._transition_uses_static_mask = lambda *args: False
        self.helper._transition_reader_changed = lambda *args: False
        self.helper.update_transition_data = lambda *a, **kw: TimelineView.update_transition_data(self.helper, *a, **kw)
        self.stack = ExitStack()
        for module in ("classes.project_data", "classes.query", "classes.updates",
                       "classes.clip_utils", "windows.views.timeline"):
            self.stack.enter_context(patch(module + ".get_app", return_value=self.app))
        QueryObject._cache_version = None
        QueryObject._cache = {}

    def close(self):
        self.stack.close()
        QueryObject._cache_version = None
        QueryObject._cache = {}

    def split(self, ids=None):
        TimelineView.Slice_Triggered(self.helper, MenuSlice.KEEP_BOTH,
                                     ids or ["C0"], [], 5.)

    def trim(self):
        clip = Clip.get(id="C0")
        clip.data["end"] = 8.
        self.helper.update_clip_data(clip.data, only_basic_props=True, ignore_reader=True)


class EditingLatencyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = EditingFixture()
        self.addCleanup(self.fixture.close)

    def test_multiple_split_final_refresh_and_undo_redo_reopened_history(self):
        f = self.fixture
        before = copy.deepcopy(f.project._data)
        f.split(["C0", "C1", "C2"])
        after = copy.deepcopy(f.project._data)
        self.assertEqual(f.refreshes, 1)
        self.assertFalse(f.ignored)
        self.assertIsNone(f.updates.transaction_id)
        self.assertEqual(len(after["clips"]), 11)
        for clip in after["clips"]:
            if clip["id"] in ("C0", "C1", "C2"):
                self.assertAlmostEqual(clip["end"], round(5 * 30000 / 1001) * 1001 / 30000)
        f.updates.save_history(f.project, 100)
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/edit.osp"
            f.project.write_to_file(path, f.project._data)
            f.project._data = f.project.read_from_file(path)
        f.updates.load_history(f.project._data)
        f.updates.undo()
        self.assertEqual(f.project.get("clips"), before["clips"])
        f.updates.redo()
        self.assertEqual(f.project.get("clips"), after["clips"])

    def test_mixed_clip_transition_split_stays_batched(self):
        f = self.fixture
        f.project._data["effects"] = [{"id": "T1", "layer": 1,
                                         "position": 0., "start": 0., "end": 10.}]
        TimelineView.Slice_Triggered(f.helper, MenuSlice.KEEP_BOTH,
                                     ["C0"], ["T1"], 5.)
        self.assertEqual(f.refreshes, 1)
        self.assertEqual(f.signals, [True, True, True, False])
        self.assertEqual(len(f.project.get("effects")), 2)
        f.updates.undo()
        self.assertEqual(len(f.project.get("effects")), 1)
        self.assertEqual(f.project.get("effects")[0]["end"], 10.)

    def test_split_failure_resumes_updates(self):
        f = self.fixture
        f.helper.update_clip_data = MagicMock(side_effect=RuntimeError("commit failed"))
        with self.assertRaises(RuntimeError):
            f.split()
        self.assertFalse(f.ignored)
        self.assertIsNone(f.updates.transaction_id)
        self.assertEqual(f.refreshes, 1)

    def test_insert_history_is_bounded_and_delete_is_reversible(self):
        f = self.fixture
        f.updates.insert(["clips"], {"id": "new", "start": 0., "end": 1.})
        self.assertEqual(f.updates.last_action.old_values, {})
        f.updates.delete(["clips", {"id": "new"}])
        f.updates.undo()
        self.assertEqual(f.project.get(["clips", {"id": "new"}])["end"], 1.)
        f.updates.undo()
        self.assertIsNone(f.project.get(["clips", {"id": "new"}]))
        f.updates.redo()
        f.updates.redo()
        self.assertIsNone(f.project.get(["clips", {"id": "new"}]))

    def test_insert_undo_finds_ids_after_siblings_reordered(self):
        f = self.fixture
        f.updates.transaction_id = "inserts"
        for item_id in ("A", "B", "D"):
            f.updates.insert(["clips"], {"id": item_id, "end": 1.})
        f.updates.transaction_id = None
        f.project._data["clips"].reverse()
        survivors = copy.deepcopy([clip for clip in f.project.get("clips")
                                   if clip["id"] not in ("A", "B", "D")])
        f.updates.undo()
        self.assertEqual(f.project.get("clips"), survivors)
        f.updates.redo()
        self.assertEqual([clip["id"] for clip in f.project.get("clips")[-3:]],
                         ["A", "B", "D"])
        f.updates.undo()
        self.assertEqual(f.project.get("clips"), survivors)

    def test_trim_final_value_preserves_waveform_and_undo(self):
        f = self.fixture
        before = copy.deepcopy(f.project.get("clips"))
        f.trim()
        self.assertEqual(f.project.get(["clips", {"id": "C0"}])["end"], 8.)
        self.assertEqual(f.project.get(["clips", {"id": "C0"}])["ui"], before[0]["ui"])
        f.updates.undo()
        self.assertEqual(f.project.get("clips"), before)
        f.updates.redo()
        self.assertEqual(f.project.get(["clips", {"id": "C0"}])["end"], 8.)

    def test_action_json_keeps_history_out_without_mutating_snapshots(self):
        values = {"history": {"undo": ["large"]}, "nested": {"points": [(1, 2)]}}
        old = copy.deepcopy(values)
        action = UpdateAction("update", ["clips"], values, old, "tx")
        expected = {"type": "update", "key": ["clips"],
                    "value": {"nested": {"points": [[1, 2]]}},
                    "old_values": {"nested": {"points": [[1, 2]]}}, "transaction": "tx"}
        self.assertEqual(json.loads(action.json()), expected)
        self.assertEqual(json.loads(action.json(is_array=True)), [expected])
        self.assertEqual(json.loads(action.json(only_value=True)), json.loads(json.dumps(values)))
        self.assertIn("history", values)
        self.assertEqual(values, old)
