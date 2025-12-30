"""
 @file
 @brief This file contains unit tests for the Query class
 @author Jonathan Thomas <jonathan@openshot.org>

 @section LICENSE

 Copyright (c) 2008-2018 OpenShot Studios, LLC
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

import sys
import os
import json

import unittest

import openshot

from PyQt5.QtGui import QGuiApplication
try:
    # QtWebEngineWidgets must be loaded prior to creating a QApplication
    # But on systems with only WebKit, this will fail (and we ignore the failure)
    from PyQt5.QtWebEngineWidgets import QWebEngineView  # noqa
except ImportError:
    pass

# Import parent folder (so it can find other imports)
PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if PATH not in sys.path:
    sys.path.append(PATH)

from classes.app import OpenShotApp
from classes.query import Clip, File, Transition
from classes import info

info.LOG_LEVEL_CONSOLE = "ERROR"


def ensure_open_shot_app():
    """Ensure an OpenShot QApplication exists before tests run."""

    instance = QGuiApplication.instance()
    if instance:
        return instance, False

    return OpenShotApp(sys.argv, mode="unittest"), True


class QueryTests(unittest.TestCase):
    """ Unit test class for Query class """

    @classmethod
    def setUpClass(cls):
        """ Init unit test data """
        # Create or reuse Qt application
        cls.app, cls._owns_app = ensure_open_shot_app()
        cls.clip_ids = []
        cls.file_ids = []
        cls.transition_ids = []

        clips = []

        # Insert some clips into the project data
        for num in range(5):
            # Create clip
            c = openshot.Clip(os.path.join(info.IMAGES_PATH, "AboutLogo.png"))
            c.Position(num * 10.0)
            c.End(5.0)

            # Parse JSON
            clip_data = json.loads(c.Json())

            # Insert into project data
            query_clip = Clip()
            query_clip.data = clip_data
            query_clip.save()

            # Keep track of the ids
            cls.clip_ids.append(query_clip.id)
            clips.append(query_clip)

        # Insert some files into the project data
        for num in range(5):
            # Create file
            r = openshot.DummyReader(openshot.Fraction(24, 1), 640, 480, 44100, 2, 30.0)

            # Parse JSON
            file_data = json.loads(r.Json())

            # Insert into project data
            query_file = File()
            query_file.data = file_data
            query_file.data["path"] = os.path.join(info.IMAGES_PATH, "AboutLogo.png")
            query_file.data["media_type"] = "image"
            query_file.save()

            # Keep track of the ids
            cls.file_ids.append(query_file.id)

        # Insert some transitions into the project data
        for c in clips:
            # Create mask object
            t = openshot.Mask()
            # Place over the last second of current clip
            pos = c.data.get("position", 0.0)
            start = c.data.get("start", 0.0)
            end = c.data.get("end", 0.0)
            t.Position((pos - start + end) - 1.0)
            t.End(1.0)

            # Insert into project data
            transitions_data = json.loads(t.Json())
            query_transition = Transition()
            query_transition.data = transitions_data
            query_transition.save()

            # Keep track of the ids
            cls.transition_ids.append(query_transition.id)

        # Don't keep the full query objects around
        del clips

    @classmethod
    def tearDownClass(cls):
        """ Clean up after running all tests in the class. """
        if getattr(cls, "_owns_app", False) and cls.app:
            cls.app.quit()

    def test_add_clip(self):

        # Find number of clips in project
        num_clips = len(Clip.filter())

        # Create clip
        c = openshot.Clip(os.path.join(info.IMAGES_PATH, "AboutLogo.png"))
        clip_data = json.loads(c.Json())

        # Insert into project data
        query_clip = Clip()
        query_clip.data = clip_data
        query_clip.save()

        self.assertTrue(query_clip)
        self.assertEqual(len(Clip.filter()), num_clips + 1)

        # Save the clip again (which should not change the total # of clips)
        query_clip.save()
        self.assertEqual(len(Clip.filter()), num_clips + 1)

    def test_update_clip(self):
        """ Test the Clip.save method """

        update_id = self.clip_ids[0]
        clip = Clip.get(id=update_id)
        self.assertTrue(clip)

        # Update clip
        clip.data["layer"] = 2
        clip.data["title"] = "My Title"
        clip.save()

        # Verify updated data
        clip = Clip.get(id=update_id)
        self.assertEqual(clip.data["layer"], 2)
        self.assertEqual(clip.data["title"], "My Title")

        clips = Clip.filter(layer=2)
        self.assertEqual(len(clips), 1)

    def test_delete_clip(self):
        """ Test the Clip.delete method """

        delete_id = self.clip_ids[4]
        clip = Clip.get(id=delete_id)
        self.assertTrue(clip)

        clip.delete()

        # Verify deleted data
        deleted_clip = Clip.get(id=delete_id)
        self.assertFalse(deleted_clip)

        # Delete clip again (should do nothing)
        clip.delete()
        deleted_clip = Clip.get(id=delete_id)
        self.assertFalse(deleted_clip)

    def test_filter_clip(self):
        """ Test the Clip.filter method """

        clips = Clip.filter(id=self.clip_ids[0])
        self.assertTrue(clips)

        # Do not find a clip
        clips = Clip.filter(id="invalidID")
        self.assertEqual(len(clips), 0)

    def test_get_clip(self):
        """ Test the Clip.get method """

        clip = Clip.get(id=self.clip_ids[1])
        self.assertTrue(clip)

        # Do not find a clip
        clip = Clip.get(id="invalidID")
        self.assertEqual(clip, None)

    def test_intersect(self):
        """ Test special filter argument 'intersect' """

        trans = Transition.get(id=self.transition_ids[0])
        self.assertTrue(trans)

        pos = trans.data.get("position", -1.0)
        duration = trans.data.get("duration", -1.0)
        self.assertTrue(pos >= 0.0)
        self.assertTrue(duration >= 0.0)

        time = pos + (duration / 2)

        def get_times(item):
            pos = item.data.get("position", -1.0)
            end = pos + item.data.get("duration", -1.0)
            return (pos, end)

        t_intersect = Transition.filter(intersect=time)
        t_ids = [t.id for t in t_intersect]
        t_all = Transition.filter()
        t_rest = [x for x in t_all if x.id not in t_ids]

        c_intersect = Clip.filter(intersect=time)
        c_ids = [c.id for c in c_intersect]
        c_all = Clip.filter()
        c_rest = [x for x in c_all if x.id not in c_ids]

        for item in t_intersect + c_intersect:
            item_id = item.id
            pos, end = get_times(item)
            self.assertTrue(pos <= time)
            self.assertTrue(time <= end)
        for item in t_rest + c_rest:
            item_id = item.id
            pos, end = get_times(item)
            if pos < time:
                self.assertTrue(end <= time)
            if end > time:
                self.assertTrue(pos >= time)

    def test_update_File(self):
        """ Test the File.save method """

        update_id = self.file_ids[0]
        file = File.get(id=update_id)
        self.assertTrue(file)

        # Update File
        file.data["height"] = 1080
        file.data["width"] = 1920
        file.save()

        # Verify updated data
        file = File.get(id=update_id)
        self.assertEqual(file.data["height"], 1080)
        self.assertEqual(file.data["width"], 1920)

    def test_delete_File(self):
        """ Test the File.delete method """

        delete_id = self.file_ids[4]
        file = File.get(id=delete_id)
        self.assertTrue(file)

        file.delete()

        # Verify deleted data
        deleted_file = File.get(id=delete_id)
        self.assertFalse(deleted_file)

        # Delete File again (should do nothing)
        file.delete()
        deleted_file = File.get(id=delete_id)
        self.assertFalse(deleted_file)

    def test_filter_File(self):
        """ Test the File.filter method """

        files = File.filter(id=self.file_ids[0])
        self.assertTrue(files)

        # Do not find a File
        files = File.filter(id="invalidID")
        self.assertEqual(len(files), 0)

    def test_get_File(self):
        """ Test the File.get method """

        file = File.get(id=self.file_ids[1])
        self.assertTrue(file)

        # Do not find a File
        file = File.get(id="invalidID")
        self.assertEqual(file, None)

    def test_add_file(self):

        # Find number of files in project
        num_files = len(File.filter())

        # Create file
        r = openshot.DummyReader(openshot.Fraction(24, 1), 640, 480, 44100, 2, 30.0)
        file_data = json.loads(r.Json())

        # Insert into project data
        query_file = File()
        query_file.data = file_data
        query_file.data["path"] = os.path.join(info.IMAGES_PATH, "AboutLogo.png")
        query_file.data["media_type"] = "image"

        query_file.save()
        self.assertTrue(query_file)
        self.assertEqual(len(File.filter()), num_files + 1)

        # Save the file again (which should not change the total # of files)
        query_file.save()
        self.assertEqual(len(File.filter()), num_files + 1)
