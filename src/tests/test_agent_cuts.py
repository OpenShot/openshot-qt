"""
 @file
 @brief Query split retains curves, isolates effect IDs, and shares undo history.

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
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from classes.agent.cuts import split_clip
from classes.agent.protocol import CommandError


class AgentCutsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        isolate_preferences(self)
        from classes.agent.service import EditingService
        from qt_api import QImage, QColor
        from classes.agent.render import image_format
        self.app.window = None
        self.app.project.new()
        self.app.updates.reset()
        self.service = EditingService(self.app, 'test-cuts', 'headless')
        self.temp = tempfile.TemporaryDirectory()
        image = QImage(64, 36, image_format())
        image.fill(QColor('red'))
        path = str(Path(self.temp.name) / 'red.png')
        image.save(path)
        file = self.service.execute('file.import', {'path': path})['data']
        self.layer = self.app.project.get('layers')[0]['number']
        self.clip = self.service.execute('clip.add', {'file_id': file['id'], 'layer': self.layer, 'position': 3, 'start': 2, 'end': 8})['data']

    def tearDown(self):
        self.temp.cleanup()

    def split(self, at):
        old = self.app.updates.transaction_id
        self.app.updates.transaction_id = 'test-split-transaction'
        try:
            return split_clip(self.service, {'id': self.clip['id'], 'at': at})
        finally:
            self.app.updates.transaction_id = old

    def test_split_retains_curves_and_groups_undo(self):
        self.service.execute('effect.add', {'clip_id': self.clip['id'], 'type': 'Saturation'})
        self.service.execute('clip.keyframe.set', {'id': self.clip['id'], 'property': 'volume', 'frame': 150, 'value': 0.2})
        before = copy.deepcopy(self.service.obj('clip', self.clip['id']).data)
        result = self.split(5.011)
        self.assertEqual(result['at'], 5)
        self.assertEqual(result['requested_at'], 5.011)
        left = self.service.obj('clip', result['left']['id']).data
        right = self.service.obj('clip', result['right']['id']).data
        self.assertEqual(left['id'], before['id'])
        self.assertEqual((left['start'], left['end'], right['start'], right['end'], right['position']), (2, 4, 4, 8, 5))
        self.assertEqual(left['volume'], before['volume'])
        self.assertEqual(right['volume'], before['volume'])
        self.assertNotEqual(left['effects'][0]['id'], right['effects'][0]['id'])
        self.service.execute('history.undo', {})
        self.assertEqual(self.service.obj('clip', before['id']).data, before)
        self.assertEqual(len(self.app.project.get('clips')), 1)
        self.service.execute('history.redo', {})
        self.assertEqual(len(self.app.project.get('clips')), 2)

    def test_boundary_locked_and_second_validation_fail_without_changes(self):
        before = copy.deepcopy(self.app.project._data)
        for at in (3, 9, 2.999, float('nan')):
            with self.assertRaises(CommandError):
                self.split(at)
        native = self.service.native
        calls = []
        def fail_second(kind, data):
            calls.append(kind)
            if len(calls) == 2:
                raise CommandError('validation_error', 'second half invalid')
            return native(kind, data)
        with patch.object(self.service, 'native', side_effect=fail_second):
            with self.assertRaises(CommandError):
                self.split(5)
        self.assertEqual(self.app.project._data, before)
        self.app.project._data['layers'][0]['lock'] = True
        with self.assertRaises(CommandError) as error:
            self.split(5)
        self.assertEqual(error.exception.code, 'locked_track')
