""" 
 @file
 @brief This file contains the clip properties model, used by the properties view
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

import os, types
from urllib.parse import urlparse
from collections import OrderedDict
from classes import updates
from classes import info
from classes.query import File, Clip
from classes.logger import log
from classes.settings import SettingStore
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QTreeWidget, QApplication, QMessageBox, QTreeWidgetItem, QAbstractItemView
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
    import json
except ImportError:
    import simplejson as json

class ClipStandardItemModel(QStandardItemModel):
	
	def __init__(self, parent=None):
		QStandardItemModel.__init__(self)
		
	def mimeData(self, indexes):
		
		# Create MimeData for drag operation
		data = QMimeData()

		# Get list of all selected file ids
		property_names = []
		for item in indexes:
			selected_row = self.itemFromIndex(item).row()
			property_names.append(self.item(selected_row, 0).data())
		data.setText(json.dumps(property_names))

		# Return Mimedata
		return data


class PropertiesModel(updates.UpdateInterface):
	
	# This method is invoked by the UpdateManager each time a change happens (i.e UpdateInterface)
	def changed(self, action):
		
		# Handle change
		if action.key and action.key[0] == "clips":
			log.info(action.values)
			# Update the model data
			self.update_model(get_app().window.txtPropertyFilter.text())

	
	# Update the selected item (which drives what properties show up)
	def update_item(self, item_id, item_type):
		# Clear previous selection
		self.selected = []
		
		if item_type == "clip":
			c = None
			clips = get_app().window.timeline_sync.timeline.Clips()
			for clip in clips:
				if clip.Id() == item_id:
					c = clip
					break
				
			self.selected.append(c)
		
		# Update the model data
		self.update_model(get_app().window.txtPropertyFilter.text())
		
	# Update the values of the selected clip, based on the current frame
	def update_frame(self, frame_number):
		
		# Check for a selected clip
		if self.selected:
			clip = self.selected[0]
			
			# Get FPS from project
			fps = get_app().project.get(["fps"])
			fps_float = float(fps["num"]) / float(fps["den"])

			# Requested time
			requested_time = float(frame_number - 1) / fps_float

			# Determine the frame needed for this clip (based on the position on the timeline)		
			time_diff = (requested_time - clip.Position()) + clip.Start();
			self.frame_number = round(time_diff * fps_float) + 1;
			
			# Calculate biggest and smallest possible frames
			min_frame_number = round((clip.Start() * fps_float)) + 1
			max_frame_number = round((clip.End() * fps_float)) + 1

			# Adjust frame number if out of range
			if self.frame_number < min_frame_number:
				self.frame_number = min_frame_number
			if self.frame_number > max_frame_number:
				self.frame_number = max_frame_number
			
			log.info("Update frame to %s" % self.frame_number)
	
			# Update the model data
			self.update_model(get_app().window.txtPropertyFilter.text())
			
	
	def value_updated(self, item, interpolation=-1):
		""" Table cell change event - also handles context menu to update interpolation value """
		
		# Determine what was changed
		property = self.model.item(item.row(), 0).data()
		property_name = property[1]["name"]
		closest_point_x = property[1]["closest_point_x"]
		property_key = property[0]
		clip_id = item.data()
		
		# Get value (if any)
		if item.text():
			new_value = float(item.text())
		else:
			new_value = None

		log.info("%s for %s changed to %s at frame %s with interpolation: %s at closest x: %s" % (property_key, clip_id, new_value, self.frame_number, interpolation, closest_point_x))
		
		# Find this clip
		c = Clip.get(id=clip_id)
		if c:
			# Update clip attribute
			if property_key in c.data:
				# Check the type of property (some are keyframe, and some are not)
				if type(c.data[property_key]) == dict:
					# Keyframe
					# Loop through points, find a matching points on this frame
					found_point = False
					point_to_delete = None
					for point in c.data[property_key]["Points"]:
						log.info("looping points: co.X = %s" % point["co"]["X"] )
						if interpolation == -1 and point["co"]["X"] == self.frame_number:
							# Found point, Update value
							found_point = True
							# Update or delete point
							if new_value != None:
								point["co"]["Y"] = float(new_value)
							else:
								point_to_delete = point
							break
							
						elif interpolation > -1 and point["co"]["X"] == closest_point_x:
							# Only update interpolation type
							found_point = True
							point["interpolation"] = interpolation
							break
					
					# Delete point (if needed)
					if point_to_delete:
						c.data[property_key]["Points"].remove(point_to_delete)
					
					# Create new point (if needed)
					if not found_point and point_to_delete == None:
						c.data[property_key]["Points"].append({'co': {'X': self.frame_number, 'Y': new_value}, 'interpolation': 1})
				
				elif type(c.data[property_key]) == int:
					# Integer
					c.data[property_key] = int(new_value)
				
				elif type(c.data[property_key]) == float:
					# Float
					c.data[property_key] = float(new_value)
				
				elif type(c.data[property_key]) == string:
					# String
					c.data[property_key] = str(new_value)
								
			# Save changes
			c.save()
			
			# Force refresh of properties
			self.update_model(get_app().window.txtPropertyFilter.text())
		
	
	def update_model(self, filter=""):
		log.info("updating clip properties model.")
		app = get_app()
		
		# Check for a selected clip
		if self.selected:
			c = self.selected[0]

			# Get raw unordered JSON properties
			raw_properties = json.loads(c.PropertiesJSON(self.frame_number))

			# Check if the properties changed for this clip?
			hash = "%s-%s" % (filter, raw_properties["hash"]["memo"])
			if hash != self.previous_hash:
				self.previous_hash = hash
			else:
				# Properties don't need to be updated (they haven't changed)
				return
			
			# Clear previous model data (if any)
			self.model.clear()
	
			# Add Headers
			self.model.setHorizontalHeaderLabels(["Property", "Value" ])

			# Sort the list of properties 
			all_properties = OrderedDict(sorted(raw_properties.items(), key=lambda x: x[1]['name']))
	
			# Loop through properties, and build a model	
			for property in all_properties.items():
				label = property[1]["name"]
				name = property[0]
				value = property[1]["value"]
				type = property[1]["type"]
				memo = property[1]["memo"]
				readonly = property[1]["readonly"]
				keyframe = property[1]["keyframe"]
				points = property[1]["points"]
				interpolation = property[1]["interpolation"]
				closest_point_x = property[1]["closest_point_x"]
				
				# Hide filtered out properties
				if filter and filter.lower() not in name.lower():
					continue
				
				row = []
				
				# Append Property Name
				col = QStandardItem("Property")
				col.setText(label)
				col.setData(property)
				if keyframe and points > 1:
					col.setBackground(QColor("green")) # Highlight keyframe background
				elif points > 1:
					col.setBackground(QColor(42, 130, 218)) # Highlight interpolated value background
				col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
				row.append(col)
				
				# Append Value
				col = QStandardItem("Value")
				col.setText("%0.2f" % value)
				col.setData(c.Id())
				if points > 1:
					# Apply icon to cell
					my_icon = QPixmap(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % interpolation))
					col.setData(my_icon, Qt.DecorationRole)
					
					log.info(os.path.join(info.IMAGES_PATH, "keyframe-%s.png" % interpolation))

					# Set the background color of the cell
					if keyframe:
						col.setBackground(QColor("green")) # Highlight keyframe background
					else:
						col.setBackground(QColor(42, 130, 218)) # Highlight interpolated value background

				col.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
				row.append(col)
	
				# Append ROW to MODEL (if does not already exist in model)
				self.model.appendRow(row)
				
		else:
			# Clear previous properties hash
			self.previous_hash = ""
			
			# Clear previous model data (if any)
			self.model.clear()
	
			# Add Headers
			self.model.setHorizontalHeaderLabels(["Property", "Value" ])



	def __init__(self, *args):
		
		# Keep track of the selected items (clips, transitions, etc...)
		self.selected = []
		self.frame_number = 1
		self.previous_hash = ""

		# Create standard model 
		self.model = ClipStandardItemModel()
		self.model.setColumnCount(2)

		# Connect data changed signal
		self.model.itemChanged.connect(self.value_updated)
		
		#Add self as listener to project data updates (used to update the timeline)
		get_app().updates.add_listener(self)
		