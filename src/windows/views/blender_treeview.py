""" 
 @file
 @brief This file contains the blender file treeview, used by the 3d animated titles screen
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

import os, time, uuid, shutil
import threading, subprocess, re
from urllib.parse import urlparse
from classes import updates
from classes import info
from classes.logger import log
from classes import settings
from classes.query import File
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo, QEvent
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from windows.models.blender_model import BlenderModel
import xml.dom.minidom as xml
import functools
import openshot # Python module for libopenshot (required video editing module installed separately)

try:
	import json
except ImportError:
	import simplejson as json
	
class QBlenderEvent(QEvent):
	""" A custom Blender QEvent """
	 
	def __init__(self, id, data=None, *args):
		# Invoke parent init
		QEvent.__init__(self, id)
		self.data = data
		self.id = id

class BlenderTreeView(QTreeView):
	""" A TreeView QWidget used on the animated title window """ 

	
	def eventFilter (self, object, event):
		""" Custom event handler """
		log.info(object)
		log.info(event.type())
		
		data = None
		try:
			data = event.data
		except:
			event.ignore()
			return False
		
		log.info('CUSTOM EVENT!')
		
		if event.id == "1":
			# Close window
			self.close()
			
		elif event.id == "2":
			# Render Finished
			self.render_finished()
			
		elif event.id == "3":
			# Error from blender (with version data)
			self.error_with_blender(event.data)
			
		elif event.id == "4":
			# Error from blender (with no data)
			self.error_with_blender()
			
		elif event.id == "5":
			# Update progress bar
			self.update_progress_bar(event.data['current_frame'], event.data['current_part'], event.data['max_parts'])
			
		elif event.id == "6":
			# Update image prevent
			self.update_image(event.data)
			
		elif event.id == "7":
			# Error from blender (with no version and custom message)
			self.error_with_blender(None, event.data)
			
		event.accept()
		return True


	def currentChanged(self, selected, deselected):
		# Get selected item
		self.selected = selected
		self.deselected = deselected
		
		# Get translation object
		_ = self.app._tr
		
		# Clear existing settings
		self.win.clear_effect_controls()

		# Get animation details
		animation = self.get_animation_details()
		self.selected_template = animation["service"]
		
		# Assign a new unique id for each template selected
		self.generateUniqueFolder()

		# Loop through params
		for param in animation["params"]:
			log.info(param["title"])
			
			# Is Hidden Param?
			if param["name"] == "start_frame" or param["name"] == "end_frame":
				# add value to dictionary
				self.params[param["name"]] = int(param["default"])
				
				# skip to next param without rendering the controls
				continue
			
			# Create Label
			widget = None
			label = QLabel()
			label.setText(_(param["title"]))
			label.setToolTip(_(param["title"]))

			if param["type"] == "spinner":
				# add value to dictionary
				self.params[param["name"]] = float(param["default"])
				
				# create spinner
				widget = QDoubleSpinBox()
				widget.setMinimum(float(param["min"]))
				widget.setMaximum(float(param["max"]))
				widget.setValue(float(param["default"]))
				widget.setSingleStep(0.01)
				widget.setToolTip(param["title"])
				widget.valueChanged.connect(functools.partial(self.spinner_value_changed, param))
				
			elif param["type"] == "text":
				# add value to dictionary
				self.params[param["name"]] = _(param["default"])
				
				# create spinner
				widget = QLineEdit()
				widget.setText(_(param["default"]))
				widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))

			elif param["type"] == "multiline":
				# add value to dictionary
				self.params[param["name"]] = _(param["default"])
				
				# create spinner
				widget = QTextEdit()
				widget.setText(_(param["default"]))
				widget.textChanged.connect(functools.partial(self.text_value_changed, widget, param))
				
			elif param["type"] == "dropdown":
				# add value to dictionary
				self.params[param["name"]] = param["default"]
				
				# create spinner
				widget = QComboBox()
				widget.currentIndexChanged.connect(functools.partial(self.dropdown_index_changed, widget, param))

				# Add values to dropdown
				if "project_files" in param["name"]:
					# override files dropdown
					param["values"] = {}
					for file in File.filter():
						if file.data["media_type"] in ("image", "video"):
							(dirName, fileName) = os.path.split(file.data["path"])
							(fileBaseName, fileExtension)=os.path.splitext(fileName)
							
							if fileExtension.lower() not in (".svg"):
								param["values"][fileName] = "|".join((file.data["path"], str(file.data["height"]), str(file.data["width"]), file.data["media_type"], str(file.data["fps"]["num"]/file.data["fps"]["den"])))

				# Add normal values
				box_index = 0
				for k,v in sorted(param["values"].items()):
					# add dropdown item
					widget.addItem(_(k), v)
					
					# select dropdown (if default)
					if v == param["default"]:
						widget.setCurrentIndex(box_index)
					box_index = box_index + 1
					
				if not param["values"]:
					widget.addItem(_("No Files Found"), "")
					widget.setEnabled(False)
					
			elif param["type"] == "color":
				# add value to dictionary
				self.params[param["name"]] = param["default"]
				
				widget = QPushButton()
				widget.setText("")
				widget.setStyleSheet("background-color: %s" % param["default"])
				widget.clicked.connect(functools.partial(self.color_button_clicked, widget, param))
				
			# Add Label and Widget to the form
			if (widget and label):
				self.win.settingsContainer.layout().addRow(label, widget)
			elif (label):
				self.win.settingsContainer.layout().addRow(label)
				
		# Enable interface
		self.enable_interface()
		
		# Init slider values
		self.init_slider_values()
		
		
	def spinner_value_changed(self, param, value ):
		self.params[param["name"]] = value
		log.info(value)
		
	def text_value_changed(self, widget, param, value=None ):
		try:
			# Attempt to load value from QTextEdit (i.e. multi-line)
			if not value:
				value = widget.toPlainText()
		except:
			pass
		self.params[param["name"]] = value
		log.info(value)
		
	def dropdown_index_changed(self, widget, param, index ):
		value = widget.itemData(index)
		self.params[param["name"]] = value
		log.info(value)
		
	def color_button_clicked(self, widget, param, index ):
		# Show color dialog
		currentColor = QColor(self.params[param["name"]])
		newColor = QColorDialog.getColor(currentColor)
		widget.setStyleSheet("background-color: %s" % newColor.name())
		self.params[param["name"]] = newColor.name()
		log.info(newColor.name())
		
	def generateUniqueFolder(self):
		""" Generate a new, unique folder name to contain Blender frames """
		
		# Assign a new unique id for each template selected
		self.unique_folder_name = str(uuid.uuid1())
		
		# Create a folder (if it does not exist)
		if not os.path.exists(os.path.join(info.BLENDER_PATH, self.unique_folder_name)):
			os.mkdir(os.path.join(info.BLENDER_PATH, self.unique_folder_name))
		
	def disable_interface(self):
		""" Disable all controls on interface """
		self.win.btnRefresh.setEnabled(False)
		self.win.sliderPreview.setEnabled(False)
		self.win.buttonBox.setEnabled(False)
	
	def enable_interface(self):
		""" Disable all controls on interface """
		self.win.btnRefresh.setEnabled(True)
		self.win.sliderPreview.setEnabled(True)
		self.win.buttonBox.setEnabled(True)
		
	def init_slider_values(self):
		""" Init the slider and preview frame label to the currently selected animation """
		
		# Get current preview slider frame
		preview_frame_number = self.win.sliderPreview.value()
		length = int(self.params["end_frame"])
		
		# Get the animation speed (if any)
		if not self.params["animation_speed"]:
			self.params["animation_speed"] = 1
		else:
			# Adjust length (based on animation speed multiplier)
			length *= int(self.params["animation_speed"])

		# Update the preview slider
		middle_frame = int(length / 2)
		# Be sure the new 'middle frame' and the current preview frame are not the same
		# This causes the thumbnail to refresh.
		if preview_frame_number == middle_frame:
			middle_frame += 1
		self.win.sliderPreview.setMinimum(self.params["start_frame"])
		self.win.sliderPreview.setMaximum(length)
		self.win.sliderPreview.setValue(middle_frame)
		
		# Update preview label
		self.win.lblFrame.setText("%s/%s" % (middle_frame, length))
	
	def btnRefresh_clicked(self, checked):
		
		# Render current frame
		preview_frame_number = self.win.sliderPreview.value()
		self.Render(preview_frame_number)
		
	def render_finished(self):
		log.info("RENDER FINISHED!")
		
		# Enable the Render button again
		self.enable_interface()
		
	def close_window(self):
		log.info("CLOSING WINDOW")
		
		# Enable the Render button again
		self.close()
		
	def update_progress_bar(self, current_frame, current_part, max_parts):

		# update label and preview slider
		self.sliderPreview.setValue(float(current_frame))
		
		# determine length of image sequence
		length = int(self.params["end_frame"])
		
		# Get the animation speed (if any)
		if self.params["animation_speed"]:
			# Adjust length (based on animation speed multiplier)
			length *= int(self.params["animation_speed"])
		
		# calculate the current percentage, and update the progress bar
		progress = float(float(current_frame) / float(length))
		#self.progressRender.set_fraction(progress)
		
	def sliderPreview_released(self):
		
		# Update preview label
		preview_frame_number = self.win.sliderPreview.value()
		length = int(self.params["end_frame"])
		self.win.lblFrame.setText("%s/%s" % (preview_frame_number, length))
		
	def get_animation_details(self):
		""" Build a dictionary of all animation settings and properties from XML """
		
		if not self.selected:
			return {}
		
		# Get all selected rows items
		ItemRow = self.blender_model.model.itemFromIndex(self.selected).row()
		animation_title = self.blender_model.model.item(ItemRow, 1).text()
		xml_path = self.blender_model.model.item(ItemRow, 2).text()
		service = self.blender_model.model.item(ItemRow, 3).text()
		
		# load xml effect file
		xmldoc = xml.parse(xml_path)
		
		# Get list of params
		animation = { "title" : animation_title, "path" : xml_path, "service" : service, "params" : [] }
		xml_params = xmldoc.getElementsByTagName("param")
		
		# Loop through params
		for param in xml_params:
			param_item = {}
			
			# Get details of param
			if param.attributes["title"]:
				param_item["title"] = param.attributes["title"].value
			
			if param.attributes["description"]:
				param_item["description"] = param.attributes["description"].value

			if param.attributes["name"]:
				param_item["name"] = param.attributes["name"].value

			if param.attributes["type"]:
				param_item["type"] = param.attributes["type"].value

			if param.getElementsByTagName("min"):
				param_item["min"] = param.getElementsByTagName("min")[0].childNodes[0].data

			if param.getElementsByTagName("max"):
				param_item["max"] = param.getElementsByTagName("max")[0].childNodes[0].data

			if param.getElementsByTagName("step"):
				param_item["step"] = param.getElementsByTagName("step")[0].childNodes[0].data

			if param.getElementsByTagName("digits"):
				param_item["digits"] = param.getElementsByTagName("digits")[0].childNodes[0].data

			if param.getElementsByTagName("default"):
				if param.getElementsByTagName("default")[0].childNodes:
					param_item["default"] = param.getElementsByTagName("default")[0].childNodes[0].data
				else:
					param_item["default"] = ""
				
			param_item["values"] = {}
			values = param.getElementsByTagName("value")
			for value in values:
				# Get list of values
				name = ""
				num = ""
				
				if value.attributes["name"]:
					name = value.attributes["name"].value
					
				if value.attributes["num"]:
					num = value.attributes["num"].value
					
				# add to parameter
				param_item["values"][name] = num
				
			# Append param object to list
			animation["params"].append(param_item)
			
		# Return animation dictionary
		return animation
		
	def contextMenuEvent(self, event):
		menu = QMenu(self)
		menu.addAction(self.win.actionDetailsView)
		menu.addAction(self.win.actionThumbnailView)
		menu.exec_(QCursor.pos())
		
		# Ignore event, propagate to parent 
		event.ignore()
		super().mouseMoveEvent(event)
	
	def mousePressEvent(self, event):

		# Ignore event, propagate to parent 
		event.ignore()
		super().mousePressEvent(event)
		
	def refresh_view(self):
		self.blender_model.update_model()
		self.hideColumn(2)
		self.hideColumn(3)
			
	def __init__(self, *args):
		# Invoke parent init
		QTreeView.__init__(self, *args)
		
		# Get a reference to the window object
		self.app = get_app()
		self.win = args[0]
		
		# Get Model data
		self.blender_model = BlenderModel()
		
		# Keep track of mouse press start position to determine when to start drag
		self.selected = None
		self.deselected = None
		
		# Init dictionary which holds the values to the template parameters
		self.params = {}
		
		# Assign a new unique id for each template selected
		self.unique_folder_name = None
		
		# Disable interface
		self.disable_interface()
		self.selected_template = ""

		# Setup header columns
		self.setModel(self.blender_model.model)
		self.setIconSize(QSize(131, 108))
		self.setIndentation(0)
		self.setSelectionBehavior(QTreeView.SelectRows)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		
		# Hook up button
		self.win.btnRefresh.clicked.connect(functools.partial(self.btnRefresh_clicked))
		self.win.sliderPreview.sliderReleased.connect(functools.partial(self.sliderPreview_released))
		
		# Refresh view
		self.refresh_view()
		
	def get_project_params(self, is_preview=True):
		""" Return a dictionary of project related settings, needed by the Blender python script. """
		
		project = self.app.project
		project_params = {}
		
		# Append on some project settings
		project_params["fps"] = project.get(["fps"])
		project_params["resolution_x"] = project.get(["width"])
		project_params["resolution_y"] = project.get(["height"])
		
		if is_preview:
			project_params["resolution_percentage"] = 50
		else:
			project_params["resolution_percentage"] = 100
		project_params["quality"] = 100
		project_params["file_format"] = "PNG"
		if is_preview:
			# preview mode - use offwhite background (i.e. horizon color)
			project_params["color_mode"] = "RGB"
		else:
			# render mode - transparent background
			project_params["color_mode"] = "RGBA"
		project_params["horizon_color"] = (0.57, 0.57, 0.57)
		project_params["animation"] = True
		project_params["output_path"] = os.path.join(info.BLENDER_PATH, self.unique_folder_name, self.params["file_name"])

		# return the dictionary
		return project_params
	
	def error_with_blender(self, version=None, command_output=None):
		""" Show a friendly error message regarding the blender executable or version. """
		_ = self.app._tr
		s = settings.get_settings()
		
		version_message = ""
		if version:
			version_message = _("\n\nVersion Detected:\n%s") % version
			
		if command_output:
			version_message = _("\n\nError Output:\n%s") % command_output
		
		# show error message
		blender_version = "2.62"
		# Handle exception
		msg = QMessageBox()
		msg.setText(_("Blender, the free open source 3D content creation suite is required for this action (http://www.blender.org).\n\nPlease check the preferences in OpenShot and be sure the Blender executable is correct.  This setting should be the path of the 'blender' executable on your computer.  Also, please be sure that it is pointing to Blender version %s or greater.\n\nBlender Path:\n%s%s") % (blender_version, s.get("blender_command"), version_message))
		msg.exec_()

		# Enable the Render button again
		self.enable_interface()
		
	def inject_params(self, path, frame=None):
		# determine if this is 'preview' mode?
		is_preview = False
		if frame:
			# if a frame is passed in, we are in preview mode.
			# This is used to turn the background color to off-white... instead of transparent
			is_preview = True
		
		# prepare string to inject
		user_params = "\n#BEGIN INJECTING PARAMS\n"
		for k,v in self.params.items():
			if type(v) == int or type(v) == float or type(v) == list or type(v) == bool:
				user_params += "params['%s'] = %s\n" % (k,v)
			if type(v) == str:
				user_params += "params['%s'] = '%s'\n" % (k, v.replace("'", r"\'"))

		for k,v in self.get_project_params(is_preview).items():
			if type(v) == int or type(v) == float or type(v) == list or type(v) == bool:
				user_params += "params['%s'] = %s\n" % (k,v)
			if type(v) == str:
				user_params += "params['%s'] = '%s'\n" % (k, v.replace("'", r"\'"))
		user_params += "#END INJECTING PARAMS\n"
		
		# Force the Frame to 1 frame (for previewing)
		if frame:
			user_params += "\n\n#ONLY RENDER 1 FRAME FOR PREVIEW\n"
			user_params += "params['%s'] = %s\n" % ("start_frame", frame)
			user_params += "params['%s'] = %s\n" % ("end_frame", frame)
			user_params += "\n\n#END ONLY RENDER 1 FRAME FOR PREVIEW\n"
		
		# Open new temp .py file, and inject the user parameters
		f = open(path, 'r')
		script_body = f.read()
		f.close()
		
		# modify script variable
		script_body = script_body.replace("#INJECT_PARAMS_HERE", user_params)
		
		# Write update script
		f = open(path, 'w')
		f.write(script_body)
		f.close()

	def update_image(self, image_path):
		log.info("update_image: %s" % image_path)

		# get the pixbuf
		item = QGraphicsPixmapItem(QPixmap.fromImage(image_path))
		scene = QGraphicsScene()
		scene.addItem(item)
		
		self.imgPreview.setScene(scene)
		self.imgPreview.show()
			
		
		# get size of real image
		#real_width = pbThumb.get_width()
		#real_height = pbThumb.get_height()
		#ratio = float(real_width) / float(real_height)

		# resize thumbnail
		#pbThumb = pbThumb.scale_simple(int(self.image_height * ratio), int(self.image_height), gtk.gdk.INTERP_BILINEAR)

		# update image
		#self.imgPreview.set_from_pixbuf(pbThumb)
		
	def Render(self, frame=None):
		""" Render an images sequence of the current template using Blender 2.62+ and the
		Blender Python API. """
		
		# Enable the Render button again
		self.disable_interface()
		
		# change cursor to "please wait"
		#self.frm3dGenerator.window.set_cursor(gtk.gdk.Cursor(150))

		blend_file_path = os.path.join(info.PATH, "blender", "blend", self.selected_template)
		source_script = os.path.join(info.PATH, "blender", "scripts", self.selected_template.replace(".blend", ".py"))
		target_script = os.path.join(info.BLENDER_PATH, self.unique_folder_name, self.selected_template.replace(".blend", ".py"))

		# Copy the .py script associated with this template to the temp folder.  This will allow
		# OpenShot to inject the user-entered params into the Python script.
		shutil.copy(source_script, target_script)
		
		# Open new temp .py file, and inject the user parameters
		self.inject_params(target_script, frame)
		
		# Create new thread to launch the Blender executable (and read the output)
		self.my_blender = None
		if frame:
			# preview mode 
			self.my_blender = BlenderCommand(self, blend_file_path, target_script, True)
		else:
			# render mode
			self.my_blender = BlenderCommand(self, blend_file_path, target_script, False)
			
		# Start blender thread
		self.my_blender.start()



class BlenderCommand(threading.Thread):
	def __init__(self, parent, blend_file_path, target_script, preview_mode=False):
		# Init regex expression used to determine blender's render progress
		s = settings.get_settings()
		
		# get the blender executable path
		self.blender_exec_path = s.get("blender_command")
		self.blender_frame_expression = re.compile(r"Fra:([0-9,]*).*Mem:(.*?) .*Part ([0-9,]*)-([0-9,]*)")
		self.blender_saved_expression = re.compile(r"Saved: (.*?) Time: (.*)")
		self.blender_version = re.compile(r"Blender (.*?) ")
		self.blend_file_path = blend_file_path
		self.target_script = target_script
		self.parent = parent
		self.preview_mode = preview_mode
		self.frame_detected = False
		self.version = None
		self.command_output = ""
		self.process = None
		self.is_running = True
		
		# base class constructor
		threading.Thread.__init__(self)
		
	def kill(self):
		""" Kill the running process, if any """
		
		self.is_running = False

		if self.process:
			# kill
			self.process.kill()
		else:
			# close window if thread was killed
			QCoreApplication.postEvent(self.parent, QBlenderEvent(1, {"data":None}))
		

	def run(self):
		_ = self.parent.app._tr

		self.myevent = QBlenderEvent(65534, {"data":None})
		QCoreApplication.sendEvent(self.parent, self.myevent)

		try:
			# Shell the blender command to create the image sequence
			command_get_version = [self.blender_exec_path, '-v']
			command_render = [self.blender_exec_path, '-b', self.blend_file_path , '-P', self.target_script]
			self.process = subprocess.Popen(command_get_version, stdout=subprocess.PIPE)
			
			# Check the version of Blender
			self.version = self.blender_version.findall(self.process.stdout.readline())

			if self.version:
				if float(self.version[0]) < 2.62:
					# change cursor to "default" and stop running blender command
					#gobject.idle_add(self.frm3dGenerator.frm3dGenerator.window.set_cursor, None)
					self.is_running = False
					
					# Wrong version of Blender.  Must be 2.62+:
					QCoreApplication.postEvent(self.parent, QBlenderEvent(3, {"data":float(self.version[0])}))
					#self.parent.error_with_blender(float(self.version[0]))
					return
			
			# debug info
			log.info("Blender command: %s %s '%s' %s '%s'" % (command_render[0], command_render[1], command_render[2], command_render[3], command_render[4]))
			
			# Run real command to render Blender project
			self.process = subprocess.Popen(command_render, stdout=subprocess.PIPE)
			
		except:
			# Error running command.  Most likely the blender executable path in the settings
			# is not correct, or is not the correct version of Blender (i.e. 2.62+)
			
			# change cursor to "default" and stop running blender command
			#gobject.idle_add(self.frm3dGenerator.frm3dGenerator.window.set_cursor, None)
			self.is_running = False
			
			QCoreApplication.postEvent(self.parent, QBlenderEvent(4, None))
			return

		while self.is_running:

			# Look for progress info in the Blender Output
			line = self.process.stdout.readline()
			self.command_output = self.command_output + line + "\n"	# append all output into a variable
			output_frame = self.blender_frame_expression.findall(line)

			# Does it have a match?
			if output_frame:
				# Yes, we have a match
				self.frame_detected = True
				current_frame = output_frame[0][0]
				memory = output_frame[0][1]
				current_part = output_frame[0][2]
				max_parts = output_frame[0][3]
				
				# Update progress bar
				if not self.preview_mode:
					# only update progress if in 'render' mode
					QCoreApplication.postEvent(self.parent, QBlenderEvent(5, {"current_frame":current_frame, "current_part":current_part, "max_parts":max_parts}))
				
			# Look for progress info in the Blender Output
			output_saved = self.blender_saved_expression.findall(line)

			# Does it have a match?
			if output_saved:
				# Yes, we have a match
				self.frame_detected = True
				image_path = output_saved[0][0]
				time_saved = output_saved[0][1]
				
				# Update preview image
				QCoreApplication.postEvent(self.parent, QBlenderEvent(6, image_path))
			
			# Are we done? Should we exit the loop?	
			if line == '' and self.process.poll() != None:
				break

				
		# change cursor to "default"
		#gobject.idle_add(self.frm3dGenerator.frm3dGenerator.window.set_cursor, None)

		# Check if NO FRAMES are detected
		if not self.frame_detected:
			# Show Error that no frames are detected.  This is likely caused by
			# the wrong command being executed... or an error in Blender.
			log.info("No frame was found in the output from Blender")
			#gobject.idle_add(self.frm3dGenerator.error_with_blender, None, _("No frame was found in the output from Blender"))
			QCoreApplication.postEvent(self.parent, QBlenderEvent(7, _("No frame was found in the output from Blender")))
		
		# Done with render (i.e. close window)
		elif not self.preview_mode:
			# only close window if in 'render' mode
			QCoreApplication.postEvent(self.parent, QEvent({"id":2, "data":None}))
			
		# Thread finished
		log.info("Blender render thread finished")
		if self.is_running == False:
			# close window if thread was killed
			QCoreApplication.postEvent(self.parent, QEvent({"id":1, "data":None}))
			
		# mark thread as finished
		self.is_running = False