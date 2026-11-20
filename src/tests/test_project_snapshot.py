# Copyright (c) 2026 OpenShot Studios, LLC
# This file is part of OpenShot Video Editor (https://www.openshot.org).
# SPDX-License-Identifier: GPL-3.0-or-later
#
# OpenShot Video Editor is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenShot Video Editor is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenShot Video Editor. If not, see <https://www.gnu.org/licenses/>.

"""Snapshot inputs must be detached and preserve all JSON fields."""

import json
import unittest

from classes.project_snapshot import ProjectSnapshot


class ProjectSnapshotTests(unittest.TestCase):
    def test_round_trip_unknown_fields_and_nested_containers(self):
        original = {"title": "日本語", "clips": [{"values": [1, None, True, {"x": "a,b]}"}]}],
                    "files": [], "unknown": {"nested": [{"path": "C:\\test\\x"}]}}
        snapshot = ProjectSnapshot.capture(original)
        self.assertEqual(snapshot.decode(), original)
        self.assertEqual(json.loads(b"".join(snapshot.chunks())), original)
        original["clips"][0]["values"].append("later edit")
        original["unknown"]["nested"][0]["path"] = "changed"
        self.assertNotEqual(snapshot.decode(), original)
        self.assertEqual(snapshot.decode()["unknown"]["nested"][0]["path"], "C:\\test\\x")

    def test_digest_covers_metadata_collection_names_and_contents(self):
        reference = ProjectSnapshot.capture({"clips": [{"x": 1}], "title": "one"})
        self.assertEqual(reference.digest(), ProjectSnapshot.capture(reference.decode()).digest())
        for other in ({"clips": [{"x": 2}], "title": "one"},
                      {"files": [{"x": 1}], "title": "one"},
                      {"clips": [{"x": 1}], "title": "two"}):
            self.assertNotEqual(reference.digest(), ProjectSnapshot.capture(other).digest())

    def test_empty_and_collection_only_projects_have_valid_json_chunks(self):
        for data in ({}, {"clips": []}, {"clips": [{"x": 1}], "files": []}):
            snapshot = ProjectSnapshot.capture(data)
            self.assertEqual(json.loads(b"".join(snapshot.chunks())), data)

    def test_non_json_value_fails_before_starting_a_worker(self):
        with self.assertRaises(TypeError):
            ProjectSnapshot.capture({"clips": [{"unexpected": object()}]})
