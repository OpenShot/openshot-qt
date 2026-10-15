"""
 @file
 @brief Timeline context preserves timing, bounds, and project state.

 @section LICENSE

 Copyright (c) 2008-2026 OpenShot Studios, LLC
 (http://www.openshotstudios.com). This file is part of
 OpenShot Video Editor (http://www.openshot.org), an open-source project
 dedicated to delivering high quality video editing and animation solutions
 to the world.

 OpenShot Video Editor is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 OpenShot Video Editor is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with OpenShot Library.  If not, see <http://www.gnu.org/licenses/>.
 """
import copy
import unittest

from classes.agent.context import overview
from classes.agent.protocol import CommandError


class TimelineContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        isolate_preferences(self)
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        data = self.app.project._data
        data['fps'] = {'num': 24, 'den': 1}
        data['layers'] = [{'number': 1000000, 'label': 'Video'}]
        data['clips'] = [self.clip('b', 5, 2, 6), self.clip('a', 0, 10, 16), self.clip('c', 12, 0, 2)]
        data['effects'] = []

    def clip(self, id, position, start, end):
        return {'id': id, 'layer': 1000000, 'position': position, 'start': start, 'end': end,
                'reader': {'fps': {'num': 30, 'den': 1}, 'has_audio': True, 'has_video': True},
                'volume': {'Points': [{'co': {'X': 1, 'Y': 0.5}}]}, 'effects': []}

    def test_viewport_coordinates_neighbors_and_read_only(self):
        original = copy.deepcopy(self.app.project._data)
        revision = self.app.updates.data_version
        result = overview(self.app, start=5, end=8, limit=1)
        row = result['items'][0]
        self.assertEqual(row['id'], 'a')
        self.assertEqual(row['visible']['frames'], [121, 145])
        self.assertEqual(row['source']['visible']['frames'], [451, 481])
        self.assertEqual(row['at_visible_start']['keyframe_frame'], 361)
        self.assertEqual(row['neighbors']['next'], {'id': 'b', 'gap_seconds': -1})
        self.assertEqual(result['pagination']['next_offset'], 1)
        second = overview(self.app, start=5, end=8, offset=1)['items'][0]
        self.assertEqual(second['id'], 'b')
        self.assertEqual(second['neighbors']['next']['gap_seconds'], 3)
        self.assertEqual(self.app.project._data, original)
        self.assertEqual(self.app.updates.data_version, revision)

    def test_remapped_source_is_not_falsely_inferred(self):
        self.app.project._data['clips'][0]['time'] = {'Points': [{'co': {'X': 1, 'Y': 10}}]}
        row = next(r for r in overview(self.app)['items'] if r['id'] == 'b')
        self.assertEqual(row['source']['mapping'], 'time_remapped')
        self.assertNotIn('visible', row['source'])

    def test_bounds_and_empty_project(self):
        for kwargs in ({'end': -1}, {'start': 2, 'end': 1}, {'limit': 501}, {'offset': -1}, {'layer': 999}):
            with self.assertRaises(CommandError):
                overview(self.app, **kwargs)
        self.app.project._data['clips'] = []
        self.assertEqual(overview(self.app)['items'], [])

    def test_stream_override_and_half_open_range(self):
        self.app.project._data['clips'][0]['has_video'] = 0
        rows = overview(self.app, start=6, end=9)['items']
        self.assertEqual([r['id'] for r in rows], ['b'])
        self.assertFalse(rows[0]['at_visible_start']['has_video'])
        self.assertTrue(rows[0]['at_visible_start']['has_audio'])

    def test_unsnapped_native_bounds_and_independent_trim_rounding(self):
        self.app.project._data['fps'] = {'num': 30, 'den': 1}
        clip = self.clip('unsnapped', .01, .02, 1.02)
        self.app.project._data['clips'] = [clip]
        row = overview(self.app)['items'][0]
        self.assertEqual(row['timeline']['frames'], [1, 31])
        self.assertEqual(row['timeline']['start'], .01)
        self.assertEqual(row['at_visible_start']['keyframe_frame'], 2)
        self.assertEqual(row['at_visible_start']['timeline_frame'], 1)
        row = overview(self.app, start=.02, end=.12)['items'][0]
        self.assertEqual(row['visible']['frames'], [2, 5])
        self.assertEqual(row['at_visible_start']['keyframe_frame'], 3)
        self.assertAlmostEqual(row['at_visible_start']['sample_seconds'], 1 / 30)

    def test_fractional_project_rate_distinct_source_coordinates(self):
        self.app.project._data['fps'] = {'num': 30000, 'den': 1001}
        self.app.project._data['clips'] = [self.clip('fractional', .01, .02, 2.02)]
        row = overview(self.app, start=1, end=1.5)['items'][0]
        self.assertEqual(row['timeline']['frames'], [1, 61])
        self.assertEqual(row['visible']['frames'], [31, 46])
        self.assertEqual(row['at_visible_start']['keyframe_frame'], 32)
        self.assertEqual(row['source']['visible']['start'], 1.01)
        self.assertEqual(row['source']['visible']['frames'], [32, 47])
        self.assertEqual(row['source']['fps'], 30)
