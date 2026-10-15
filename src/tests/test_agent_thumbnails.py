"""
 @file
 @brief Reader reuse/cache validation for private Qt timeline snapshots.

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
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class SnapshotThumbnailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_query import ensure_open_shot_app
        cls.app, _ = ensure_open_shot_app()

    def setUp(self):
        from tests.agent_test_support import isolate_preferences
        isolate_preferences(self)
        from classes.agent.service import EditingService
        from qt_api import QImage, QColor
        from windows.views.timeline_backend.qwidget.snapshot import _THUMBNAILS
        _THUMBNAILS.clear()
        self.app.window = None
        self.app.project.new()
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/'image.png')
        image = QImage(80, 40, QImage.Format_ARGB32)
        image.fill(QColor('red'))
        image.save(self.path)
        self.file = EditingService(self.app, 'thumb-test', 'headless').execute('file.import', {'path': self.path})['data']

    def tearDown(self):
        self.temp.cleanup()

    def provider(self):
        from windows.views.timeline_backend.qwidget.snapshot import SnapshotThumbnails
        widget = SimpleNamespace(clip_painter=SimpleNamespace(thumb_cache={}, clear_render_cache=lambda: None))
        return SnapshotThumbnails(widget)

    def test_repeated_source_frame_pixels_equal_original_and_cached(self):
        from classes.thumbnail import GenerateThumbnail
        from qt_api import QImage
        provider = self.provider()
        provider.request_thumbnail('clip-a', self.file['id'], 1, 0)
        provider.request_thumbnail('clip-b', self.file['id'], 1, 0)
        provider.resolve(self.temp.name, 64)
        self.assertEqual(provider.metrics['reader_opens'], 1)
        self.assertEqual(provider.metrics['generated'], 1)
        self.assertEqual(provider.metrics['cache_hits'], 1)
        old = str(Path(self.temp.name)/'original.png')
        GenerateThumbnail(self.path, old, 1, 320, 180, '', '')
        self.assertEqual(provider.widget.clip_painter.thumb_cache[('clip-a', 1)].toImage().convertToFormat(QImage.Format_ARGB32), QImage(old).convertToFormat(QImage.Format_ARGB32))
        warmed = self.provider()
        warmed.request_thumbnail('clip-a', self.file['id'], 1, 0)
        warmed.resolve(self.temp.name, 64)
        self.assertEqual(warmed.metrics['reader_opens'], 0)
        self.assertEqual(warmed.metrics['generated'], 0)
        self.assertEqual(warmed.metrics['cache_hits'], 1)

    def test_source_change_invalidates_and_cache_is_bounded(self):
        from qt_api import QImage, QColor
        from windows.views.timeline_backend.qwidget.snapshot import _THUMBNAILS
        provider = self.provider()
        provider.request_thumbnail('clip-a', self.file['id'], 1, 0)
        provider.resolve(self.temp.name, 64)
        before = provider.widget.clip_painter.thumb_cache[('clip-a', 1)].toImage()
        image = QImage(83, 41, QImage.Format_ARGB32)
        image.fill(QColor('blue'))
        image.save(self.path)
        changed = self.provider()
        changed.request_thumbnail('clip-a', self.file['id'], 1, 0)
        with patch('windows.views.timeline_backend.qwidget.snapshot._MAX_THUMBNAIL_BYTES', 1):
            changed.resolve(self.temp.name, 64)
        self.assertEqual(changed.metrics['generated'], 1)
        self.assertNotEqual(before, changed.widget.clip_painter.thumb_cache[('clip-a', 1)].toImage())
        self.assertEqual(len(_THUMBNAILS), 0)

    def test_inspection_png_compression_and_byte_metadata(self):
        import openshot
        from qt_api import QImage
        from classes.agent.service import EditingService
        service = EditingService(self.app, 'png-test', 'headless')
        output = str(Path(self.temp.name)/'compressed.png')
        result = service.execute('file.thumbnail', {'id': self.file['id'], 'frame': 1,
                                                   'width': 160, 'height': 90, 'output': output})['data']
        original = str(Path(self.temp.name)/'original-quality.png')
        reader = openshot.Clip.CreateReader(self.path, False)
        reader.Open()
        try:
            reader.GetFrame(1).Thumbnail(original, 160, 90, '', '', '#000000', False, 'png', 90, 0.0, openshot.SCALE_FIT)
        finally:
            reader.Close()
        self.assertEqual(QImage(output), QImage(original))
        self.assertEqual(result['image_bytes'], Path(output).stat().st_size)
        self.assertLess(result['image_bytes'], Path(original).stat().st_size)
        strip = str(Path(self.temp.name)/'strip.png')
        result = service.execute('file.strip', {'id': self.file['id'], 'start': 0, 'end': 1,
                                               'count': 2, 'width': 160, 'height': 90, 'output': strip})['data']
        self.assertEqual(result['image_bytes'], Path(strip).stat().st_size)
