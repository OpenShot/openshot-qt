"""
 @file
 @brief This file loads the main window (i.e. the primary user-interface)
 @author Noah Figg <eggmunkee@hotmail.com>
 @author Jonathan Thomas <jonathan@openshot.org>
 @author Olivier Girard <olivier@openshot.org>

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
from classes.timeline import TimelineSync
from classes.query import File, Clip
from images import openshot_rc
from windows.views.files_treeview import FilesTreeView
from windows.views.files_listview import FilesListView
from windows.views.transitions_treeview import TransitionsTreeView
from windows.views.transitions_listview import TransitionsListView
from windows.views.effects_treeview import EffectsTreeView
from windows.views.effects_listview import EffectsListView
from windows.video_widget import VideoWidget
from windows.preview_thread import PreviewThread
import xml.etree.ElementTree as ElementTree
import webbrowser

class MainWindow(QMainWindow, updates.UpdateWatcher, updates.UpdateInterface):
	""" This class contains the logic for the main window widget """
	
	# Path to ui file
	ui_path = os.path.join(info.PATH, 'windows','ui', 'main-window.ui')
	
	#Save window settings on close
	def closeEvent(self, event):
		# Save settings
		self.save_settings()
		
		# Stop threads
		self.preview_thread.kill()
		
	def actionNew_trigger(self, event):
		# clear data and start new project
		get_app().project.load("")
		get_app().updates.reset()
		self.filesTreeView.refresh_view()
		log.info("New Project created.")
		
		# Set Window title
		self.SetWindowTitle()
		
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
			
	def actionImportImageSequence_trigger(self, event):
		#show dialog
		from windows.Import_image_seq import ImportImageSeq
		win = ImportImageSeq()
		#Run the dialog event loop - blocking interaction on this window during that time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('Import image sequence add confirmed')
		else:
			log.info('Import image sequence add cancelled') 
			
	def actionImportTransition_trigger(self, event):
		#show dialog
		from windows.Import_transitions import ImportTransition
		win = ImportTransition()
		#Run the dialog event loop -blocking interaction on this window during that time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('Import transition add confirmed')
		else:
			log.info('Import transition add cancelled')
			
	def actionImportTitle_trigger(self, event):
		#show dialog
		from windows.Import_titles import ImportTitles
		win = ImportTitles()
		# Run the dialog event loop - blocking interaction on this window during that time
		result == win.exec_()
		if result ==  QDialog.Accepted:
			log.info('Import title add confirmed')
		else:
			log.info('Import title add cancelled')
			
			
	def save_project(self, file_path):
		""" Save a project to a file path, and refresh the screen """
		app = get_app()
		
		try:
			# Save project to file
			app.project.save(file_path)

			# Set Window title
			self.SetWindowTitle()
			
			# Load recent projects again
			self.load_recent_menu()
			
			log.info("Saved project {}".format(file_path))
			
		except Exception as ex:
			log.error("Couldn't save project {}".format(file_path))
			
			
	def open_project(self, file_path):
		""" Open a project from a file path, and refresh the screen """
		
		app = get_app()
		
		try:
			if os.path.exists(file_path.encode('UTF-8')):
				# Load project file
				app.project.load(file_path)
				
				# Set Window title
				self.SetWindowTitle()
				
				# Reset undo/redo history
				app.updates.reset()
				
				# Refresh file tree
				self.filesTreeView.refresh_view()
				
				# Load recent projects again
				self.load_recent_menu()
				
				log.info("Loaded project {}".format(file_path))
				
		except Exception as ex:
			log.error("Couldn't save project {}".format(file_path))
							
							
	def actionOpen_trigger(self, event):
		app = get_app()
		_ = app._tr
		file_path, file_type = QFileDialog.getOpenFileName(self, _("Open Project...")) #, options=QFileDialog.DontUseNativeDialog)

		# Load project file
		self.open_project(file_path)

		
	def actionSave_trigger(self, event):
		app = get_app()
		_ = app._tr
		#Get current filepath if any, otherwise ask user
		file_path = app.project.current_filepath
		if not file_path:
			file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Project..."))
		
		if file_path:
			# Save project
			self.save_project(file_path)

	def actionSaveAs_trigger(self, event):
		app = get_app()
		_ = app._tr
		file_path, file_type = QFileDialog.getSaveFileName(self, _("Save Project As..."))
		if file_path:
			# Save project
			self.save_project(file_path)
		
	def actionImportFiles_trigger(self, event):
		app = get_app()
		_ = app._tr
		files = QFileDialog.getOpenFileNames(self, _("Import File..."))[0]
		for file_path in files:
			self.filesTreeView.add_file(file_path)
			self.filesTreeView.refresh_view()
			log.info("Loaded project {}".format(file_path))

	def actionUploadVideo_trigger(self, event):
		#show window
		from windows.upload_video import UploadVideo
		win = UploadVideo()
		#Run the dialog event loop - blocking interaction on this window during this time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('Upload Video add confirmed')
		else:
			log.info('Upload Video add cancelled')
			
	def actionExportVideo_trigger(self, event):
		#show window
		from windows.export_video import ExportVideo
		win = ExportVideo()
		#Run the dialog event loop - blocking interaction on this window during this time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('Export Video add confirmed')
		else:
			log.info('Export Video add cancelled')
	
	def actionUndo_trigger(self, event):
		app = get_app()
		app.updates.undo()
		#log.info(app.project._data)

	def actionRedo_trigger(self, event):
		app = get_app()
		app.updates.redo()
		#log.info(app.project._data)
		
	def actionPreferences_trigger(self, event):
		#Show dialog
		from windows.preferences import Preferences
		win = Preferences()
		#Run the dialog event loop - blocking interaction on this window during this time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('Preferences add confirmed')
		else:
			log.info('Preferences add cancelled')
		
	def actionFilesShowAll_trigger(self, event):
		self.filesTreeView.refresh_view()
	def actionFilesShowVideo_trigger(self, event):
		self.filesTreeView.refresh_view()
	def actionFilesShowAudio_trigger(self, event):
		self.filesTreeView.refresh_view()
	def actionFilesShowImage_trigger(self, event):
		self.filesTreeView.refresh_view()
	def actionTransitionsShowAll_trigger(self, event):
		self.transitionsTreeView.refresh_view()
	def actionTransitionsShowCommon_trigger(self, event):
		self.transitionsTreeView.refresh_view()
	def actionEffectsShowAll_trigger(self, event):
		self.effectsTreeView.refresh_view()
	def actionEffectsShowVideo_trigger(self, event):
		self.effectsTreeView.refresh_view()
	def actionEffectsShowAudio_trigger(self, event):
		self.effectsTreeView.refresh_view()
		
	def actionHelpContents_trigger(self, event):
		try:
			webbrowser.open("http://openshotusers.com/")
			log.info("Help Contents is open")
		except:
			QMessageBox.information(self, "Error !", "Unable to open the Help Contents. Please ensure the openshot-doc package is installed.")
			log.info("Unable to open the Help Contents")
		
	def actionAbout_trigger(self, event):
		#Show dialog
		from windows.about import About
		win = About()
		#Run the dialog event loop - blocking interaction on this window during this time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('About Openshot add confirmed')
		else:
			log.info('About Openshot add cancelled')
			
	def actionReportBug_trigger(self, event):
		try:
			webbrowser.open("https://bugs.launchpad.net/openshot/+filebug")
			log.info("Open the Report Bug Launchpad web page with success")
		except:
			QMessageBox.information(self, "Error !", "Unable to open the launchpad web page")
			log.info("Unable to open the Report Bug launchpad web page") 
			
	def actionAskQuestion_trigger(self, event):
		try:
			webbrowser.open("https://answers.launchpad.net/openshot/+addquestion")
			log.info("Open the Question launchpad web page with success")
		except:
			QMessageBox.information(self, "Error !", "Unable to open the Question web page")
			log.info("Unable to open the Question web page")
			
	def actionTranslate_trigger(self, event):
		try:
			webbrowser.open("https://translations.launchpad.net/openshot")
			log.info("Open the Translate launchpad web page with success")
		except:
			QMessageBox.information(self, "Error !", "Unable to open the Translation web page")
			log.info("Unable to open the Translation web page")
			
	def actionDonate_trigger(self, event):
		try:
			webbrowser.open("http://openshot.org/donate/")
			log.info("Open the Donate web page with success")
		except:
			QMessageBox.information(self, "Error !", "Unable to open the Donate web page")
			log.info("Unable to open the Donate web page") 

	def actionPlay_trigger(self, event):

		if self.actionPlay.isChecked():
			ui_util.setup_icon(self, self.actionPlay, "actionPlay", "media-playback-pause")
			#TODO: call on library to pause
			self.preview_thread.Play()
			
		else:
			ui_util.setup_icon(self, self.actionPlay, "actionPlay") #to default
			#TODO: call on library to play
			self.preview_thread.Pause()
			
	def actionPreview_File_trigger(self, event):
		""" Preview the selected media file """
		log.info('actionPreview_File_trigger')
		
		if self.selected_files:
			# Find matching file
			f = File.get(id=self.selected_files[0])
			if f:
				# Get file path
				previewPath = f.data["path"]
				
				# Load file into player
				self.preview_thread.LoadFile(previewPath)

				# Trigger play button
				self.actionPlay.setChecked(False)
				self.actionPlay.trigger()
		
	def actionFastForward_trigger(self, event):
		pass
		
	def keyPressEvent(self, event):
		""" Add some shortkey for Player """
		self.key = ""
		
		#TODO : replace method by the corresponding and check them
		# Basic shortcuts i.e just a letter
		if event.key() == Qt.Key_Left:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_Right:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_Up:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_Down:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_C:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_J:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_L:
			self.actionFastForward.trigger()

		elif event.key() == Qt.Key_M:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_D:
			#Add the Ctrl key 
			if event.modifiers() & Qt.ControlModifier:
				self.actionFastForward.trigger()

		elif event.key() == Qt.Key_End:
			#Add the Ctrl key
			if event.modifiers() & Qt.ControlModifier:
				self.actionFastForward.trigger()

		elif event.key() == Qt.Key_Home:
			#Add the Ctrl key
			if event.modifiers() & Qt.ControlModifier:
				self.actionFastForward.trigger()

		elif event.key() == Qt.Key_K or Qt.Key_Space:
			self.actionPlay.trigger()

		elif event.key() == Qt.Key_Tab:
			self.actionPlay.trigger()
			
		# Bubble event on
		event.ignore()
		
	def actionProfile_trigger(self, event):
		#Show dialog
		from windows.profile import Profile
		win = Profile()
		#Run the dialog event loop - blocking interaction on this window during this time
		result = win.exec_()
		if result == QDialog.Accepted:
			log.info('Profile add confirmed')
			
	def actionRemove_from_Project_trigger(self, event):
		log.info("actionRemove_from_Project_trigger")
		
		# Loop through selected files
		for file_id in self.selected_files:
			# Find matching file
			f = File.get(id=file_id)
			if f:
				# Remove file
				f.delete()
				
				# Find matching clips (if any)
				clips = Clip.filter(file_id=file_id)
				for c in clips: 
					# Remove clip
					c.delete()
			
		# Clear selected files
		self.selected_files = []
		
	def actionRemoveClip_trigger(self, event):
		log.info('actionRemoveClip_trigger')

		# Loop through selected clips
		for clip_id in self.selected_clips:
			# Find matching file
			clips = Clip.filter(id=clip_id)
			for c in clips: 
				# Remove clip
				c.delete()
				
		# Clear selected clips
		self.selected_clips = []
		
	
	def actionTimelineZoomIn_trigger(self, event):
		self.sliderZoom.setValue(self.sliderZoom.value() + self.sliderZoom.singleStep())
	
	def actionTimelineZoomOut_trigger(self, event):
		self.sliderZoom.setValue(self.sliderZoom.value() - self.sliderZoom.singleStep())
		
	def actionFullscreen_trigger(self, event):
		# Hide fullscreen button, and display exit fullscreen button
		self.actionFullscreen.setVisible(False)
		self.actionExit_Fullscreen.setVisible(True)

	def actionExit_Fullscreen_trigger(self, event):
		# Hide exit fullscreen button, and display fullscreen button
		self.actionExit_Fullscreen.setVisible(False)
		self.actionFullscreen.setVisible(True)

	def actionDetailsView_trigger(self, event):
		log.info("Switch to Details View")
		
		# Get settings
		app = get_app()
		s = settings.get_settings()
		
		# Files
		if app.context_menu_object == "files":
			s.set("file_view", "details")
			self.tabFiles.layout().removeWidget(self.filesTreeView)
			self.filesTreeView.deleteLater()
			self.filesTreeView = None
			self.filesTreeView = FilesTreeView(self)
			self.tabFiles.layout().addWidget(self.filesTreeView)
			
		# Transitions
		elif app.context_menu_object == "transitions":
			s.set("transitions_view", "details")
			self.tabTransitions.layout().removeWidget(self.transitionsTreeView)
			self.transitionsTreeView.deleteLater()
			self.transitionsTreeView = None
			self.transitionsTreeView = TransitionsTreeView(self)
			self.tabTransitions.layout().addWidget(self.transitionsTreeView)
			
		# Effects
		elif app.context_menu_object == "effects":
			s.set("effects_view", "details")
			self.tabEffects.layout().removeWidget(self.effectsTreeView)
			self.effectsTreeView.deleteLater()
			self.effectsTreeView = None
			self.effectsTreeView = EffectsTreeView(self)
			self.tabEffects.layout().addWidget(self.effectsTreeView)

		
	def actionThumbnailView_trigger(self, event):
		log.info("Switch to Thumbnail View")

		# Get settings
		app = get_app()
		s = settings.get_settings()
		
		# Files
		if app.context_menu_object == "files":
			s.set("file_view", "thumbnail")
			self.tabFiles.layout().removeWidget(self.filesTreeView)
			self.filesTreeView.deleteLater()
			self.filesTreeView = None
			self.filesTreeView = FilesListView(self)
			self.tabFiles.layout().addWidget(self.filesTreeView)
			
		# Transitions
		elif app.context_menu_object == "transitions":
			s.set("transitions_view", "thumbnail")
			self.tabTransitions.layout().removeWidget(self.transitionsTreeView)
			self.transitionsTreeView.deleteLater()
			self.transitionsTreeView = None
			self.transitionsTreeView = TransitionsListView(self)
			self.tabTransitions.layout().addWidget(self.transitionsTreeView)

		# Effects
		elif app.context_menu_object == "effects":
			s.set("effects_view", "thumbnail")
			self.tabEffects.layout().removeWidget(self.effectsTreeView)
			self.effectsTreeView.deleteLater()
			self.effectsTreeView = None
			self.effectsTreeView = EffectsListView(self)
			self.tabEffects.layout().addWidget(self.effectsTreeView)
			
	def resize_contents(self):
		if self.filesTreeView:
			self.filesTreeView.resize_contents()
			
	def getDocks(self):
		""" Get a list of all dockable widgets """
		return [ self.dockFiles,
				 self.dockTransitions,
				 self.dockEffects,
				 self.dockVideo ]

	def removeDocks(self):
		""" Remove all dockable widgets on main screen """
		for dock in self.getDocks():
			self.removeDockWidget(dock)
		
	def addAllDocks(self, area):
		""" Add all dockable widgets to the same dock area on the main screen """
		for dock in self.getDocks():
			self.addDockWidget(area, dock)
		
	def floatDocks(self, is_floating):
		""" Float or Un-Float all dockable widgets above main screen """
		for dock in self.getDocks():
			dock.setFloating(is_floating)
		
	def showDocks(self):
		""" Show all dockable widgets on the main screen """
		for dock in self.getDocks():
			dock.show()
			
	def freezeDocks(self):
		""" Freeze all dockable widgets on the main screen (no float, moving, or closing) """
		for dock in self.getDocks():
			dock.setFeatures(QDockWidget.NoDockWidgetFeatures)

	def unFreezeDocks(self):
		""" Un-freeze all dockable widgets on the main screen (allow them to be moved, closed, and floated) """
		for dock in self.getDocks():
			dock.setFeatures(QDockWidget.AllDockWidgetFeatures)
		
	def hideDocks(self):
		""" Hide all dockable widgets on the main screen """
		for dock in self.getDocks():
			dock.hide()
		
	def actionSimple_View_trigger(self, event):
		""" Switch to the default / simple view  """
		self.removeDocks()
		self.addAllDocks(Qt.TopDockWidgetArea)
		self.floatDocks(False)
		self.tabifyDockWidget(self.dockFiles, self.dockTransitions)
		self.tabifyDockWidget(self.dockTransitions, self.dockEffects)
		self.showDocks()

	def actionAdvanced_View_trigger(self, event):
		""" Switch to an alternative view """
		self.removeDocks()

		# Top Dock
		self.addDockWidget(Qt.TopDockWidgetArea, self.dockFiles)
		self.addDockWidget(Qt.TopDockWidgetArea, self.dockTransitions)
		self.addDockWidget(Qt.TopDockWidgetArea, self.dockVideo)
		
		# Right Dock
		self.addDockWidget(Qt.RightDockWidgetArea, self.dockEffects)

		self.floatDocks(False)
		self.showDocks()
		
	def actionFreeze_View_trigger(self, event):
		""" Freeze all dockable widgets on the main screen """
		self.freezeDocks()
		self.actionFreeze_View.setVisible(False)
		self.actionUn_Freeze_View.setVisible(True)
	
	def actionUn_Freeze_View_trigger(self, event):
		""" Un-Freeze all dockable widgets on the main screen """
		self.unFreezeDocks()
		self.actionFreeze_View.setVisible(True)
		self.actionUn_Freeze_View.setVisible(False)
		
	def actionShow_All_trigger(self, event):
		""" Show all dockable widgets """
		self.showDocks()
		
	# Init fullscreen menu visibility
	def init_fullscreen_menu(self):
		if self.isFullScreen():
			self.actionFullscreen_trigger(None)
		else:
			self.actionExit_Fullscreen_trigger(None)

	def SetWindowTitle(self, profile=None):
		""" Set the window title based on a variety of factors """
		
		#Get translation function
		_ =  get_app()._tr
		
		if not profile:
			profile = get_app().project.get(["profile"])
		
		# Is this a saved project?
		if not get_app().project.current_filepath:
			# Not saved yet
			self.setWindowTitle("%s [%s] - %s" % (_("Untitled Project"), profile, "OpenShot Video Editor"))
		else:
			# Yes, project is saved
			# Get just the filename
			parent_path, filename = os.path.split(get_app().project.current_filepath)
			filename = filename.replace(".json", "").replace("_", " ").replace("-", " ").capitalize()
			self.setWindowTitle("%s [%s] - %s" % (filename, profile, "OpenShot Video Editor"))

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
	
	#Get window settings from setting store
	def load_settings(self):
		s = settings.get_settings()
		
		# Window state and geometry (also toolbar and dock locations)
		if s.get('window_geometry'): self.restoreGeometry(qt_types.str_to_bytes(s.get('window_geometry')))
		if s.get('window_state'): self.restoreState(qt_types.str_to_bytes(s.get('window_state')))
		
		# Load Recent Projects
		self.load_recent_menu()

			
	def load_recent_menu(self):
		""" Clear and load the list of recent menu items """
		s = settings.get_settings()
		_ =  get_app()._tr #Get translation function

		# Get list of recent projects
		recent_projects = s.get("recent_projects")
		
		# Add Recent Projects menu (after Open File)
		import functools
		if not self.recent_menu:
			# Create a new recent menu
			self.recent_menu = self.menuFile.addMenu(QIcon.fromTheme("document-open-recent"), _("Recent Projects"))
			self.menuFile.insertMenu(self.actionRecent_Placeholder, self.recent_menu)
		else:
			# Clear the existing children
			self.recent_menu.clear()

		# Add recent projects to menu
		for file_path in reversed(recent_projects):
			new_action = self.recent_menu.addAction(file_path)
			new_action.triggered.connect(functools.partial(self.recent_project_clicked, file_path))
			
	def recent_project_clicked(self, file_path):
		""" Load a recent project when clicked """

		# Load project file
		self.open_project(file_path)


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
		self.timelineToolbar.addAction(self.actionTimelineZoomOut)
		self.timelineToolbar.addWidget(self.sliderZoom)
		self.timelineToolbar.addAction(self.actionTimelineZoomIn)
		self.timelineToolbar.addWidget(self.zoomScaleLabel)
		
		#Add timeline toolbar to web frame
		self.frameWeb.addWidget(self.timelineToolbar)

	def __init__(self):

		#Create main window base class
		QMainWindow.__init__(self)
		
		#set window on app for reference during initialization of children
		get_app().window = self
		
		#Load UI from designer
		ui_util.load_ui(self, self.ui_path)
		
		#Load user settings for window
		s = settings.get_settings()
		self.recent_menu = None

		#Init UI
		ui_util.init_ui(self)

		#Setup toolbars that aren't on main window, set initial state of items, etc
		self.setup_toolbars()

		# Add window as watcher to receive undo/redo status updates
		get_app().updates.add_watcher(self)
		
		# Track the selected file(s)
		self.selected_files = []
		self.selected_clips = []
		
		# Init fullscreen menu visibility
		self.init_fullscreen_menu()
		
		# Setup timeline
		self.timeline = TimelineWebView(self)
		self.frameWeb.layout().addWidget(self.timeline)
		
		# Set Window title
		self.SetWindowTitle()
		
		# Setup files tree
		if s.get("file_view") == "details":
			self.filesTreeView = FilesTreeView(self)
		else:
			self.filesTreeView = FilesListView(self)
		self.tabFiles.layout().addWidget(self.filesTreeView)

		# Setup transitions tree
		if s.get("transitions_view") == "details":
			self.transitionsTreeView = TransitionsTreeView(self)
		else:
			self.transitionsTreeView = TransitionsListView(self)
		self.tabTransitions.layout().addWidget(self.transitionsTreeView)

		# Setup effects tree
		if s.get("effects_view") == "details":
			self.effectsTreeView = EffectsTreeView(self)
		else:
			self.effectsTreeView = EffectsListView(self)
		self.tabEffects.layout().addWidget(self.effectsTreeView)
		
		# Setup video preview QWidget
		self.videoPreview = VideoWidget()
		self.tabVideo.layout().insertWidget(0, self.videoPreview)

		# Load window state and geometry
		self.load_settings()
		
		# Create the timeline sync object (used for previewing timeline)
		self.timeline_sync = TimelineSync()
		
		# Start the preview thread
		self.preview_thread = PreviewThread(self, self.timeline_sync.timeline)
		self.preview_thread.start()
		
