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
from _sre import MAXREPEAT
from urllib.parse import urlparse
from classes import updates
from classes import info
from classes.logger import log
from classes import settings
from classes.query import File
from classes.app import get_app
from PyQt5.QtCore import QMimeData, QSize, Qt, QCoreApplication, QPoint, QFileInfo, QEvent, QObject, QThread, pyqtSlot, pyqtSignal, QMetaObject, Q_ARG
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
	""" A custom Blender QEvent, which can safely be sent from the Blender thread to the Qt thread (to communicate) """
	 
	def __init__(self, id, data=None, *args):
		# Invoke parent init
		QEvent.__init__(self, id)
		self.data = data
		self.id = id

class BlenderTreeView(QTreeView):
	""" A TreeView QWidget used on the animated title window """ 

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
				color = QColor(param["default"])
				self.params[param["name"]] = [color.redF(), color.greenF(), color.blueF()]
				
				widget = QPushButton()
				widget.setText("")
				widget.setStyleSheet("background-color: {}".format(param["default"]))
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
		widget.setStyleSheet("background-color: {}".format(newColor.name()))
		self.params[param["name"]] = [newColor.redF(), newColor.greenF(), newColor.blueF()]
		log.info(newColor.name())
		
	def generateUniqueFolder(self):
		""" Generate a new, unique folder name to contain Blender frames """
		
		# Assign a new unique id for each template selected
		self.unique_folder_name = str(uuid.uuid1())
		
		# Create a folder (if it does not exist)
		if not os.path.exists(os.path.join(info.BLENDER_PATH, self.unique_folder_name)):
			os.mkdir(os.path.join(info.BLENDER_PATH, self.unique_folder_name))
		
	def disable_interface(self, cursor=True):
		""" Disable all controls on interface """
		self.win.btnRefresh.setEnabled(False)
		self.win.sliderPreview.setEnabled(False)
		self.win.buttonBox.setEnabled(False)
		
		# Show 'Wait' cursor
		if cursor:
			QApplication.setOverrideCursor(Qt.WaitCursor)
	
	def enable_interface(self):
		""" Disable all controls on interface """
		self.win.btnRefresh.setEnabled(True)
		self.win.sliderPreview.setEnabled(True)
		self.win.buttonBox.setEnabled(True)
		
		# Restore normal cursor
		QApplication.restoreOverrideCursor()
		
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
		
		self.win.sliderPreview.setMinimum(self.params["start_frame"])
		self.win.sliderPreview.setMaximum(length)
		self.win.sliderPreview.setValue(middle_frame)
		
		# Update preview label
		self.win.lblFrame.setText("{}/{}".format(middle_frame, length))
		
		# Click the refresh button
		self.btnRefresh_clicked(None)

	def btnRefresh_clicked(self, checked):
		
		# Render current frame
		preview_frame_number = self.win.sliderPreview.value()
		self.Render(preview_frame_number)
		
		
	def render_finished(self):
		log.info("RENDER FINISHED!")
		
		# Add file to project
		final_path = os.path.join(info.BLENDER_PATH, self.unique_folder_name, self.params["file_name"] + "%04d.png")
		log.info(final_path)
		
		# Add to project files
		self.win.add_file(final_path)
		
		# Enable the Render button again
		self.win.close()
		
	def close_window(self):
		log.info("CLOSING WINDOW")
		
		# Close window
		self.close()
		
	def update_progress_bar(self, current_frame, current_part, max_parts):

		# update label and preview slider
		self.win.sliderPreview.setValue(current_frame)
		
	def sliderPreview_released(self):
		log.info('sliderPreview_released')
		
		# Update preview label
		preview_frame_number = self.win.sliderPreview.value()
		length = int(self.params["end_frame"])
		self.win.lblFrame.setText("{}/{}".format(preview_frame_number, length))
		
		# Render current frame
		self.Render(preview_frame_number)
		
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
			version_message = _("\n\nVersion Detected:\n{}").format(version)
			
		if command_output:
			version_message = _("\n\nError Output:\n{}").format(command_output)
		
		# show error message
		blender_version = "2.62"
		# Handle exception
		msg = QMessageBox()
		msg.setText(_("Blender, the free open source 3D content creation suite is required for this action (http://www.blender.org).\n\nPlease check the preferences in OpenShot and be sure the Blender executable is correct.  This setting should be the path of the 'blender' executable on your computer.  Also, please be sure that it is pointing to Blender version {} or greater.\n\nBlender Path:\n{}{}").format(blender_version, s.get("blender_command"), version_message))
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
				user_params += "params['{}'] = {}\n".format(k,v)
			if type(v) == str:
				user_params += "params['{}'] = '{}'\n".format(k, v.replace("'", r"\'"))

		for k,v in self.get_project_params(is_preview).items():
			if type(v) == int or type(v) == float or type(v) == list or type(v) == bool:
				user_params += "params['{}'] = {}\n".format(k,v)
			if type(v) == str:
				user_params += "params['{}'] = '{}'\n".format(k, v.replace("'", r"\'"))
		user_params += "#END INJECTING PARAMS\n"
		
		# Force the Frame to 1 frame (for previewing)
		if frame:
			user_params += "\n\n#ONLY RENDER 1 FRAME FOR PREVIEW\n"
			user_params += "params['{}'] = {}\n".format("start_frame", frame)
			user_params += "params['{}'] = {}\n".format("end_frame", frame)
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

		# get the pixbuf
		image = QImage(image_path)
		scaled_image = image.scaledToHeight(self.win.imgPreview.height(), Qt.SmoothTransformation);
		pixmap = QPixmap.fromImage(scaled_image)
		self.win.imgPreview.setPixmap(pixmap)

	def Render(self, frame=None):
		""" Render an images sequence of the current template using Blender 2.62+ and the
		Blender Python API. """
		
		# Enable the Render button again
		self.disable_interface()

		# Init blender paths
		blend_file_path = os.path.join(info.PATH, "blender", "blend", self.selected_template)
		source_script = os.path.join(info.PATH, "blender", "scripts", self.selected_template.replace(".blend", ".py"))
		target_script = os.path.join(info.BLENDER_PATH, self.unique_folder_name, self.selected_template.replace(".blend", ".py"))

		# Copy the .py script associated with this template to the temp folder.  This will allow
		# OpenShot to inject the user-entered params into the Python script.
		shutil.copy(source_script, target_script)
		
		# Open new temp .py file, and inject the user parameters
		self.inject_params(target_script, frame)
		
		# Create new thread to launch the Blender executable (and read the output)
		if frame:
			# preview mode 
			QMetaObject.invokeMethod(self.worker, 'Render', Qt.QueuedConnection,
											Q_ARG(str, blend_file_path),
											Q_ARG(str, target_script),
											Q_ARG(bool, True))
		else:
			# render mode
			#self.my_blender = BlenderCommand(self, blend_file_path, target_script, False)
			QMetaObject.invokeMethod(self.worker, 'Render', Qt.QueuedConnection,
											Q_ARG(str, blend_file_path),
											Q_ARG(str, target_script),
											Q_ARG(bool, False))


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
		self.disable_interface(cursor=False)
		self.selected_template = ""

		# Setup header columns
		self.setModel(self.blender_model.model)
		self.setIconSize(QSize(131, 108))
		self.setIndentation(0)
		self.setSelectionBehavior(QTreeView.SelectRows)
		self.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.setWordWrap(True)
		self.setStyleSheet('QTreeView::item { padding-top: 2px; }')
		
		# Hook up button
		self.win.btnRefresh.clicked.connect(functools.partial(self.btnRefresh_clicked))
		self.win.sliderPreview.sliderReleased.connect(functools.partial(self.sliderPreview_released))
		
		# Refresh view
		self.refresh_view()


		# Background Worker Thread (for Blender process)
		self.background = QThread(self)
		self.worker = Worker()  # no parent!
		
		# Hook up signals to Background Worker
		self.worker.closed.connect(self.onCloseWindow)
		self.worker.finished.connect(self.onRenderFinish)
		self.worker.blender_version_error.connect(self.onBlenderVersionError)
		self.worker.blender_error_nodata.connect(self.onBlenderErrorNoData)
		self.worker.progress.connect(self.onUpdateProgress)
		self.worker.image_updated.connect(self.onUpdateImage)
		self.worker.blender_error_with_data.connect(self.onBlenderErrorMessage)
		self.worker.enable_interface.connect(self.onRenableInterface)

		# Move Worker to new thread, and Start
		self.worker.moveToThread(self.background)
		self.background.start()
		
	# Signal when to close window (1001)
	def onCloseWindow(self):
		log.info ('onCloseWindow')
		self.close()
	
	# Signal when render is finished (1002)
	def onRenderFinish(self):
		log.info ('onRenderFinish')
		self.render_finished()
		
	# Error from blender (with version number) (1003)
	def onBlenderVersionError(self, version):
		log.info ('onBlenderVersionError')
		self.error_with_blender(version)
		
	# Error from blender (with no data) (1004)
	def onBlenderErrorNoData(self):
		log.info ('onBlenderErrorNoData')
		self.error_with_blender()
		
	# Signal when to update progress bar (1005)
	def onUpdateProgress(self, current_frame, current_part, max_parts):
		#log.info ('onUpdateProgress')		
		self.update_progress_bar(current_frame, current_part, max_parts)

	# Signal when to update preview image (1006)
	def onUpdateImage(self, image_path):
		#log.info ('onUpdateImage: %s' % image_path)
		self.update_image(image_path)

	# Signal error from blender (with custom message) (1007)
	def onBlenderErrorMessage(self, error):
		log.info ('onBlenderErrorMessage')
		self.error_with_blender(None, error)
			
	# Signal when to re-enable interface (1008)
	def onRenableInterface(self):
		log.info ('onRenableInterface')
		self.enable_interface()


class Worker(QObject):
	""" Background Worker Object (to run the Blender commands) """
	
	closed = pyqtSignal() # 1001
	finished = pyqtSignal() # 1002
	blender_version_error = pyqtSignal(str) # 1003
	blender_error_nodata = pyqtSignal() # 1004
	progress = pyqtSignal(int, int, int) # 1005
	image_updated = pyqtSignal(str) # 1006
	blender_error_with_data = pyqtSignal(str) # 1007
	enable_interface = pyqtSignal() # 1008

	@pyqtSlot(str, str, bool)
	def Render(self, blend_file_path, target_script, preview_mode=False):
		""" Worker's Render method which invokes the Blender rendering commands """
		log.info ("QThread Render Method Invoked")

		# Init regex expression used to determine blender's render progress
		s = settings.get_settings()
		
		# get the blender executable path
		self.blender_exec_path = s.get("blender_command")
		self.blender_frame_expression = re.compile(r"Fra:([0-9,]*).*Mem:(.*?) .*Part ([0-9,]*)-([0-9,]*)")
		self.blender_saved_expression = re.compile(r"Saved: (.*?) Time: (.*)")
		self.blender_version = re.compile(r"Blender (.*?) ")
		self.blend_file_path = blend_file_path
		self.target_script = target_script
		self.preview_mode = preview_mode
		self.frame_detected = False
		self.version = None
		self.command_output = ""
		self.process = None
		self.is_running = True
		_ = get_app()._tr
		
		try:
			# Shell the blender command to create the image sequence
			command_get_version = [self.blender_exec_path, '-v']
			command_render = [self.blender_exec_path, '-b', self.blend_file_path , '-P', self.target_script]
			self.process = subprocess.Popen(command_get_version, stdout=subprocess.PIPE)
			
			# Check the version of Blender
			self.version = self.blender_version.findall(str(self.process.stdout.readline()))

			if self.version:
				if float(self.version[0]) < 2.62:
					# change cursor to "default" and stop running blender command
					self.is_running = False
					
					# Wrong version of Blender.  Must be 2.62+:
					self.blender_version_error.emit(float(self.version[0]))
					return
			
			# debug info
			log.info("Blender command: {} {} '{}' {} '{}'".format(command_render[0], command_render[1], command_render[2], command_render[3], command_render[4]))
			
			# Run real command to render Blender project
			self.process = subprocess.Popen(command_render, stdout=subprocess.PIPE)
			
		except:
			# Error running command.  Most likely the blender executable path in the settings
			# is not correct, or is not the correct version of Blender (i.e. 2.62+)
			self.is_running = False
			self.blender_error_nodata.emit()
			return


		while self.is_running and self.process.poll() is None:

			# Look for progress info in the Blender Output
			line = str(self.process.stdout.readline())
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
					self.progress.emit(float(current_frame), float(current_part), float(max_parts))
				
			# Look for progress info in the Blender Output
			output_saved = self.blender_saved_expression.findall(str(line))

			# Does it have a match?
			if output_saved:
				# Yes, we have a match
				self.frame_detected = True
				image_path = output_saved[0][0]
				time_saved = output_saved[0][1]
				
				# Update preview image
				self.image_updated.emit(image_path)


		# Re-enable the interface
		self.enable_interface.emit()

		# Check if NO FRAMES are detected
		if not self.frame_detected:
			# Show Error that no frames are detected.  This is likely caused by
			# the wrong command being executed... or an error in Blender.
			self.blender_error_with_data.emit(_("No frame was found in the output from Blender"))
		
		# Done with render (i.e. close window)
		elif not self.preview_mode:
			# only close window if in 'render' mode
			self.finished.emit()
			
		# Thread finished
		log.info("Blender render thread finished")
		if self.is_running == False:
			# close window if thread was killed
			self.closed.emit()
			
		# mark thread as finished
		self.is_running = False

