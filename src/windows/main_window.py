"""
 @file
 @brief This file loads the main window (i.e. the primary user-interface)
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <eolinwen@gmail.com>

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
from PyQt5 import uic, QtGui
from windows.timeline_webview import TimelineWebView
from classes import info, ui_util, settings, qt_types, updates
from classes.app import get_app
from classes.logger import log
from images import openshot_rc
from windows.media_treeview import MediaTreeView
import xml.etree.ElementTree as ElementTree

class MainWindow(QMainWindow, updates.UpdateWatcher, updates.UpdateInterface):
	""" This class contains the logic for the main window widget """
	
	# Path to ui file
	ui_path = os.path.join(info.PATH, 'windows','ui', 'main-window.ui')
	
	#Save window settings on close
	def closeEvent(self, event):
		self.save_settings()
		
	def actionNew_trigger(self, event):
		get_app().project.new()
		log.info("New Project created.")
		
	def actionAnimatedTitle_trigger(self, event):
		# show dialog
		from windows.animated_title import AnimatedTitle
		win = AnimatedTitle()
		#Run the dialog event loop - blocking interaction on this window during that time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('animated title add confirmed')
		else:
			log.info('animated title add cancelled')
			
	def actionTitle_trigger(self, event):
		# show dialog
		from windows.title_editor import TitleEditor
		win = TitleEditor()
		#Run the dialog event loop - blocking interaction on this window during that time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('title editor add confirmed')
		else:
			log.info('title editor add cancelled')
			
	#def actionImportImageSequence_trigger(self, event):
		#show dialog
		#from windows.Import_image_seq import ImportImageSeq
		#win = ImportImageSeq()
		#Run the dialog event loop - blocking interaction on this window during that time
		#result = win.exec_()
		#if result == QDialog.Accepted:
			#log.info('Import image sequence add confirmed')
		#else:
			#log.info('Import image sequence add cancelled') 
			
	#def actionImportTransition_trigger(self, event):
		#show dialog
		#from windows.Import_transitions import ImportTransition
		#win = ImportTransition()
		#Run the dialog event loop -blocking interaction on this window during that time
		#result = win.exec_()
		#if result == QDialog.Accepted:
			#log.info('Import transition add confirmed')
		#else:
			#log.info('Import transition add cancelled')
				
	def actionOpen_trigger(self, event):
		app = get_app()
		_ = app._tr
		file_path, file_type = QFileDialog.getOpenFileName(self, _("Open Project...")) #, options=QFileDialog.DontUseNativeDialog)
		if file_path:
			app.project.load(file_path)
			app.project.current_filepath = file_path
			app.updates.reset()
			self.filesTreeView.update_model()
			log.info("Loaded project {}".format(file_path))
		
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
				log.info("Saved {}".format(file_path))
			except Exception as ex:
				log.error("Couldn't save project {}".format(file_path))

	def actionSaveAs_trigger(self, event):
		app = get_app()
		_ = app._tr
		file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Project As..."))
		if file_path:
			try:
				app.project.save(file_path)
				app.project.current_filepath = file_path
				log.info("Saved {}".format(file_path))
			except Exception as ex:
				log.error("Couldn't save project {}".format(file_path))
		
	def actionImportFiles_trigger(self, event):
		app = get_app()
		_ = app._tr
		files = QFileDialog.getOpenFileNames(self, _("Import File..."))[0]
		for file_path in files:
			self.filesTreeView.add_file(file_path)
			self.filesTreeView.update_model()
			log.info("Loaded project {}".format(file_path))

		
	def actionUndo_trigger(self, event):
		app = get_app()
		app.updates.undo()
		#log.info(app.project._data)

	def actionRedo_trigger(self, event):
		app = get_app()
		app.updates.redo()
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
			# app.updates.insert("settings/nfigg-setting", {"a": 1, "b": 5})
		# else:
			# log.info ("Increment value")
			# update = dict()
			# update["a"] = curr_val["a"] + 1
			# app.updates.update("settings/nfigg-setting", update, partial_update=True)
		#log.info(app.project._data)
	#Other project settings test code
		# app = get_app()
		# curr_val = app.project.get("settings/nfigg-setting")
		# if not curr_val == None and curr_val["a"] > 1:
			# log.info ("Decrement value")
			# update = dict()
			# update["a"] = curr_val["a"] - 1
			# app.updates.update("settings/nfigg-setting", update, partial_update=True)
		# elif not curr_val == None:
			# log.info ("Remove value")
			# app.updates.delete("settings/nfigg-setting")
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
		
	def actionFullscreen_trigger(self, event):
		# Hide fullscreen button, and display exit fullscreen button
		self.actionFullscreen.setVisible(False)
		self.actionExit_Fullscreen.setVisible(True)

	def actionExit_Fullscreen_trigger(self, event):
		# Hide exit fullscreen button, and display fullscreen button
		self.actionExit_Fullscreen.setVisible(False)
		self.actionFullscreen.setVisible(True)
		
	# Init fullscreen menu visibility
	def init_fullscreen_menu(self):
		if self.isFullScreen():
			self.actionFullscreen_trigger(None)
		else:
			self.actionExit_Fullscreen_trigger(None)

	#Update undo and redo buttons enabled/disabled to available changes
	def updateStatusChanged(self, undo_status, redo_status):
		self.actionUndo.setEnabled(undo_status)
		self.actionRedo.setEnabled(redo_status)
	
	#Update window settings in setting store
	def save_settings(self):
		s = settings.get_settings()

		#Save window state and geometry (saves toolbar and dock locations)
		s.set('window_state', qt_types.bytes_to_str(self.saveState()))
		s.set('window_geometry', qt_types.bytes_to_str(self.saveGeometry()))

		#Splitter sizes
		sizes = self.splitter_2.sizes()
		s.set('window_splitter_2_pos', sizes)
		sizes = self.splitter.sizes()
		s.set('window_splitter_pos', sizes)
		
		#TODO: Call save_settings on any sub-objects necessary
	
	#Get window settings from setting store
	def load_settings(self):
		s = settings.get_settings()
		
		#Window state and geometry (also toolbar and dock locations)
		if s.get('window_geometry'): self.restoreGeometry(qt_types.str_to_bytes(s.get('window_geometry')))
		if s.get('window_state'): self.restoreState(qt_types.str_to_bytes(s.get('window_state')))
		
		#Splitter sizes
		if s.get('window_splitter_pos'): self.splitter.setSizes(s.get('window_splitter_pos'))
		if s.get('window_splitter_2_pos'): self.splitter_2.setSizes(s.get('window_splitter_2_pos'))

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

		self.zoomScaleLabel = QLabel(_("{} seconds").format(self.sliderZoom.value()))
		
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
		
		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)
		
		#Load user settings for window
		self.load_settings()

		#Init UI
		ui_util.init_ui(self)

		#Setup toolbars that aren't on main window, set initial state of items, etc
		self.setup_toolbars()
		
		# Add window as watcher to receive undo/redo status updates
		get_app().updates.add_watcher(self)
		
		# Init fullscreen menu visibility
		self.init_fullscreen_menu()
		
		#sys.path.insert(0,"/usr/local/share/pyshared/libopenshot")
		#import openshot
		#import sip
		
		# Draw test image to QGraphicsView
		#scene = QGraphicsScene()
		#self.videoDisplay.setScene(scene)
		#reader = openshot.DummyReader(openshot.Fraction(24,1), 640, 480, 48000, 2, 10.0)
		#reader.DrawFrameOnScene("/home/jonathan/Pictures/tux.jpg", int(sip.unwrapinstance(scene)))

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
		
