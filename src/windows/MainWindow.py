""" 
 @file
 @brief This file loads the main window (i.e. the primary user-interface)
 @author Noah Figg <eggmunkee@hotmail.com>
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
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import *
from PyQt5 import uic
from windows.TimelineWebView import TimelineWebView
from classes import info, ui_util, SettingStore, qt_types, UpdateManager
from classes.OpenShotApp import get_app
from classes.logger import log
from images import openshot_rc
from windows.MediaTreeView import MediaTreeView
import xml.etree.ElementTree as ElementTree

#This class contains the logic for the main window widget
class MainWindow(QMainWindow, UpdateManager.UpdateWatcher, UpdateManager.UpdateInterface):
	ui_path = os.path.join(info.PATH, 'windows','ui', 'main.ui')
	
	#Save window settings on close
	def closeEvent(self, event):
		self.save_settings()
		
	def actionNew_trigger(self, event):
		get_app().project.new()
		log.info("New Project created.")
		
	def actionAnimatedTitle_trigger(self, event):
		# show dialog
		from windows.AnimatedTitle import AnimatedTitle
		win = AnimatedTitle()
		#Run the dialog event loop - blocking interaction on this window during that time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('animated title add confirmed')
		else:
			log.info('animated title add cancelled')
		
	def actionOpen_trigger(self, event):
		app = get_app()
		_ = app._tr
		file_path, file_type = QFileDialog.getOpenFileName(self, _("Open Project...")) #, options=QFileDialog.DontUseNativeDialog)
		if file_path:
			app.project.load(file_path)
			app.project.current_filepath = file_path
			app.update_manager.reset()
			self.filesTreeView.update_model()
			log.info("Loaded project %s" % (file_path))
		
	def actionSave_trigger(self, event):
		app = get_app()
		_ = app._tr
		#Get current filepath if any, otherwise ask user
		file_path = app.project.current_filepath
		if not file_path:
			file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Project..."))
		
		if file_path:
			try:
				app.project.save(file_path)
				app.project.current_filepath = file_path
				log.info("Saved %s" % (file_path))
			except Exception as ex:
				log.error("Couldn't save project %s", file_path)

	def actionSaveAs_trigger(self, event):
		app = get_app()
		_ = app._tr
		file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Project As..."))
		if file_path:
			try:
				app.project.save(file_path)
				app.project.current_filepath = file_path
				log.info("Saved %s" % (file_path))
			except Exception as ex:
				log.error("Couldn't save project %s", file_path)
		
	def actionImportFiles_trigger(self, event):
		app = get_app()
		_ = app._tr
		files = QFileDialog.getOpenFileNames(self, _("Import File..."))[0]
		for file_path in files:
			self.filesTreeView.add_file(file_path)
			self.filesTreeView.update_model()
			log.info("Loaded project %s" % (file_path))

		
	def actionUndo_trigger(self, event):
		app = get_app()
		app.update_manager.undo()
		#log.info(app.project._data)

	def actionRedo_trigger(self, event):
		app = get_app()
		app.update_manager.redo()
		#log.info(app.project._data)
		
	def actionFilesShowAll_trigger(self, event):
		self.filesTreeView.update_model()
	def actionFilesShowVideo_trigger(self, event):
		self.filesTreeView.update_model()
	def actionFilesShowAudio_trigger(self, event):
		self.filesTreeView.update_model()
	def actionFilesShowImage_trigger(self, event):
		self.filesTreeView.update_model()

	#Project settings test code
		# app = get_app()
		# curr_val = app.project.get("settings/nfigg-setting")
		# if curr_val == None:
			# log.info ("Addvalue")
			# app.update_manager.add("settings/nfigg-setting", {"a": 1, "b": 5})
		# else:
			# log.info ("Increment value")
			# update = dict()
			# update["a"] = curr_val["a"] + 1
			# app.update_manager.update("settings/nfigg-setting", update, partial_update=True)
		#log.info(app.project._data)
	#Other project settings test code
		# app = get_app()
		# curr_val = app.project.get("settings/nfigg-setting")
		# if not curr_val == None and curr_val["a"] > 1:
			# log.info ("Decrement value")
			# update = dict()
			# update["a"] = curr_val["a"] - 1
			# app.update_manager.update("settings/nfigg-setting", update, partial_update=True)
		# elif not curr_val == None:
			# log.info ("Remove value")
			# app.update_manager.remove("settings/nfigg-setting")
		#log.info(app.project._data)
		
	def actionPlay_trigger(self, event):
		if self.actionPlay.isChecked():
			ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
			#TODO: call on library to pause
		else:
			ui_util.setup_icon(self, self.actionPlay, "actionPlay") #to default
			#TODO: call on library to play
		
	def actionFastForward_trigger(self, event):
		pass
	
	def actionTimelineZoomIn_trigger(self, event):
		self.sliderZoom.setValue(self.sliderZoom.value() - self.sliderZoom.singleStep())
	
	def actionTimelineZoomOut_trigger(self, event):
		self.sliderZoom.setValue(self.sliderZoom.value() + self.sliderZoom.singleStep())

	#Update undo and redo buttons enabled/disabled to available changes
	def updateStatusChanged(self, undo_status, redo_status):
		self.actionUndo.setEnabled(undo_status)
		self.actionRedo.setEnabled(redo_status)
	
	#Update window settings in setting store
	def save_settings(self):
		settings = SettingStore.get_settings()

		#Save window state and geometry (saves toolbar and dock locations)
		settings.set('window_state', qt_types.bytes_to_str(self.saveState()))
		settings.set('window_geometry', qt_types.bytes_to_str(self.saveGeometry()))

		#Splitter sizes
		sizes = self.splitter_2.sizes()
		settings.set('window_splitter_2_pos', sizes)
		sizes = self.splitter.sizes()
		settings.set('window_splitter_pos', sizes)
		
		#TODO: Call save_settings on any sub-objects necessary
	
	#Get window settings from setting store
	def load_settings(self):
		settings = SettingStore.get_settings()
		
		#Window state and geometry (also toolbar and dock locations)
		if settings.get('window_geometry'): self.restoreGeometry(qt_types.str_to_bytes(settings.get('window_geometry')))
		if settings.get('window_state'): self.restoreState(qt_types.str_to_bytes(settings.get('window_state')))
		
		#Splitter sizes
		if settings.get('window_splitter_pos'): self.splitter.setSizes(settings.get('window_splitter_pos'))
		if settings.get('window_splitter_2_pos'): self.splitter_2.setSizes(settings.get('window_splitter_2_pos'))

		#TODO: Call load_settings on any sub-objects necessary
		
	def setup_toolbars(self):
		_ =  get_app()._tr #Get translation function
		
		#Start undo and redo actions disabled
		self.actionUndo.setEnabled(False)
		self.actionRedo.setEnabled(False)
		
		#Add files toolbar =================================================================================
		self.filesToolbar = QToolBar("Files Toolbar")
		self.filesActionGroup = QActionGroup(self)
		self.filesActionGroup.setExclusive(True)
		self.filesActionGroup.addAction(self.actionFilesShowAll)
		self.filesActionGroup.addAction(self.actionFilesShowVideo)
		self.filesActionGroup.addAction(self.actionFilesShowAudio)
		self.filesActionGroup.addAction(self.actionFilesShowImage)
		self.actionFilesShowAll.setChecked(True)
		self.filesToolbar.addAction(self.actionFilesShowAll)
		self.filesToolbar.addAction(self.actionFilesShowVideo)
		self.filesToolbar.addAction(self.actionFilesShowAudio)
		self.filesToolbar.addAction(self.actionFilesShowImage)
		self.filesFilter = QLineEdit()
		self.filesFilter.setObjectName("filesFilter")
		self.filesToolbar.addWidget(self.filesFilter)
		self.actionFilesClear.setEnabled(False)
		self.filesToolbar.addAction(self.actionFilesClear)
		self.tabFiles.layout().addWidget(self.filesToolbar)
		
		#Add transitions toolbar =================================================================================
		self.transitionsToolbar = QToolBar("Transitions Toolbar")
		self.transitionsActionGroup = QActionGroup(self)
		self.transitionsActionGroup.setExclusive(True)
		self.transitionsActionGroup.addAction(self.actionTransitionsShowAll)
		self.transitionsActionGroup.addAction(self.actionTransitionsShowCommon)
		self.actionTransitionsShowAll.setChecked(True)
		self.transitionsToolbar.addAction(self.actionTransitionsShowAll)
		self.transitionsToolbar.addAction(self.actionTransitionsShowCommon)
		self.transitionsFilter = QLineEdit()
		self.transitionsFilter.setObjectName("transitionsFilter")
		self.transitionsToolbar.addWidget(self.transitionsFilter)
		self.actionTransitionsClear.setEnabled(False)
		self.transitionsToolbar.addAction(self.actionTransitionsClear)
		self.tabTransitions.layout().addWidget(self.transitionsToolbar)
		
		#Add effects toolbar =================================================================================
		self.effectsToolbar = QToolBar("Effects Toolbar")
		self.effectsActionGroup = QActionGroup(self)
		self.effectsActionGroup.setExclusive(True)
		self.effectsActionGroup.addAction(self.actionEffectsShowAll)
		self.effectsActionGroup.addAction(self.actionEffectsShowVideo)
		self.effectsActionGroup.addAction(self.actionEffectsShowAudio)
		self.actionEffectsShowAll.setChecked(True)
		self.effectsToolbar.addAction(self.actionEffectsShowAll)
		self.effectsToolbar.addAction(self.actionEffectsShowVideo)
		self.effectsToolbar.addAction(self.actionEffectsShowAudio)
		self.effectsFilter = QLineEdit()
		self.effectsFilter.setObjectName("effectsFilter")
		self.effectsToolbar.addWidget(self.effectsFilter)
		self.actionEffectsClear.setEnabled(False)
		self.effectsToolbar.addAction(self.actionEffectsClear)
		self.tabEffects.layout().addWidget(self.effectsToolbar)	

		#Add Video Preview toolbar ==========================================================================
		self.videoToolbar = QToolBar("Video Toolbar")
		
		#Add left spacer
		spacer = QWidget(self)
		spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.videoToolbar.addWidget(spacer)
		
		#Playback controls
		self.videoToolbar.addAction(self.actionJumpStart)
		self.videoToolbar.addAction(self.actionRewind)
		self.videoToolbar.addAction(self.actionPlay)
		self.videoToolbar.addAction(self.actionFastForward)
		self.videoToolbar.addAction(self.actionJumpEnd)
		self.actionPlay.setCheckable(True)
		
		#Add right spacer
		spacer = QWidget(self)
		spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.videoToolbar.addWidget(spacer)
		
		self.tabVideo.layout().addWidget(self.videoToolbar)
		
		#Add Timeline toolbar ================================================================================
		self.timelineToolbar = QToolBar("Timeline Toolbar", self)
		
		self.timelineToolbar.addAction(self.actionAddTrack)
		self.timelineToolbar.addSeparator()

		#Create togglable group of actions for selecting current tool
		self.toolActionGroup = QActionGroup(self)
		self.toolActionGroup.setExclusive(True)
		self.toolActionGroup.addAction(self.actionArrowTool)
		self.toolActionGroup.addAction(self.actionRazorTool)
		self.actionArrowTool.setChecked(True)
		self.timelineToolbar.addAction(self.actionArrowTool)
		self.timelineToolbar.addAction(self.actionRazorTool)

		#rest of options
		self.timelineToolbar.addAction(self.actionSnappingTool)
		self.timelineToolbar.addSeparator()
		self.timelineToolbar.addAction(self.actionAddMarker)
		self.timelineToolbar.addAction(self.actionPreviousMarker)
		self.timelineToolbar.addAction(self.actionNextMarker)
		self.timelineToolbar.addSeparator()

		#Setup Zoom slider
		self.sliderZoom = QSlider(Qt.Horizontal, self)
		self.sliderZoom.setPageStep(6)
		self.sliderZoom.setRange(8, 200)
		self.sliderZoom.setValue(20)
		self.sliderZoom.setInvertedControls(True)
		#self.sliderZoom.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
		self.sliderZoom.resize(100, 16)

		self.zoomScaleLabel = QLabel(_("%s seconds") % self.sliderZoom.value())
		
		#add zoom widgets
		self.timelineToolbar.addAction(self.actionTimelineZoomIn)
		self.timelineToolbar.addWidget(self.sliderZoom)
		self.timelineToolbar.addAction(self.actionTimelineZoomOut)
		self.timelineToolbar.addWidget(self.zoomScaleLabel)
		
		#Add timeline toolbar to web frame
		self.frameWeb.layout().addWidget(self.timelineToolbar)
		
	def __init__(self):

		#Create main window base class
		QMainWindow.__init__(self)
		#set window on app for reference during initialization of children
		get_app().window = self
		
		#Load theme if not set by OS
		ui_util.load_theme()
		
		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)
		
		#Load user settings for window
		self.load_settings()

		#Init UI
		ui_util.init_ui(self)

		#Setup toolbars that aren't on main window, set initial state of items, etc
		self.setup_toolbars()
		
		# Add window as watcher to receive undo/redo status updates
		get_app().update_manager.add_watcher(self)
		
		#setup timeline
		self.timeline = TimelineWebView(self)
		self.frameWeb.layout().addWidget(self.timeline)
		
		#setup files tree
		self.filesTreeView = MediaTreeView(self)
		self.tabFiles.layout().addWidget(self.filesTreeView) #gridLayout_2  , 1, 0

		#setup transitions tree
		self.transitionsTreeView = MediaTreeView(self)
		self.tabTransitions.layout().addWidget(self.transitionsTreeView) #gridLayout_2  , 1, 0

		#setup effects tree
		self.effectsTreeView = MediaTreeView(self)
		self.tabEffects.layout().addWidget(self.effectsTreeView) #gridLayout_2  , 1, 0
		
