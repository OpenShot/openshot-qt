""" 
 @file
 @brief This file contains unit tests for the Query class
 @author Jonathan Thomas <jonathan@openshot.org>
 
 @section LICENSE
 
 Copyright (c) 2008-2014 OpenShot Studios, LLC
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

import sys, os
# Import parent folder (so it can find other imports)
PATH = os.path.dirname(os.path.dirname( os.path.realpath( __file__) ))
if not PATH in sys.path:
	sys.path.append(PATH)

import random
import unittest
import uuid
from classes.app import OpenShotApp
from classes import info
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
    import json
except ImportError:
    import simplejson as json
    

class TestQueryClass(unittest.TestCase):
	""" Unit test class for Query class """

	@classmethod
	def setUpClass(TestQueryClass):
		""" Init unit test data """
		# Create Qt application
		TestQueryClass.app = OpenShotApp(sys.argv)
		TestQueryClass.clip_ids = []
		TestQueryClass.file_ids = []
		TestQueryClass.transition_ids = []
		
		# Import additional classes that need the app defined first
		from classes.query import Clip, File, Transition

		# Insert some clips into the project data
		for num in range(5):
			# Create clip
			c = openshot.Clip(os.path.join(info.IMAGES_PATH, "AboutLogo.png" ))
			
			# Parse JSON
			clip_data = json.loads(c.Json())
			
			# Insert into project data
			query_clip = Clip()
			query_clip.data = clip_data
			query_clip.save()
			
			# Keep track of the ids
			TestQueryClass.clip_ids.append(query_clip.id)
			
		# Insert some files into the project data
		for num in range(5):
			# Create file
			r = openshot.DummyReader(openshot.Fraction(24,1), 640, 480, 44100, 2, 30.0)
			
			# Parse JSON
			file_data = json.loads(r.Json())
			
			# Insert into project data
			query_file = File()
			query_file.data = file_data
			query_file.data["path"] = os.path.join(info.IMAGES_PATH, "AboutLogo.png" )
			query_file.data["media_type"] = "image"
			query_file.save()
			
			# Keep track of the ids
			TestQueryClass.file_ids.append(query_file.id)
			
		# Insert some transitions into the project data
		for num in range(5):
			# Create dummy transition
			transitions_data = {
	             "id" : str(num), 
                 "layer" : num, 
                 "title" : "Transition",
                 "position" : 20.0 + num,
                 "duration" : 30 + num
	             }

			# Insert into project data
			query_transition = Transition()
			query_transition.data = transitions_data
			query_transition.save()
			
			# Keep track of the ids
			TestQueryClass.transition_ids.append(query_transition.id)
			
			
	def test_add_clip(self):
		""" Test the Clip.save method by adding multiple clips """
		
		# Import additional classes that need the app defined first
		from classes.query import Clip
		
		# Find number of clips in project
		num_clips = len(Clip.filter())
		
		# Create clip
		c = openshot.Clip(os.path.join(info.IMAGES_PATH, "AboutLogo.png" ))
		
		# Parse JSON
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
		
		# Import additional classes that need the app defined first
		from classes.query import Clip
		
		# Find a clip named file1
		update_id = TestQueryClass.clip_ids[0]
		clip = Clip.get(id=update_id)
		self.assertTrue(clip)
		
		# Update clip
		clip.data["layer"] = 2
		clip.data["title"] = "My Title"
		clip.save()
		
		# Verify updated data
		# Get clip again
		clip = Clip.get(id=update_id)
		self.assertEqual(clip.data["layer"], 2)
		self.assertEqual(clip.data["title"], "My Title")
			
	def test_delete_clip(self):
		""" Test the Clip.delete method """
		
		# Import additional classes that need the app defined first
		from classes.query import Clip
		
		# Find a clip named file1
		delete_id = TestQueryClass.clip_ids[4]
		clip = Clip.get(id=delete_id)
		self.assertTrue(clip)
		
		# Delete clip
		clip.delete()
		
		# Verify deleted data
		deleted_clip = Clip.get(id=delete_id)
		self.assertFalse(deleted_clip)
		
		# Delete clip again (should do nothing)
		clip.delete()
		
		# Verify deleted data
		deleted_clip = Clip.get(id=delete_id)
		self.assertFalse(deleted_clip)

	def test_filter_clip(self):
		""" Test the Clip.filter method """
		
		# Import additional classes that need the app defined first
		from classes.query import Clip
		
		# Find all clips named file1
		clips = Clip.filter(id=TestQueryClass.clip_ids[0])
		self.assertTrue(clips)
		
		# Do not find a clip
		clips = Clip.filter(id="invalidID")
		self.assertEqual(len(clips), 0)

	def test_get_clip(self):
		""" Test the Clip.get method """
		
		# Import additional classes that need the app defined first
		from classes.query import Clip
		
		# Find a clip named file1
		clip = Clip.get(id=TestQueryClass.clip_ids[1])
		self.assertTrue(clip)
		
		# Do not find a clip
		clip = Clip.get(id="invalidID")
		self.assertEqual(clip, None)
		
	def test_update_File(self):
		""" Test the File.save method """
		
		# Import additional classes that need the app defined first
		from classes.query import File
		
		# Find a File named file1
		update_id = TestQueryClass.file_ids[0]
		file = File.get(id=update_id)
		self.assertTrue(file)
		
		# Update File
		file.data["height"] = 1080
		file.data["width"] = 1920
		file.save()
		
		# Verify updated data
		# Get File again
		file = File.get(id=update_id)
		self.assertEqual(file.data["height"], 1080)
		self.assertEqual(file.data["width"], 1920)
			
	def test_delete_File(self):
		""" Test the File.delete method """
		
		# Import additional classes that need the app defined first
		from classes.query import File
		
		# Find a File named file1
		delete_id = TestQueryClass.file_ids[4]
		file = File.get(id=delete_id)
		self.assertTrue(file)
		
		# Delete File
		file.delete()
		
		# Verify deleted data
		deleted_file = File.get(id=delete_id)
		self.assertFalse(deleted_file)
		
		# Delete File again (should do nothing
		file.delete()

		# Verify deleted data
		deleted_file = File.get(id=delete_id)
		self.assertFalse(deleted_file)

	def test_filter_File(self):
		""" Test the File.filter method """
		
		# Import additional classes that need the app defined first
		from classes.query import File
		
		# Find all Files named file1
		files = File.filter(id=TestQueryClass.file_ids[0])
		self.assertTrue(files)
		
		# Do not find a File
		files = File.filter(id="invalidID")
		self.assertEqual(len(files), 0)

	def test_get_File(self):
		""" Test the File.get method """
		
		# Import additional classes that need the app defined first
		from classes.query import File
		
		# Find a File named file1
		file = File.get(id=TestQueryClass.file_ids[1])
		self.assertTrue(file)
		
		# Do not find a File
		file = File.get(id="invalidID")
		self.assertEqual(file, None)
		
	def test_add_file(self):
		""" Test the File.save method by adding multiple files """
		
		# Import additional classes that need the app defined first
		from classes.query import File
		
		# Find number of files in project
		num_files = len(File.filter())
		
		# Create file
		r = openshot.DummyReader(openshot.Fraction(24,1), 640, 480, 44100, 2, 30.0)
		
		# Parse JSON
		file_data = json.loads(r.Json())
		
		# Insert into project data
		query_file = File()
		query_file.data = file_data
		query_file.data["path"] = os.path.join(PATH, "images", "openshot.png")
		query_file.data["media_type"] = "image"
		query_file.save()
		
		self.assertTrue(query_file)
		self.assertEqual(len(File.filter()), num_files + 1)
		
		# Save the file again (which should not change the total # of files)
		query_file.save()
		
		self.assertEqual(len(File.filter()), num_files + 1)


if __name__ == '__main__':
	unittest.main()